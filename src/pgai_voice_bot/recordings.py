from __future__ import annotations

import httpx

from .artifacts import call_slug, recording_path, scenario_for_call
from .calls import twilio_client
from .config import settings


def fetch_recordings() -> list[str]:
    settings.require_twilio()
    client = twilio_client()
    saved: list[str] = []

    for recording in client.recordings.list(limit=100):
        call_sid = recording.call_sid
        if not call_sid:
            continue
        scenario_id = scenario_for_call(call_sid)
        slug = call_slug(call_sid, scenario_id) if scenario_id else call_sid
        target = recording_path(slug, "mp3")
        url = f"https://api.twilio.com{recording.uri.replace('.json', '.mp3')}"
        response = httpx.get(
            url,
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            timeout=60,
        )
        response.raise_for_status()
        target.write_bytes(response.content)
        saved.append(str(target))

    return saved
