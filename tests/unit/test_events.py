import re
from argparse import Namespace
from typing import TypeVar

import pytest

# from dbt.adapters.events import types as adapter_types
from dbt_common.events.event_manager_client import ctx_set_event_manager
# from dbt.artifacts.schemas.results import TimingInfo, RunStatus
# from dbt.artifacts.schemas.run import RunResult
from dbt_common.events import types
# from dbt.adapters.events.logging import AdapterLogger
from dbt_common.events.base_types import msg_from_base_event
# from dbt.events import types as core_types
from dbt_common.events.base_types import (
    BaseEvent,
    DebugLevel,
    DynamicLevel,
    ErrorLevel,
    InfoLevel,
    TestLevel,
    WarnLevel,
)
from dbt_common.events.event_manager import TestEventManager, EventManager
from dbt_common.events.functions import msg_to_dict, msg_to_json


# takes in a class and finds any subclasses for it
def get_all_subclasses(cls):
    all_subclasses = []
    for subclass in cls.__subclasses__():
        if subclass not in [TestLevel, DebugLevel, WarnLevel, InfoLevel, ErrorLevel, DynamicLevel]:
            all_subclasses.append(subclass)
        all_subclasses.extend(get_all_subclasses(subclass))
    return set(all_subclasses)


class TestEventCodes:

    # checks to see if event codes are duplicated to keep codes singluar and clear.
    # also checks that event codes follow correct namming convention ex. E001
    def test_event_codes(self):
        all_concrete = get_all_subclasses(BaseEvent)
        all_codes = set()

        for event_cls in all_concrete:
            code = event_cls.code(event_cls)
            # must be in the form 1 capital letter, 3 digits
            assert re.match("^[A-Z][0-9]{3}", code)
            # cannot have been used already
            assert (
                code not in all_codes
            ), f"{code} is assigned more than once. Check types.py for duplicates."
            all_codes.add(code)


sample_values = [
    # N.B. Events instantiated here include the module prefix in order to
    # avoid having the entire list twice in the code.
    # M - Deps generation ======================
    types.RetryExternalCall(attempt=0, max=0),
    types.RecordRetryException(exc=""),
    # Z - misc ======================
    types.SystemCouldNotWrite(path="", reason="", exc=""),
    types.SystemExecutingCmd(cmd=[""]),
    types.SystemStdOut(bmsg=str(b"")),
    types.SystemStdErr(bmsg=str(b"")),
    types.SystemReportReturnCode(returncode=0),
    types.Formatting(),
    types.Note(msg="This is a note."),
]


class TestEventJSONSerialization:

    # attempts to test that every event is serializable to json.
    # event types that take `Any` are not possible to test in this way since some will serialize
    # just fine and others won't.
    def test_all_serializable(self):
        all_non_abstract_events = set(
            get_all_subclasses(BaseEvent),
        )
        all_event_values_list = list(map(lambda x: x.__class__, sample_values))
        diff = all_non_abstract_events.difference(set(all_event_values_list))
        assert (
            not diff
        ), f"{diff}test is missing concrete values in `sample_values`. Please add the values for the aforementioned event classes"

        # make sure everything in the list is a value not a type
        for event in sample_values:
            assert type(event) != type

        # if we have everything we need to test, try to serialize everything
        count = 0
        for event in sample_values:
            msg = msg_from_base_event(event)
            print(f"--- msg: {msg.info.name}")
            # Serialize to dictionary
            try:
                msg_to_dict(msg)
            except Exception as e:
                raise Exception(
                    f"{event} can not be converted to a dict. Originating exception: {e}"
                )
            # Serialize to json
            try:
                msg_to_json(msg)
            except Exception as e:
                raise Exception(f"{event} is not serializable to json. Originating exception: {e}")
            # Serialize to binary
            try:
                msg.SerializeToString()
            except Exception as e:
                raise Exception(
                    f"{event} is not serializable to binary protobuf. Originating exception: {e}"
                )
            count += 1
        print(f"--- Found {count} events")


def test_bad_serialization():
    """Tests that bad serialization enters the proper exception handling

    When pytest is in use the exception handling of `BaseEvent` raises an
    exception. When pytest isn't present, it fires a Note event. Thus to test
    that bad serializations are properly handled, the best we can do is test
    that the exception handling path is used.
    """

    with pytest.raises(Exception) as excinfo:
        types.Note(param_event_doesnt_have="This should break")

    assert (
        str(excinfo.value)
        == "[Note]: Unable to parse dict {'param_event_doesnt_have': 'This should break'}"
    )
