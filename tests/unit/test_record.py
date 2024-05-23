import dataclasses
import os
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


def test_decorator_records():
    prev = os.environ.get("DBT_RECORDER_MODE", None)
    try:
        os.environ["DBT_RECORDER_MODE"] = "Record"
        recorder = Recorder(RecorderMode.RECORD)
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

    finally:
        if prev is None:
            os.environ.pop("DBT_RECORDER_MODE", None)
        else:
            os.environ["DBT_RECORDER_MODE"] = prev


def test_decorator_replays():
    prev = os.environ.get("DBT_RECORDER_MODE", None)
    try:
        os.environ["DBT_RECORDER_MODE"] = "Replay"
        recorder = Recorder(RecorderMode.REPLAY)
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

    finally:
        if prev is None:
            os.environ.pop("DBT_RECORDER_MODE", None)
        else:
            os.environ["DBT_RECORDER_MODE"] = prev
