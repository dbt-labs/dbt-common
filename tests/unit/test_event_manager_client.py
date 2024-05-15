from pytest_mock import MockerFixture

from dbt_common.events.event_manager import EventManager
from dbt_common.events.event_manager_client import add_callback_to_manager, get_event_manager
from tests.unit.utils import EventCatcher


def test_add_callback_to_manager(mocker: MockerFixture) -> None:
    # mock out the global event manager so the callback doesn't get added to all other tests
    mocker.patch("dbt_common.events.event_manager_client._EVENT_MANAGER", EventManager())
    manager = get_event_manager()
    assert len(manager.callbacks) == 0

    add_callback_to_manager(EventCatcher().catch)
    assert len(manager.callbacks) == 1
