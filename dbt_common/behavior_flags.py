import inspect
from typing import Any, Dict, List, TypedDict

try:
    from typing import NotRequired
except ImportError:
    # NotRequired was introduced in Python 3.11
    # This is the suggested way to implement a TypedDict with optional arguments
    from typing import Optional as NotRequired

from dbt_common.events.base_types import WarnLevel
from dbt_common.events.functions import fire_event
from dbt_common.events.types import BehaviorDeprecationEvent
from dbt_common.exceptions import DbtInternalError


class BehaviorFlag:
    """
    The canonical behavior flag that gets used through dbt packages

    Args:
        name: the name of the behavior flag, e.g. enforce_quoting_on_relation_creation
        setting: the flag setting, after accounting for user input and the default
        deprecation_event: the event to fire if the flag evaluates to False
    """

    def __init__(self, name: str, setting: bool, deprecation_event: WarnLevel) -> None:
        self.name = name
        self.setting = setting
        self.deprecation_event = deprecation_event

    @property
    def setting(self) -> bool:
        if self._setting is False:
            fire_event(self.deprecation_event)
        return self._setting

    @setting.setter
    def setting(self, value: bool) -> None:
        self._setting = value

    @property
    def no_warn(self) -> bool:
        return self._setting

    def __bool__(self) -> bool:
        return self.setting


class RawBehaviorFlag(TypedDict):
    """
    A set of config used to create a BehaviorFlag

    Args:
        name: the name of the behavior flag
        default:  default setting, starts as False, becomes True in the next minor release
        deprecation_version: the version when the default will change to True
        deprecation_message: an additional message to send when the flag evaluates to False
        docs_url: the url to the relevant docs on docs.getdbt.com
    """

    name: str
    default: bool
    source: NotRequired[str]
    deprecation_version: NotRequired[str]
    deprecation_message: NotRequired[str]
    docs_url: NotRequired[str]


# this is effectively a dictionary that supports dot notation
# it makes usage easy, e.g. adapter.behavior.my_flag
class Behavior:
    _flags: List[BehaviorFlag]

    def __init__(
        self,
        behavior_flags: List[RawBehaviorFlag],
        user_overrides: Dict[str, Any],
    ) -> None:
        flags = []
        for raw_flag in behavior_flags:
            flags.append(
                BehaviorFlag(
                    name=raw_flag["name"],
                    setting=user_overrides.get(raw_flag["name"], raw_flag["default"]),
                    deprecation_event=_behavior_deprecation_event(raw_flag),
                )
            )
        self._flags = flags

    def __getattr__(self, name: str) -> BehaviorFlag:
        for flag in self._flags:
            if flag.name == name:
                return flag
        raise DbtInternalError(f"The flag {name} has not be registered.")


def _behavior_deprecation_event(flag: RawBehaviorFlag) -> BehaviorDeprecationEvent:
    return BehaviorDeprecationEvent(
        flag_name=flag["name"],
        flag_source=flag.get("source", _default_source()),
        deprecation_version=flag.get("deprecation_version"),
        deprecation_message=flag.get("deprecation_message"),
        docs_url=flag.get("docs_url"),
    )


def _default_source() -> str:
    """
    If the maintainer did not provide a source, default to the module that called `register`.
    For adapters, this will likely be `dbt.adapters.<foo>.impl` for `dbt-foo`.
    """
    frame = inspect.stack()[3]
    if module := inspect.getmodule(frame[0]):
        return module.__name__
    return "Unknown"
