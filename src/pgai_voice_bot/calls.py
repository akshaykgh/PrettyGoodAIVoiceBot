from __future__ import annotations

import time
from urllib.parse import urlencode

from twilio.rest import Client

from .artifacts import append_jsonl, call_index_path, call_slug, events_path, utc_stamp
from .config import settings
from .scenarios import DEFAULT_SUITE, get_scenario


def _assert_target_number(to_number: str) -> None:
    normalized = to_number.replace("-", "").replace(" ", "")
    if normalized != settings.normalized_target_number:
        raise ValueError(
            f"Refusing to call {to_number}. This challenge runner is locked to {settings.target_number}."
        )


def twilio_client() -> Client:
    settings.require_twilio()
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def place_call(scenario_id: str, to_number: str | None = None) -> str:
    scenario = get_scenario(scenario_id)
    destination = to_number or settings.target_number
    _assert_target_number(destination)

    query = urlencode({"scenario_id": scenario.id})
    voice_url = f"{settings.base_url}/voice?{query}"
    recording_status_url = f"{settings.base_url}/recording-status?{query}"

    call = twilio_client().calls.create(
        to=destination,
        from_=settings.twilio_from_number,
        url=voice_url,
        method="POST",
        record=True,
        recording_channels="dual",
        recording_status_callback=recording_status_url,
        recording_status_callback_method="POST",
        timeout=30,
        time_limit=settings.call_timeout_seconds,
    )

    slug = call_slug(call.sid, scenario.id)
    append_jsonl(
        events_path(slug),
        {
            "ts": utc_stamp(),
            "source": "runner",
            "event": "call_created",
            "call_sid": call.sid,
            "scenario_id": scenario.id,
            "to": destination,
            "from": settings.twilio_from_number,
        },
    )
    append_jsonl(
        call_index_path(),
        {
            "ts": utc_stamp(),
            "call_sid": call.sid,
            "scenario_id": scenario.id,
            "to": destination,
            "from": settings.twilio_from_number,
        },
    )
    return call.sid


TERMINAL_CALL_STATES = {"completed", "failed", "busy", "no-answer", "canceled"}


def wait_for_call_completion(call_sid: str, poll_seconds: int = 5) -> str:
    client = twilio_client()
    while True:
        call = client.calls(call_sid).fetch()
        status = str(call.status)
        if status in TERMINAL_CALL_STATES:
            return status
        time.sleep(poll_seconds)


def run_suite(wait: bool = True) -> list[tuple[str, str, str | None]]:
    results = []
    for scenario_id in DEFAULT_SUITE:
        call_sid = place_call(scenario_id)
        status = wait_for_call_completion(call_sid) if wait else None
        results.append((scenario_id, call_sid, status))
    return results
