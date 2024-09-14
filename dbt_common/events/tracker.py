from dataclasses import dataclass
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

from snowplow_tracker import Emitter, Tracker
from snowplow_tracker.typing import FailureCallback

from dbt_common.events.base_types import EventMsg


@dataclass
class TrackerConfig:
    invocation_id: Optional[str] = None
    endpoint: Optional[str] = None
    protocol: Optional[str] = None
    on_failure: Optional[FailureCallback] = None
    name: Optional[str] = None
    output_file_name: Optional[str] = None
    output_file_max_bytes: Optional[int] = 10 * 1024 * 1024  # 10 mb


class _Tracker:
    def __init__(self, config: TrackerConfig) -> None:
        self.invocation_id: Optional[str] = config.invocation_id

        if all([config.name, config.output_file_name]):
            file_handler = RotatingFileHandler(
                filename=str(config.output_file_name),
                encoding="utf8",
                maxBytes=config.output_file_max_bytes,  # type: ignore
                backupCount=5,
            )
            self._tracker = self._python_file_logger(config.name, file_handler)

        elif all([config.endpoint, config.protocol]):
            self._tracker = self._snowplow_tracker(config.endpoint, config.protocol)

    def track(self, msg: EventMsg) -> str:
        raise NotImplementedError()

    def _python_file_logger(self, name: str, handler: logging.Handler) -> logging.Logger:
        log = logging.getLogger(name)
        log.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(fmt="%(message)s"))
        log.handlers.clear()
        log.propagate = False
        log.addHandler(handler)
        return log

    def _snowplow_tracker(
        self,
        endpoint: str,
        protocol: Optional[str] = "https",
        on_failure: Optional[FailureCallback] = None,
    ) -> Tracker:
        emitter = Emitter(
            endpoint,
            protocol,
            method="post",
            batch_size=30,
            on_failure=on_failure,
            byte_limit=None,
            request_timeout=5.0,
        )
        tracker = Tracker(
            emitters=emitter,
            namespace="cf",
            app_id="dbt",
        )
        return tracker
