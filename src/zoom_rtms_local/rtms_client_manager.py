from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import rtms

from .audio_writer import MeetingAudioRecorder
from .store import InMemoryStateStore

logger = logging.getLogger(__name__)


@dataclass
class RtmsSessionRuntime:
    meeting_uuid: str
    stream_id: str
    server_urls: str
    client: rtms.Client
    recorder: MeetingAudioRecorder
    stop_event: threading.Event
    poll_thread: threading.Thread


class RtmsClientManager:
    def __init__(
        self,
        store: InMemoryStateStore,
        recordings_root: Path,
        sample_rate: int,
        channels: int,
        sample_width_bytes: int,
        zoom_client_id: str,
        zoom_client_secret: str,
    ) -> None:
        self._store = store
        self._recordings_root = recordings_root
        self._sample_rate = sample_rate
        self._channels = channels
        self._sample_width_bytes = sample_width_bytes
        self._zoom_client_id = zoom_client_id
        self._zoom_client_secret = zoom_client_secret
        self._sessions: dict[str, RtmsSessionRuntime] = {}
        self._lock = threading.Lock()

    def handle_rtms_started(self, meeting_uuid: str, stream_id: str, server_urls: str) -> None:
        with self._lock:
            if meeting_uuid in self._sessions:
                logger.warning("rtms session already active", extra={"meeting_uuid": meeting_uuid, "stream_id": stream_id})
                return

            client = rtms.Client()
            recorder = MeetingAudioRecorder(
                meeting_uuid=meeting_uuid,
                recordings_root=self._recordings_root,
                sample_rate=self._sample_rate,
                channels=self._channels,
                sample_width_bytes=self._sample_width_bytes,
            )
            stop_event = threading.Event()

            self._register_handlers(client, meeting_uuid, recorder)

            poll_thread = threading.Thread(
                target=self._poll_loop,
                args=(client, stop_event),
                name=f"rtms-poller-{meeting_uuid[:8]}",
                daemon=True,
            )
            runtime = RtmsSessionRuntime(
                meeting_uuid=meeting_uuid,
                stream_id=stream_id,
                server_urls=server_urls,
                client=client,
                recorder=recorder,
                stop_event=stop_event,
                poll_thread=poll_thread,
            )
            self._sessions[meeting_uuid] = runtime

        logger.info("joining rtms stream", extra={"meeting_uuid": meeting_uuid, "stream_id": stream_id})
        client.join(
            meeting_uuid=meeting_uuid,
            rtms_stream_id=stream_id,
            server_urls=server_urls,
            client=self._zoom_client_id,
            secret=self._zoom_client_secret,
        )
        poll_thread.start()

    def handle_rtms_stopped(self, meeting_uuid: str) -> None:
        runtime = self._sessions.pop(meeting_uuid, None)
        if not runtime:
            return
        logger.info("stopping rtms session", extra={"meeting_uuid": meeting_uuid, "stream_id": runtime.stream_id})
        runtime.stop_event.set()
        try:
            runtime.client.leave()
        except Exception:
            logger.exception("error while leaving rtms", extra={"meeting_uuid": meeting_uuid})
        runtime.poll_thread.join(timeout=2)
        runtime.recorder.close()

    def _register_handlers(self, client: rtms.Client, meeting_uuid: str, recorder: MeetingAudioRecorder) -> None:
        @client.onJoinConfirm
        def _on_join(reason: Any) -> None:
            logger.info("rtms join confirmed", extra={"meeting_uuid": meeting_uuid, "event": str(reason)})

        @client.onLeave
        def _on_leave(reason: Any) -> None:
            logger.info("rtms leave", extra={"meeting_uuid": meeting_uuid, "event": str(reason)})

        @client.onParticipantEvent
        def _on_participant(event: str, _timestamp: int, participants: list[dict[str, Any]]) -> None:
            joined = event.lower() in {"join", "joined", "participant_join", "participant_joined"}
            for participant in participants:
                user_id = str(participant.get("user_id") or participant.get("userId") or "unknown")
                user_name = str(participant.get("user_name") or participant.get("userName") or "unknown")
                self._store.mark_participant_event(meeting_uuid, user_id, user_name, joined=joined)
                logger.info(
                    "participant event",
                    extra={"meeting_uuid": meeting_uuid, "participant_id": user_id, "event": event},
                )

        @client.onActiveSpeakerEvent
        def _on_active_speaker(_timestamp: int, user_id: str, user_name: str) -> None:
            self._store.mark_active_speaker(meeting_uuid, str(user_id))
            logger.info(
                "active speaker",
                extra={"meeting_uuid": meeting_uuid, "participant_id": str(user_id), "event": user_name},
            )

        @client.onAudioData
        def _on_audio(data: bytes, size: int, timestamp: int, metadata: Any) -> None:
            user_id = str(getattr(metadata, "userId", "mixed"))
            user_name = str(getattr(metadata, "userName", "mixed"))
            if not user_id or user_id == "None":
                user_id = "mixed"
            if not user_name or user_name == "None":
                user_name = "mixed"
            recorder.write(user_id, user_name, data[:size])
            self._store.mark_audio(meeting_uuid, user_id, timestamp)

    @staticmethod
    def _poll_loop(client: rtms.Client, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            client._poll_if_needed()
            time.sleep(0.01)
