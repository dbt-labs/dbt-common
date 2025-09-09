import dataclasses
import json
import sys
import os
from io import StringIO

import pytest
from typing import Optional

from mashumaro.types import SerializationStrategy

from dbt_common.context import set_invocation_context, get_invocation_context
from dbt_common.record import (
    record_function,
    Record,
    Recorder,
    RecorderMode,
    auto_record_function,
    supports_replay,
)


@dataclasses.dataclass
class TestRecordParams:
    a: int
    b: str
    c: Optional[str] = None


@dataclasses.dataclass
class TestRecordResult:
    return_val: str


@Recorder.register_record_type
class TestRecord(Record):
    params_cls = TestRecordParams
    result_cls = TestRecordResult


@dataclasses.dataclass
class NotTestRecordParams:
    a: int
    b: str
    c: Optional[str] = None


@dataclasses.dataclass
class NotTestRecordResult:
    return_val: str


@Recorder.register_record_type
class NotTestRecord(Record):
    params_cls = NotTestRecordParams
    result_cls = NotTestRecordResult


@pytest.fixture(scope="function", autouse=True)
def setup():
    # capture the previous state of the environment variables
    prev_mode = os.environ.get("DBT_RECORDER_MODE", None)
    prev_type = os.environ.get("DBT_RECORDER_TYPES", None)
    prev_fp = os.environ.get("DBT_RECORDER_FILE_PATH", None)
    # clear the environment variables
    os.environ.pop("DBT_RECORDER_MODE", None)
    os.environ.pop("DBT_RECORDER_TYPES", None)
    os.environ.pop("DBT_RECORDER_FILE_PATH", None)
    yield
    # reset the environment variables to their previous state
    if prev_mode is None:
        os.environ.pop("DBT_RECORDER_MODE", None)
    else:
        os.environ["DBT_RECORDER_MODE"] = prev_mode
    if prev_type is None:
        os.environ.pop("DBT_RECORDER_TYPES", None)
    else:
        os.environ["DBT_RECORDER_TYPES"] = prev_type
    if prev_fp is None:
        os.environ.pop("DBT_RECORDER_FILE_PATH", None)
    else:
        os.environ["DBT_RECORDER_FILE_PATH"] = prev_fp


def test_decorator_records(setup) -> None:
    os.environ["DBT_RECORDER_MODE"] = "Record"
    recorder = Recorder(RecorderMode.RECORD, None, in_memory=True)
    set_invocation_context({})
    get_invocation_context().recorder = recorder

    @record_function(TestRecord)
    def test_func(a: int, b: str, c: Optional[str] = None) -> str:
        return str(a) + b + (c if c else "")

    test_func(123, "abc")

    expected_record = TestRecord(
        params=TestRecordParams(123, "abc"), result=TestRecordResult("123abc")
    )

    assert recorder._records_by_type["TestRecord"][-1].params == expected_record.params
    assert recorder._records_by_type["TestRecord"][-1].result == expected_record.result


def test_record_types(setup):
    os.environ["DBT_RECORDER_MODE"] = "Record"
    os.environ["DBT_RECORDER_TYPES"] = "TestRecord"
    recorder = Recorder(RecorderMode.RECORD, ["TestRecord"], in_memory=True)
    set_invocation_context({})
    get_invocation_context().recorder = recorder

    @record_function(TestRecord)
    def test_func(a: int, b: str, c: Optional[str] = None) -> str:
        return str(a) + b + (c if c else "")

    @record_function(NotTestRecord)
    def not_test_func(a: int, b: str, c: Optional[str] = None) -> str:
        return str(a) + b + (c if c else "")

    test_func(123, "abc")
    not_test_func(456, "def")

    expected_record = TestRecord(
        params=TestRecordParams(123, "abc"), result=TestRecordResult("123abc")
    )

    assert recorder._records_by_type["TestRecord"][-1].params == expected_record.params
    assert recorder._records_by_type["TestRecord"][-1].result == expected_record.result
    assert NotTestRecord not in recorder._records_by_type


def test_record_types_streamed(setup):
    # Same as test above except in_memory mode is not used, so that we can
    # test file streaming.
    os.environ["DBT_RECORDER_MODE"] = "Record"
    os.environ["DBT_RECORDER_TYPES"] = "TestRecord"
    recorder = Recorder(RecorderMode.RECORD, ["TestRecord"])
    set_invocation_context({})
    get_invocation_context().recorder = recorder

    @record_function(TestRecord)
    def test_func(a: int, b: str, c: Optional[str] = None) -> str:
        return str(a) + b + (c if c else "")

    @record_function(NotTestRecord)
    def not_test_func(a: int, b: str, c: Optional[str] = None) -> str:
        return str(a) + b + (c if c else "")

    test_func(123, "abc")
    not_test_func(456, "def")

    recorder.write()

    rec = {}
    with open("recording.json", "r") as f:
        rec = json.load(f)

    assert rec[-1]["params"] == {"a": 123, "b": "abc", "c": None}
    assert rec[-1]["result"] == {"return_val": "123abc"}
    assert NotTestRecord not in recorder._records_by_type

    assert recorder.in_memory_recording_size > 0


