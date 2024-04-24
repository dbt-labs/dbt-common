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

Port = NewType("Port", int)


class NVEnum(StrEnum):
    novalue = "novalue"

    def __eq__(self, other):
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

    def _validate_items(self, items: List[str]):
        pass


class WarnErrorOptions(IncludeExclude):
    def __init__(
        self,
        include: Union[str, List[str]],
        exclude: Optional[List[str]] = None,
        valid_error_names: Optional[Set[str]] = None,
        silence: Optional[List[str]] = None,
    ):
        self.silence = silence or []
        self._valid_error_names: Set[str] = valid_error_names or set()
        super().__init__(include=include, exclude=(exclude or []))

    def __post_init__(self):
        super().__post_init__()
        self._validate_items(self.silence)

    def includes(self, item_name: str) -> bool:
        return super().includes(item_name) and not self.silenced(item_name)

    def silenced(self, item_name: str) -> bool:
        return item_name in self.silence

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
