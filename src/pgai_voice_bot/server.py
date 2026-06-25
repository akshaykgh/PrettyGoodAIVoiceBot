from __future__ import annotations

import asyncio
import inspect
import json
import ssl
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import certifi
import websockets
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse, Response
from twilio.twiml.voice_response import Connect, VoiceResponse

from .artifacts import TranscriptWriter, append_jsonl, call_slug, events_path, utc_stamp
from .config import settings
from .scenarios import get_scenario


app = FastAPI(title="PGAI Voice Bot")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.api_route("/voice", methods=["GET", "POST"])
async def voice(request: Request) -> Response:
    params = dict(request.query_params)
    form = {}
    if request.method == "POST":
        form = dict(await request.form())

    scenario_id = params.get("scenario_id") or form.get("scenario_id") or "appointment_basic"
    scenario = get_scenario(scenario_id)
    call_sid = form.get("CallSid") or params.get("CallSid") or "pending"

    query = urlencode({"scenario_id": scenario.id, "call_sid": call_sid})
    stream_url = f"{settings.websocket_base_url}/media?{query}"

    response = VoiceResponse()
    connect = Connect()
    stream = connect.stream(url=stream_url)
    stream.parameter(name="scenario_id", value=scenario.id)
    stream.parameter(name="call_sid", value=call_sid)
    response.append(connect)
    return Response(content=str(response), media_type="application/xml")


@app.post("/recording-status")
async def recording_status(request: Request) -> PlainTextResponse:
    form = dict(await request.form())
    scenario_id = request.query_params.get("scenario_id", "unknown")
    call_sid = form.get("CallSid", "unknown")
    slug = call_slug(call_sid, scenario_id)
    append_jsonl(
        events_path(slug),
        {
            "ts": utc_stamp(),
            "source": "twilio_recording_status",
            "event": form,
        },
    )
    return PlainTextResponse("ok")


@app.websocket("/media")
async def media(websocket: WebSocket) -> None:
    await websocket.accept()

    parsed = urlparse(str(websocket.url))
    query = parse_qs(parsed.query)
    fallback_scenario_id = query.get("scenario_id", ["appointment_basic"])[0]
    fallback_call_sid = query.get("call_sid", ["pending"])[0]

    start_event = await wait_for_twilio_start(websocket, fallback_scenario_id, fallback_call_sid)
    start_payload = start_event.get("start", {})
    custom_parameters = start_payload.get("customParameters", {})
    scenario_id = custom_parameters.get("scenario_id") or fallback_scenario_id
    call_sid = custom_parameters.get("call_sid") or start_payload.get("callSid") or fallback_call_sid
    stream_sid = start_payload.get("streamSid")

    scenario = get_scenario(scenario_id)
    slug = call_slug(call_sid, scenario_id)
    event_log = events_path(slug)
    transcript = TranscriptWriter(slug, scenario_id)

    settings.require_openai()
    openai_url = f"wss://api.openai.com/v1/realtime?model={settings.openai_realtime_model}"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "OpenAI-Safety-Identifier": "pgai-challenge-patient-bot",
    }

    append_jsonl(event_log, {"ts": utc_stamp(), "source": "system", "event": "media_connected"})
    append_jsonl(event_log, {"ts": utc_stamp(), "source": "twilio", "event": start_event})

    connect_kwargs = {"max_size": 8 * 1024 * 1024}
    connect_kwargs["ssl"] = ssl.create_default_context(cafile=certifi.where())
    headers_arg = (
        "additional_headers"
        if "additional_headers" in inspect.signature(websockets.connect).parameters
        else "extra_headers"
    )
    connect_kwargs[headers_arg] = headers

    async with websockets.connect(openai_url, **connect_kwargs) as openai_ws:
        await configure_realtime(openai_ws, scenario.instructions())
        stream_sid_holder: dict[str, str] = {"sid": stream_sid} if stream_sid else {}

        async def twilio_to_openai() -> None:
            try:
                while True:
                    message = await websocket.receive_text()
                    data = json.loads(message)
                    append_jsonl(event_log, {"ts": utc_stamp(), "source": "twilio", "event": data})

                    event = data.get("event")
                    if event == "start":
                        stream_sid_holder["sid"] = data["start"]["streamSid"]
                    elif event == "media":
                        await openai_ws.send(
                            json.dumps(
                                {
                                    "type": "input_audio_buffer.append",
                                    "audio": data["media"]["payload"],
                                }
                            )
                        )
                    elif event == "stop":
                        await openai_ws.close()
                        break
            except WebSocketDisconnect:
                await openai_ws.close()

        async def openai_to_twilio() -> None:
            async for raw in openai_ws:
                event = json.loads(raw)
                append_jsonl(event_log, {"ts": utc_stamp(), "source": "openai", "event": event})
                event_type = event.get("type")

                if event_type in {"response.audio.delta", "response.output_audio.delta"}:
                    stream_sid = stream_sid_holder.get("sid")
                    delta = event.get("delta")
                    if stream_sid and delta:
                        await websocket.send_json(
                            {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": delta},
                            }
                        )

                elif event_type in {
                    "conversation.item.input_audio_transcription.completed",
                    "conversation.item.input_audio_transcript.completed",
                    "input_audio_buffer.transcription_completed",
                }:
                    text = event.get("transcript") or event.get("text") or ""
                    transcript.add_turn("Agent", text)

                elif event_type in {"response.audio_transcript.done", "response.output_audio_transcript.done"}:
                    text = event.get("transcript", "")
                    transcript.add_turn("Patient", text)

                elif event_type == "error":
                    transcript.add_turn("System", f"Realtime error: {event}")

        await asyncio.gather(twilio_to_openai(), openai_to_twilio())


async def wait_for_twilio_start(
    websocket: WebSocket, fallback_scenario_id: str, fallback_call_sid: str
) -> dict[str, Any]:
    provisional_log = events_path(call_slug(fallback_call_sid, fallback_scenario_id))
    while True:
        message = await websocket.receive_text()
        event = json.loads(message)
        append_jsonl(provisional_log, {"ts": utc_stamp(), "source": "twilio", "event": event})
        if event.get("event") == "start":
            return event


async def configure_realtime(openai_ws: object, instructions: str) -> None:
    await openai_ws.send(
        json.dumps(
            {
                "type": "session.update",
                "session": {
                    "type": "realtime",
                    "model": settings.openai_realtime_model,
                    "output_modalities": ["audio"],
                    "instructions": instructions,
                    "audio": {
                        "input": {
                            "format": {"type": "audio/pcmu"},
                            "turn_detection": {"type": "semantic_vad"},
                            "transcription": {"model": settings.openai_transcribe_model},
                        },
                        "output": {
                            "format": {"type": "audio/pcmu"},
                            "voice": "marin",
                        },
                    },
                },
            }
        )
    )
