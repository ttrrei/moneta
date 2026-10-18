# Data

This directory holds **runtime data artifacts** (raw Bronze, Silver, Gold tiers, intermediate parquet/CSV/zip files, DuckDB databases).

- Contents here are generated/derived from upstream ingestion (OCI Object Storage) and are **not** tracked in Git.
- Keep only the directory itself and this `README.md` in version control. All other files under `data/` must remain git-ignored to avoid committing large binary blobs and secrets.