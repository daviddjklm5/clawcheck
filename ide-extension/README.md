# clawcheck Chat Extension (Optional)

This is a thin VS Code WebView entry for the clawcheck chat capability.

## What it does

- Adds command: `clawcheck: Open Chat Panel`
- Opens a WebView panel that calls clawcheck API endpoints under `/api/chat`
- Reuses the server-side chat runtime (Codex CLI + external model API key)

## Prerequisites

1. Start clawcheck API service.
2. Ensure chat config is valid:
   - `CLAWCHECK_AI_API_KEY` (or env name from `ai.api_key_env`)
   - `CLAWCHECK_AI_BASE_URL` / `CLAWCHECK_AI_MODEL` as needed

## Setting

- `clawcheck.chatApiBaseUrl`
  - Default: `http://127.0.0.1:8000/api`
  - Must include `/api` suffix

## Build

```bash
npm install
npm run compile
```

