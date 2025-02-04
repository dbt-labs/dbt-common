"""The record module provides a record/replay mechanism for recording dbt's
interactions with external systems during a command invocation, so that the
command can be re-run later with the recording 'replayed' to dbt.

The rationale for and architecture of this module are described in detail in the
docs/guides/record_replay.md document in this repository.
"""
import functools
import dataclasses
import inspect
import json
import os

from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, TextIO, Tuple, Type
import contextvars

from mashumaro import field_options
from mashumaro.mixins.json import DataClassJSONMixin
from mashumaro.types import SerializationStrategy

RECORDED_BY_HIGHER_FUNCTION = contextvars.ContextVar("RECORDED_BY_HIGHER_FUNCTION", default=False)


class Record:
    """An instance of this abstract Record class represents a request made by dbt
    to an external process or the operating system. The 'params' are the arguments
    to the request, and the 'result' is what is returned."""

    params_cls: type
    result_cls: Optional[type] = None
    group: Optional[str] = None

    def __init__(self, params, result) -> None:
        self.params = params
        self.result = result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "params": self.params._to_dict()
            if hasattr(self.params, "_to_dict")
            else dataclasses.asdict(self.params),
            "result": self.result._to_dict()
            if hasattr(self.result, "_to_dict")
            else dataclasses.asdict(self.result)
            if self.result is not None
            else None,
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
    def __init__(self, current_recording_path: str, previous_recording_path: str) -> None:
        # deepdiff is expensive to import, so we only do it here when we need it
        from deepdiff import DeepDiff  # type: ignore

        self.diff = DeepDiff

        self.current_recording_path = current_recording_path
        self.previous_recording_path = previous_recording_path

    def diff_query_records(self, current: List, previous: List) -> Dict[str, Any]:
        # some of the table results are returned as a stringified list of dicts that don't
        # diff because order isn't consistent. convert it into a list of dicts so it can
        # be diffed ignoring order

        for i in range(len(current)):
            if current[i].get("result").get("table") is not None:
                current[i]["result"]["table"] = json.loads(current[i]["result"]["table"])
        for i in range(len(previous)):
            if previous[i].get("result").get("table") is not None:
                previous[i]["result"]["table"] = json.loads(previous[i]["result"]["table"])

        return self.diff(previous, current, ignore_order=True, verbose_level=2)

    def diff_env_records(self, current: List, previous: List) -> Dict[str, Any]:
        # The mode and filepath may change.  Ignore them.

        exclude_paths = [
            "root[0]['result']['env']['DBT_RECORDER_FILE_PATH']",
            "root[0]['result']['env']['DBT_RECORDER_MODE']",
        ]

        return self.diff(
            previous, current, ignore_order=True, verbose_level=2, exclude_paths=exclude_paths
        )

    def diff_default(self, current: List, previous: List) -> Dict[str, Any]:
        return self.diff(previous, current, ignore_order=True, verbose_level=2)

    def calculate_diff(self) -> Dict[str, Any]:
        with open(self.current_recording_path) as current_recording:
            current_dct = json.load(current_recording)

        with open(self.previous_recording_path) as previous_recording:
            previous_dct = json.load(previous_recording)

        diff = {}
        for record_type in current_dct:
            if record_type == "QueryRecord":
                diff[record_type] = self.diff_query_records(
                    current_dct[record_type], previous_dct[record_type]
                )
            elif record_type == "GetEnvRecord":
                diff[record_type] = self.diff_env_records(
                    current_dct[record_type], previous_dct[record_type]
                )
            else:
                diff[record_type] = self.diff_default(
                    current_dct[record_type], previous_dct[record_type]
                )

        return diff


class RecorderMode(Enum):
    RECORD = 1
    REPLAY = 2
    DIFF = 3  # records and does diffing


