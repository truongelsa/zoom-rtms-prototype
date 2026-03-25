# Live RTMS Test Guide

This runbook is for a real end-to-end test with:
- Zoom Marketplace app configuration
- your local backend running in Docker
- `ngrok` exposing your local backend
- a real Zoom meeting that should trigger `meeting.rtms_started`

Use this file when you are ready to move beyond the manual `curl` webhook test.

## 1. Goal

The live test is successful when all of these are true:
- Zoom can reach your public webhook endpoint
- Zoom sends `meeting.rtms_started`
- the backend logs `joining rtms stream`
- the RTMS client logs `rtms join confirmed`
- `/state` shows the meeting and participant updates
- audio files appear under `recordings/`

## 2. Current values

These are the values currently in use in this repo:
- Local backend URL: `http://127.0.0.1:8000`
- Current public tunnel URL: `https://colby-discreet-erectly.ngrok-free.dev`
- Webhook endpoint URL: `https://colby-discreet-erectly.ngrok-free.dev/webhook`

If you restart `ngrok`, the public URL may change. If it changes, update the Zoom app configuration before testing again.

## 3. Zoom Website Checklist

Open your Zoom Marketplace app and verify these items before starting the meeting.

### Access > Secret Token
- Confirm the Secret Token in Zoom matches `.env`
- Current local value is in [.env](/Users/truongnn/Documents/elsa_be/zoom-rtms-prototype/.env#L3)

### Access > Event Subscription
- The Event Subscription feature is enabled
- `Webhook` is selected, not `WebSocket`
- Event notification endpoint URL is:
  `https://colby-discreet-erectly.ngrok-free.dev/webhook`
- The subscription is saved

### Events
- Make sure the subscription includes at least:
  - `meeting.rtms_started`
  - `meeting.rtms_stopped`

### OAuth Information
- The OAuth Redirect URL and OAuth Allow List can point to a real route on your backend such as:
  `https://colby-discreet-erectly.ngrok-free.dev/health`
- These OAuth fields are not the webhook endpoint
- They do not replace `/webhook`

### Local Test
- Make sure the app is available for local testing if Zoom requires that for your account/app type

## 4. Prepare the Backend

From the repo root:

```bash
cd /Users/truongnn/Documents/elsa_be/zoom-rtms-prototype
```

Restart the backend before the live test so you start with clean logs and clean in-memory state:

```bash
docker compose down
docker compose up --build -d
```

Confirm the backend is running:

```bash
docker compose ps
curl -s http://127.0.0.1:8000/health
```

Expected health response:

```json
{"status":"ok"}
```

Optional: confirm state is empty before the live meeting:

```bash
curl -s http://127.0.0.1:8000/state | jq
```

Expected before the live event:

```json
{
  "meetings": {}
}
```

## 5. Start ngrok

In a separate terminal:

```bash
ngrok http 8000
```

Confirm the forwarding URL still matches the URL configured in Zoom:

```text
https://colby-discreet-erectly.ngrok-free.dev
```

If ngrok shows a different URL, update the Zoom webhook endpoint to:

```text
<new-ngrok-url>/webhook
```

## 6. Open Monitoring Windows

Keep these running during the live test.

### Terminal 1: backend logs

```bash
cd /Users/truongnn/Documents/elsa_be/zoom-rtms-prototype
docker compose logs -f backend
```

### Terminal 2: state checks on demand

```bash
cd /Users/truongnn/Documents/elsa_be/zoom-rtms-prototype
watch -n 2 'curl -s http://127.0.0.1:8000/state | jq'
```

If `watch` is unavailable on your machine, run this manually when needed instead:

```bash
curl -s http://127.0.0.1:8000/state | jq
```

### Browser: ngrok inspector

Open:

[http://127.0.0.1:4040](http://127.0.0.1:4040)

This lets you see whether Zoom is actually sending:
- `POST /webhook`

## 7. Optional Pre-Flight Check

Before using a real meeting, you can confirm the public webhook path still works:

```bash
curl -s -X POST https://colby-discreet-erectly.ngrok-free.dev/webhook \
  -H 'Content-Type: application/json' \
  -d '{"event":"endpoint.url_validation","payload":{"plainToken":"manual-test"}}'
```

Expected response:

```json
{
  "plainToken": "manual-test",
  "encryptedToken": "..."
}
```

If this fails, do not continue to the meeting test yet.

## 8. Start the Real Zoom Meeting

Use the Zoom desktop app or Zoom web client to start the meeting that should trigger RTMS.

Recommended approach:
- use the same Zoom account that owns or locally tests the app
- start a real meeting, not just a scheduled meeting page
- have at least one participant join and speak for a few seconds

If your RTMS access is restricted by account or authorization rules, make sure the meeting is started under the correct account/app context.

## 9. What You Should See

### In ngrok inspector

You should see one or more entries like:
- `POST /webhook`

### In backend logs

Success should look roughly like this sequence:

```text
webhook received
joining rtms stream
rtms join confirmed
participant event
active speaker
opened audio file
```

The minimum useful milestone sequence is:
- `webhook received` with event `meeting.rtms_started`
- `joining rtms stream`
- `rtms join confirmed`

### In `/state`

Run:

```bash
curl -s http://127.0.0.1:8000/state | jq
```

Expected after `meeting.rtms_started`:
- a new entry appears under `meetings`
- it contains:
  - `meeting_uuid`
  - `rtms_stream_id`
  - `signaling_server_url`

Expected later during the meeting:
- `participants` becomes non-empty
- `active_speaker_user_id` is updated
- participant records show `is_present`, `joined_at`, and possibly `last_audio_ts`

### On disk

Check:

```bash
ls -R /Users/truongnn/Documents/elsa_be/zoom-rtms-prototype/recordings
```

Expected:
- a folder for the meeting UUID
- one or more `.wav` files inside it

## 10. How to Decide if the Live Test Passed

Use this decision tree:

### Case A: `POST /webhook` never appears
- Zoom did not send the event to your backend
- Check the Event Subscription URL again
- Confirm the saved URL ends with `/webhook`
- Confirm `ngrok` is still running and the URL did not change

### Case B: `POST /webhook` appears, but no `meeting.rtms_started`
- Zoom reached your backend, but that specific event was not sent
- Check the event subscription list in Zoom
- Confirm `meeting.rtms_started` is included
- Confirm the meeting and account are RTMS-enabled

### Case C: `meeting.rtms_started` appears, but no `rtms join confirmed`
- Webhook delivery works, but RTMS session establishment failed
- Check backend logs for SDK errors after `joining rtms stream`
- Common causes:
  - meeting/account lacks RTMS entitlement
  - app authorization or account scope mismatch
  - meeting started under the wrong account context

### Case D: `rtms join confirmed` appears, but no participant or audio data
- RTMS session joined, but media/participant callbacks are not arriving yet
- Have another participant join
- Speak into the microphone for several seconds
- Keep checking logs and `/state`

### Case E: audio files appear in `recordings/`
- This is the strongest sign that the RTMS flow is working end to end

## 11. Exact Commands to Run During the Live Test

### Backend status

```bash
cd /Users/truongnn/Documents/elsa_be/zoom-rtms-prototype
docker compose ps
curl -s http://127.0.0.1:8000/health
```

### Live logs

```bash
cd /Users/truongnn/Documents/elsa_be/zoom-rtms-prototype
docker compose logs -f backend
```

### Current state

```bash
cd /Users/truongnn/Documents/elsa_be/zoom-rtms-prototype
curl -s http://127.0.0.1:8000/state | jq
```

### Recordings

```bash
cd /Users/truongnn/Documents/elsa_be/zoom-rtms-prototype
ls -R recordings
```

## 12. What to Send Back for Help

If the live test does not work, collect these three things:

1. The most recent 50 backend log lines:

```bash
cd /Users/truongnn/Documents/elsa_be/zoom-rtms-prototype
docker compose logs --no-color --tail=50 backend
```

2. The current state snapshot:

```bash
cd /Users/truongnn/Documents/elsa_be/zoom-rtms-prototype
curl -s http://127.0.0.1:8000/state | jq
```

3. A screenshot of the Zoom Event Subscription section showing:
- the saved endpoint URL
- whether `meeting.rtms_started` is included

With those three items, the failure point is usually easy to identify.
