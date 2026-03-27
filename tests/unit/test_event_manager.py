import pytest

from dbt_common.events.event_catcher import EventCatcher
from dbt_common.events.event_manager import EventManager
from dbt_common.events.types import BehaviorChangeEvent
from dbt_common.exceptions.events import EventCompilationError
from dbt_common.helper_types import WarnErrorOptionsV2


class TestEventManager:
    def test_add_callback(self) -> None:
        event_manager = EventManager()
        assert len(event_manager.callbacks) == 0

        event_manager.add_callback(EventCatcher().catch)
        assert len(event_manager.callbacks) == 1

    def test_default_warn_error_options(self) -> None:
        event_manager = EventManager()
        assert event_manager.warn_error_options.to_dict() == WarnErrorOptionsV2().to_dict()


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


class TestDeferredWarnErrors:
    def create_events(self, count: int = 1):
        return [
            BehaviorChangeEvent(
                flag_name=f"test_{i}",
                flag_source="test",
                description="test",
                docs_url="test",
            )
            for i in range(count)
        ]

    def test_defer_multiple_when_show_all_warn_errors(self) -> None:
        event_manager = EventManager()
        event_manager.warn_error = True
        event_manager.defer_warn_errors = True
        for event in self.create_events(2):
            event_manager.fire_event(event, force_warn_or_error_handling=True)
        assert len(event_manager._deferred_warn_errors) == 2

    def test_immediate_raise_when_show_all_warn_errors_false(self) -> None:
        event_manager = EventManager()
        event_manager.warn_error = True
        event_manager.defer_warn_errors = False
        with pytest.raises(EventCompilationError):
            event_manager.fire_event(self.create_events(1)[0], force_warn_or_error_handling=True)

    def test_raise_deferred_combines_and_clears(self) -> None:
        event_manager = EventManager()
        event_manager.warn_error = True
        event_manager.defer_warn_errors = True
        events = self.create_events(2)
        for event in events:
            event_manager.fire_event(event, force_warn_or_error_handling=True)
        with pytest.raises(EventCompilationError) as excinfo:
            event_manager.raise_deferred_warn_errors()
        msg = str(excinfo.value)
        for event in events:
            assert event.flag_name in msg
        assert event_manager._deferred_warn_errors == []

    def test_raise_deferred_warn_errors_empty(self) -> None:
        event_manager = EventManager()
        event_manager.defer_warn_errors = True
        event_manager.raise_deferred_warn_errors()
        assert event_manager._deferred_warn_errors == []
