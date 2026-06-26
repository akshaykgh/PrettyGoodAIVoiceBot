# Pretty Good AI Voice Bot

Automated Python voice bot for the Pretty Good AI engineering challenge. It calls only the assessment test line, behaves like a realistic patient, records/transcribes conversations, and analyzes transcripts for agent quality issues.

## What It Does

- Places outbound calls through Twilio to `+1-805-439-8008` only.
- Bridges the live phone audio to OpenAI Realtime so the caller can hold a natural voice conversation.
- Uses varied patient scenarios for scheduling, refills, office questions, insurance, cancellations, and edge cases.
- Saves raw call events, transcripts, recordings metadata, and generated bug reports under `artifacts/`.
- Uses a single caller number for every test call via `TWILIO_FROM_NUMBER`.

## Repository Layout

- `src/pgai_voice_bot/cli.py`: CLI entrypoint for serving, calling, running suites, fetching recordings, and analysis.
- `src/pgai_voice_bot/server.py`: FastAPI webhook and Twilio Media Stream bridge to OpenAI Realtime.
- `src/pgai_voice_bot/calls.py`: outbound call creation and suite orchestration.
- `src/pgai_voice_bot/scenarios.py`: patient personas, facts, and prompt instructions.
- `src/pgai_voice_bot/recordings.py`: Twilio recording download helpers.
- `src/pgai_voice_bot/analyze.py`: transcript analysis and markdown bug report generation.
- `src/pgai_voice_bot/artifacts.py`: artifact directory, transcript writing, and JSONL logging helpers.
- `docs/architecture.md`: architecture and design rationale.

## Where to Find Submission Artifacts

- Architecture document: `docs/architecture.md`
- Source code: `src/pgai_voice_bot/`
- Transcripts: `artifacts/transcripts/`
- Audio recordings: `artifacts/recordings/`
- Bug report: `artifacts/reports/bug_report.md`
- Raw event logs: `artifacts/events/`
- Call index: `artifacts/calls.jsonl`

## Setup

1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies:

```bash
pip install -e .
```

3. Copy `.env.example` to `.env` and fill in Twilio/OpenAI values.
4. Expose the local server to Twilio, for example:

```bash
ngrok http 8000
```

5. Set `PUBLIC_BASE_URL` in `.env` to the HTTPS tunnel URL.

## Run

Use the module form below if your machine has another `pgai-bot` command installed elsewhere. It avoids command-name collisions with older local projects.

If you prefer a shorter command flow, a `Makefile` is included. After your local server and ngrok tunnel are running, `make full` runs the rest of the project flow in one command: it places the full scenario suite, fetches recordings, and analyzes transcripts to generate the final bug report.

Start the webhook and media bridge:

```bash
python3 -m pgai_voice_bot.cli serve
```

In a second terminal, place one call:

```bash
python3 -m pgai_voice_bot.cli call --scenario appointment_basic
```

Run the required 10-call suite:

```bash
python3 -m pgai_voice_bot.cli run-suite
```

By default, the suite waits for each call to finish before starting the next one. This takes longer, but produces cleaner conversations and keeps every test on the same caller number.

After calls finish, fetch Twilio recording files and analyze transcripts:

```bash
python3 -m pgai_voice_bot.cli fetch-recordings
python3 -m pgai_voice_bot.cli analyze
```

The generated submission artifacts are written to:

- `artifacts/transcripts/*.txt`
- `artifacts/recordings/*.mp3`
- `artifacts/reports/bug_report.md`
- `artifacts/events/*.jsonl`

To list built-in scenarios:

```bash
python3 -m pgai_voice_bot.cli list-scenarios
```

Equivalent `make` commands:

```bash
make serve
make call SCENARIO=appointment_basic
make suite
make fetch
make analyze
make full
```

## End-to-End Flow

1. Start the local FastAPI server.
2. Expose it publicly with `ngrok http 8000`.
3. Confirm `.env` contains the current ngrok HTTPS URL in `PUBLIC_BASE_URL`.
4. Place one validation call and confirm a transcript appears in `artifacts/transcripts/`.
5. Run the full suite.
6. Download Twilio recordings.
7. Generate the final markdown bug report.

## Important Safety Guardrail

The code enforces `TARGET_NUMBER=+18054398008`. If any command tries to call a different number, it raises an error before contacting Twilio.

## Environment Variables

- `TWILIO_ACCOUNT_SID`: Twilio account SID.
- `TWILIO_AUTH_TOKEN`: Twilio auth token.
- `TWILIO_FROM_NUMBER`: single Twilio caller number to use for all calls, in E.164 format.
- `PUBLIC_BASE_URL`: public HTTPS URL for Twilio webhooks.
- `OPENAI_API_KEY`: OpenAI API key.
- `OPENAI_REALTIME_MODEL`: realtime voice model.
- `OPENAI_TRANSCRIBE_MODEL`: audio transcription model for Realtime input transcription.
- `TARGET_NUMBER`: must remain `+18054398008`.
- `CALL_TIMEOUT_SECONDS`: max call length.
- `ARTIFACTS_DIR`: output directory.

## Troubleshooting

- If `pgai-bot` tries to run a different local project, use `python3 -m pgai_voice_bot.cli ...` instead.
- If calls are created but no transcript files appear, check that the FastAPI server is running from this repository and that ngrok points to the same port.
- If you edit `scenarios.py`, restart the server before placing another call.
- If `pgai-bot serve` says port `8000` is already in use, stop the old process or restart on a different port and update ngrok plus `PUBLIC_BASE_URL`.
- Transcript files are only created for fresh calls that successfully pass through the live `/media` websocket bridge.

## Submission Checklist

- Public GitHub repository link.
- Loom walkthrough link.
- Loom or screen recording showing AI-assisted debugging.
- One phone number used for all test calls: your `TWILIO_FROM_NUMBER`.
- At least 10 complete calls with transcript and audio recording.
- Final generated bug report in `artifacts/reports/bug_report.md`.
- Matching call artifacts under `artifacts/transcripts/`, `artifacts/recordings/`, and `artifacts/events/`.
