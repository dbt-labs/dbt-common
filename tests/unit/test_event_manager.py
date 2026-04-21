import pytest

from dbt_common.events.base_types import EventGroupType
from dbt_common.events.event_catcher import EventCatcher
from dbt_common.events.event_manager import EventManager
from dbt_common.events.types import BehaviorChangeEvent, GetMetaKeyWarning
from dbt_common.exceptions.events import EventCompilationError
from dbt_common.helper_types import WarnErrorOptionsV2


def _make_event(description: str = "test") -> BehaviorChangeEvent:
    return BehaviorChangeEvent(
        flag_name="test",
        flag_source="test",
        description=description,
        docs_url="test",
    )


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


class TestFireOrDeferEvent:
    def test_fires_immediately_when_deferral_disabled(self) -> None:
        catcher = EventCatcher()
        em = EventManager()
        em.add_callback(catcher.catch)

        em.fire_or_defer_event(_make_event(), EventGroupType.PARSE)

        assert len(catcher.caught_events) == 1
        assert em._deferred_event_groups[EventGroupType.PARSE] == []

    def test_queues_event_when_deferral_enabled(self) -> None:
        catcher = EventCatcher()
        em = EventManager()
        em.add_callback(catcher.catch)
        em.allow_deferral = True

        em.fire_or_defer_event(_make_event(), EventGroupType.PARSE)

        assert len(catcher.caught_events) == 0
        assert len(em._deferred_event_groups[EventGroupType.PARSE]) == 1

    def test_preserves_fire_event_args_on_defer(self) -> None:
        em = EventManager()
        em.allow_deferral = True
        evt = _make_event()

        em.fire_or_defer_event(
            evt,
            EventGroupType.PARSE,
            level=None,
            node="my_node",
            force_warn_or_error_handling=True,
        )

        (queued,) = em._deferred_event_groups[EventGroupType.PARSE]
        assert queued.event is evt
        assert queued.node == "my_node"
        assert queued.force_warn_or_error_handling is True


class TestFireDeferredEvents:
    def test_aggregates_warn_errors_into_single_exception(self) -> None:
        em = EventManager()
        em.warn_error = True
        em.allow_deferral = True

        em.fire_or_defer_event(
            _make_event("first warning"),
            EventGroupType.PARSE,
            force_warn_or_error_handling=True,
        )
        em.fire_or_defer_event(
            _make_event("second warning"),
            EventGroupType.PARSE,
            force_warn_or_error_handling=True,
        )

        with pytest.raises(EventCompilationError) as exc_info:
            em.fire_deferred_events(EventGroupType.PARSE)

        msg = str(exc_info.value)
        assert "first warning" in msg
        assert "second warning" in msg

    def test_drains_group_after_flush(self) -> None:
        em = EventManager()
        em.warn_error = True
        em.allow_deferral = True
        em.fire_or_defer_event(
            _make_event(),
            EventGroupType.PARSE,
            force_warn_or_error_handling=True,
        )

        with pytest.raises(EventCompilationError):
            em.fire_deferred_events(EventGroupType.PARSE)

        assert em._deferred_event_groups[EventGroupType.PARSE] == []

    def test_non_raising_events_still_delivered_to_callbacks(self) -> None:
        catcher = EventCatcher()
        em = EventManager()
        em.add_callback(catcher.catch)
        em.allow_deferral = True

        em.fire_or_defer_event(_make_event(), EventGroupType.PARSE)
        em.fire_deferred_events(EventGroupType.PARSE)

        assert len(catcher.caught_events) == 1

    def test_groups_are_isolated(self) -> None:
        em = EventManager()
        em.warn_error = True
        em.allow_deferral = True

        em.fire_or_defer_event(
            _make_event("first"),
            EventGroupType.PARSE,
            force_warn_or_error_handling=True,
        )
        with pytest.raises(EventCompilationError):
            em.fire_deferred_events(EventGroupType.PARSE)

        em.fire_or_defer_event(_make_event("second"), EventGroupType.PARSE)
        assert len(em._deferred_event_groups[EventGroupType.PARSE]) == 1
        assert em._deferred_event_groups[EventGroupType.PARSE][0].event.description == "second"

    def test_does_not_raise_when_nothing_errored(self) -> None:
        em = EventManager()
        em.fire_deferred_events(EventGroupType.PARSE)

    def test_respects_warn_error_options_across_event_types(self) -> None:
        catcher = EventCatcher()
        em = EventManager()
        em.add_callback(catcher.catch)
        em.warn_error_options = WarnErrorOptionsV2(
            error=["BehaviorChangeEvent"],
            silence=["GetMetaKeyWarning"],
            valid_error_names={"BehaviorChangeEvent", "GetMetaKeyWarning"},
        )
        em.allow_deferral = True

        errored = _make_event("migration required")
        silenced = GetMetaKeyWarning(meta_key="my_key")

        em.fire_or_defer_event(errored, EventGroupType.PARSE, force_warn_or_error_handling=True)
        em.fire_or_defer_event(silenced, EventGroupType.PARSE, force_warn_or_error_handling=True)

        with pytest.raises(EventCompilationError) as exc_info:
            em.fire_deferred_events(EventGroupType.PARSE)

        msg = str(exc_info.value)
        assert "migration required" in msg
        assert "my_key" not in msg
        caught_names = {ev.info.name for ev in catcher.caught_events}
        assert "GetMetaKeyWarning" not in caught_names


class TestDefaultEventGroup:
    def test_default_group_used_when_unspecified(self) -> None:
        em = EventManager()
        em.allow_deferral = True

        em.fire_or_defer_event(_make_event())

        assert len(em._deferred_event_groups[EventGroupType.DEFAULT]) == 1
        assert em._deferred_event_groups[EventGroupType.PARSE] == []

    def test_default_group_flushes_independently_of_parse(self) -> None:
        em = EventManager()
        em.warn_error = True
        em.allow_deferral = True

        em.fire_or_defer_event(_make_event("default group"), force_warn_or_error_handling=True)
        em.fire_or_defer_event(
            _make_event("parse group"),
            EventGroupType.PARSE,
            force_warn_or_error_handling=True,
        )

        with pytest.raises(EventCompilationError) as exc_info:
            em.fire_deferred_events()

        assert "default group" in str(exc_info.value)
        assert "parse group" not in str(exc_info.value)
        assert len(em._deferred_event_groups[EventGroupType.PARSE]) == 1
