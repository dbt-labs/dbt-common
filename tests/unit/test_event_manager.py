from dbt_common.events.event_manager import EventManager
from tests.unit.utils import EventCatcher


class TestEventManager:
    def test_add_callback(self) -> None:
        event_manager = EventManager()
        assert len(event_manager.callbacks) == 0

        event_manager.add_callback(EventCatcher().catch)
        assert len(event_manager.callbacks) == 1
