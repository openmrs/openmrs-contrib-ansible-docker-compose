"""Complexity-router classifier plugin that tries a list of classifiers in order.

The `auto` router in config.yaml uses this as its `classifier_plugin`. Each classifier named in
ROUTER_CLASSIFIERS ("jev", "llm") is a private LiteLLM ComplexityRouter configured with that
built-in classifier type, so classification reuses LiteLLM's own Jev client, LLM rubric,
conversation-context handling, circuit breakers, and spend logging. The first classifier that
actually decides the tier wins. If none does, `classify` returns None and the `auto` router's
`classifier_fallback` (the local heuristic scorer) picks the tier.

Configuration (environment variables on the litellm container):
    ROUTER_CLASSIFIERS       Comma-separated order, default "jev,llm". "jev" is skipped with a
                             warning when the `jev-router` model is missing or has no TypeSafe key.
    ROUTER_CLASSIFIER_MODEL  model_list name the "llm" classifier calls, default "fast". Must be a
                             plain model, not a router like `auto`; otherwise the "llm"
                             classifier is skipped with an error.
    TYPESAFE_API_KEY         TypeSafe credential for Jev, used by the `jev-router` model unless it
                             sets its own api_key.

The "jev" classifier calls the `jev-router` decision model in config.yaml through LiteLLM's
Decisions API, so its connection settings live there like any other model's.

This depends on LiteLLM internals (ComplexityRouter, _extract_current_ask_and_system_prompt), so
re-test it whenever the LiteLLM image tag changes. The router's `classifier_plugin_timeout_ms` must
cover the sum of the per-classifier timeouts below.
"""

from __future__ import annotations

import os
from contextvars import ContextVar
from typing import Any, Final

from litellm._logging import verbose_router_logger
from litellm.router_strategy.complexity_router.complexity_router import (
    ComplexityRouter,
    _extract_current_ask_and_system_prompt,
)
from litellm.types.router import RoutingContext

# Only non-empty pools matter here: a delegate's verdict is a tier name, and the `auto` router
# maps it to models using its own `tiers`.
_DELEGATE_TIERS: Final = {"SIMPLE": "fast", "MEDIUM": "balanced", "COMPLEX": "balanced", "REASONING": "strong"}

# ClassificationOutcome.cause when the named classifier, not a fallback, chose the tier.
_DECIDED_CAUSE: Final = {"jev": "jev_classifier", "llm": "llm_classifier"}

_JEV_DEPLOYMENT: Final = "jev-router"
_JEV_TIMEOUT_MS: Final = 3000
_LLM_TIMEOUT_MS: Final = 3000

# Set while a classification is in progress. If the classifier's own model call routes back into
# an auto router that uses this plugin, the nested classify() sees it and declines immediately
# instead of recursing.
_classifying: ContextVar[bool] = ContextVar("tier_classifier_classifying", default=False)


def _router_model_problem(router: Any, model_name: str) -> str | None:
    """Why `model_name` can't be the LLM classifier's model, or None if it can.

    Rejects names with no deployment and names that resolve (directly or through a model group
    alias) to a router model such as `auto`, since classifying with a router would call this
    plugin again.
    """
    deployments = router.get_model_list(model_name=model_name) or []
    if not deployments:
        return f"model {model_name!r} is not in the LiteLLM model list"
    routers = [
        d["litellm_params"]["model"]
        for d in deployments
        if str(d.get("litellm_params", {}).get("model", "")).startswith("auto_router/")
    ]
    if routers:
        return f"model {model_name!r} is a router ({routers[0]}), so classifying with it would call the classifier again"
    return None


def _jev_deployment_problem(router: Any) -> str | None:
    """Why the Jev classifier can't use the `jev-router` model, or None if it can.

    LiteLLM only finds a missing TypeSafe key when it makes the call, so without this check every
    request would wait for a failed Jev call before the next classifier ran.
    """
    deployments = router.get_model_list(model_name=_JEV_DEPLOYMENT) or []
    if not deployments:
        return f"model {_JEV_DEPLOYMENT!r} is not in the LiteLLM model list"
    if not any(d.get("litellm_params", {}).get("api_key") for d in deployments) and not os.environ.get("TYPESAFE_API_KEY"):
        return f"model {_JEV_DEPLOYMENT!r} has no api_key and TYPESAFE_API_KEY is unset"
    return None


