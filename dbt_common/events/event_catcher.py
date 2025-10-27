from dataclasses import dataclass, field
from typing import Callable, List, Optional

from dbt_common.events.base_types import EventMsg, EventType


@dataclass
class EventCatcher:
    event_to_catch: Optional[EventType] = None
    caught_events: List[EventMsg] = field(default_factory=list)
    predicate: Callable[[EventMsg], bool] = lambda event: True

    def _check_event_type(self, event: EventMsg) -> bool:
        return self.event_to_catch is None or event.info.name == self.event_to_catch.__name__

    def catch(self, event: EventMsg):
        if self._check_event_type(event) and self.predicate(event):
            self.caught_events.append(event)

    def flush(self) -> None:
        self.caught_events = []
