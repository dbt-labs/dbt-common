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
    """
    This class is used to configure the behavior of the warn_error feature (now part of fire_event).

    include: "all", "*", or a list of event names.
    exclude: a list of event names.
    silence: a list of event names.
    valid_error_names: a set of event names that can be named in include, exclude, and silence.

    In a hierarchy of configuration, the following rules apply:
    1. named > Deprecations > "all"/"*"
    2. silence > exclude > include
    3. (1) > (2)
    """

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

    def __post_init__(self):
        if isinstance(self.include, str) and self.include not in self.INCLUDE_ALL:
            raise ValidationError(
                f"include must be one of {self.INCLUDE_ALL} or a list of strings"
            )

        # To specify exclude, either `include` must be "all" or "deprecations" must be
        # in `include` or `silence`.
        if self.exclude and not (
            self.include in self.INCLUDE_ALL
            or self.DEPRECATIONS in self.include
            or self.DEPRECATIONS in self.silence
        ):
            raise ValidationError(
                f"exclude can only be specified if include is one of {self.INCLUDE_ALL} or "
                f"{self.DEPRECATIONS} is in include or silence."
            )

        if isinstance(self.include, list):
            self._validate_items(self.include)

        if isinstance(self.exclude, list):
            self._validate_items(self.exclude)

        if isinstance(self.silence, list):
            self._validate_items(self.silence)

    def _includes_all(self) -> bool:
        """Is `*` or `all` set as include?"""
        return self.include in self.INCLUDE_ALL

    def _named_inclusion(self, item_name: str) -> bool:
        """Is the item_name named in the include list?"""
        return item_name in self.include

    def _named_exclusion(self, item_name: str) -> bool:
        """Is the item_name named in the exclude list?"""
        return item_name in self.exclude

    def _named_silence(self, item_name: str) -> bool:
        """Is the item_name named in the silence list?"""
        return item_name in self.silence

    def _include_as_deprecation(self, event: Optional[BaseEvent]) -> bool:
        """Is event included as a deprecation?"""
        return (
            event is not None
            and event.code().startswith("D")
            and self.DEPRECATIONS in self.include
        )

    def _exclude_as_deprecation(self, event: Optional[BaseEvent]) -> bool:
        """Is event excluded as a deprecation?"""
        return (
            event is not None
            and event.code().startswith("D")
            and self.DEPRECATIONS in self.exclude
        )

    def _silence_as_deprecation(self, event: Optional[BaseEvent]) -> bool:
        """Is event silenced as a deprecation?"""
        return (
            event is not None
            and event.code().startswith("D")
            and self.DEPRECATIONS in self.silence
        )

    def includes(self, item_name: Union[str, BaseEvent]) -> bool:
        """Is the event included?

        An event included if any of the following are true:
        - The event is named in `include` and not named in `exclude` or `silence`
        - "*" or "all" is specified for `include`, and the event is not named in `exclude` or `silence`
        - The event is a deprecation, "deprecations" is in `include`, and the event is not named in `exclude` or `silence`
          nor is "deprecations" in `exclude` or `silence`
        """
        # Setup based on item_name type
        if isinstance(item_name, str):
            event_name = item_name
            event = None
        else:
            event_name = type(item_name).__name__
            event = item_name

        # Pre-compute checks that will be used multiple times
        named_elsewhere = self._named_exclusion(event_name) or self._named_silence(event_name)
        deprecation_elsewhere = self._exclude_as_deprecation(
            event
        ) or self._silence_as_deprecation(event)

        # Calculate result
        if self._named_inclusion(event_name) and not named_elsewhere:
            return True
        elif self._include_as_deprecation(event) and not (
            named_elsewhere or deprecation_elsewhere
        ):
            return True
        elif self._includes_all() and not (named_elsewhere or deprecation_elsewhere):
            return True
        else:
            return False

    def silenced(self, item_name: Union[str, BaseEvent]) -> bool:
        """Is the event silenced?

        An event silenced if any of the following are true:
        - The event is named in `silence`
        - "Deprecations" is in `silence` and the event is not named in `include` or `exclude`
        """
        # Setup based on item_name type
        if isinstance(item_name, str):
            event_name = item_name
            event = None
        else:
            event_name = type(item_name).__name__
            event = item_name

        # Pre-compute checks that will be used multiple times
        named_elsewhere = self._named_inclusion(event_name) or self._named_exclusion(event_name)

        # Calculate result
        if self._named_silence(event_name):
            return True
        elif self._silence_as_deprecation(event) and not named_elsewhere:
            return True
        else:
            return False

    def _validate_items(self, items: List[str]):
        for item in items:
            if item not in self._valid_error_names:
                raise ValidationError(f"{item} is not a valid dbt error name.")


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
