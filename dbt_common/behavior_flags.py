import inspect
from types import SimpleNamespace
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
Behavior = SimpleNamespace


def register(
    behavior_flags: List[RawBehaviorFlag],
    user_flags: Dict[str, Any],
) -> Behavior:
    flags = {}
    for raw_flag in behavior_flags:
        flag = {
            "name": raw_flag["name"],
            "setting": raw_flag["default"],
        }

        # specifically evaluate for `None` since `False` and `None` should be treated differently
        if user_flags.get(raw_flag["name"]) is not None:
            flag["setting"] = user_flags.get(raw_flag["name"])

        event = BehaviorDeprecationEvent(
            flag_name=raw_flag["name"],
            flag_source=raw_flag.get("source", _default_source()),
            deprecation_version=raw_flag.get("deprecation_version"),
            deprecation_message=raw_flag.get("deprecation_message"),
            docs_url=raw_flag.get("docs_url"),
        )
        flag["deprecation_event"] = event

        flags[flag["name"]] = BehaviorFlag(**flag)  # type: ignore

    return Behavior(**flags)  # type: ignore


def _default_source() -> str:
    """
    If the maintainer did not provide a source, default to the module that called `register`.
    For adapters, this will likely be `dbt.adapters.<foo>.impl` for `dbt-foo`.
    """
    frame = inspect.stack()[2]
    if module := inspect.getmodule(frame[0]):
        return module.__name__
    return "Unknown"
