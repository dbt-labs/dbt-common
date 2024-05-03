from dataclasses import dataclass
from typing import Dict, Optional

from dbt_common.dataclass_schema import dbtClassMixin


@dataclass
class MySubObject(dbtClassMixin):
    name: str

    def __post_serialize__(self, dct: Dict, context: Optional[Dict] = None):
        if context and "artifact" in context:
            dct["name"] = "xxxx"
        return dct


@dataclass
class MyObject(dbtClassMixin):
    sub_object: MySubObject
    unique_id: str

    def __post_serialize__(self, dct: Dict, context: Optional[Dict] = None):
        if context and "artifact" in context:
            dct["unique_id"] = "my.xxxx.object"
        return dct


def test_serialization_context():
    sub_obj = MySubObject("testing")

    obj = MyObject(sub_object=sub_obj, unique_id="my.test.object")

    assert obj

    dct = obj.to_dict()
    assert dct == {"unique_id": "my.test.object", "sub_object": {"name": "testing"}}

    mod_dct = obj.to_dict(context={"artifact": True})
    assert mod_dct == {"unique_id": "my.xxxx.object", "sub_object": {"name": "xxxx"}}

    obj = MyObject.from_dict(dct)
    assert obj.sub_object.name == "testing"
