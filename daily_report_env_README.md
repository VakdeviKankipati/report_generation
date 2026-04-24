# `daily_report_env` (OpenEnv package)

This directory is the **OpenEnv environment package**. Full documentation, HF Space metadata, baseline numbers, and root `Dockerfile` / `inference.py` live in the **repository root** [`README.md`](../README.md).

Quick start:

```bash
uv sync
uv run openenv validate --verbose
uv run uvicorn server.app:app --host 0.0.0.0 --port 8000
```
