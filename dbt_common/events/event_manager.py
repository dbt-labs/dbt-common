import os
import traceback
from typing import Any, List, Optional, Protocol, Tuple

from dbt_common.events.base_types import BaseEvent, EventLevel, msg_from_base_event, TCallback
from dbt_common.events.logger import LoggerConfig, _Logger, _TextLogger, _JsonLogger, LineFormat
from dbt_common.exceptions.events import EventCompilationError
from dbt_common.helper_types import WarnErrorOptions


class EventManager:
    def __init__(self) -> None:
        self.loggers: List[_Logger] = []
        self.callbacks: List[TCallback] = []
        self.warn_error: bool = False
        self.warn_error_options: WarnErrorOptions = WarnErrorOptions(include=[], exclude=[])

    def fire_event(
        self,
        e: BaseEvent,
        level: Optional[EventLevel] = None,
        node: Any = None,
        force_warn_or_error_handling: bool = False,
    ) -> None:
        msg = msg_from_base_event(e, level=level)

        if force_warn_or_error_handling and msg.info.level == "warn":
            event_name = type(e).__name__
            if self.warn_error or self.warn_error_options.includes(event_name):
                # This has the potential to create an infinite loop if the handling of the raised
                # EventCompilationError fires an event as a warning instead of an error.
                raise EventCompilationError(e.message(), node)
            elif self.warn_error_options.silenced(event_name):
                # Return early if the event is silenced
                return

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

        for callback in self.callbacks:
            callback(msg)

    def add_logger(self, config: LoggerConfig) -> None:
        logger = (
            _JsonLogger(config) if config.line_format == LineFormat.Json else _TextLogger(config)
        )
        self.loggers.append(logger)

    def add_callback(self, callback: TCallback) -> None:
        self.callbacks.append(callback)

    def flush(self) -> None:
        for logger in self.loggers:
            logger.flush()


class IEventManager(Protocol):
    callbacks: List[TCallback]
    loggers: List[_Logger]
    warn_error: bool
    warn_error_options: WarnErrorOptions

    def fire_event(
        self,
        e: BaseEvent,
        level: Optional[EventLevel] = None,
        node: Any = None,
        force_warn_or_error_handling: bool = False,
    ) -> None:
        ...

    def add_logger(self, config: LoggerConfig) -> None:
        ...

    def add_callback(self, callback: TCallback) -> None:
        ...


class TestEventManager(IEventManager):
    __test__ = False

    def __init__(self) -> None:
        self.event_history: List[Tuple[BaseEvent, Optional[EventLevel]]] = []
        self.loggers = []

    def fire_event(
        self, e: BaseEvent, level: Optional[EventLevel] = None, node: Any = None
    ) -> None:
        self.event_history.append((e, level))

    def add_logger(self, config: LoggerConfig) -> None:
        raise NotImplementedError()
