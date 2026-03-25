from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


def compute_zoom_signature(secret_token: str, timestamp: str, body: dict[str, Any]) -> str:
    message = f"v0:{timestamp}:{json.dumps(body, separators=(',', ':'), ensure_ascii=False)}"
    digest = hmac.new(secret_token.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"v0={digest}"


def compute_plain_token_hmac(secret_token: str, plain_token: str) -> str:
    return hmac.new(secret_token.encode("utf-8"), plain_token.encode("utf-8"), hashlib.sha256).hexdigest()