class Recorder:
    _record_cls_by_name: Dict[str, Type] = {}
    _record_name_by_params_name: Dict[str, str] = {}
    _auto_serialization_strategies: Dict[Type, SerializationStrategy] = {}

    def __init__(
        self,
        mode: RecorderMode,
        types: Optional[List],
        current_recording_path: str = "recording.json",
        previous_recording_path: Optional[str] = None,
    ) -> None:
        self.mode = mode
        self.recorded_types = types
        self._records_by_type: Dict[str, List[Record]] = {}
        self._unprocessed_records_by_type: Dict[str, List[Dict[str, Any]]] = {}
        self._replay_diffs: List["Diff"] = []
        self.diff: Optional[Diff] = None
        self.previous_recording_path = previous_recording_path
        self.current_recording_path = current_recording_path

        if self.previous_recording_path is not None and self.mode in (
            RecorderMode.REPLAY,
            RecorderMode.DIFF,
        ):
            self.diff = Diff(
                current_recording_path=self.current_recording_path,
                previous_recording_path=self.previous_recording_path,
            )

            if self.mode == RecorderMode.REPLAY:
                self._unprocessed_records_by_type = self.load(self.previous_recording_path)

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
        rec_type_name = self._record_name_by_params_name.get(type(params).__name__)

        if rec_type_name is None:
            raise Exception(
                f"A record of type {type(params).__name__} was requested, but no such type has been registered."
            )

        self._ensure_records_processed(rec_type_name)
        records = self._records_by_type[rec_type_name]
        match: Optional[Record] = None
        for rec in records:
            if rec.params == params:
                match = rec
                records.remove(match)
                break

        return match

    def write_json(self, out_stream: TextIO):
        d = self._to_dict()
        json.dump(d, out_stream)

    def write(self) -> None:
        with open(self.current_recording_path, "w") as file:
            self.write_json(file)

    def _to_dict(self) -> Dict:
        dct: Dict[str, Any] = {}

        for record_type in self._records_by_type:
            record_list = [r.to_dict() for r in self._records_by_type[record_type]]
            dct[record_type] = record_list

        return dct

    @classmethod
    def load(cls, file_name: str) -> Dict[str, List[Dict[str, Any]]]:
        with open(file_name) as file:
            return cls.load_json(file)

    @classmethod
    def load_json(cls, in_stream: TextIO) -> Dict[str, List[Dict[str, Any]]]:
        return json.load(in_stream)

    def _ensure_records_processed(self, record_type_name: str) -> None:
        if record_type_name in self._records_by_type:
            return

        rec_list = []
        record_cls = self._record_cls_by_name[record_type_name]
        for record_dct in self._unprocessed_records_by_type[record_type_name]:
            rec = record_cls.from_dict(record_dct)
            rec_list.append(rec)  # type: ignore
        self._records_by_type[record_type_name] = rec_list

    def expect_record(self, params: Any) -> Any:
        record = self.pop_matching_record(params)

        if record is None:
            raise Exception()

        if record.result is None:
            return None

        result_tuple = dataclasses.astuple(record.result)
        return result_tuple[0] if len(result_tuple) == 1 else result_tuple

    def write_diffs(self, diff_file_name) -> None:
        assert self.diff is not None
        with open(diff_file_name, "w") as f:
            json.dump(self.diff.calculate_diff(), f)

    def print_diffs(self) -> None:
        assert self.diff is not None
        print(repr(self.diff.calculate_diff()))

    @classmethod
    def register_serialization_strategy(
        cls, t: Type, serialization_strategy: SerializationStrategy
    ) -> None:
        cls._auto_serialization_strategies[t] = serialization_strategy


def get_record_mode_from_env() -> Optional[RecorderMode]:
    """
    Get the record mode from the environment variables.

    If the mode is not set to 'RECORD', 'DIFF' or 'REPLAY', return None.
    Expected format: 'DBT_RECORDER_MODE=RECORD'
    """
    record_mode = os.environ.get("DBT_RECORDER_MODE")

    if record_mode is None:
        return None

    if record_mode.lower() == "record":
        return RecorderMode.RECORD
    # diffing requires a file path, otherwise treat as noop
    elif record_mode.lower() == "diff" and os.environ.get("DBT_RECORDER_FILE_PATH") is not None:
        return RecorderMode.DIFF
    # replaying requires a file path, otherwise treat as noop
    elif record_mode.lower() == "replay" and os.environ.get("DBT_RECORDER_FILE_PATH") is not None:
        return RecorderMode.REPLAY

    # if you don't specify record/replay it's a noop
    return None


