from dbt_common.events.event_catcher import EventCatcher
from dbt_common.events.event_manager import EventManager
from dbt_common.events.types import Formatting, Note


class TestEventCatcher:
    def test_basic_catcher(self) -> None:
        # Setup
        event_manager = EventManager()
        event_catcher = EventCatcher()
        event_manager.add_callback(event_catcher.catch)

        # Fire events
        event_manager.fire_event(Note(msg="test"))

        # Validate
        assert len(event_catcher.caught_events) == 1

    def test_catching_specific_event(self) -> None:
        # Setup
        event_manager = EventManager()
        note_catcher = EventCatcher(event_to_catch=Note)
        event_manager.add_callback(note_catcher.catch)

        # Fire events
        event_manager.fire_event(Formatting(msg="woof"))
        event_manager.fire_event(Note(msg="meow"))

        # Validate
        assert len(note_catcher.caught_events) == 1
        assert note_catcher.caught_events[0].data.msg == "meow"

    def test_catching_specific_event_with_predicate(self) -> None:
        # Setup
        event_manager = EventManager()
        predicate_catcher = EventCatcher(predicate=lambda event: event.data.msg == "woof")
        event_manager.add_callback(predicate_catcher.catch)

        # Fire events
        event_manager.fire_event(Formatting(msg="woof"))
        event_manager.fire_event(Note(msg="meow"))

        # Validate
        assert len(predicate_catcher.caught_events) == 1
        assert predicate_catcher.caught_events[0].data.msg == "woof"

    def test_catching_specific_event_with_predicate_and_event_to_catch(self) -> None:
        # Setup
        event_manager = EventManager()
        note_catcher = EventCatcher(
            event_to_catch=Note, predicate=lambda event: event.data.msg == "neigh"
        )
        event_manager.add_callback(note_catcher.catch)

        # Fire events
        event_manager.fire_event(Note(msg="woof"))
        event_manager.fire_event(Note(msg="neigh"))
        event_manager.fire_event(Note(msg="meow"))
        event_manager.fire_event(Formatting(msg="neigh"))

        # Validate
        assert len(note_catcher.caught_events) == 1
        assert note_catcher.caught_events[0].data.msg == "neigh"
