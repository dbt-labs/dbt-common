from dataclasses import dataclass, field
from typing import List

import pytest
from pytest_mock import MockerFixture

from dbt_common.events.base_types import EventMsg
from dbt_common.events.event_manager import EventManager
from dbt_common.events.event_manager_client import add_callback_to_manager


@dataclass
class EventCatcher:
    caught_events: List[EventMsg] = field(default_factory=list)

    def catch(self, event: EventMsg) -> None:
        self.caught_events.append(event)


@pytest.fixture(scope="function")
def event_catcher(mocker: MockerFixture) -> EventCatcher:
    # mock out the global event manager so the callback doesn't get added to all other tests
    mocker.patch("dbt_common.events.event_manager_client._EVENT_MANAGER", EventManager())
    catcher = EventCatcher()
    add_callback_to_manager(catcher.catch)
    return catcher
