import dataclasses
import os
import pytest
from typing import Optional

from dbt_common.context import set_invocation_context, get_invocation_context
from dbt_common.record import record_function, Record, Recorder, RecorderMode


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


def test_decorator_records(setup):
    os.environ["DBT_RECORDER_MODE"] = "Record"
    recorder = Recorder(RecorderMode.RECORD, None)
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

    expected_record = TestRecord(
        params=TestRecordParams(123, "abc"), result=TestRecordResult("123abc")
    )

    assert recorder._records_by_type["TestRecord"][-1].params == expected_record.params
    assert recorder._records_by_type["TestRecord"][-1].result == expected_record.result
    assert NotTestRecord not in recorder._records_by_type


def test_decorator_replays(setup):
    os.environ["DBT_RECORDER_MODE"] = "Replay"
    os.environ["DBT_RECORDER_FILE_PATH"] = "record.json"
    recorder = Recorder(RecorderMode.REPLAY, None)
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
