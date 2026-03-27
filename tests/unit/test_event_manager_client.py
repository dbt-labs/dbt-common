import pytest
from pytest_mock import MockerFixture

from dbt_common.exceptions.events import EventCompilationError
from dbt_common.events.event_catcher import EventCatcher
from dbt_common.events.event_manager import EventManager
from dbt_common.events.event_manager_client import (
    add_callback_to_manager,
    get_event_manager,
    raise_deferred_warn_errors,
)
from dbt_common.events.types import BehaviorChangeEvent


def test_add_callback_to_manager(mocker: MockerFixture) -> None:
    # mock out the global event manager so the callback doesn't get added to all other tests
    mocker.patch("dbt_common.events.event_manager_client._EVENT_MANAGER", EventManager())
    manager = get_event_manager()
    assert len(manager.callbacks) == 0

    add_callback_to_manager(EventCatcher().catch)
    assert len(manager.callbacks) == 1


def test_raise_deferred_warn_errors(mocker: MockerFixture) -> None:
    manager = get_event_manager()
    manager.defer_warn_errors = True
    manager.warn_error = True
    event = BehaviorChangeEvent(
        flag_name="test",
        flag_source="test",
        description="test",
        docs_url="test",
    )
    manager.fire_event(event, force_warn_or_error_handling=True)  # should not raise

    with pytest.raises(EventCompilationError) as excinfo:
        raise_deferred_warn_errors()
    assert event.flag_name in str(excinfo.value)
