import pytest
from pytest_mock import MockerFixture

from dbt_common.events.event_catcher import EventCatcher
from dbt_common.events.event_manager import EventManager
from dbt_common.events.event_manager_client import add_callback_to_manager


@pytest.fixture(scope="function")
def event_catcher(mocker: MockerFixture) -> EventCatcher:
    # mock out the global event manager so the callback doesn't get added to all other tests
    mocker.patch("dbt_common.events.event_manager_client._EVENT_MANAGER", EventManager())
    catcher = EventCatcher()
    add_callback_to_manager(catcher.catch)
    return catcher
