from __future__ import annotations

import argparse
import sys

from twilio.base.exceptions import TwilioRestException
import uvicorn

from .analyze import analyze_transcripts
from .calls import place_call, run_suite
from .config import settings
from .recordings import fetch_recordings
from .scenarios import SCENARIOS


def main() -> None:
    parser = argparse.ArgumentParser(description="Pretty Good AI voice bot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve", help="Run the webhook/media server")
    serve_parser.add_argument("--host", default=settings.server_host)
    serve_parser.add_argument("--port", type=int, default=settings.server_port)

    call_parser = subparsers.add_parser("call", help="Place one scenario call")
    call_parser.add_argument("--scenario", required=True, choices=sorted(SCENARIOS))

    suite_parser = subparsers.add_parser("run-suite", help="Place one call for each built-in scenario")
    suite_parser.add_argument("--no-wait", action="store_true", help="Start all calls without waiting")
    subparsers.add_parser("fetch-recordings", help="Download Twilio recordings as MP3 files")
    subparsers.add_parser("analyze", help="Generate a markdown bug report from transcripts")
    subparsers.add_parser("list-scenarios", help="List available scenarios")

    args = parser.parse_args()

    try:
        if args.command == "serve":
            uvicorn.run("pgai_voice_bot.server:app", host=args.host, port=args.port)
        elif args.command == "call":
            call_sid = place_call(args.scenario)
            print(f"Created call {call_sid} for scenario {args.scenario}")
        elif args.command == "run-suite":
            for scenario_id, call_sid, status in run_suite(wait=not args.no_wait):
                suffix = f" ({status})" if status else ""
                print(f"{scenario_id}: {call_sid}{suffix}")
        elif args.command == "fetch-recordings":
            for path in fetch_recordings():
                print(path)
        elif args.command == "analyze":
            print(analyze_transcripts())
        elif args.command == "list-scenarios":
            for scenario_id, scenario in SCENARIOS.items():
                print(f"{scenario_id}: {scenario.title}")
    except TwilioRestException as exc:
        print(f"Twilio error {exc.code}: {exc.msg}", file=sys.stderr)
        if exc.code == 21219:
            print(
                "Your Twilio account is in trial mode. Trial accounts can only call verified recipient "
                "numbers, so Twilio will block the challenge number. Upgrade the Twilio account, then "
                "rerun the same pgai-bot command.",
                file=sys.stderr,
            )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
