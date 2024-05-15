from dataclasses import dataclass, field
from typing import List

from dbt_common.events.base_types import EventMsg


@dataclass
class EventCatcher:
    caught_events: List[EventMsg] = field(default_factory=list)

    def catch(self, event: EventMsg) -> None:
        self.caught_events.append(event)
