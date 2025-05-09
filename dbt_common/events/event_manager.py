import os
import traceback
from typing import Any, List, Optional, Protocol, Tuple, Union

from dbt_common.events.base_types import BaseEvent, EventLevel, msg_from_base_event, TCallback
from dbt_common.events.logger import LoggerConfig, _Logger, _TextLogger, _JsonLogger, LineFormat
from dbt_common.exceptions.events import EventCompilationError
from dbt_common.helper_types import WarnErrorOptions, WarnErrorOptionsV2


class EventManager:
    def __init__(self) -> None:
        self.loggers: List[_Logger] = []
        self.callbacks: List[TCallback] = []
        self._warn_error: Optional[bool] = None
        self._warn_error_options: Optional[Union[WarnErrorOptions, WarnErrorOptionsV2]] = None
        self.require_warn_or_error_handling: bool = False

    @property
    def warn_error(self) -> bool:
        if self._warn_error is None:
            from dbt_common.events.functions import WARN_ERROR

            return WARN_ERROR
        return self._warn_error

    @warn_error.setter
    def warn_error(self, warn_error: bool) -> None:
        self._warn_error = warn_error

    @property
    def warn_error_options(self) -> Union[WarnErrorOptions, WarnErrorOptionsV2]:
        # Technically this always returns a WarnErrorOptionsV2, but to remain backwards compatible
        # with the protocol, we need to type the function as being able to return either.

        if self._warn_error_options is None:
            from dbt_common.events.functions import WARN_ERROR_OPTIONS

            return WARN_ERROR_OPTIONS._warn_error_options_v2

        return self._warn_error_options._warn_error_options_v2

    @warn_error_options.setter
    def warn_error_options(
        self, warn_error_options: Union[WarnErrorOptions, WarnErrorOptionsV2]
    ) -> None:
        self._warn_error_options = warn_error_options

    def fire_event(
        self,
        e: BaseEvent,
        level: Optional[EventLevel] = None,
        node: Any = None,
        force_warn_or_error_handling: bool = False,
    ) -> None:
        msg = msg_from_base_event(e, level=level)

        if force_warn_or_error_handling or (
            self.require_warn_or_error_handling and msg.info.level == "warn"
        ):
            if self.warn_error or self.warn_error_options.errors(e):
                # This has the potential to create an infinite loop if the handling of the raised
                # EventCompilationError fires an event as a warning instead of an error.
                raise EventCompilationError(e.message(), node)
            elif self.warn_error_options.silenced(e):
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
    warn_error_options: Union[WarnErrorOptions, WarnErrorOptionsV2]
    require_warn_or_error_handling: bool

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
        self.warn_error = False
        self.warn_error_options = WarnErrorOptions(include=[], exclude=[])
        self.require_warn_or_error_handling = False

    def fire_event(
        self,
        e: BaseEvent,
        level: Optional[EventLevel] = None,
        node: Any = None,
        force_warn_or_error_handling: bool = False,
    ) -> None:
        self.event_history.append((e, level))

    def add_logger(self, config: LoggerConfig) -> None:
        raise NotImplementedError()
