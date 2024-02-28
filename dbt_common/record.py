"""The record module provides a mechanism for recording dbt's interaction with
external systems during a command invocation, so that the command can be re-run
later with the recording 'replayed' to dbt.

If dbt behaves sufficiently deterministically, we will be able to use the
record/replay mechanism in several interesting test and debugging scenarios.
"""
import functools
import dataclasses
import json
import os
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Type

from dbt_common.context import get_invocation_context


class Record:
    """An instance of this abstract Record class represents a request made by dbt
    to an external process or the operating system. The 'params' are the arguments
    to the request, and the 'result' is what is returned."""

    params_cls: type
    result_cls: Optional[type]

    def __init__(self, params, result) -> None:
        self.params = params
        self.result = result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "params": self.params._to_dict() if hasattr(self.params, "_to_dict") else dataclasses.asdict(self.params),  # type: ignore
            "result": self.result._to_dict() if hasattr(self.result, "_to_dict") else dataclasses.asdict(self.result) if self.result is not None else None,  # type: ignore
        }

    @classmethod
    def from_dict(cls, dct: Mapping) -> "Record":
        p = (
            cls.params_cls._from_dict(dct["params"])
            if hasattr(cls.params_cls, "_from_dict")
            else cls.params_cls(**dct["params"])
        )
        r = (
            cls.result_cls._from_dict(dct["result"])  # type: ignore
            if hasattr(cls.result_cls, "_from_dict")
            else cls.result_cls(**dct["result"])
            if cls.result_cls is not None
            else None
        )
        return cls(params=p, result=r)


class Diff:
    """Marker class for diffs?"""

    pass


class RecorderMode(Enum):
    RECORD = 1
    REPLAY = 2


class Recorder:
    _record_cls_by_name: Dict[str, Type] = {}
    _record_name_by_params_name: Dict[str, str] = {}

    def __init__(self, mode: RecorderMode, recording_path: Optional[str] = None) -> None:
        self.mode = mode
        self._records_by_type: Dict[str, List[Record]] = {}
        self._replay_diffs: List["Diff"] = []

        if recording_path is not None:
            self._records_by_type = self.load(recording_path)

    @classmethod
    def register_record_type(cls, rec_type) -> Any:
        cls._record_cls_by_name[rec_type.__name__] = rec_type
        cls._record_name_by_params_name[rec_type.params_cls.__name__] = rec_type.__name__
        return rec_type

    def add_record(self, record: Record) -> None:
        rec_cls_name = record.__class__.__name__  # type: ignore
        if rec_cls_name not in self._records_by_type:
            self._records_by_type[rec_cls_name] = []
        self._records_by_type[rec_cls_name].append(record)

    def pop_matching_record(self, params: Any) -> Optional[Record]:
        rec_type_name = self._record_name_by_params_name[type(params).__name__]
        records = self._records_by_type[rec_type_name]
        match: Optional[Record] = None
        for rec in records:
            if rec.params == params:
                match = rec
                records.remove(match)
                break

        return match

    def write(self, file_name) -> None:
        with open(file_name, "w") as file:
            json.dump(self._to_dict(), file)

    def _to_dict(self) -> Dict:
        dct: Dict[str, Any] = {}

        for record_type in self._records_by_type:
            record_list = [r.to_dict() for r in self._records_by_type[record_type]]
            dct[record_type] = record_list

        return dct

    @classmethod
    def load(cls, file_name: str) -> Dict[str, List[Record]]:
        with open(file_name) as file:
            loaded_dct = json.load(file)

        records_by_type: Dict[str, List[Record]] = {}

        for record_type_name in loaded_dct:
            record_cls = cls._record_cls_by_name[record_type_name]
            rec_list = []
            for record_dct in loaded_dct[record_type_name]:
                rec = record_cls.from_dict(record_dct)
                rec_list.append(rec)  # type: ignore
            records_by_type[record_type_name] = rec_list

        return records_by_type

    def expect_record(self, params: Any) -> Any:
        record = self.pop_matching_record(params)

        if record is None:
            raise Exception()

        result_tuple = dataclasses.astuple(record.result)
        return result_tuple[0] if len(result_tuple) == 1 else result_tuple

    def write_diffs(self, diff_file_name) -> None:
        json.dump(
            self._replay_diffs,
            open(diff_file_name, "w"),
        )

    def print_diffs(self) -> None:
        print(repr(self._replay_diffs))


def get_record_mode_from_env() -> Optional[RecorderMode]:
    replay_val = os.environ.get("DBT_REPLAY")
    if replay_val is not None and replay_val != "0" and replay_val.lower() != "false":
        return RecorderMode.REPLAY

    record_val = os.environ.get("DBT_RECORD")
    if record_val is not None and record_val != "0" and record_val.lower() != "false":
        return RecorderMode.RECORD

    return None


def record_function(record_type, method=False, tuple_result=False):
    def record_function_inner(func_to_record):
        # To avoid runtime overhead and other unpleasantness, we only apply the
        # record/replay decorator if a relevant env var is set.
        if get_record_mode_from_env() is None:
            return func_to_record

        @functools.wraps(func_to_record)
        def record_replay_wrapper(*args, **kwargs):
            recorder: Recorder = None
            try:
                recorder = get_invocation_context().recorder
            except LookupError:
                pass

            if recorder is None:
                return func_to_record(*args, **kwargs)

            # For methods, peel off the 'self' argument before calling the
            # params constructor.
            param_args = args[1:] if method else args

            params = record_type.params_cls(*param_args, **kwargs)

            include = True
            if hasattr(params, "_include"):
                include = params._include()

            if not include:
                return func_to_record(*args, **kwargs)

            if recorder.mode == RecorderMode.REPLAY:
                return recorder.expect_record(params)

            r = func_to_record(*args, **kwargs)
            result = (
                None
                if r is None or record_type.result_cls is None
                else record_type.result_cls(*r)
                if tuple_result
                else record_type.result_cls(r)
            )
            recorder.add_record(record_type(params=params, result=result))
            return r

        return record_replay_wrapper

    return record_function_inner
