# never name this package "types", or mypy will crash in ugly ways

# necessary for annotating constructors
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple, AbstractSet, Union
from typing import Callable, cast, Generic, Optional, TypeVar, List, NewType, Set

from dbt_common.dataclass_schema import (
    dbtClassMixin,
    ValidationError,
    StrEnum,
)
from dbt_common.events.base_types import BaseEvent

Port = NewType("Port", int)


class NVEnum(StrEnum):
    novalue = "novalue"

    def __eq__(self, other) -> bool:
        return isinstance(other, NVEnum)


@dataclass
class NoValue(dbtClassMixin):
    """Sometimes, you want a way to say none that isn't None!"""

    novalue: NVEnum = field(default_factory=lambda: NVEnum.novalue)


@dataclass
class IncludeExclude(dbtClassMixin):
    INCLUDE_ALL = ("all", "*")

    include: Union[str, List[str]]
    exclude: List[str] = field(default_factory=list)

    def __post_init__(self):
        if isinstance(self.include, str) and self.include not in self.INCLUDE_ALL:
            raise ValidationError(
                f"include must be one of {self.INCLUDE_ALL} or a list of strings"
            )

        if self.exclude and self.include not in self.INCLUDE_ALL:
            raise ValidationError(
                f"exclude can only be specified if include is one of {self.INCLUDE_ALL}"
            )

        if isinstance(self.include, list):
            self._validate_items(self.include)

        if isinstance(self.exclude, list):
            self._validate_items(self.exclude)

    def includes(self, item_name: str) -> bool:
        return (
            item_name in self.include or self.include in self.INCLUDE_ALL
        ) and item_name not in self.exclude

    def _validate_items(self, items: List[str]) -> None:
        pass


class WarnErrorOptions(IncludeExclude):
    """Deprecated, use WarnErrorOptionsV2 instead."""

    DEPRECATIONS = "Deprecations"

    def __init__(
        self,
        include: Union[str, List[str]],
        exclude: Optional[List[str]] = None,
        valid_error_names: Optional[Set[str]] = None,
        silence: Optional[List[str]] = None,
    ):
        self.silence = silence or []
        self._valid_error_names: Set[str] = valid_error_names or set()
        self._valid_error_names.add(self.DEPRECATIONS)
        super().__init__(include=include, exclude=(exclude or []))

        self._warn_error_options_v2 = WarnErrorOptionsV2(
            error=self.include,
            warn=self.exclude,
            silence=self.silence,
            valid_error_names=self._valid_error_names,
        )

    def __post_init__(self):
        # We don't want IncludeExclude's post_init to run, so we override it.
        # We are fine with just having the WarnErrorOptionsV2's post_init run on instantiation.
        pass

    def includes(self, item_name: Union[str, BaseEvent]) -> bool:
        return self._warn_error_options_v2.includes(item_name)

    def errors(self, item_name: Union[str, BaseEvent]) -> bool:
        """Exists for forward compatibility with WarnErrorOptionsV2."""
        return self._warn_error_options_v2.errors(item_name)

    def silenced(self, item_name: Union[str, BaseEvent]) -> bool:
        return self._warn_error_options_v2.silenced(item_name)


