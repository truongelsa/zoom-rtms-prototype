# Zoom RTMS Local Prototype (Python + FastAPI)

This repository contains a runnable local prototype backend for Zoom Webhooks + RTMS using Python 3.11+.

For the full feasibility and design output (phases 1–4), see: `docs/PROTOTYPE_PLAN.md`.

## 5) Run the backend with Docker Desktop

### What the Docker support in this repo does
- Builds the image from [`Dockerfile`](Dockerfile)
- Starts the app with `python -m zoom_rtms_local`
- Loads environment variables from `.env`
- Runs the container as `linux/amd64` so it can use the officially supported Linux RTMS wheel on Apple Silicon Docker Desktop
- Publishes `${PORT:-8000}` from the container to the same port on your machine
- Mounts [`recordings/`](recordings) on the host to `/app/recordings` in the container
- Runs the backend as the `backend` service defined in [`docker-compose.yml`](docker-compose.yml)

### Prerequisites
- Docker Desktop installed and running
- Zoom account/app with RTMS access enabled
- Public tunnel for local webhook testing (e.g., ngrok)

### 1. Start Docker Desktop
Open Docker Desktop and wait until the Docker engine is running before you run `docker compose`.

If Docker Desktop is not fully started, `docker compose up` will fail with an error similar to:
```text
Cannot connect to the Docker daemon at unix:///Users/<your-user>/.docker/run/docker.sock
```

### 2. Create the local environment file
From the repo root:
```bash
cp .env.example .env
```

### 3. Fill in `.env`
Edit `.env` with your real Zoom values:
- `ZOOM_CLIENT_ID`
- `ZOOM_CLIENT_SECRET`
- `ZOOM_WEBHOOK_SECRET_TOKEN`

These app settings are also relevant for Docker:
- Keep `HOST=0.0.0.0` so the app listens inside the container.
- `PORT=8000` is the default. If you change it, Docker will publish that same port on your machine.
- `RECORDINGS_DIR` in `.env` is ignored for the Docker run because Compose forces it to `/app/recordings` inside the container and bind-mounts the host [`recordings/`](recordings) folder there.

### 4. Build and start the backend
Run this from the repo root:
```bash
docker compose up --build -d
```

If you prefer to keep the logs attached in your terminal, omit `-d`:
```bash
docker compose up --build
```

After the service starts, Docker Desktop will show a Compose app/project for this repo with a `backend` service/container.

### 5. Check that the backend is up
```bash
docker compose ps
docker compose logs -f backend
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/state | jq
```

The backend listens on `http://127.0.0.1:8000` by default. If you changed `PORT` in `.env`, use that port in the `curl` commands instead.

### 6. Stop the backend
```bash
docker compose down
```

### Docker note for Apple Silicon
This repo is configured to run the `backend` container as `linux/amd64`. That is intentional: the official Zoom RTMS Python package publishes Linux wheels for `x86_64`, while Docker Desktop on Apple Silicon defaults to `linux/arm64`.

### Optional non-Docker run
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m zoom_rtms_local
```

### Expose localhost for Zoom webhook
Example with ngrok:
```bash
ngrok http 8000
```
Then set Zoom event notification endpoint to:
`https://<ngrok-id>.ngrok-free.app/webhook`
If you changed `PORT` in `.env`, use that port instead of `8000` for both `ngrok` and the local checks below.

### Verify locally
```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/state | jq
```

### Expected logs
You should see JSON log events like:
- `endpoint validation handled`
- `webhook received` (`meeting.rtms_started`)
- `joining rtms stream`
- `participant event`
- `active speaker`
- `opened audio file`

### Audio output location
- Host: `recordings/<meeting_uuid>/<participant_id>_<participant_name>.wav`
- Container: `/app/recordings/<meeting_uuid>/<participant_id>_<participant_name>.wav`
- If attribution is unavailable, fallback file uses `mixed` naming.

## 6) Zoom configuration guide

> Source of truth used for this prototype: Zoom official RTMS SDK repo + Zoom official RTMS samples repo + Zoom official webhook sample repo.

### App type
Use a **General App (User-Managed)** in Zoom Marketplace with RTMS event subscriptions/scopes as described in Zoom RTMS sample setup docs.

### Required configuration areas
1. **Credentials**: collect Client ID and Client Secret.
2. **Webhook secret token**: set and copy secret used for signature verification.
3. **Event subscriptions**:
   - `meeting.rtms_started`
   - `meeting.rtms_stopped`
   - endpoint validation event (`endpoint.url_validation`) is implicit during setup.
4. **RTMS access/scopes**:
   - Add RTMS/Meeting scopes required by your account entitlements.

### Webhook endpoint
- Set endpoint to your public tunnel URL + `/webhook`.
- Zoom will POST validation challenge and expect `plainToken` + HMAC `encryptedToken`.

### Meeting/account prerequisites
- Meeting must run under account/app context that has RTMS entitlement.
- Cross-account meetings may have restrictions based on app publication/install/permissions.

### Common mistakes
- Wrong webhook secret token (signature failures).
- Missing `meeting.rtms_started` subscription.
- RTMS not enabled/entitled in account.
- Tunnel URL changed but not updated in Zoom app.

## 7) Verification checklist

- [ ] `/health` returns `{"status":"ok"}`.
- [ ] Zoom webhook validation succeeds.
- [ ] Signed webhook `meeting.rtms_started` is accepted.
- [ ] RTMS session logs show join confirmation.
- [ ] Participant join/leave events appear in logs and `/state`.
- [ ] Active speaker updates appear in logs and `/state`.
- [ ] WAV files are created under `recordings/<meeting_uuid>/`.
- [ ] On `meeting.rtms_stopped`, session closes and files are finalized.

## 8) Known limitations and next steps

### Known limitations
- In-memory state only (lost on restart).
- No retry/backoff orchestration beyond SDK defaults.
- Per-participant isolation depends on Zoom stream mode/metadata availability.
- Local filesystem recording only (no retention policy).

### Next steps
- Add persistent state and event journal.
- Add reconnect/backoff telemetry and alarms.
- Add replay-protection checks on webhook timestamps.
- Export metrics/traces.
- Move recordings to object storage.

## 9) Running quick smoke tests

```bash
python -m compileall src
docker compose up --build -d
curl -s http://127.0.0.1:8000/health
docker compose down
```
If you changed `PORT` in `.env`, use that port for the health check instead of `8000`.
