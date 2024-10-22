from dataclasses import dataclass
import logging
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional, Protocol, Self

import snowplow_tracker
from snowplow_tracker.typing import FailureCallback

from dbt_common.events.base_types import EventMsg, msg_to_dict
from dbt_common.events.format import timestamp_to_datetime_string


@dataclass
class TrackerConfig:
    invocation_id: Optional[str] = None
    msg_schemas: Optional[Dict[str, str]] = None
    endpoint: Optional[str] = None
    protocol: Optional[str] = "https"
    on_failure: Optional[FailureCallback] = None
    name: Optional[str] = None
    output_file_name: Optional[str] = None
    output_file_max_bytes: Optional[int] = 10 * 1024 * 1024  # 10 mb


class Tracker(Protocol):
    @classmethod
    def from_config(cls, config: TrackerConfig) -> Self:
        ...

    def track(self, msg: EventMsg) -> None:
        ...

    def enable_tracking(self, cookie: Dict[str, Any]) -> None:
        ...

    def disable_tracking(self) -> None:
        ...


class FileTracker(Tracker):
    def __init__(self, logger: logging.Logger, invocation_id: Optional[str]) -> None:
        self.logger = logger
        self.invocation_id = invocation_id

    @classmethod
    def from_config(cls, config: TrackerConfig) -> Self:
        file_handler = RotatingFileHandler(
            filename=config.output_file_name,
            maxBytes=config.output_file_max_bytes,  # type: ignore
            backupCount=5,
            encoding="utf8",
        )
        file_handler.setFormatter(logging.Formatter(fmt="%(message)s"))

        logger = logging.getLogger(config.name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        logger.propagate = False
        logger.addHandler(file_handler)
        return cls(logger, config.invocation_id)

    def track(self, msg: EventMsg) -> None:
        ts: str = timestamp_to_datetime_string(msg.info.ts)
        log_line = f"{ts} | {msg.info.msg}"
        self.logger.debug(log_line)

    def enable_tracking(self, cookie: Dict[str, Any]) -> None:
        pass

    def disable_tracking(self) -> None:
        pass


class SnowplowTracker(Tracker):
    def __init__(
        self,
        tracker: snowplow_tracker.Tracker,
        msg_schemas: Dict[str, str],
        invocation_id: Optional[str],
    ) -> None:
        self.tracker = tracker
        self.msg_schemas = msg_schemas
        self.invocation_id = invocation_id

    @classmethod
    def from_config(cls, config: TrackerConfig) -> Self:
        emitter = snowplow_tracker.Emitter(
            config.endpoint,
            config.protocol,
            method="post",
            batch_size=30,
            on_failure=config.on_failure,
            byte_limit=None,
            request_timeout=5.0,
        )
        tracker = snowplow_tracker.Tracker(
            emitters=emitter,
            namespace="cf",
            app_id="dbt",
        )
        return cls(tracker, config.msg_schemas, config.invocation_id)

    def track(self, msg: EventMsg) -> None:
        data = msg_to_dict(msg)
        schema = self.msg_schemas.get(msg.info.name)
        context = [snowplow_tracker.SelfDescribingJson(schema, data)]
        event = snowplow_tracker.StructuredEvent(
            category="dbt",
            action=msg.info.name,
            label=self.invocation_id,
            context=context,
        )
        self.tracker.track(event)

    def enable_tracking(self, cookie: Dict[str, Any]) -> None:
        subject = snowplow_tracker.Subject()
        subject.set_user_id(cookie.get("id"))
        self.tracker.set_subject(subject)

    def disable_tracking(self) -> None:
        self.tracker.set_subject(None)