def test_decorator_replays(setup) -> None:
    os.environ["DBT_RECORDER_MODE"] = "Replay"
    os.environ["DBT_RECORDER_FILE_PATH"] = "record.json"
    recorder = Recorder(RecorderMode.REPLAY, None, in_memory=True)
    set_invocation_context({})
    get_invocation_context().recorder = recorder

    expected_record = TestRecord(
        params=TestRecordParams(123, "abc"), result=TestRecordResult("123abc")
    )

    recorder._records_by_type["TestRecord"] = [expected_record]

    @record_function(TestRecord)
    def test_func(a: int, b: str, c: Optional[str] = None) -> str:
        raise Exception("This should not actually be called")

    res = test_func(123, "abc")

    assert res == "123abc"


def test_nested_recording(setup) -> None:
    os.environ["DBT_RECORDER_MODE"] = "Record"
    recorder = Recorder(RecorderMode.RECORD, None, in_memory=True)
    set_invocation_context({})
    get_invocation_context().recorder = recorder

    @record_function(TestRecord)
    def inner_func(a: int, b: str) -> str:
        return str(a) + b

    @record_function(TestRecord)
    def outer_func(a: int, b: str) -> str:
        # This should record
        result1 = inner_func(a, b)
        # This should not record again since it's nested
        result2 = inner_func(a + 1, b)
        return result1 + result2

    outer_func(123, "abc")
    inner_func(1, "a")

    # Only two records should exist - one for inner_func and one for outter
    assert len(recorder._records_by_type["TestRecord"]) == 2

    # Verify the first record is from outer_func
    expected_outer = TestRecord(
        params=TestRecordParams(123, "abc"), result=TestRecordResult("123abc124abc")
    )
    assert recorder._records_by_type["TestRecord"][0].params == expected_outer.params
    assert recorder._records_by_type["TestRecord"][0].result == expected_outer.result

    # Verify the second record is from inner_func
    expected_inner = TestRecord(params=TestRecordParams(1, "a"), result=TestRecordResult("1a"))
    assert recorder._records_by_type["TestRecord"][1].params == expected_inner.params
    assert recorder._records_by_type["TestRecord"][1].result == expected_inner.result


def test_nested_recording_replay(setup) -> None:
    os.environ["DBT_RECORDER_MODE"] = "Replay"
    os.environ["DBT_RECORDER_FILE_PATH"] = "record.json"
    recorder = Recorder(RecorderMode.REPLAY, None)
    set_invocation_context({})
    get_invocation_context().recorder = recorder

    outer_record = TestRecord(
        params=TestRecordParams(123, "abc"), result=TestRecordResult("123abc124abc")
    )
    recorder._records_by_type["TestRecord"] = [outer_record]

    @record_function(TestRecord)
    def inner_func(a: int, b: str) -> str:
        raise Exception("This should not be called in replay mode")

    @record_function(TestRecord)
    def outer_func(a: int, b: str) -> str:
        result1 = inner_func(a, b)
        result2 = inner_func(a + 1, b)
        return result1 + result2

    result = outer_func(123, "abc")
    assert result == "123abc124abc"


def test_auto_decorator_records(setup) -> None:
    os.environ["DBT_RECORDER_MODE"] = "Record"
    recorder = Recorder(RecorderMode.RECORD, None, in_memory=True)
    set_invocation_context({})
    get_invocation_context().recorder = recorder

    @auto_record_function("TestAuto", index_on_thread_name=False, method=False)
    def test_func(a: int, b: str, c: Optional[str] = None) -> str:
        return str(a) + b + (c if c else "")

    test_func(123, "abc")

    assert recorder._records_by_type["TestAutoRecord"][-1].params.a == 123
    assert recorder._records_by_type["TestAutoRecord"][-1].params.b == "abc"
    assert recorder._records_by_type["TestAutoRecord"][-1].result.return_val == "123abc"

    assert recorder.in_memory_recording_size == sys.getsizeof(recorder._records_by_type["TestAutoRecord"][-1])


def test_recorded_function_with_override() -> None:
    os.environ["DBT_RECORDER_MODE"] = "Record"
    recorder = Recorder(RecorderMode.RECORD, None, in_memory=True)
    set_invocation_context({})
    get_invocation_context().recorder = recorder

    @supports_replay
    class Recordable:
        @auto_record_function("TestAuto")
        def test_func(self, a: int) -> int:
            return 2 * a

    class RecordableSubclass(Recordable):
        def test_func(self, a: int) -> int:
            return 3 * a

    class RecordableSubSubclass(RecordableSubclass):
        def test_func(self, a: int) -> int:
            return 4 * a

    rs = RecordableSubSubclass()

    rs.test_func(1)

    assert recorder._records_by_type["TestAutoRecord"][-1].params.a == 1
    assert recorder._records_by_type["TestAutoRecord"][-1].result.return_val == 4