def get_record_types_from_env() -> Optional[List]:
    """
    Get the record subset from the environment variables.

    If no types are provided, there will be no filtering.
    Invalid types will be ignored.
    Expected format: 'DBT_RECORDER_TYPES=Database,FileLoadRecord'
    """
    record_types_str = os.environ.get("DBT_RECORDER_TYPES")

    # if all is specified we don't want any type filtering
    if record_types_str is None or record_types_str.lower == "all":
        return None

    return record_types_str.split(",")


def get_record_types_from_dict(fp: str) -> List:
    """Get the record subset from the dict."""
    with open(fp) as file:
        loaded_dct = json.load(file)
    return list(loaded_dct.keys())


def auto_record_function(
    record_name: str,
    method: bool = True,
    group: Optional[str] = None,
    index_on_thread_name: bool = True,
) -> Callable:
    """This is the @auto_record_function decorator. It works in a similar way to
    the @record_function decorator, except automatically generates boilerplate
    classes for the Record, Params, and Result classes which would otherwise be
    needed. That makes it suitable for quickly adding record support to simple
    functions with simple parameters."""
    return functools.partial(
        _record_function_inner,
        record_name,
        method,
        False,
        None,
        group,
        index_on_thread_name,
        False,
    )


def record_function(
    record_type,
    method: bool = False,
    tuple_result: bool = False,
    id_field_name: Optional[str] = None,
) -> Callable:
    """This is the @record_function decorator, which marks functions which will
    have their function calls recorded during record mode, and mocked out with
    previously recorded replay data during replay."""
    return functools.partial(
        _record_function_inner,
        record_type,
        method,
        tuple_result,
        id_field_name,
        None,
        False,
        False,
    )


def _get_arg_fields(
    spec: inspect.FullArgSpec,
    skip_first: bool = False,
) -> List[Tuple[str, Optional[Type], dataclasses.Field]]:
    arg_fields = []
    defaults = len(spec.defaults) if spec.defaults else 0
    for i, arg_name in enumerate(spec.args):
        if skip_first and i == 0:
            continue
        annotation = spec.annotations.get(arg_name)
        if annotation is None:
            raise Exception("Recorded functions must have type annotations.")
        field = _get_field(arg_name, annotation)
        if i >= len(spec.args) - defaults:
            field[2].default = (
                spec.defaults[i - len(spec.args) + defaults] if spec.defaults else None
            )
        arg_fields.append(field)
    return arg_fields


def _get_field(field_name: str, t: Type) -> Tuple[str, Optional[Type], dataclasses.Field]:
    dc_field: dataclasses.Field = dataclasses.field()
    strat = Recorder._auto_serialization_strategies.get(t)
    if strat is not None:
        dc_field.metadata = field_options(serialization_strategy=Recorder._auto_serialization_strategies[t])  # type: ignore

    return field_name, t, dc_field


@dataclasses.dataclass
class AutoValues(DataClassJSONMixin):
    def _to_dict(self):
        return self.to_dict()

    def _from_dict(self, data):
        return self.from_dict(data)


