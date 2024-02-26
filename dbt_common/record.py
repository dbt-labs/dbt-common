"""The record module provides a mechanism for recording dbt's interaction with
external systems during a command invocation, so that the command can be re-run
later with the recording 'replayed' to dbt.

If dbt behaves sufficiently deterministically, we will be able to use the
record/replay mechanism in several interesting test and debugging scenarios.
"""
import functools
import dataclasses
import json
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
            "params": self.params.to_dict() if hasattr(self.params, "to_dict") else dataclasses.asdict(self.params),  # type: ignore
            "result": self.result.to_dict() if hasattr(self.result, "to_dict") else dataclasses.asdict(self.result) if self.result is not None else None,  # type: ignore
        }

    @classmethod
    def from_dict(cls, dct: Mapping) -> "Record":
        p = cls.params_cls(**dct["params"])
        r = cls.result_cls(**dct["result"]) if cls.result_cls is not None else None
        return cls(params=p, result=r)


class RecorderMode(Enum):
    RECORD = 1
    REPLAY = 2


class Recorder:
    _record_cls_by_name: Dict[str, Type] = {}
    _record_name_by_params_type: Dict[type, str] = {}

    def __init__(self, mode: RecorderMode, recording_path: Optional[str] = None) -> None:
        self.mode = mode
        self._records_by_type: Dict[str, List[Record]] = {}

        if recording_path is not None:
            self._records_by_type = self.load(recording_path)

    @classmethod
    def register_record_type(cls, rec_type) -> Any:
        rec_name = rec_type.__name__
        cls._record_cls_by_name[rec_name] = rec_type
        cls._record_name_by_params_type[rec_name] = rec_type.params_cls
        return rec_type

    def add_record(self, record: Record) -> None:
        rec_cls_name = record.__class__.__name__  # type: ignore
        if rec_cls_name not in self._records_by_type:
            self._records_by_type[rec_cls_name] = []
        self._records_by_type[rec_cls_name].append(record)

    def pop_record(self, params: Any) -> Optional[Record]:
        rec_type_name = self._record_name_by_params_type[type(params)]
        records = self._records_by_type[rec_type_name]
        if len(records) > 0 and records[0].params == params:
            r = records[0]
            records.pop(0)
            return r
        else:
            return None

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
                rec_list.append(record_cls.from_dict(record_dct))  # type: ignore
            records_by_type[record_type_name] = rec_list

        return records_by_type

    def expect_record(self, params: Any) -> Any:
        record = self.recording.pop_record(params)

        if record is None:
            raise Exception()

        return record.result.contents

    def write_diffs(self, diff_file_name) -> None:
        json.dump(
            self._diffs,
            open(diff_file_name, "w"),
        )
        self.print_diffs()

    def print_diffs(self) -> None:
        print(repr(self._diffs))


@dataclasses.dataclass
class LoadFileParams:
    path: str
    strip: bool = True

    def _include(self, path: str, strip: bool = True):
        # Do not record or replay file reads that were performed against files
        # which are actually part of dbt's implementation.
        return (
            "dbt/include/global_project" not in path
            and "/plugins/postgres/dbt/include/" not in path
        )


@dataclasses.dataclass
class LoadFileResult:
    contents: str


@Recorder.register_record_type
class LoadFileRecord(Record):
    """Record of file load operation"""

    params_cls = LoadFileParams
    result_cls = LoadFileResult


@dataclasses.dataclass
class WriteFileParams:
    path: str
    contents: str

    def _include(self, path: str, contents: str):
        # Do not record or replay file reads that were performed against files
        # which are actually part of dbt's implementation.
        return (
            "dbt/include/global_project" not in path
            and "/plugins/postgres/dbt/include/" not in path
        )


@Recorder.register_record_type
class WriteFileRecord(Record):
    """Record of a file write operation."""

    params_cls = WriteFileParams
    result_cls = None


@dataclasses.dataclass
class FindMatchingParams:
    root_path: str
    relative_paths_to_search: List[str]
    file_pattern: str
    # ignore_spec: Optional[PathSpec] = None

    def __init__(
        self,
        root_path: str,
        relative_paths_to_search: List[str],
        file_pattern: str,
        ignore_spec: Optional[Any] = None,
    ):
        self.root_path = root_path
        self.relative_paths_to_search = relative_paths_to_search
        self.file_pattern = file_pattern

    def _include(
        self,
        root_path: str,
        relative_paths_to_search: List[str],
        file_pattern: str,
        ignore_spec: Optional[Any] = None,
    ):
        # Do not record or replay filesystem searches that were performed against
        # files which are actually part of dbt's implementation.
        return (
            "dbt/include/global_project" not in root_path
            and "/plugins/postgres/dbt/include/" not in root_path
        )


@dataclasses.dataclass
class FindMatchingResult:
    matches: List[Dict[str, Any]]


@Recorder.register_record_type
class FindMatchingRecord(Record):
    """Record of calls to the directory search function find_matching()"""

    params_cls = FindMatchingParams
    result_cls = FindMatchingResult


@dataclasses.dataclass
class GetEnvParams:
    pass


@dataclasses.dataclass
class GetEnvResult:
    env: Dict[str, str]


@Recorder.register_record_type
class GetEnvRecord(Record):
    params_cls = GetEnvParams
    result_cls = GetEnvResult


class Diff:
    pass


@dataclasses.dataclass
class UnexpectedQueryDiff(Diff):
    sql: str
    node_unique_id: str


@dataclasses.dataclass
class FileWriteDiff(Diff):
    path: str
    recorded_contents: str
    replay_contents: str


@dataclasses.dataclass
class UnexpectedFileWriteDiff(Diff):
    path: str
    contents: str


def record_function(record_type):
    def record_function_inner(func_to_record):
        @functools.wraps(func_to_record)
        def record_replay_wrapper(*args, **kwargs):
            recorder: Recorder = None
            try:
                recorder = get_invocation_context().recorder
            except LookupError:
                pass

            if recorder is None:
                return func_to_record(*args, **kwargs)

            params = record_type.params_cls(*args, **kwargs)

            include = True
            if hasattr(params, "_include"):
                include = params._include(*args, **kwargs)

            if not include:
                return func_to_record(*args, **kwargs)

            if recorder.mode == RecorderMode.REPLAY:
                return recorder.expect_record(params)

            r = func_to_record(*args, **kwargs)
            result = record_type.result_cls(r)
            recorder.add_record(record_type(params=params, result=result))
            return r

        return record_replay_wrapper

    return record_function_inner
