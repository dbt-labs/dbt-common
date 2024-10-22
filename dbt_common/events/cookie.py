from pathlib import Path
import uuid
from typing import Any, Dict

import yaml

# the C version is faster, but it doesn't always exist
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:
    from yaml import SafeLoader


class Cookie:
    def __init__(self, directory: Path) -> None:
        self.id: str = str(uuid.uuid4())
        self.path: Path = directory / ".user.yml"
        self.save()

    def as_dict(self) -> Dict[str, Any]:
        return {"id": self.id}

    def save(self) -> None:
        with open(self.path, "w") as fh:
            yaml.dump(self.as_dict(), fh)

    def load(self) -> Dict[str, Any]:
        with open(self.path, "r") as fh:
            try:
                return yaml.load(fh, Loader=SafeLoader)
            except yaml.reader.ReaderError:
                return {}
