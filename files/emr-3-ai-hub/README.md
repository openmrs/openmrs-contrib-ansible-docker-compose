# emr-3-ai-hub

OpenMRS Reference Application 3 (`nightly-chartsearch`) with **QueryStore on Elasticsearch 8.13.4**, the **prebuilt OpenClinAI HIV dataset baseline** (MariaDB dump + pre-embedded 514k-doc QueryStore snapshot + `all-MiniLM-L6-v2` ONNX embedder), **`med-agent-hub`**, and **`llama-router`** (`llama.cpp` Router Mode).

## Architecture

- **OpenMRS core stack** (`gateway`, `frontend`, `backend`, `db`): Reference Application 3 `nightly-chartsearch` images on host port `8889:80` (configurable via `GATEWAY_PORT`). `backend` configures QueryStore to use Elasticsearch (`OMRS_EXTRA_QUERYSTORE_BACKEND=elasticsearch`, `OMRS_EXTRA_QUERYSTORE_ELASTICSEARCH_URI=http://elasticsearch:9200`) and sets `OMRS_EXTRA_OPTIMIZED_STARTUP=false` for pre-populated upgrades.
- **QueryStore CQRS Read Store** (`elasticsearch`): Single-node `docker.elastic.co/elasticsearch/elasticsearch:8.13.4` storing all 10 `querystore_*` indices (514,682 pre-embedded documents from the HIV baseline).
- **Idempotent Prebuilt HIV Baseline Init** (`hiv-db-probe`, `hiv-baseline-stage`, `hiv-baseline-db`):
  1. `hiv-db-probe` reads `openclinai.hivBaseline.image` from MariaDB (`global_property`) to check whether the database already matches `HIV_BASELINE_IMAGE`.
  2. `hiv-baseline-stage` checks both the DB probe flag and Elasticsearch `querystore_*` document counts, pulls `HIV_BASELINE_IMAGE` anonymously from GHCR with SHA-256 verification only when DB or ES restore is needed, restores the Elasticsearch snapshot (`_snapshot/hiv_baseline`), verifies all 10 index document counts, stages `/openmrs/data/chartsearchai/{model.onnx,vocab.txt}` (`all-MiniLM-L6-v2`, SHA-256 verified), and clears stale `.openmrs-lib-cache/{chartsearchai,querystore}` on DB refresh.
  3. `hiv-baseline-db` imports `openmrs.sql.gz` into MariaDB when needed and records `openclinai.hivBaseline.image` and `chartsearchai.demo.seededDataset=openclinai-hiv-baseline` so `backend` never re-downloads the smaller demo dump over the baseline.
- **Clinical AI Hub** (`med-agent-hub`): Serves staged clinical QA workflows (`/v1/models`, `/v1/chat/completions`), reading patient records over REST from QueryStore under a least-privileged OpenMRS service account (`med-agent-hub`).
- **Model Router** (`llama-router`): In-stack `ghcr.io/ggml-org/llama.cpp` Router Mode server configured via `router/llama-router.ini` with presets for `gemma-4-12b` (default), `gemma-4-12b-q4`, `gemma-e4b`, `gemma-e2b`, `gemma-26b`, `qwen3.5-9b`, and `qwen2.5-14b`, sharing the persistent `llm-models` volume.
- **Automated OpenMRS Wiring** (`models-init`, `hub-config-init`):
  - `models-init` prepares permissions on `llm-models`.
  - `hub-config-init` runs `config/configure-openmrs.py` once `backend` and `med-agent-hub` are healthy to verify `querystore` and `chartsearchai` modules started, reconcile the 10-privilege `Med Agent Hub Patient Reader` role and `med-agent-hub` user, remove stale `chartsearchai.chartMode` overrides, wire both `hub` and `bundled` (via `llama-router`) Global Properties, trigger `POST searchindexupdate` + verify `/ws/rest/v1/querystore/indexingstatus` and `querystore/patientrecord/<uuid>` as `med-agent-hub`, optionally provision the 7 `eval-*` synthetic-research accounts when `EVALUATION_PASSWORD` is set, and check `med-agent-hub`'s `/v1/models`.
- **Observability** (`monitoring-init`, `loki`, `alloy`, `grafana`): Matches `emr-3-ai`.

## Configuration & Secrets

1. Copy `env.template` to `.env` and fill in strong random values for all `CHANGE_ME_*` variables (`ansible-vault` encrypted in OpenMRS infrastructure). Never commit plaintext `.env` files.
2. `deploy.env` sets `DESTROY_VOLUMES=false` and `HEALTH_CHECK_TIMEOUT=2400` so the OpenMRS database, Elasticsearch indices, and downloaded GGUF models persist across redeploys without re-downloading.
3. Optional research accounts: set `EVALUATION_PASSWORD` in `.env` if you also want `hub-config-init` to provision/reconcile the 7 `eval-*` accounts (`eval-clinical-officer`, `eval-nurse`, `eval-pharmacy`, `eval-counsellor`, `eval-records`, `eval-doctor`, `eval-peer`).

## Inference Backend Modes

### Mode A — Self-Hosted `llama.cpp` Router (Default)

By default, `MED_AGENT_LLM_PROVIDER=openai-compatible`, `MED_AGENT_LLM_BASE_URL=http://llama-router:8077`, and `MED_AGENT_PRELOAD_MODELS=gemma-4-12b`. `med-agent-hub` downloads and SHA-256 verifies pinned GGUFs into `llm-models`, and `llama-router` serves all configured presets in `router/llama-router.ini` (including `gemma-4-12b` with `swa-full = true`, `ctx-size = 98304`, `parallel = 2`). ChartSearchAI's `bundled` provider also points at `http://llama-router:8077/v1/chat/completions` so `bundled` and `hub` share the single router without spawning a second embedded `llama-server`.

### Mode B — Remote OpenRouter / OpenAI-Compatible Endpoint

To offload inference to OpenRouter (or another remote OpenAI-compatible API) without changing the ChartSearchAI setup, set in `.env`:

```dotenv
MED_AGENT_LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=<your-openrouter-key>
MED_AGENT_PRELOAD_MODELS=
```

Optional per-alias overrides can be supplied via `MED_AGENT_LLM_MODEL_MAP`.
