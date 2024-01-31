import decimal
from _typeshed import Incomplete
from mashumaro.core.const import Sentinel
from typing import Any, Optional, Union
from typing_extensions import Literal

class SerializableType: ...
class GenericSerializableType: ...

class SerializationStrategy:
    def serialize(self, value: Any) -> Any: ...
    def deserialize(self, value: Any) -> Any: ...

class RoundedDecimal(SerializationStrategy):
    exp: Incomplete
    rounding: Incomplete
    def __init__(self, places: Optional[int] = ..., rounding: Optional[str] = ...) -> None: ...
    def serialize(self, value: decimal.Decimal) -> str: ...
    def deserialize(self, value: str) -> decimal.Decimal: ...

class Discriminator:
    field: Optional[str]
    include_supertypes: bool
    include_subtypes: bool
    def __post_init__(self) -> None: ...
    def __init__(self, field, include_supertypes, include_subtypes) -> None: ...