def _record_function_inner(
    record_type,
    method,
    tuple_result,
    id_field_name,
    group,
    index_on_thread_id,
    is_classmethod,
    func_to_record,
):
    if isinstance(record_type, str):
        return_type = inspect.signature(func_to_record).return_annotation
        fields = _get_arg_fields(inspect.getfullargspec(func_to_record), method)
        if index_on_thread_id:
            id_field_name = "thread_id"
            fields.insert(0, _get_field("thread_id", str))
        params_cls = dataclasses.make_dataclass(
            f"{record_type}Params", fields, bases=(AutoValues,)
        )
        result_cls = (
            None
            if return_type is None or return_type == inspect._empty
            else dataclasses.make_dataclass(
                f"{record_type}Result",
                [_get_field("return_val", return_type)],
                bases=(AutoValues,),
            )
        )

        record_type = type(
            f"{record_type}Record",
            (Record,),
            {"params_cls": params_cls, "result_cls": result_cls, "group": group},
        )

        Recorder.register_record_type(record_type)

    @functools.wraps(func_to_record)
    def record_replay_wrapper(*args, **kwargs) -> Any:
        recorder: Optional[Recorder] = None
        try:
            from dbt_common.context import get_invocation_context

            recorder = get_invocation_context().recorder
        except LookupError:
            pass

        call_args = args[1:] if is_classmethod else args

        if recorder is None:
            return func_to_record(*call_args, **kwargs)

        if recorder.recorded_types is not None and not (
            record_type.__name__ in recorder.recorded_types
            or record_type.group in recorder.recorded_types
        ):
            return func_to_record(*call_args, **kwargs)

        # For methods, peel off the 'self' argument before calling the
        # params constructor.
        param_args = args[1:] if method else args
        if method and id_field_name is not None:
            if index_on_thread_id:
                from dbt_common.context import get_invocation_context

                param_args = (get_invocation_context().name,) + param_args
            else:
                param_args = (getattr(args[0], id_field_name),) + param_args

        params = record_type.params_cls(*param_args, **kwargs)

        include = True
        if hasattr(params, "_include"):
            include = params._include()

        if not include:
            return func_to_record(*call_args, **kwargs)

        if recorder.mode == RecorderMode.REPLAY:
            return recorder.expect_record(params)
        if RECORDED_BY_HIGHER_FUNCTION.get():
            return func_to_record(*call_args, **kwargs)

        RECORDED_BY_HIGHER_FUNCTION.set(True)
        r = func_to_record(*call_args, **kwargs)
        result = (
            None
            if record_type.result_cls is None
            else record_type.result_cls(*r)
            if tuple_result
            else record_type.result_cls(r)
        )
        RECORDED_BY_HIGHER_FUNCTION.set(False)
        recorder.add_record(record_type(params=params, result=result))
        return r

    setattr(
        record_replay_wrapper,
        "_record_metadata",
        {
            "record_type": record_type,
            "method": method,
            "tuple_result": tuple_result,
            "id_field_name": id_field_name,
            "group": group,
            "index_on_thread_id": index_on_thread_id,
        },
    )

    return record_replay_wrapper


def _is_classmethod(method):
    b = inspect.ismethod(method) and isinstance(method.__self__, type)
    return b


def supports_replay(cls):
    """Class decorator which adds record/replay support for a class. In particular,
    this decorator ensures that calls to overriden functions are still recorded."""

    # When record/replay is inactive, do nothing.
    if get_record_mode_from_env() is None:
        return cls

    # Replace the __init_subclass__ method of this class so that when it
    # is subclassed, methods on the new subclass which override recorded
    # functions are modified to be recorded as well.
    original_init_subclass = cls.__init_subclass__

    @classmethod
    def wrapping_init_subclass(sub_cls):
        for method_name in dir(cls):
            method = getattr(cls, method_name)
            metadata = getattr(method, "_record_metadata", None)
            if method and getattr(method, "_record_metadata", None):
                sub_method = getattr(sub_cls, method_name, None)
                recorded_sub_method = _record_function_inner(
                    metadata["record_type"],
                    metadata["method"],
                    metadata["tuple_result"],
                    metadata["id_field_name"],
                    metadata["group"],
                    metadata["index_on_thread_id"],
                    _is_classmethod(method),
                    sub_method,
                )

                if _is_classmethod(method):
                    recorded_sub_method = classmethod(recorded_sub_method)

                if sub_method is not None:
                    setattr(
                        sub_cls,
                        method_name,
                        recorded_sub_method,
                    )

        original_init_subclass()

    cls.__init_subclass__ = wrapping_init_subclass

    return cls
