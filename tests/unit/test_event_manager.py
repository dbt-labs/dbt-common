from dbt_common.events.event_manager import EventManager
from dbt_common.events.types import BehaviorChangeEvent
from tests.unit.utils import EventCatcher


class TestEventManager:
    def test_add_callback(self) -> None:
        event_manager = EventManager()
        assert len(event_manager.callbacks) == 0

        event_manager.add_callback(EventCatcher().catch)
        assert len(event_manager.callbacks) == 1


class TestEventManagerSilencedDeprecation:
    def test_can_silenced_deprecation_event(self) -> None:
        event_catcher = EventCatcher()
        event_manager = EventManager()
        event_manager.add_callback(event_catcher.catch)

        event = BehaviorChangeEvent(
            flag_name="test",
            flag_source="test",
            description="test",
            docs_url="test",
        )

        event_manager.fire_event(e=event, force_warn_or_error_handling=True)
        assert len(event_manager.callbacks) == 1

        event_catcher.caught_events.clear()
        event_manager.warn_error_options.silence.append("Deprecations")
        event_manager.fire_event(e=event, force_warn_or_error_handling=True)
        assert len(event_catcher.caught_events) == 0
