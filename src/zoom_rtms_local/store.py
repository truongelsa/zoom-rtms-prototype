from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any


@dataclass
class ParticipantState:
    user_id: str
    user_name: str
    joined_at: datetime | None = None
    left_at: datetime | None = None
    is_present: bool = False
    last_audio_ts: int | None = None


@dataclass
class MeetingState:
    meeting_uuid: str
    rtms_stream_id: str | None = None
    signaling_server_url: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active_speaker_user_id: str | None = None
    participants: dict[str, ParticipantState] = field(default_factory=dict)


class InMemoryStateStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._meetings: dict[str, MeetingState] = {}

    def get_or_create_meeting(self, meeting_uuid: str) -> MeetingState:
        with self._lock:
            state = self._meetings.get(meeting_uuid)
            if state is None:
                state = MeetingState(meeting_uuid=meeting_uuid)
                self._meetings[meeting_uuid] = state
            return state

    def update_meeting_rtms(self, meeting_uuid: str, rtms_stream_id: str, server_url: str | None) -> MeetingState:
        with self._lock:
            state = self.get_or_create_meeting(meeting_uuid)
            state.rtms_stream_id = rtms_stream_id
            state.signaling_server_url = server_url
            return state

    def mark_participant_event(self, meeting_uuid: str, user_id: str, user_name: str, joined: bool) -> ParticipantState:
        with self._lock:
            meeting = self.get_or_create_meeting(meeting_uuid)
            participant = meeting.participants.get(user_id)
            if participant is None:
                participant = ParticipantState(user_id=user_id, user_name=user_name)
                meeting.participants[user_id] = participant
            participant.user_name = user_name or participant.user_name
            now = datetime.now(timezone.utc)
            if joined:
                participant.is_present = True
                participant.joined_at = participant.joined_at or now
            else:
                participant.is_present = False
                participant.left_at = now
            return participant

    def mark_active_speaker(self, meeting_uuid: str, user_id: str) -> None:
        with self._lock:
            meeting = self.get_or_create_meeting(meeting_uuid)
            meeting.active_speaker_user_id = user_id

    def mark_audio(self, meeting_uuid: str, user_id: str, ts: int) -> None:
        with self._lock:
            meeting = self.get_or_create_meeting(meeting_uuid)
            participant = meeting.participants.get(user_id)
            if participant:
                participant.last_audio_ts = ts

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "meetings": {
                    meeting_uuid: {
                        "meeting_uuid": m.meeting_uuid,
                        "rtms_stream_id": m.rtms_stream_id,
                        "signaling_server_url": m.signaling_server_url,
                        "started_at": m.started_at.isoformat(),
                        "active_speaker_user_id": m.active_speaker_user_id,
                        "participants": {
                            pid: {
                                "user_id": p.user_id,
                                "user_name": p.user_name,
                                "joined_at": p.joined_at.isoformat() if p.joined_at else None,
                                "left_at": p.left_at.isoformat() if p.left_at else None,
                                "is_present": p.is_present,
                                "last_audio_ts": p.last_audio_ts,
                            }
                            for pid, p in m.participants.items()
                        },
                    }
                    for meeting_uuid, m in self._meetings.items()
                }
            }
