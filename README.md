# moneta

> Early-stage scaffolding for **Nova**, an ultra-lightweight quantitative strategy discovery and optimization engine for forex, precious metals, crude oil, and equity indices.

## Current Status

This repository started from the single-line `# moneta` initial commit and now contains an **early, partial Bronze data-ingestion implementation** on top of scaffolding. Only the items explicitly listed below as implemented actually exist; the rest of the "Nova" stack is still planned.

Implemented so far:

- `pipeline/extract_oci.py` — OCI PAR listing + download, safe path handling, zip extraction to a flat CSV directory, YAML config loading (`config/setting.yml`), and a `main()` entry point.
- `tests/test_extract_oci.py` — 7 unit tests covering the above (run with `pytest -q`).
- `legacy/extract_zips.py` and `legacy/sync_oci.py` — older reference implementations kept for migration context (not active; their constants/APIs differ from `pipeline/`).

Still **not** implemented (see Roadmap):

- Silver/Gold transformations, DuckDB loading, feature engineering
- YAML strategy schema, vectorized backtest, deduplication, evaluation metrics
- AI strategy generation pipeline, strategy zoo, CI

What currently exists in the working tree:

- `README.md` — this document
- `LICENSE` — MIT License
- `.gitignore` — Python ignore rules plus local ignores for `legacy/` contents, `data/` contents, and `config/setting.yml`
- `requirement.txt` — Python dependency manifest (currently untracked)
- `config/setting.example.yml` — template for `config/setting.yml` (currently untracked)
- `config/setting.yml` — local OCI PAR URL (git-ignored, untracked)
- `pipeline/` — Bronze ingestion implementation (currently untracked)
- `tests/` — pipeline unit tests (currently untracked)
- `legacy/` — reference-only code (contents git-ignored except `README.md`)
- `data/` — runtime artifacts (contents git-ignored except `README.md`)

The Git history currently consists of a single initial commit on `main`; all implementation files above are still untracked in the working tree.

## Project Vision (planned, not yet implemented)

Nova is intended to be an automated quantitative strategy discovery system built around a multi-timeframe state-transition trading paradigm:

- **Trend determination** on the 1-hour timeframe
- **Entry execution** on the 5-minute timeframe
- **Look-ahead bias elimination** by locking 1-hour features to the last fully closed candle during 5-minute signal calculation

Planned capabilities, listed as goals rather than implemented features:

- AI-driven strategy generation (Gemini + Gemma multi-model pipeline)
- Self-describing YAML strategy specifications
- Four-level progressive deduplication (syntax normalization, SHA-256 fingerprinting, AI self-reflection retries, signal-correlation deduplication)
- Vectorized backtesting on DuckDB with R-Multiple normalization and pessimistic collision handling
- Anti-overfitting constraints (time uniformity, win-rate stability, equity thickness)
- Medallion data architecture (Bronze → Silver → Gold) over Apache Parquet

## Planned (future) project structure

The layout below describes the intended structure. Note that it uses `nova/` and `data_pipeline/` as target names while the code implemented so far lives under `pipeline/` and `tests/` instead; the tree itself (including `nova/` and `main.py`) is not present yet.

```text
nova/
├── data_pipeline/
│   ├── sync_oci.py
│   ├── build_silver.py
│   └── build_gold_features.py
├── ai_engine/
├── backtest_engine/
├── ideas_backlog/
├── strategies_zoo/
├── DESIGN.md
└── main.py
```

## Tech stack (target, from `requirement.txt`)

| Category | Technology |
|----------|------------|
| Language | Python 3.12+ |
| Data engine | DuckDB, Apache Parquet (pyarrow) |
| Object storage | OCI Object Storage |
| AI / LLM SDKs | `google-genai` |
| Utilities | NumPy, pandas, PyYAML, python-dotenv |

## Getting started

Create and activate a virtual environment, then install the declared dependencies:

```bash
python -m venv .venv
# PowerShell
. .venv/Scripts/Activate.ps1
# or cmd.exe
.venv\Scripts\activate.bat

pip install -r requirement.txt
```

There is now a runnable Bronze entry point: `python -m pipeline.extract_oci` (or `python pipeline/extract_oci.py`) downloads and extracts raw data; the commands above still only prepare the environment for everything else. Silver/Gold and beyond remain unimplemented.

## Configuration

Raw market data is fetched from OCI Object Storage using the PAR URL in `config/setting.yml`:

```yaml
oci:
  par_url: "https://objectstorage.ap-sydney-1.oraclecloud.com/p/.../n/.../b/.../o/"
```

Historical OANDA candles can be downloaded with `pipeline.extract_oanda`. Put
the OANDA API token in the ignored local `config/setting.yml` (start from
`config/setting.example.yml`):

```yaml
oanda:
  api_token: "YOUR_ROTATED_TOKEN"
  environment: "practice" # or live
  price: "MBA"
  smooth: false
```

Extract either a gap or a historical interval by specifying inclusive UTC
timestamps:

```bash
python -m pipeline.extract_oanda --instrument GBP_USD \
  --from 2026-07-08T02:25:00Z --to 2026-07-08T20:47:00Z
```

The extractor paginates requests at OANDA's 5,000-candle limit and writes the
raw CSV schema under `data/raw_csv/<instrument>/`, ready for
`python -m pipeline.load_data`. Re-running the same interval replaces that
interval's output file; loading deduplicates overlapping intervals by
`(instrument, time)`. Use `--output` to select a specific CSV destination or
`--json-out` to preserve the raw API response. `OANDA_API_TOKEN` and `--token`
can override the configured token.

Tokens should not be committed. Any token pasted into a chat, command history,
or other shared location should be revoked and replaced before use.

## Roadmap

- [x] Bronze data ingestion from OCI Object Storage (extract step only: `pipeline/extract_oci.py`)
- [ ] DuckDB loading of raw CSVs
- [ ] Silver transformation (resampling to 5m / 1h)
- [ ] Gold feature wide tables
- [ ] YAML strategy schema
- [ ] Vectorized backtest engine
- [ ] Deduplication engine
- [ ] Evaluation metrics
- [ ] AI strategy generation pipeline
- [ ] Strategy Zoo management
- [ ] Automated tests and CI (partial: 7 pipeline unit tests, no CI)

## License

[MIT License](LICENSE)
