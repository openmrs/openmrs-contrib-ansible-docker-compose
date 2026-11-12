# emr-3-ai-hub

OpenMRS Reference Application 3 (`nightly-chartsearch`) paired with ChartSearchAI's external `med-agent-hub` provider and an optional in-stack `llama.cpp` model router.

## Architecture

- **OpenMRS core stack** (`gateway`, `frontend`, `backend`, `db`): Standard Reference Application 3 `nightly-chartsearch` images on host port `8889:80` (configurable via `GATEWAY_PORT`).
- **Clinical AI Hub** (`med-agent-hub`): Serves staged clinical QA workflows (`/v1/models`, `/v1/chat/completions`), reading patient records over REST from QueryStore under a least-privileged OpenMRS service account (`med-agent-hub`).
- **Model Router** (`llama-router`): In-stack `ghcr.io/ggml-org/llama.cpp` Router Mode server configured via `router/llama-router.ini`, sharing the persistent `llm-models` volume.
- **Automated OpenMRS Wiring** (`models-init`, `hub-config-init`):
  - `models-init` prepares permissions on the `llm-models` volume.
  - `hub-config-init` runs `config/configure-openmrs.py` once `backend` and `med-agent-hub` are healthy to reconcile the 10-privilege `Med Agent Hub Patient Reader` role, create/update the `med-agent-hub` service user, and configure ChartSearchAI Global Properties (`chartsearchai.hub.endpointUrl`, `chartsearchai.providers.enabled=bundled,hub`, `chartsearchai.providers.default=hub`).
- **Observability** (`monitoring-init`, `loki`, `alloy`, `grafana`): Matches `emr-3-ai`.

## Configuration & Secrets

1. Copy `env.template` to `.env` and fill in strong random values for all `CHANGE_ME_*` variables (`ansible-vault` encrypted in OpenMRS infrastructure). Never commit plaintext `.env` files.
2. `deploy.env` sets `DESTROY_VOLUMES=false` and `HEALTH_CHECK_TIMEOUT=900` so the OpenMRS database, Lucene/QueryStore index, and downloaded GGUF models persist across redeploys.

## Inference Backend Modes

### Mode A — Self-Hosted `llama.cpp` Router (Default)

By default, `MED_AGENT_LLM_PROVIDER=openai-compatible` and `MED_AGENT_LLM_BASE_URL=http://llama-router:8077`. `med-agent-hub` downloads and SHA-256 verifies `gemma-e4b` (`MED_AGENT_PRELOAD_MODELS=gemma-e4b`) into `llm-models`, and `llama-router` serves `[gemma-e4b]` and `[gemma-e2b]` from `router/llama-router.ini`.

To enable larger models (`gemma-4-12b-q4`, `gemma-4-12b`, `gemma-26b`, `qwen3.5-9b`) on GPU or high-RAM hosts, uncomment the desired sections in `router/llama-router.ini` and update `MED_AGENT_PRELOAD_MODELS` in `.env`.

### Mode B — Remote OpenRouter / OpenAI-Compatible Endpoint

To offload inference to OpenRouter (or another remote OpenAI-compatible API) without changing the ChartSearchAI setup, set in `.env`:

```dotenv
MED_AGENT_LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=<your-openrouter-key>
MED_AGENT_PRELOAD_MODELS=
```

Optional per-alias overrides can be supplied via `MED_AGENT_LLM_MODEL_MAP`.
