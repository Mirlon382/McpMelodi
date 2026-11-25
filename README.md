# MCP Melodi

A [Model Context Protocol](https://modelcontextprotocol.io) server that puts INSEE's **Melodi** open-data store — the dataset catalogue and the observations behind it — in front of an LLM.

![Status: BETA](https://img.shields.io/badge/status-BETA-yellow?style=for-the-badge)
[![CI](https://github.com/Mirlon382/McpMelodi/actions/workflows/ci.yml/badge.svg)](https://github.com/Mirlon382/McpMelodi/actions/workflows/ci.yml)
[![License: Etalab 2.0](https://img.shields.io/badge/licence-Etalab%202.0-blue)](LICENSE)

> **⚠️ BETA — NOT PRODUCTION READY**
> This project is still in beta. It should not be considered a finished or officially supported product from INSEE.

## What works today, and what does not

Three tools, all read-only, and **one of them needs nothing but the public API**:

| Tool | Question it answers | Needs |
| --- | --- | --- |
| `get_melodi_observations` | The rows of one dataset, filtered by year and modality codes | Nothing — the public REST API, keyless |
| `search_melodi_datasets` | Which dataset covers this subject, and which columns it holds | An Elasticsearch index |
| `search_melodi_modalities` | The exact modality code for a value, within a dataset | The same index |

The two search tools read prebuilt indices (`melodi_datasets`, `melodi_columns`) that are **not published yet** — the index builder is still to come. Until then, a deployment without `ES_HOST` is a supported configuration: the server starts, the observations tool answers, and the two searches return an error that says so instead of failing obscurely. When the indices exist, set `ES_HOST` (see the configuration table) and the two tools start working with no code change.

A dataset id can always be found by hand in the [Melodi catalogue](https://catalogue-donnees.insee.fr), which is also what those indices are built from: `GET https://api.insee.fr/melodi/catalog/all` returns **163 datasets, 31 metadata fields each**, keyless.

## A run against the real store

Every output below is what the server returned, not an illustration. `get_melodi_observations`, on a public dataset:

```json
{"dataset_id": "DS_DECES_MORTALITE_SERIES",
 "years": [2024],
 "column_filters": {"FREQ": "A"},
 "number_of_observations": 2}
```

```json
{"dataset_id": "DS_DECES_MORTALITE_SERIES",
 "observations": [
   {"attributes": {"OBS_STATUS": "A", "DECIMALS": "0", "UNIT_MULT": "0", "OBS_STATUS_FR": "D"},
    "dimensions": {"GEO": "2025-DEP-75", "EC_MEASURE": "DTH_PLACE_RES", "SEASONAL_ADJUST": "N",
                   "SEX": "_T", "FREQ": "A", "TIME_PERIOD": "2024", "UNIT_MEASURE": "NR", "AGE": "_T"},
    "measures": {"OBS_VALUE_NIVEAU": {"value": 14079.0}}},
   {"attributes": {"OBS_STATUS": "P", "DECIMALS": "0", "UNIT_MULT": "0", "OBS_STATUS_FR": "PROV"},
    "dimensions": {"GEO": "2025-FRANCE-FM", "EC_MEASURE": "MOR_RT", "SEASONAL_ADJUST": "N",
                   "SEX": "F", "FREQ": "A", "TIME_PERIOD": "2024", "UNIT_MEASURE": "PM", "AGE": "Y80T89"},
    "measures": {"OBS_VALUE_NIVEAU": {"value": 46.0}}}],
 "count": 2}
```

And with no index configured, the search tool answers like this instead of failing silently:

```text
[BACKEND_UNAVAILABLE] This server has no Elasticsearch configured (ES_HOST is unset), so the dataset
and modality indices cannot be searched. The observations tool does not need them, but its dataset_id
has to come from somewhere else -- the Melodi catalogue at https://catalogue-donnees.insee.fr lists
the identifiers. An operator can enable these two tools by setting ES_HOST and building the indices.
```

Two behaviours worth knowing about `get_melodi_observations`:

- **Years are filtered here, not upstream.** The API's own period filter matches only periods that start on that date, so `TIME_PERIOD=2025` returns the yearly row and January but not August. The tool fetches the dataset once and keeps the years asked for, which is why a monthly dataset still returns every month of a year.
- **The result is truncated after filtering**, to `number_of_observations` (100 by default, 1000 at most).

## How to run it

### Locally

You need [uv](https://docs.astral.sh/uv/) — it installs the right Python (3.12) itself:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```bash
git clone https://github.com/Mirlon382/McpMelodi.git
cd McpMelodi
uv sync
uv run mcpserver
```

It listens on `http://0.0.0.0:8000`, MCP endpoint at `/mcp`. Startup prints:

```text
INFO | mcpserver.lifespan.melodi | MELODI client initialized for https://api.insee.fr/melodi/data
WARNING | mcpserver.lifespan.melodi | ES_HOST is not set: the two Melodi search tools will answer with an error.
INFO | mcp.server.streamable_http_manager | StreamableHTTP session manager started
INFO | uvicorn.error | Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Check it is alive without a model or a browser — this lists the tools the server publishes:

```bash
npx -y @modelcontextprotocol/inspector --cli http://127.0.0.1:8000/mcp --method tools/list
```

Drop `--cli` and the same command opens the Inspector's web UI, where you can call the tools by hand.

### In a container

```bash
docker build -t mcpmelodi .
docker run --rm -p 8000:8000 mcpmelodi
```

With podman, add `--format docker`: the OCI image format it defaults to cannot store a `HEALTHCHECK`, and the build silently drops the one in the Dockerfile.

```bash
podman build --format docker -t mcpmelodi .
podman run --rm -p 8000:8000 mcpmelodi
podman inspect --format '{{.State.Health.Status}}' <container>   # → healthy
```

The image runs as uid 1000 and installs no dev dependencies. Its healthcheck opens a TCP connection rather than sending an HTTP request — the MCP endpoint answers `400` without a session handshake, so an HTTP probe would report a healthy server as broken.

`k8s/manifest.yaml` is a template, not a deployment: the hostname (`mcpmelodi.example.com`) and the image are placeholders, `ALLOWED_HOSTS` has to match the Ingress host, and `ES_HOST` is shown commented out because a cluster without the indices is a working deployment.

### Configuration

Copy `.env.example` to `.env`; every variable is optional and the file carries the shipped default. Lists are JSON, never comma-separated: `ALLOWED_HOSTS=["a.example.com","b.example.com"]`.

| Variable | Default | What it does |
| --- | --- | --- |
| `MCP_HOST` / `MCP_PORT` | `0.0.0.0` / `8000` | Where uvicorn binds |
| `ALLOWED_HOSTS` | `["*"]` | Hostnames checked against the `Host` header — `*` disables the check |
| `ALLOWED_ORIGINS` | `[]` | Browser origins; empty rejects every cross-origin call |
| `TRUSTED_PROXY_HOSTS` | `["127.0.0.1"]` | Peers whose `X-Forwarded-For` is believed, for rate-limit identity |
| `ES_HOST` | unset | Elasticsearch address. Unset is supported: the two search tools then answer with an error |
| `ES_INDEX_MELODI_DATASETS` / `ES_INDEX_MELODI_COLUMNS` | `melodi_datasets` / `melodi_columns` | Index names |
| `ES_TLS_VERIFY` | `true` | Verify the cluster certificate |
| `MELODI_DATA_BASE_URL` | `https://api.insee.fr/melodi/data` | The public API being called |
| `MELODI_DEFAULT_OBSERVATIONS` / `MELODI_MAX_OBSERVATIONS` | `100` / `1000` | Rows returned by default, and the ceiling the model may ask for |
| `MELODI_DEFAULT_DATASETS` / `MELODI_MAX_DATASETS` | `5` / `20` | Same pair, for dataset searches |
| `MELODI_DEFAULT_MODALITIES` / `MELODI_MAX_MODALITIES` | `10` / `50` | Same pair, per column, for modality searches |
| `RATE_LIMIT_MAX_REQUESTS` / `RATE_LIMIT_WINDOW_MINUTES` | `100` / `1` | Per-client sliding window |
| `LOG_LEVEL` | `INFO` | Root logger level |

The six `MELODI_*` budgets are what the tool schemas advertise, so changing one changes what the model sees, after a restart. A default above its maximum is refused at startup.

### Development

```bash
uv run pytest -q          # 34 tests
uv run ruff check .       # lint
uv run ruff format .      # format
```

Nothing in the suite touches the network or a cluster: `test_api_service.py` runs the REST client against an `httpx.MockTransport` (200/400/404/500, timeout, non-JSON, missing payload), `test_query_shaping.py` pins the two Elasticsearch bodies without a client, `test_index_service.py` feeds the service the envelope Elasticsearch returns and asserts the mapping — plus the no-`ES_HOST` case, `test_observations_tool.py` covers the year filter and the truncation, and `test_tools.py` reads back the schemas a client actually receives.

`.github/workflows/ci.yml` runs those three commands on every push and pull request, against a `uv.lock` it refuses to re-resolve (`uv sync --locked`), plus a container build that proves the Dockerfile still works.

### What it deliberately does not do

- **No authentication.** Anyone who can reach the port can query. `ALLOWED_HOSTS=["*"]` and an empty `ALLOWED_ORIGINS` are development defaults: set both before exposing this beyond localhost.
- **No persistence.** The rate limiter lives in the process; restarting forgets it, and several replicas each keep their own.
- **No writes.** Every tool is read-only, and INSEE's API is public read-only anyway.
- **No index builder, yet.** The two search tools need indices this repository does not build. That is the next piece of work, not a configuration mistake.

### Licence

Released under the [Licence Ouverte / Open Licence 2.0](LICENSE) (Etalab), the French licence for public information. It grants reuse — commercial included — on condition of attribution and of not suggesting official endorsement. The full text in [`LICENSE`](LICENSE) is authoritative.

This repository is not an INSEE product: it is an independent client of INSEE's public APIs, and the licence above covers the code here, not the Melodi data, which stays under INSEE's own terms.