@dataclass
class WarnErrorOptionsV2(dbtClassMixin):
    """
    This class is used to configure the behavior of the warn_error feature (now part of fire_event).

    error: "all", "*", or a list of event names.
    warn: a list of event names.
    silence: a list of event names.
    valid_error_names: a set of event names that can be named in error, warn, and silence.

    In a hierarchy of configuration, the following rules apply:
    1. named > Deprecations > "all"/"*"
    2. silence > warn > error
    3. (1) > (2)
    """

    ERROR_ALL = ("all", "*")
    DEPRECATIONS = "Deprecations"

    error: Union[str, List[str]]
    warn: List[str]
    silence: List[str]

    def __init__(
        self,
        error: Optional[Union[str, List[str]]] = None,
        warn: Optional[List[str]] = None,
        silence: Optional[List[str]] = None,
        valid_error_names: Optional[Set[str]] = None,
    ):
        self._valid_error_names: Set[str] = valid_error_names or set()
        self._valid_error_names.add(self.DEPRECATIONS)

        # We can't do `= error or []` because if someone passes in an empty list, and latter appends to that list
        # they would expect references to the original list to be updated.
        self.error = error if error is not None else []
        self.warn = warn if warn is not None else []
        self.silence = silence if silence is not None else []

        # since we're overriding the dataclass auto __init__, we need to call __post_init__ manually
        self.__post_init__()

    def __post_init__(self):
        if isinstance(self.error, str) and self.error not in self.ERROR_ALL:
            raise ValidationError(f"error must be one of {self.ERROR_ALL} or a list of strings")

        # To specify `warn`, one of the following must be true
        # 1. `error` must be "all"/"*"
        # 2. "deprecations" must be in either `error` or `silence`.
        if self.warn and not (
            self.error in self.ERROR_ALL
            or self.DEPRECATIONS in self.error
            or self.DEPRECATIONS in self.silence
        ):
            raise ValidationError(
                f"`warn` can only be specified if `error` is one of {self.ERROR_ALL} or "
                f"{self.DEPRECATIONS} is in `error` or silence."
            )

        if isinstance(self.error, list):
            self._validate_items(self.error)

        if isinstance(self.warn, list):
            self._validate_items(self.warn)

        if isinstance(self.silence, list):
            self._validate_items(self.silence)

    def _validate_items(self, items: List[str]):
        for item in items:
            if item not in self._valid_error_names:
                raise ValidationError(f"{item} is not a valid dbt error name.")

    @property
    def _warn_error_options_v2(self) -> WarnErrorOptionsV2:
        # This is necessary because in core we directly set the WARN_ERROR_OPTIONS global variable
        # without this we'd need to do isinstance checks in `EventManager.warn_error_options`, which
        # would be costly as it gets called every time an event is fired.
        return self

    def _error_all(self) -> bool:
        """Is `*` or `all` set as error?"""
        return self.error in self.ERROR_ALL

    def _named_error(self, item_name: str) -> bool:
        """Is the item_name named in the error list?"""
        return item_name in self.error

    def _named_warn(self, item_name: str) -> bool:
        """Is the item_name named in the warn list?"""
        return item_name in self.warn

    def _named_silence(self, item_name: str) -> bool:
        """Is the item_name named in the silence list?"""
        return item_name in self.silence

    def _error_as_deprecation(self, event: Optional[BaseEvent]) -> bool:
        """Is the event a deprecation, and if so should it be treated as an error?"""
        return (
            event is not None and event.code().startswith("D") and self.DEPRECATIONS in self.error
        )

    def _warn_as_deprecation(self, event: Optional[BaseEvent]) -> bool:
        """Is the event a deprecation, and if so should it be treated as an warning?"""
        return (
            event is not None and event.code().startswith("D") and self.DEPRECATIONS in self.warn
        )

    def _silence_as_deprecation(self, event: Optional[BaseEvent]) -> bool:
        """Is the event a deprecation, and if so should it be silenced?"""
        return (
            event is not None
            and event.code().startswith("D")
            and self.DEPRECATIONS in self.silence
        )

    def errors(self, item_name: Union[str, BaseEvent]) -> bool:
        """Should the event be treated as an error?

        An event should error if any of the following are true:
        - The event is named in `error` and not named in `warn` or `silence`
        - "*" or "all" is specified for `error`, and the event is not named in `warn` or `silence`
        - The event is a deprecation, "deprecations" is in `error`, and the event is not named in `warn` or `silence`
          nor is "deprecations" in `warn` or `silence`
        """
        # Setup based on item_name type
        if isinstance(item_name, str):
            event_name = item_name
            event = None
        else:
            event_name = type(item_name).__name__
            event = item_name

        # Pre-compute checks that will be used multiple times
        named_elsewhere = self._named_warn(event_name) or self._named_silence(event_name)
        deprecation_elsewhere = self._warn_as_deprecation(event) or self._silence_as_deprecation(
            event
        )

        # Calculate result
        if self._named_error(event_name) and not named_elsewhere:
            return True
        elif self._error_as_deprecation(event) and not (named_elsewhere or deprecation_elsewhere):
            return True
        elif self._error_all() and not (named_elsewhere or deprecation_elsewhere):
            return True
        else:
            return False

    def includes(self, item_name: Union[str, BaseEvent]) -> bool:
        """Deprecated, use `errors` instead."""
        return self.errors(item_name)

    def silenced(self, item_name: Union[str, BaseEvent]) -> bool:
        """Is the event silenced?

        An event silenced if any of the following are true:
        - The event is named in `silence`
        - "Deprecations" is in `silence` and the event is not named in `error` or `warn`
        """
        # Setup based on item_name type
        if isinstance(item_name, str):
            event_name = item_name
            event = None
        else:
            event_name = type(item_name).__name__
            event = item_name

        # Pre-compute checks that will be used multiple times
        named_elsewhere = self._named_error(event_name) or self._named_warn(event_name)

        # Calculate result
        if self._named_silence(event_name):
            return True
        elif self._silence_as_deprecation(event) and not named_elsewhere:
            return True
        else:
            return False


FQNPath = Tuple[str, ...]
PathSet = AbstractSet[FQNPath]

T = TypeVar("T")


# A data type for representing lazily evaluated values.
#
# usage:
# x = Lazy.defer(lambda: expensive_fn())
# y = x.force()
#
# inspired by the purescript data type
# https://pursuit.purescript.org/packages/purescript-lazy/5.0.0/docs/Data.Lazy
@dataclass
class Lazy(Generic[T]):
    _f: Callable[[], T]
    memo: Optional[T] = None

    # constructor for lazy values
    @classmethod
    def defer(cls, f: Callable[[], T]) -> Lazy[T]:
        return Lazy(f)

    # workaround for open mypy issue:
    # https://github.com/python/mypy/issues/6910
    def _typed_eval_f(self) -> T:
        return cast(Callable[[], T], getattr(self, "_f"))()

    # evaluates the function if the value has not been memoized already
    def force(self) -> T:
        if self.memo is None:
            self.memo = self._typed_eval_f()
        return self.memo


# This class is used in to_target_dict, so that accesses to missing keys
# will return an empty string instead of Undefined
class DictDefaultEmptyStr(dict):
    def __getitem__(self, key):
        return dict.get(self, key, "")
