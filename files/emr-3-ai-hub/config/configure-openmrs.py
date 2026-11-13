#!/usr/bin/env python3
"""Configure OpenMRS for ChartSearchAI + med-agent-hub on stack startup.

Idempotently:
1. Waits for OpenMRS REST API to accept admin credentials and verifies
   querystore and chartsearchai modules are started.
2. Reconciles the least-privileged QueryStore service role and account
   holding the exact 10 OpenMRS Core read privileges required by QueryStore.
3. Configures ChartSearchAI Global Properties so the module routes clinical
   answer requests through med-agent-hub while wiring bundled inference to
   the shared llama-router and clearing stale chartMode overrides.
4. Verifies QueryStore indexing completeness and patient record reads under
   the med-agent-hub service account, optionally reconciles eval-* research
   accounts, and checks med-agent-hub's /v1/models endpoint.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


ROLE_NAME = "Med Agent Hub Patient Reader"
DEFAULT_SERVICE_USERNAME = "med-agent-hub"
DEFAULT_SAMPLE_PATIENT_UUID = "dd75c020-1691-11df-97a5-7038c432aabf"
CORE_READ_PRIVILEGES: tuple[str, ...] = (
    "Get Patients",
    "Get Observations",
    "Get Encounters",
    "Get Visits",
    "Get Conditions",
    "Get Diagnoses",
    "Get Allergies",
    "Get Orders",
    "Get Patient Programs",
    "Get Medication Dispense",
)
EVAL_ACCESS_ROLE = "Application: Uses ChartSearchAI (Research)"
EVAL_REQUIRED_PRIVILEGES: tuple[str, ...] = (
    "AI Query Patient Data",
    "Get Patients",
    "Get People",
    "Get Concept Sources",
    "Get Care Settings",
    "Get Observations",
    "Get Encounters",
    "Get Visits",
    "Get Conditions",
    "Get Diagnoses",
    "Get Allergies",
    "Get Orders",
    "Get Patient Programs",
    "Get Medication Dispense",
)
EVAL_ACCOUNTS: tuple[tuple[str, str, bool], ...] = (
    ("eval-clinical-officer", "Organizational: Clinical Officer", False),
    ("eval-nurse", "Organizational: Nurse", True),
    ("eval-pharmacy", "Organizational: Pharmaceutical Technologist", False),
    ("eval-counsellor", "Organizational: Adherence Counsellor", False),
    ("eval-records", "Organizational: Health Records Officer", False),
    ("eval-doctor", "Organizational: Doctor", True),
    ("eval-peer", "Organizational: Peer Educator", False),
)


class OpenMrsClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        self.headers = {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
        }

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: int = 30,
    ) -> Any:
        data = None
        headers = dict(self.headers)
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            f"{self.base_url}/ws/rest/v1/{path.lstrip('/')}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"OpenMRS {method} {path} failed with HTTP {exc.code}: {detail}"
            ) from exc
        return json.loads(body) if body else {}

    def exact(self, resource: str, field: str, value: str) -> dict[str, Any] | None:
        query = urllib.parse.urlencode({"q": value, "v": "full", "limit": 100})
        payload = self.request("GET", f"{resource}?{query}")
        match = next(
            (item for item in payload.get("results", []) if item.get(field) == value),
            None,
        )
        if match is not None:
            return match

        # Some OpenMRS REST resources (notably /privilege) ignore `q`.
        start = 0
        while True:
            page_query = urllib.parse.urlencode(
                {"v": "full", "limit": 100, "startIndex": start}
            )
            page = self.request("GET", f"{resource}?{page_query}")
            rows = page.get("results", [])
            match = next((item for item in rows if item.get(field) == value), None)
            if match is not None:
                return match
            if len(rows) < 100:
                return None
            start += len(rows)


def wait_for_openmrs(client: OpenMrsClient, timeout_seconds: int = 120) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "no response"
    while True:
        try:
            session = client.request("GET", "session")
            if session.get("authenticated") is True:
                return
            last_error = "OpenMRS admin credentials were not authenticated"
        except Exception as exc:  # noqa: BLE001 - retry until backend REST is ready
            last_error = str(exc)
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"Timed out waiting for authenticated OpenMRS REST session: {last_error}"
            )
        time.sleep(3)


def _full(client: OpenMrsClient, resource: str, uuid: str) -> dict[str, Any]:
    return client.request("GET", f"{resource}/{uuid}?v=full")


def _effective_privileges(
    client: OpenMrsClient,
    role: dict[str, Any],
    *,
    seen: set[str] | None = None,
) -> set[str]:
    visited = seen if seen is not None else set()
    role_uuid = str(role.get("uuid") or "")
    if role_uuid and role_uuid in visited:
        return set()
    if role_uuid:
        visited.add(role_uuid)
    privileges = {
        str(item.get("name"))
        for item in role.get("privileges", [])
        if item.get("name")
    }
    for inherited in role.get("inheritedRoles", []):
        inherited_uuid = str(inherited.get("uuid") or "")
        if inherited_uuid and inherited_uuid not in visited:
            privileges.update(
                _effective_privileges(
                    client,
                    _full(client, "role", inherited_uuid),
                    seen=visited,
                )
            )
    return privileges


def reconcile_querystore_account(
    client: OpenMrsClient,
    *,
    service_username: str,
    service_password: str,
) -> dict[str, Any]:
    resolved_privileges: dict[str, str] = {}
    missing: list[str] = []
    for name in CORE_READ_PRIVILEGES:
        priv = client.exact("privilege", "name", name)
        if priv is None or not priv.get("uuid"):
            missing.append(name)
        else:
            resolved_privileges[name] = str(priv["uuid"])
    if missing:
        raise RuntimeError(
            "OpenMRS is missing required QueryStore read privileges: "
            + ", ".join(missing)
        )

    expected_names = set(CORE_READ_PRIVILEGES)
    privilege_uuids = [resolved_privileges[name] for name in CORE_READ_PRIVILEGES]

    role = client.exact("role", "name", ROLE_NAME)
    role_payload = {
        "name": ROLE_NAME,
        "description": "Read-only patient chart access for the med-agent-hub service.",
        "privileges": privilege_uuids,
        "inheritedRoles": [],
    }
    if role is None:
        role = client.request("POST", "role", role_payload)
    else:
        current = {item.get("name") for item in role.get("privileges", [])}
        inherited = {item.get("uuid") for item in role.get("inheritedRoles", [])}
        if current != expected_names or inherited:
            client.request("POST", f"role/{role['uuid']}", role_payload)

    role_uuid = str(role["uuid"])
    user = client.exact("user", "username", service_username)
    if user is None:
        user = client.request(
            "POST",
            "user",
            {
                "username": service_username,
                "systemId": service_username,
                "password": service_password,
                "person": {
                    "names": [{"givenName": "Med Agent", "familyName": "Hub"}],
                    "gender": "U",
                },
                "roles": [role_uuid],
            },
        )
    else:
        client.request(
            "POST",
            f"user/{user['uuid']}",
            {"password": service_password, "roles": [role_uuid]},
        )

    verified_role = _full(client, "role", role_uuid)
    verified_user = _full(client, "user", str(user["uuid"]))
    effective = _effective_privileges(client, verified_role)
    assigned = {
        str(item.get("uuid"))
        for item in verified_user.get("roles", [])
        if item.get("uuid")
    }
    if effective != expected_names or assigned != {role_uuid}:
        raise RuntimeError(
            "QueryStore service-account least-privilege verification failed: "
            f"effective_privileges={sorted(effective)!r}, assigned_roles={sorted(assigned)!r}"
        )

    return {
        "username": service_username,
        "role": ROLE_NAME,
        "privileges": list(CORE_READ_PRIVILEGES),
    }


def require_modules_started(
    client: OpenMrsClient,
    required_modules: tuple[str, ...] = ("querystore", "chartsearchai"),
) -> dict[str, bool]:
    payload = client.request(
        "GET",
        "module?v=custom:(uuid,name,packageName,started,startupErrorMessage)&limit=100",
    )
    by_key: dict[str, dict[str, Any]] = {}
    for mod in payload.get("results", []):
        for key in (mod.get("uuid"), mod.get("name")):
            if key:
                by_key[str(key).strip().lower()] = mod

    statuses: dict[str, bool] = {}
    failures: list[str] = []
    for mod_id in required_modules:
        mod = by_key.get(mod_id.lower())
        if mod is None:
            failures.append(f"{mod_id}: missing from /ws/rest/v1/module")
            continue
        started = bool(mod.get("started"))
        statuses[mod_id] = started
        if not started:
            err = mod.get("startupErrorMessage") or "not started"
            failures.append(f"{mod_id}: {err}")

    if failures:
        raise RuntimeError("Required OpenMRS modules failed startup: " + "; ".join(failures))
    return statuses


def set_global_property(client: OpenMrsClient, name: str, value: str) -> None:
    encoded = urllib.parse.quote(name, safe="")
    try:
        client.request("POST", f"systemsetting/{encoded}", {"value": value})
    except RuntimeError as exc:
        if "HTTP 404" not in str(exc):
            raise
        client.request("POST", "systemsetting", {"property": name, "value": value})


def delete_global_property(client: OpenMrsClient, name: str) -> bool:
    encoded = urllib.parse.quote(name, safe="")
    try:
        client.request("DELETE", f"systemsetting/{encoded}?purge=true")
        return True
    except RuntimeError as exc:
        if "HTTP 404" in str(exc):
            return False
        raise


def verify_querystore_index(
    admin_client: OpenMrsClient,
    service_client: OpenMrsClient,
    *,
    sample_patient_uuid: str,
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    admin_client.request("POST", "searchindexupdate", {}, timeout=1800)

    deadline = time.monotonic() + timeout_seconds
    status_payload: dict[str, Any] = {}
    while True:
        status_payload = admin_client.request("GET", "querystore/indexingstatus")
        if status_payload.get("complete") is True:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"Timed out waiting for QueryStore indexing completion: {status_payload!r}"
            )
        time.sleep(3)

    sample_keys: list[str] = []
    if sample_patient_uuid:
        encoded_patient = urllib.parse.quote(sample_patient_uuid, safe="")
        record = service_client.request(
            "GET", f"querystore/patientrecord?patient={encoded_patient}&limit=5"
        )
        if not isinstance(record, dict) or not record.get("results"):
            raise RuntimeError(
                f"QueryStore patientrecord?patient={sample_patient_uuid} returned empty results: {record!r}"
            )
        sample_keys = sorted(str(key) for key in record.keys())

    return {
        "complete": True,
        "sample_patient_uuid": sample_patient_uuid or None,
        "sample_patient_keys": sample_keys,
    }


def reconcile_evaluation_accounts(
    client: OpenMrsClient,
    *,
    omrs_base_url: str,
    eval_password: str,
) -> list[str]:
    privilege_uuids: list[str] = []
    for name in EVAL_REQUIRED_PRIVILEGES:
        priv = client.exact("privilege", "name", name)
        if priv is None or not priv.get("uuid"):
            raise RuntimeError(f"Required evaluation privilege is missing: {name}")
        privilege_uuids.append(str(priv["uuid"]))

    access_role = client.exact("role", "name", EVAL_ACCESS_ROLE)
    if access_role is None:
        access_role = client.request(
            "POST",
            "role",
            {
                "name": EVAL_ACCESS_ROLE,
                "description": "ChartSearchAI access for synthetic-data research.",
                "privileges": privilege_uuids,
                "inheritedRoles": [],
            },
        )
    else:
        current_privs = {str(item.get("uuid")) for item in access_role.get("privileges", [])}
        if current_privs != set(privilege_uuids) or access_role.get("inheritedRoles"):
            client.request(
                "POST",
                f"role/{access_role['uuid']}",
                {"privileges": privilege_uuids, "inheritedRoles": []},
            )

    provisioned: list[str] = []
    for username, role_name, require_existing in EVAL_ACCOUNTS:
        occ_role = client.exact("role", "name", role_name)
        if occ_role is None:
            if require_existing:
                raise RuntimeError(f"Required OpenMRS role is missing: {role_name}")
            occ_role = client.request(
                "POST",
                "role",
                {
                    "name": role_name,
                    "description": "Occupational label for synthetic-data research.",
                    "privileges": [],
                    "inheritedRoles": [],
                },
            )

        desired_roles = [str(occ_role["uuid"]), str(access_role["uuid"])]
        user = client.exact("user", "username", username)
        if user is None:
            user = client.request(
                "POST",
                "user",
                {
                    "username": username,
                    "systemId": username,
                    "password": eval_password,
                    "roles": desired_roles,
                    "person": {
                        "names": [{"givenName": "Evaluation", "familyName": username[5:]}],
                        "gender": "U",
                    },
                },
            )
        else:
            client.request(
                "POST",
                f"user/{user['uuid']}",
                {"password": eval_password, "roles": desired_roles},
            )

        session = OpenMrsClient(omrs_base_url, username, eval_password).request("GET", "session")
        if not session.get("authenticated") or (session.get("user") or {}).get("uuid") != user["uuid"]:
            raise RuntimeError(f"Verified login failed for evaluation account {username}")
        provisioned.append(username)

    return provisioned


def verify_hub_models(hub_base_url: str, hub_api_key: str) -> int:
    headers = {"Accept": "application/json"}
    if hub_api_key:
        headers["Authorization"] = f"Bearer {hub_api_key}"
    url = f"{hub_base_url.rstrip('/')}/v1/models"
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        if resp.status < 200 or resp.status >= 300:
            raise RuntimeError(f"GET {url} returned HTTP {resp.status}")
        payload = json.loads(resp.read().decode("utf-8"))
    data = payload.get("data")
    if not isinstance(data, list):
        raise RuntimeError(f"GET {url} did not return a JSON 'data' list")
    return len(data)


def main() -> int:
    omrs_base_url = os.environ.get("OMRS_BASE_URL", "http://backend:8080/openmrs").strip()
    admin_user = os.environ.get("OMRS_ADMIN_USER", "admin").strip()
    admin_password = os.environ.get("OMRS_ADMIN_PASSWORD", "Admin123")
    service_username = os.environ.get(
        "QUERYSTORE_USERNAME", DEFAULT_SERVICE_USERNAME
    ).strip()
    service_password = os.environ.get("QUERYSTORE_PASSWORD", "")
    hub_endpoint_url = os.environ.get(
        "CHARTSEARCH_HUB_ENDPOINT_URL", "http://med-agent-hub:8080/v1/chat/completions"
    ).strip()
    providers_enabled = os.environ.get("CHARTSEARCH_PROVIDERS_ENABLED", "bundled,hub").strip()
    providers_default = os.environ.get("CHARTSEARCH_PROVIDERS_DEFAULT", "hub").strip()
    bundled_engine = os.environ.get("CHARTSEARCH_BUNDLED_ENGINE", "remote").strip()
    bundled_endpoint_url = os.environ.get(
        "CHARTSEARCH_BUNDLED_ENDPOINT_URL", "http://llama-router:8077/v1/chat/completions"
    ).strip()
    bundled_model_name = os.environ.get("CHARTSEARCH_BUNDLED_MODEL_NAME", "gemma-4-12b").strip()
    reference_date = os.environ.get("CHARTSEARCHAI_REFERENCE_DATE", "").strip()
    hub_base_url = os.environ.get("HUB_BASE_URL", "http://med-agent-hub:8080").strip()
    hub_api_key = os.environ.get("CHARTSEARCH_HUB_API_KEY", "").strip()
    eval_password = os.environ.get("EVALUATION_PASSWORD", "").strip()
    hiv_baseline_enabled = os.environ.get("HIV_BASELINE_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    raw_sample_uuid = os.environ.get("VERIFY_SAMPLE_PATIENT_UUID", "").strip()
    if raw_sample_uuid.lower() in {"none", "off", "false"}:
        sample_patient_uuid = ""
    elif raw_sample_uuid:
        sample_patient_uuid = raw_sample_uuid
    elif hiv_baseline_enabled:
        sample_patient_uuid = DEFAULT_SAMPLE_PATIENT_UUID
    else:
        sample_patient_uuid = ""
    index_timeout_seconds = int(os.environ.get("QUERYSTORE_INDEX_TIMEOUT_SECONDS", "600"))

    if not service_password.strip():
        print(
            "ERROR: QUERYSTORE_PASSWORD must be set in .env before starting hub-config-init.",
            file=sys.stderr,
        )
        return 1

    client = OpenMrsClient(omrs_base_url, admin_user, admin_password)
    wait_for_openmrs(client)
    modules = require_modules_started(client)
    account = reconcile_querystore_account(
        client,
        service_username=service_username,
        service_password=service_password,
    )

    chart_mode_deleted = delete_global_property(client, "chartsearchai.chartMode")
    properties: dict[str, str] = {
        "chartsearchai.hub.endpointUrl": hub_endpoint_url,
        "chartsearchai.providers.enabled": providers_enabled,
        "chartsearchai.providers.default": providers_default,
        "chartsearchai.llm.engine": bundled_engine,
    }
    if bundled_endpoint_url:
        properties["chartsearchai.llm.remote.endpointUrl"] = bundled_endpoint_url
    if bundled_model_name:
        properties["chartsearchai.llm.remote.modelName"] = bundled_model_name
    if reference_date:
        properties["chartsearchai.referenceDate"] = reference_date

    for prop_name, prop_value in properties.items():
        set_global_property(client, prop_name, prop_value)

    service_client = OpenMrsClient(omrs_base_url, service_username, service_password)
    querystore_status = verify_querystore_index(
        client,
        service_client,
        sample_patient_uuid=sample_patient_uuid,
        timeout_seconds=index_timeout_seconds,
    )

    eval_accounts: list[str] = []
    if eval_password:
        eval_accounts = reconcile_evaluation_accounts(
            client,
            omrs_base_url=omrs_base_url,
            eval_password=eval_password,
        )

    profile_count = verify_hub_models(hub_base_url, hub_api_key)
    print(
        json.dumps(
            {
                "status": "configured",
                "modules": modules,
                "account": account,
                "chart_mode_deleted": chart_mode_deleted,
                "global_properties": properties,
                "querystore": querystore_status,
                "evaluation_accounts": eval_accounts,
                "hub_profiles_count": profile_count,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
