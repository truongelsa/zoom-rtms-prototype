from __future__ import annotations

import logging
import re
import wave
from pathlib import Path

logger = logging.getLogger(__name__)


class WavSink:
    def __init__(self, path: Path, sample_rate: int, channels: int, sample_width_bytes: int) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._wf = wave.open(str(self.path), "wb")
        self._wf.setnchannels(channels)
        self._wf.setsampwidth(sample_width_bytes)
        self._wf.setframerate(sample_rate)

    def write(self, data: bytes) -> None:
        self._wf.writeframesraw(data)

    def close(self) -> None:
        self._wf.close()


class MeetingAudioRecorder:
    def __init__(self, meeting_uuid: str, recordings_root: Path, sample_rate: int, channels: int, sample_width_bytes: int) -> None:
        self.meeting_uuid = meeting_uuid
        self.meeting_dir = recordings_root / meeting_uuid
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width_bytes = sample_width_bytes
        self._sinks: dict[str, WavSink] = {}

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("_") or "unknown"

    def write(self, participant_id: str, participant_name: str, data: bytes) -> Path:
        safe_name = self._safe_name(participant_name)
        key = f"{participant_id}_{safe_name}"
        sink = self._sinks.get(key)
        if sink is None:
            path = self.meeting_dir / f"{key}.wav"
            sink = WavSink(path, self.sample_rate, self.channels, self.sample_width_bytes)
            self._sinks[key] = sink
            logger.info("opened audio file", extra={"meeting_uuid": self.meeting_uuid, "participant_id": participant_id, "path": str(path)})
        sink.write(data)
        return sink.path

    def close(self) -> None:
        for sink in self._sinks.values():
            sink.close()
        self._sinks.clear()
