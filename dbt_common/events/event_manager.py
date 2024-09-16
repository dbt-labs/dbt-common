import os
import traceback
from typing import List, Optional, Protocol, Tuple

from dbt_common.events.base_types import BaseEvent, EventLevel, msg_from_base_event, TCallback
from dbt_common.events.functions import track, tracker_factory
from dbt_common.events.logger import LoggerConfig, _Logger, _TextLogger, _JsonLogger, LineFormat
from dbt_common.events.tracker import TrackerConfig, Tracker
from dbt_common.events.user import User


class EventManager:
    def __init__(self) -> None:
        self.loggers: List[_Logger] = []
        self.trackers: List[Tracker] = []
        self.callbacks: List[TCallback] = []
        self.user: Optional[User] = None

    def fire_event(self, e: BaseEvent, level: Optional[EventLevel] = None) -> None:
        msg = msg_from_base_event(e, level=level)

        if os.environ.get("DBT_TEST_BINARY_SERIALIZATION"):
            print(f"--- {msg.info.name}")
            try:
                msg.SerializeToString()
            except Exception as exc:
                raise Exception(
                    f"{msg.info.name} is not serializable to binary. ",
                    f"Originating exception: {exc}, {traceback.format_exc()}",
                )

        for logger in self.loggers:
            if logger.filter(msg):  # type: ignore
                logger.write_line(msg)

        for tracker in self.trackers:
            track(tracker, self.user, msg)

        for callback in self.callbacks:
            callback(msg)

    def add_logger(self, config: LoggerConfig) -> None:
        logger = (
            _JsonLogger(config) if config.line_format == LineFormat.Json else _TextLogger(config)
        )
        self.loggers.append(logger)

    def add_tracker(self, config: TrackerConfig) -> None:
        self.trackers.append(tracker_factory(config))

    def add_callback(self, callback: TCallback) -> None:
        self.callbacks.append(callback)

    def add_user(self, user: User) -> None:
        self.user = user

    def flush(self) -> None:
        for logger in self.loggers:
            logger.flush()


class IEventManager(Protocol):
    callbacks: List[TCallback]
    loggers: List[_Logger]
    trackers: List[Tracker]

    def fire_event(self, e: BaseEvent, level: Optional[EventLevel] = None) -> None:
        ...

    def add_logger(self, config: LoggerConfig) -> None:
        ...

    def add_tracker(self, config: TrackerConfig) -> None:
        ...

    def add_callback(self, callback: TCallback) -> None:
        ...


class TestEventManager(IEventManager):
    __test__ = False

    def __init__(self) -> None:
        self.event_history: List[Tuple[BaseEvent, Optional[EventLevel]]] = []
        self.loggers = []

    def fire_event(self, e: BaseEvent, level: Optional[EventLevel] = None) -> None:
        self.event_history.append((e, level))

    def add_logger(self, config: LoggerConfig) -> None:
        raise NotImplementedError()
