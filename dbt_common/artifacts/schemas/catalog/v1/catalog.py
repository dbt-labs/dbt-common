from dataclasses import dataclass
from typing import Dict, Optional, Union

from dbt_common.dataclass_schema import dbtClassMixin


@dataclass
class StatsItem(dbtClassMixin):
    id: str
    label: str
    value: Union[bool, str, float, None]
    include: bool
    description: Optional[str] = None


StatsDict = Dict[str, StatsItem]


@dataclass
class TableMetadata(dbtClassMixin):
    type: str
    schema: str
    name: str
    database: Optional[str] = None
    comment: Optional[str] = None
    owner: Optional[str] = None
