import uuid
from datetime import datetime

_INVOCATION_ID = str(uuid.uuid4())
_INVOCATION_STARTED_AT = datetime.utcnow()


def get_invocation_id() -> str:
    return _INVOCATION_ID


def get_invocation_started_at() -> datetime:
    return _INVOCATION_STARTED_AT


def reset_invocation_id() -> None:
    global _INVOCATION_ID, _INVOCATION_STARTED_AT
    _INVOCATION_ID = str(uuid.uuid4())
    _INVOCATION_STARTED_AT = datetime.utcnow()