class CustomType:
    def __init__(self, n: int):
        self.value = n


class CustomSerializationStrategy(SerializationStrategy):
    def serialize(self, obj: CustomType) -> int:
        return obj.value

    def deserialize(self, value: int) -> CustomType:
        return CustomType(value)


def test_recorded_with_custom_serializer() -> None:
    os.environ["DBT_RECORDER_MODE"] = "Record"
    recorder = Recorder(RecorderMode.RECORD, None)
    set_invocation_context({})
    get_invocation_context().recorder = recorder

    recorder.register_serialization_strategy(CustomType, CustomSerializationStrategy())

    @auto_record_function("TestAuto")
    def test_func(a: CustomType) -> CustomType:
        return CustomType(a.value * 2)

    test_func(CustomType(21))

    buffer = StringIO("")
    recorder.write_json(buffer)
    buffer.seek(0)
    recorder.load_json(buffer)


def test_record_classmethod() -> None:
    os.environ["DBT_RECORDER_MODE"] = "Record"
    recorder = Recorder(RecorderMode.RECORD, None, in_memory=True)
    set_invocation_context({})
    get_invocation_context().recorder = recorder

    @supports_replay
    class Recordable:
        @classmethod
        @auto_record_function("TestAuto")
        def test_func(cls, a: int) -> int:
            return 2 * a

    Recordable.test_func(1)

    assert recorder._records_by_type["TestAutoRecord"][-1].params.a == 1
    assert recorder._records_by_type["TestAutoRecord"][-1].result.return_val == 2


def test_record_classmethod_override() -> None:
    os.environ["DBT_RECORDER_MODE"] = "Record"
    recorder = Recorder(RecorderMode.RECORD, None, in_memory=True)
    set_invocation_context({})
    get_invocation_context().recorder = recorder

    @supports_replay
    class Recordable:
        # Static class variable facilitates checking that the recorded function
        # is called with the correct value of cls.
        static_val = "1"

        @classmethod
        @auto_record_function("TestAuto")
        def test_func(cls, a: int) -> str:
            return "1" + cls.static_val + str(a)

    class RecordableSubclass(Recordable):
        # This sub-class validates that recording works when there was
        # an override
        static_val = "2"

        @classmethod
        def test_func(cls, a: int) -> str:
            return "2" + cls.static_val + str(a)

    class RecordableSubSubclass(RecordableSubclass):
        # This sub-class validates that recording works when there was
        # a second override
        static_val = "3"

        @classmethod
        def test_func(cls, a: int) -> str:
            return "3" + cls.static_val + str(a)

    class RecordableSubclassNoDef(Recordable):
        # This sub-class validates that recording works when there was
        # no override

        # Mark this sub-sub-class with a unique value of static_val
        static_val = "4"

    class RecordableSubSubclassNoDef(RecordableSubclassNoDef):
        # This sub-class validates that recording works even when overriding
        # has "skipped" a generation"

        # Mark this sub-sub-class with a unique value of static_val
        static_val = "5"

        @classmethod
        def test_func(cls, a: int) -> str:
            return "5" + cls.static_val + str(a)

    Recordable.test_func(1)
    RecordableSubclass.test_func(2)
    RecordableSubSubclass.test_func(3)
    RecordableSubclassNoDef.test_func(4)
    RecordableSubSubclassNoDef.test_func(5)

    assert len(recorder._records_by_type["TestAutoRecord"]) == 5

    assert recorder._records_by_type["TestAutoRecord"][0].params.a == 1
    assert recorder._records_by_type["TestAutoRecord"][0].result.return_val == "111"
    a = recorder._records_by_type["TestAutoRecord"][0].seq
    assert recorder._records_by_type["TestAutoRecord"][1].params.a == 2
    assert recorder._records_by_type["TestAutoRecord"][1].result.return_val == "222"
    assert recorder._records_by_type["TestAutoRecord"][1].seq == a + 1
    assert recorder._records_by_type["TestAutoRecord"][2].params.a == 3
    assert recorder._records_by_type["TestAutoRecord"][2].result.return_val == "333"
    assert recorder._records_by_type["TestAutoRecord"][2].seq == a + 2
    assert recorder._records_by_type["TestAutoRecord"][3].params.a == 4
    assert recorder._records_by_type["TestAutoRecord"][3].result.return_val == "144"
    assert recorder._records_by_type["TestAutoRecord"][3].seq == a + 3
    assert recorder._records_by_type["TestAutoRecord"][4].params.a == 5
    assert recorder._records_by_type["TestAutoRecord"][4].result.return_val == "555"
    assert recorder._records_by_type["TestAutoRecord"][4].seq == a + 4


