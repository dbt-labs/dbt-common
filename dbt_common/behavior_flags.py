import inspect
from typing import Any, Dict, List, TypedDict

try:
    from typing import NotRequired
except ImportError:
    # NotRequired was introduced in Python 3.11
    # This is the suggested way to implement a TypedDict with optional arguments
    from typing import Optional as NotRequired

from dbt_common.events.functions import fire_event
from dbt_common.events.types import BehaviorDeprecationEvent
from dbt_common.exceptions import DbtInternalError


class BehaviorFlag(TypedDict):
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


class BehaviorFlagRendered:
    """
    The canonical behavior flag that gets used through dbt packages

    Args:
        flag: the configuration for the behavior flag
        user_overrides: a set of user settings, one of which may be an override on this behavior flag
    """

    def __init__(self, flag: BehaviorFlag, user_overrides: Dict[str, Any]) -> None:
        self.name = flag["name"]
        self.setting = user_overrides.get(flag["name"], flag["default"])
        self.deprecation_event = self._deprecation_event(flag)

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

    def _deprecation_event(self, flag: BehaviorFlag) -> BehaviorDeprecationEvent:
        return BehaviorDeprecationEvent(
            flag_name=flag["name"],
            flag_source=flag.get("source", self._default_source()),
            deprecation_version=flag.get("deprecation_version"),
            deprecation_message=flag.get("deprecation_message"),
            docs_url=flag.get("docs_url"),
        )

    @staticmethod
    def _default_source() -> str:
        """
        If the maintainer did not provide a source, default to the module that called `register`.
        For adapters, this will likely be `dbt.adapters.<foo>.impl` for `dbt-foo`.
        """
        for frame in inspect.stack():
            if module := inspect.getmodule(frame[0]):
                if module.__name__ != __name__:
                    return module.__name__
        return "Unknown"

    def __bool__(self) -> bool:
        return self.setting


# this is effectively a dictionary that supports dot notation
# it makes usage easy, e.g. adapter.behavior.my_flag
class Behavior:
    _flags: List[BehaviorFlagRendered]

    def __init__(self, flags: List[BehaviorFlag], user_overrides: Dict[str, Any]) -> None:
        self._flags = [BehaviorFlagRendered(flag, user_overrides) for flag in flags]

    def __getattr__(self, name: str) -> BehaviorFlagRendered:
        for flag in self._flags:
            if flag.name == name:
                return flag
        raise DbtInternalError(f"The flag {name} has not be registered.")