class ChainedTierClassifier:
    """Implements LiteLLM's ClassifierPlugin protocol by trying classifiers in order."""

    def __init__(self, classifiers: tuple[str, ...], llm_model: str) -> None:
        unknown = [name for name in classifiers if name not in _DECIDED_CAUSE]
        if unknown:
            raise ValueError(f"ROUTER_CLASSIFIERS has unknown classifiers {unknown}; expected any of {list(_DECIDED_CAUSE)}")
        self._classifiers = classifiers
        self._llm_model = llm_model
        # Built on first use (the proxy's Router does not exist yet when LiteLLM imports this
        # module) and rebuilt whenever the proxy replaces its Router.
        self._router: Any = None
        self._delegates: tuple[tuple[str, ComplexityRouter], ...] = ()

    @classmethod
    def from_env(cls) -> ChainedTierClassifier:
        order = os.environ.get("ROUTER_CLASSIFIERS", "jev,llm")
        return cls(
            classifiers=tuple(name.strip() for name in order.split(",") if name.strip()),
            llm_model=os.environ.get("ROUTER_CLASSIFIER_MODEL", "fast"),
        )

    def _current_delegates(self) -> tuple[tuple[str, ComplexityRouter], ...]:
        from litellm.proxy import proxy_server

        router = proxy_server.llm_router
        if router is None:
            raise RuntimeError("LiteLLM proxy router is not initialized")
        if router is not self._router:
            self._delegates = self._build_delegates(router)
            self._router = router
        return self._delegates

    def _build_delegates(self, router: Any) -> tuple[tuple[str, ComplexityRouter], ...]:
        configs = {
            "jev": {
                "classifier_type": "jev",
                "jev_classifier_config": {"deployment_name": _JEV_DEPLOYMENT, "timeout_ms": _JEV_TIMEOUT_MS},
            },
            "llm": {
                "classifier_type": "llm",
                "classifier_llm_config": {"model": self._llm_model, "timeout_ms": _LLM_TIMEOUT_MS},
            },
        }
        delegates = []
        for name in self._classifiers:
            if name == "llm":
                problem = _router_model_problem(router, self._llm_model)
                if problem is not None:
                    verbose_router_logger.error("tier_classifier: skipping llm classifier: ROUTER_CLASSIFIER_MODEL %s", problem)
                    continue
            if name == "jev":
                problem = _jev_deployment_problem(router)
                if problem is not None:
                    verbose_router_logger.warning("tier_classifier: skipping jev classifier: %s", problem)
                    continue
            try:
                delegate = ComplexityRouter(
                    model_name=f"tier-classifier-{name}",
                    litellm_router_instance=router,
                    complexity_router_config={**configs[name], "tiers": _DELEGATE_TIERS},
                    derive_savings_baseline=False,
                )
            except ValueError as e:
                verbose_router_logger.warning("tier_classifier: skipping %s classifier: %s", name, e)
                continue
            delegates.append((name, delegate))
        return tuple(delegates)

    async def classify(self, context: RoutingContext) -> str | None:
        if _classifying.get():
            verbose_router_logger.error(
                "tier_classifier: classify() re-entered from its own classifier call; declining to avoid recursion"
            )
            return None
        token = _classifying.set(True)
        try:
            return await self._classify(context)
        finally:
            _classifying.reset(token)

    async def _classify(self, context: RoutingContext) -> str | None:
        request_kwargs = {"metadata": dict(context.metadata)}
        for name, delegate in self._current_delegates():
            markers = delegate._reminder_markers_for_request(request_kwargs)
            ask, system_prompt = _extract_current_ask_and_system_prompt(context.structured_messages, markers)
            if ask is None:
                return None
            outcome = await delegate.aclassify(
                ask, system_prompt, request_kwargs=request_kwargs, messages=context.structured_messages
            )
            if outcome.cause == _DECIDED_CAUSE[name]:
                return outcome.tier.value
            verbose_router_logger.warning(
                "tier_classifier: %s classifier did not decide (cause=%s), trying next", name, outcome.cause
            )
        return None


classifier = ChainedTierClassifier.from_env()