def test_record_override() -> None:
    os.environ["DBT_RECORDER_MODE"] = "Record"
    recorder = Recorder(RecorderMode.RECORD, None, in_memory=True)
    set_invocation_context({})
    get_invocation_context().recorder = recorder

    @supports_replay
    class Recordable:
        # Static class variable facilitates checking that the recorded function
        # is called with the correct value of cls.
        static_val = "1"

        @auto_record_function("TestAuto")
        def test_func(self, a: int) -> str:
            return "1" + self.static_val + str(a)

    class RecordableSubclass(Recordable):
        # This sub-class validates that recording works when there was
        # an override
        static_val = "2"

        def test_func(self, a: int) -> str:
            return "2" + self.static_val + str(a)

    class RecordableSubSubclass(RecordableSubclass):
        # This sub-class validates that recording works when there was
        # a second override
        static_val = "3"

        def test_func(self, a: int) -> str:
            return "3" + self.static_val + str(a)

    class RecordableSubclassNoDef(Recordable):
        # This sub-class validates that recording works when there was
        # no override

        # Mark this sub-sub-class with a unique value of static_val
        static_val = "4"

    class RecordableSubSubclassNoDef(RecordableSubclassNoDef):
        # This sub-class validates that recording works even when overriding
        # has "skipped" a generation"

        # Mark this sub-sub-class with a unique value of static_val
        static_val = "5"

        def test_func(self, a: int) -> str:
            return "5" + self.static_val + str(a)

    Recordable().test_func(1)
    RecordableSubclass().test_func(2)
    RecordableSubSubclass().test_func(3)
    RecordableSubclassNoDef().test_func(4)
    RecordableSubSubclassNoDef().test_func(5)

    assert len(recorder._records_by_type["TestAutoRecord"]) == 5

    assert recorder._records_by_type["TestAutoRecord"][0].params.a == 1
    assert recorder._records_by_type["TestAutoRecord"][0].result.return_val == "111"
    a = recorder._records_by_type["TestAutoRecord"][0].seq
    assert recorder._records_by_type["TestAutoRecord"][1].params.a == 2
    assert recorder._records_by_type["TestAutoRecord"][1].result.return_val == "222"
    assert recorder._records_by_type["TestAutoRecord"][1].seq == a + 1
    assert recorder._records_by_type["TestAutoRecord"][2].params.a == 3
    assert recorder._records_by_type["TestAutoRecord"][2].result.return_val == "333"
    assert recorder._records_by_type["TestAutoRecord"][2].seq == a + 2
    assert recorder._records_by_type["TestAutoRecord"][3].params.a == 4
    assert recorder._records_by_type["TestAutoRecord"][3].result.return_val == "144"
    assert recorder._records_by_type["TestAutoRecord"][3].seq == a + 3
    assert recorder._records_by_type["TestAutoRecord"][4].params.a == 5
    assert recorder._records_by_type["TestAutoRecord"][4].result.return_val == "555"
    assert recorder._records_by_type["TestAutoRecord"][4].seq == a + 4


def test_record_classmethod_override_by_non_classmethod() -> None:
    # Validate that when a classmethod is overriden by an instance method, recording
    # still works as best as can be expected.

    os.environ["DBT_RECORDER_MODE"] = "Record"
    recorder = Recorder(RecorderMode.RECORD, None, in_memory=True)
    set_invocation_context({})
    get_invocation_context().recorder = recorder

    @supports_replay
    class Recordable:
        # Static class variable facilitates checking that the recorded function
        # is called with the correct value of cls.
        static_val = "1"

        @classmethod
        @auto_record_function("TestAuto")
        def test_func(cls, a: int) -> str:
            return "1" + cls.static_val + str(a)

    class RecordableSubclass(Recordable):
        # This sub-class validates that recording works when there was
        # an override
        static_val = "2"

        def test_func(cls, a: int) -> str:
            return "2" + cls.static_val + str(a)

    Recordable.test_func(1)
    RecordableSubclass().test_func(2)

    assert len(recorder._records_by_type["TestAutoRecord"]) == 2

    assert recorder._records_by_type["TestAutoRecord"][0].params.a == 1
    assert recorder._records_by_type["TestAutoRecord"][0].result.return_val == "111"
    a = recorder._records_by_type["TestAutoRecord"][0].seq
    assert recorder._records_by_type["TestAutoRecord"][1].params.a == 2
    assert recorder._records_by_type["TestAutoRecord"][1].result.return_val == "222"
    assert recorder._records_by_type["TestAutoRecord"][1].seq == a + 1
