import pytest

from dbt_common.events import functions
from dbt_common.events.base_types import EventLevel, WarnLevel
from dbt_common.events.event_manager import EventManager
from dbt_common.events.event_manager_client import ctx_set_event_manager
from dbt_common.exceptions import EventCompilationError
from dbt_common.helper_types import WarnErrorOptions
from tests.unit.utils import EventCatcher
from typing import Set


# Re-implementing `Note` event as a warn event for
# our testing purposes
class Note(WarnLevel):
    def code(self) -> str:
        return "Z050"

    def message(self) -> str:
        return self.msg


@pytest.fixture(scope="function")
def event_catcher() -> EventCatcher:
    return EventCatcher()


@pytest.fixture(scope="function")
def set_event_manager_with_catcher(event_catcher: EventCatcher) -> None:
    event_manager = EventManager()
    event_manager.callbacks.append(event_catcher.catch)
    ctx_set_event_manager(event_manager)


@pytest.fixture(scope="function")
def valid_error_names() -> Set[str]:
    return {Note.__name__}


class TestWarnOrError:
    def test_fires_error(self, valid_error_names: Set[str]) -> None:
        functions.WARN_ERROR_OPTIONS = WarnErrorOptions(
            include="*", valid_error_names=valid_error_names
        )
        with pytest.raises(EventCompilationError):
            functions.warn_or_error(Note(msg="hi"))

    def test_fires_warning(
        self,
        valid_error_names: Set[str],
        event_catcher: EventCatcher,
        set_event_manager_with_catcher: None,
    ) -> None:
        functions.WARN_ERROR_OPTIONS = WarnErrorOptions(
            include="*", exclude=list(valid_error_names), valid_error_names=valid_error_names
        )
        functions.warn_or_error(Note(msg="hi"))
        assert len(event_catcher.caught_events) == 1
        assert event_catcher.caught_events[0].info.level == EventLevel.WARN.value

    def test_silenced(
        self,
        valid_error_names: Set[str],
        event_catcher: EventCatcher,
        set_event_manager_with_catcher: None,
    ) -> None:
        functions.WARN_ERROR_OPTIONS = WarnErrorOptions(
            include="*", silence=list(valid_error_names), valid_error_names=valid_error_names
        )
        functions.warn_or_error(Note(msg="hi"))
        assert len(event_catcher.caught_events) == 0
