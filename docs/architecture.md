# Architecture

The bot is a small Python service built around a live audio bridge between Twilio and OpenAI Realtime. Twilio places the outbound call to the assessment number and requests TwiML from the FastAPI server. That TwiML connects the call to a bidirectional Twilio Media Stream. The media stream websocket forwards 8 kHz G.711 audio to OpenAI Realtime, and OpenAI Realtime returns synthesized patient audio back to Twilio. This keeps the call interactive: the bot listens to the agent, responds using server-side voice activity detection, and follows a scenario-specific patient persona rather than reading a rigid script.

## Goals

- Conduct natural multi-turn voice calls as a realistic patient.
- Keep every test constrained to the single allowed assessment number.
- Reuse one caller number across all scenarios.
- Save enough evidence to review failures after the call: transcripts, recordings, raw events, and a synthesized bug report.

## Main Components

- `cli.py`
  Exposes operational commands: `serve`, `call`, `run-suite`, `fetch-recordings`, `analyze`, and `list-scenarios`.

- `calls.py`
  Creates outbound Twilio calls, applies the hard target-number guardrail, and runs the full suite sequentially.

- `server.py`
  Hosts the FastAPI app. `/voice` returns TwiML that connects the call to the media stream. `/media` bridges Twilio audio to OpenAI Realtime and routes generated audio back into the live call.

- `scenarios.py`
  Defines the patient personas, stable facts, and shared behavioral rules. This is where scenario-level prompt engineering lives.

- `artifacts.py`
  Manages artifact directories and writes transcripts plus raw event logs as the call runs.

- `recordings.py`
  Downloads Twilio recordings after calls complete so the realtime path stays focused on the live conversation.

- `analyze.py`
  Performs a second-pass review over saved transcripts and produces `artifacts/reports/bug_report.md`.

## Runtime Flow

1. A local FastAPI server starts on port `8000`.
2. `ngrok` exposes the server publicly and its HTTPS URL is stored in `PUBLIC_BASE_URL`.
3. `calls.py` places an outbound Twilio call to the locked challenge number.
4. Twilio requests `/voice`, which returns TwiML containing a `<Connect><Stream /></Connect>` directive.
5. Twilio opens the `/media` websocket and streams inbound call audio.
6. The server forwards base64-encoded G.711 audio frames to OpenAI Realtime.
7. OpenAI Realtime returns output audio deltas and transcript events.
8. The server writes transcript turns and raw JSONL events under `artifacts/`.
9. After the suite, recordings are fetched from Twilio and transcript analysis generates the final markdown bug report.

## Why This Design

I chose this shape because voice quality is the first evaluation criterion. A live full-duplex bridge gives better turn-taking and pacing than pre-recorded prompts or text-only automation, while still keeping the implementation small enough to reason about. Separating live call handling from post-call recording downloads and transcript analysis also keeps the critical realtime path narrow.

## Safety and Operational Constraints

- The code enforces `TARGET_NUMBER=+18054398008`. Any attempt to dial another number fails locally before the API request is sent.
- All calls are expected to originate from the single configured `TWILIO_FROM_NUMBER`.
- Transcript generation only happens for fresh calls that successfully pass through the `/media` websocket bridge.
- Scenario changes require a server restart because the FastAPI process loads prompt instructions at runtime.

## Artifact Strategy

Each call produces a consistent set of reviewable artifacts:

- `artifacts/events/*.jsonl`
  Raw Twilio and OpenAI event stream for debugging.

- `artifacts/transcripts/*.txt`
  Human-readable turn-by-turn transcript assembled during the live call.

- `artifacts/recordings/*.mp3`
  Twilio recording downloads retrieved after the call completes.

- `artifacts/reports/bug_report.md`
  Final LLM-assisted summary of concrete agent issues with evidence and severity.

## Known Practical Gotchas

- If another local project installed a different `pgai-bot` command, use `python3 -m pgai_voice_bot.cli ...` to avoid command-name collisions.
- If Twilio creates the call but no transcript appears, the first thing to inspect is whether the active FastAPI server and ngrok tunnel are pointing at the same repo and port.
- The OpenAI Realtime websocket depends on a valid SSL trust chain. The server uses `certifi` explicitly to avoid machine-specific certificate failures.
