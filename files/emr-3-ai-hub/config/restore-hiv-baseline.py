#!/usr/bin/env python3
"""Stage and restore the published OpenMRS HIV baseline (DB dump, ES snapshot, ONNX embedder)."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASELINE_IMAGE = (
    "ghcr.io/pmanko/openclinai-hiv-baseline"
    "@sha256:6d828211831ef5bf1d37955bf024bc422383a63b9af728d1fa40e4c1acbd5394"
)
DEFAULT_MODEL_URL = (
    "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/"
    "1110a243fdf4706b3f48f1d95db1a4f5529b4d41/onnx/model.onnx"
)
DEFAULT_VOCAB_URL = (
    "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/"
    "1110a243fdf4706b3f48f1d95db1a4f5529b4d41/vocab.txt"
)
DEFAULT_MODEL_SHA256 = "6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452"
DEFAULT_VOCAB_SHA256 = "07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3"

FALLBACK_INDICES: dict[str, int] = {
    "querystore_allergy": 2,
    "querystore_condition": 4454,
    "querystore_diagnosis": 3,
    "querystore_drug_order": 43412,
    "querystore_encounter": 14322,
    "querystore_obs": 427890,
    "querystore_patient": 5333,
    "querystore_program": 3921,
    "querystore_test_order": 1095,
    "querystore_visit": 14250,
}

MANIFEST_ACCEPT = ", ".join(
    [
        "application/vnd.oci.image.index.v1+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.docker.distribution.manifest.v2+json",
    ]
)


def log(message: str) -> None:
    print(f"[hiv-baseline] {message}", flush=True)


def env_bool(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verify_digest(actual_hex: str, expected: str, label: str) -> None:
    expected_clean = expected.removeprefix("sha256:")
    if actual_hex != expected_clean:
        raise RuntimeError(
            f"SHA-256 mismatch for {label}: expected {expected_clean}, got {actual_hex}"
        )


def parse_image_ref(image_ref: str) -> tuple[str, str, str]:
    ref = image_ref.strip()
    digest_part = ""
    if "@" in ref:
        ref, digest_part = ref.split("@", 1)

    parts = ref.split("/", 1)
    if len(parts) == 2 and ("." in parts[0] or ":" in parts[0] or parts[0] == "localhost"):
        registry, repo_and_tag = parts[0], parts[1]
    else:
        registry, repo_and_tag = "ghcr.io", ref

    if ":" in repo_and_tag:
        repo, tag = repo_and_tag.rsplit(":", 1)
    else:
        repo, tag = repo_and_tag, "latest"

    reference = digest_part or tag
    return registry, repo, reference


def host_arch() -> str:
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return "amd64"
    if machine in {"aarch64", "arm64"}:
        return "arm64"
    return machine


def http_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    json_body: Any | None = None,
    timeout: int = 60,
) -> tuple[int, bytes]:
    req_headers = dict(headers or {})
    data: bytes | None = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=data, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read()
        if exc.code == 404:
            return 404, body
        text = body.decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code} for {method} {url}: {text}") from exc


def http_download(
    url: str,
    dest: Path,
    *,
    headers: dict[str, str] | None = None,
    expected_sha256: str | None = None,
    timeout: int = 300,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest.with_name(f".{dest.name}.tmp")
    request = urllib.request.Request(url, method="GET", headers=dict(headers or {}))
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=timeout) as response, tmp_path.open("wb") as out:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            out.write(chunk)
    if expected_sha256:
        verify_digest(digest.hexdigest(), expected_sha256, str(dest.name))
    tmp_path.replace(dest)


def fetch_registry_token(token_base_url: str, repo: str) -> str | None:
    query = urllib.parse.urlencode({"scope": f"repository:{repo}:pull"})
    url = f"{token_base_url.rstrip('/')}?{query}"
    try:
        status, body = http_request(url, timeout=30)
    except Exception as exc:
        log(f"Registry token endpoint unavailable ({exc}); trying anonymous pull")
        return None
    if status != 200:
        return None
    payload = json.loads(body.decode("utf-8"))
    token = payload.get("token") or payload.get("access_token")
    return str(token) if token else None


def fetch_oci_manifest(
    registry_base_url: str,
    repo: str,
    reference: str,
    auth_headers: dict[str, str],
) -> dict[str, Any]:
    manifest_url = f"{registry_base_url}/v2/{repo}/manifests/{reference}"
    headers = {"Accept": MANIFEST_ACCEPT, **auth_headers}
    _, raw = http_request(manifest_url, headers=headers, timeout=60)
    if reference.startswith("sha256:"):
        verify_digest(hashlib.sha256(raw).hexdigest(), reference, f"manifest {reference}")
    data = json.loads(raw.decode("utf-8"))

    if "manifests" in data and "layers" not in data:
        manifests = data["manifests"]
        arch = host_arch()
        chosen = None
        for entry in manifests:
            plat = entry.get("platform") or {}
            if plat.get("os") == "linux" and plat.get("architecture") == arch:
                chosen = entry
                break
        if chosen is None:
            for entry in manifests:
                plat = entry.get("platform") or {}
                if plat.get("os") == "linux":
                    chosen = entry
                    break
        if chosen is None:
            chosen = manifests[0]
        child_digest = chosen["digest"]
        log(f"Resolved multi-arch manifest to {child_digest} ({chosen.get('platform')})")
        return fetch_oci_manifest(registry_base_url, repo, child_digest, auth_headers)

    return data


def safe_relpath(member_name: str, prefix: str) -> Path | None:
    normalized = member_name.lstrip("./")
    if not normalized.startswith(prefix):
        return None
    rel_str = normalized[len(prefix) :].lstrip("/")
    if not rel_str:
        return Path(".")
    rel_path = Path(rel_str)
    if rel_path.is_absolute() or ".." in rel_path.parts:
        raise RuntimeError(f"Unsafe archive member path rejected: {member_name}")
    return rel_path


def chown_tree(root: Path, uid: int, gid: int) -> None:
    if not root.exists():
        return
    try:
        os.chown(root, uid, gid)
        for current, dirs, files in os.walk(root):
            for name in dirs:
                os.chown(Path(current) / name, uid, gid)
            for name in files:
                os.chown(Path(current) / name, uid, gid)
    except PermissionError:
        log(f"Skipping chown on {root} (insufficient privileges)")


def clear_directory_contents(directory: Path) -> None:
    if not directory.exists():
        return
    for entry in directory.iterdir():
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def extract_baseline_layers(
    registry_base_url: str,
    token_url: str,
    repo: str,
    manifest: dict[str, Any],
    *,
    need_db: bool,
    need_es: bool,
    staging_dir: Path,
    snapshot_dir: Path,
) -> dict[str, Any]:
    parsed_manifest: dict[str, Any] = {}
    es_snapshot_root = snapshot_dir / "es-snapshot"
    if need_es:
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        clear_directory_contents(snapshot_dir)
        es_snapshot_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="hiv-layer-", dir=staging_dir) as tmp_root:
        tmp_dir = Path(tmp_root)
        for idx, layer in enumerate(manifest.get("layers", [])):
            token = fetch_registry_token(token_url, repo)
            auth_headers = {"Authorization": f"Bearer {token}"} if token else {}
            digest = layer["digest"]
            blob_url = f"{registry_base_url}/v2/{repo}/blobs/{digest}"
            blob_path = tmp_dir / f"layer-{idx}.tar.gz"
            log(f"Downloading baseline layer {idx + 1}/{len(manifest['layers'])} ({digest[:19]}...)")
            http_download(blob_url, blob_path, headers=auth_headers, expected_sha256=digest, timeout=1800)

            with tarfile.open(blob_path, "r:*") as archive:
                for member in archive.getmembers():
                    name = member.name.lstrip("./")
                    if name == "baseline/manifest.json" and member.isfile():
                        extracted = archive.extractfile(member)
                        if extracted is not None:
                            parsed_manifest = json.loads(extracted.read().decode("utf-8"))
                    elif name == "baseline/openmrs.sql.gz" and member.isfile() and need_db:
                        dest = staging_dir / "openmrs.sql.gz"
                        extracted = archive.extractfile(member)
                        if extracted is not None:
                            with dest.open("wb") as out:
                                shutil.copyfileobj(extracted, out)
                            log(f"Extracted {dest} ({dest.stat().st_size} bytes)")
                    elif need_es:
                        rel_snap = safe_relpath(member.name, "baseline/es-snapshot")
                        if rel_snap is None or rel_snap == Path("."):
                            continue
                        target = es_snapshot_root / rel_snap
                        if member.isdir():
                            target.mkdir(parents=True, exist_ok=True)
                        elif member.isfile():
                            target.parent.mkdir(parents=True, exist_ok=True)
                            extracted = archive.extractfile(member)
                            if extracted is not None:
                                with target.open("wb") as out:
                                    shutil.copyfileobj(extracted, out)
            blob_path.unlink(missing_ok=True)

    return parsed_manifest


def check_es_indices(es_url: str, expected_indices: dict[str, int]) -> tuple[bool, dict[str, int]]:
    status, _ = http_request(f"{es_url}/querystore_*/_refresh", method="POST", timeout=30)
    if status == 404:
        return True, {index_name: 0 for index_name in expected_indices}

    counts: dict[str, int] = {}
    need_es = False
    for index_name, min_docs in expected_indices.items():
        status, body = http_request(f"{es_url}/{index_name}/_count", timeout=15)
        if status == 404:
            counts[index_name] = 0
            need_es = True
            continue
        payload = json.loads(body.decode("utf-8"))
        count = int(payload.get("count", 0))
        counts[index_name] = count
        if count < min_docs:
            need_es = True
    return need_es, counts


def restore_es_snapshot(
    es_url: str,
    expected_indices: dict[str, int],
) -> None:
    log("Waiting for Elasticsearch cluster health before snapshot restore...")
    http_request(f"{es_url}/_cluster/health?wait_for_status=yellow&timeout=60s", timeout=75)

    log("Registering filesystem snapshot repository hiv_baseline at /snapshots/es-snapshot...")
    http_request(
        f"{es_url}/_snapshot/hiv_baseline?verify=false",
        method="PUT",
        json_body={
            "type": "fs",
            "settings": {"location": "/snapshots/es-snapshot", "readonly": True},
        },
        timeout=30,
    )

    _, snaps_raw = http_request(f"{es_url}/_snapshot/hiv_baseline/_all", timeout=30)
    snapshots = json.loads(snaps_raw.decode("utf-8")).get("snapshots", [])
    if not snapshots:
        raise RuntimeError("No snapshots found in /snapshots/es-snapshot repository hiv_baseline")
    snapshot_name = snapshots[0]["snapshot"]

    log("Clearing any partial querystore_* indices prior to restore...")
    http_request(
        f"{es_url}/querystore_*?ignore_unavailable=true",
        method="DELETE",
        timeout=60,
    )

    log(f"Restoring Elasticsearch snapshot {snapshot_name} (querystore_*)...")
    _, restore_raw = http_request(
        f"{es_url}/_snapshot/hiv_baseline/{urllib.parse.quote(snapshot_name)}/_restore"
        "?wait_for_completion=true",
        method="POST",
        json_body={
            "indices": "querystore_*",
            "ignore_unavailable": False,
            "include_global_state": False,
            "include_aliases": True,
        },
        timeout=1800,
    )
    restored = json.loads(restore_raw.decode("utf-8")) if restore_raw else {}
    if restored.get("snapshot", {}).get("shards", {}).get("failed", 0) != 0:
        raise RuntimeError(f"Elasticsearch snapshot restore reported failed shards: {restored!r}")

    http_request(
        f"{es_url}/_cluster/health/querystore_*?wait_for_status=yellow&timeout=120s",
        timeout=135,
    )

    still_missing, counts = check_es_indices(es_url, expected_indices)
    if still_missing:
        raise RuntimeError(
            f"Restored Elasticsearch indices below expected counts: {counts} vs {expected_indices}"
        )

    http_request(f"{es_url}/_snapshot/hiv_baseline", method="DELETE", timeout=30)
    total_docs = sum(counts.values())
    log(f"Verified {len(counts)} QueryStore indices restored ({total_docs} documents)")


def ensure_embedder_files(
    data_dir: Path,
    model_sha256: str,
    vocab_sha256: str,
) -> None:
    target_dir = data_dir / "chartsearchai"
    target_dir.mkdir(parents=True, exist_ok=True)
    model_url = os.environ.get("EMBEDDING_MODEL_URL", DEFAULT_MODEL_URL).strip()
    vocab_url = os.environ.get("EMBEDDING_VOCAB_URL", DEFAULT_VOCAB_URL).strip()

    for filename, url, expected_sha in [
        ("model.onnx", model_url, model_sha256),
        ("vocab.txt", vocab_url, vocab_sha256),
    ]:
        dest = target_dir / filename
        if dest.is_file() and sha256_file(dest) == expected_sha:
            log(f"Verified existing {dest}")
            continue
        log(f"Downloading {filename} to {dest}...")
        http_download(url, dest, expected_sha256=expected_sha, timeout=300)
        log(f"Downloaded and SHA-256 verified {dest}")


def main() -> int:
    staging_dir = Path(os.environ.get("STAGING_DIR", "/staging"))
    snapshot_dir = Path(os.environ.get("SNAPSHOT_DIR", "/snapshots"))
    data_dir = Path(os.environ.get("OPENMRS_DATA_DIR", "/openmrs/data"))
    es_url = os.environ.get("ES_URL", "http://elasticsearch:9200").rstrip("/")
    needs_db_flag = staging_dir / "needs-db-restore"
    staging_dir.mkdir(parents=True, exist_ok=True)

    if not env_bool("HIV_BASELINE_ENABLED", default=True):
        log("HIV_BASELINE_ENABLED is false; skipping baseline restore")
        needs_db_flag.write_text("no\n", encoding="utf-8")
        (staging_dir / "openmrs.sql.gz").unlink(missing_ok=True)
        return 0

    baseline_image = os.environ.get("HIV_BASELINE_IMAGE", DEFAULT_BASELINE_IMAGE).strip()
    if not baseline_image:
        baseline_image = DEFAULT_BASELINE_IMAGE

    db_probe_file = staging_dir / "db-baseline-image"
    current_db_image = (
        db_probe_file.read_text(encoding="utf-8").strip() if db_probe_file.is_file() else ""
    )
    need_db = current_db_image != baseline_image

    receipt_path = data_dir / ".hiv-baseline-manifest.json"
    cached_manifest: dict[str, Any] = {}
    if receipt_path.is_file():
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if receipt.get("image") == baseline_image:
                cached_manifest = receipt.get("manifest") or {}
        except Exception as exc:
            log(f"Ignoring unreadable receipt {receipt_path}: {exc}")

    expected_indices = cached_manifest.get("indices") or FALLBACK_INDICES
    need_es, es_counts = check_es_indices(es_url, expected_indices)

    model_sha256 = (
        (cached_manifest.get("embedding") or {}).get("model_sha256") or DEFAULT_MODEL_SHA256
    )
    vocab_sha256 = (
        (cached_manifest.get("embedding") or {}).get("vocab_sha256") or DEFAULT_VOCAB_SHA256
    )

    log(
        f"Baseline status: image={baseline_image} need_db={need_db} "
        f"(db_tag={current_db_image or '<none>'}) need_es={need_es}"
    )

    parsed_manifest = cached_manifest
    if need_db or need_es:
        registry, repo, reference = parse_image_ref(baseline_image)
        registry_base = os.environ.get("GHCR_REGISTRY_URL", f"https://{registry}").rstrip("/")
        token_url = os.environ.get("GHCR_TOKEN_URL", f"{registry_base}/token").rstrip("/")

        token = fetch_registry_token(token_url, repo)
        auth_headers = {"Authorization": f"Bearer {token}"} if token else {}

        oci_manifest = fetch_oci_manifest(registry_base, repo, reference, auth_headers)
        parsed_manifest = extract_baseline_layers(
            registry_base,
            token_url,
            repo,
            oci_manifest,
            need_db=need_db,
            need_es=need_es,
            staging_dir=staging_dir,
            snapshot_dir=snapshot_dir,
        )
        if not parsed_manifest:
            parsed_manifest = cached_manifest

        model_sha256 = (
            (parsed_manifest.get("embedding") or {}).get("model_sha256") or model_sha256
        )
        vocab_sha256 = (
            (parsed_manifest.get("embedding") or {}).get("vocab_sha256") or vocab_sha256
        )
        expected_indices = parsed_manifest.get("indices") or expected_indices

        if need_es:
            es_uid = int(os.environ.get("ES_HOST_UID", "1000"))
            es_gid = int(os.environ.get("ES_HOST_GID", "0"))
            chown_tree(snapshot_dir, es_uid, es_gid)
            restore_es_snapshot(es_url, expected_indices)
            clear_directory_contents(snapshot_dir)

        if need_db:
            sql_dump = staging_dir / "openmrs.sql.gz"
            if not sql_dump.is_file():
                raise RuntimeError(f"Expected {sql_dump} after layer extraction")
            for cache_subdir in ("chartsearchai", "querystore"):
                shutil.rmtree(data_dir / ".openmrs-lib-cache" / cache_subdir, ignore_errors=True)
    else:
        total_docs = sum(es_counts.values())
        log(f"Database and Elasticsearch indices already match baseline ({total_docs} ES docs)")
        (staging_dir / "openmrs.sql.gz").unlink(missing_ok=True)

    ensure_embedder_files(data_dir, model_sha256, vocab_sha256)

    data_dir.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps({"image": baseline_image, "manifest": parsed_manifest}, indent=2) + "\n",
        encoding="utf-8",
    )

    omrs_uid = int(os.environ.get("OPENMRS_UID", "1001"))
    omrs_gid = int(os.environ.get("OPENMRS_GID", "1001"))
    chown_tree(data_dir, omrs_uid, omrs_gid)

    needs_db_flag.write_text("yes\n" if need_db else "no\n", encoding="utf-8")
    log(f"Staging complete (needs-db-restore={'yes' if need_db else 'no'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
