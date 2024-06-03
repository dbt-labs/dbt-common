import pytest
from dataclasses import dataclass
from typing import Dict, Optional

from dbt_common.dataclass_schema import dbtClassMixin, ValidationError, StrEnum


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


class MyEnum(StrEnum):
    One = "one"
    Two = "two"
    Three = "three"


@dataclass
class SomeObject(dbtClassMixin):
    name: str
    an_attr: Optional[str] = None
    an_int: int = 1
    an_enum: Optional[MyEnum] = None
    a_bool: bool = True


def test_validation():
    dct = {"name": "testing"}
    SomeObject.validate(dct)
    # check that use_default is not set in compile method
    assert "an_attr" not in dct

    dct = {"an_attr": "fubar"}
    with pytest.raises(ValidationError) as excinfo:
        SomeObject.validate(dct)
    # former message: "'name' is a required property"
    assert (
        excinfo.value.message
        == "Invalid value '{'an_attr': 'fubar'}': data must contain ['name'] properties"
    )

    dct = {"name": "testing", "an_int": "some_str"}
    with pytest.raises(ValidationError) as excinfo:
        SomeObject.validate(dct)
    # former message: "'some_str' is not of type 'integer'"
    assert excinfo.value.message == "Invalid value 'some_str': data.an_int must be integer"

    # Note: any field with multiple types (such as Optional[...]) will get the
    # "cannot be validated by any definition" message.
    dct = {"name": "testing", "an_enum": "four"}
    with pytest.raises(ValidationError) as excinfo:
        SomeObject.validate(dct)
    # former message: "'four' is not valid under any of the given schemas"
    assert (
        excinfo.value.message
        == "Invalid value 'four': data.an_enum cannot be validated by any definition"
    )

    dct = {"name": "testing", "a_bool": "True or False"}
    with pytest.raises(ValidationError) as excinfo:
        SomeObject.validate(dct)
    # former message: "'True or False' is not of type 'boolean'"
    assert excinfo.value.message == "Invalid value 'True or False': data.a_bool must be boolean"
