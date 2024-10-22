from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

import pytz

from dbt_common.events.functions import get_invocation_id


class User:
    def __init__(self, directory: Union[str, Path]) -> None:
        self.cookie: Dict[str, Any] = {}
        self.directory: Path = Path(directory)
        self.invocation_id: str = get_invocation_id()
        self.run_started_at: datetime = datetime.now(tz=pytz.utc)

    @property
    def id(self) -> Optional[str]:
        if self.cookie:
            return self.cookie.get("id")

    @property
    def do_not_track(self) -> bool:
        return self.cookie != {}

    def state(self):
        return "do not track" if self.do_not_track else "tracking"

    @property
    def profile(self) -> Path:
        return Path(self.directory) / "profiles.yml"

    def enable_tracking(self, cookie: Dict[str, Any]):
        self.cookie = cookie

    def disable_tracking(self):
        self.cookie = {}
