from dbt_common.events.functions import msg_to_dict, msg_to_json, reset_metadata_vars
from dbt_common.events import types_pb2
from dbt_common.events.base_types import msg_from_base_event
from dbt_common.events.types import RetryExternalCall
from google.protobuf.json_format import MessageToDict

info_keys = {
    "name",
    "code",
    "msg",
    "level",
    "invocation_id",
    "pid",
    "thread",
    "ts",
    "extra",
    "category",
}


def test_events():
    # M020 event
    event_code = "M020"
    event = RetryExternalCall(attempt=3, max=5)
    msg = msg_from_base_event(event)
    msg_dict = msg_to_dict(msg)
    msg_json = msg_to_json(msg)
    serialized = msg.SerializeToString()
    assert "Retrying external call. Attempt: 3" in str(serialized)
    assert set(msg_dict.keys()) == {"info", "data"}
    assert set(msg_dict["data"].keys()) == {"attempt", "max"}
    assert set(msg_dict["info"].keys()) == info_keys
    assert msg_json
    assert msg.info.code == event_code

    # Extract EventInfo from serialized message
    generic_msg = types_pb2.GenericMessage()
    generic_msg.ParseFromString(serialized)
    assert generic_msg.info.code == event_code
    # get the message class for the real message from the generic message
    message_class = getattr(types_pb2, f"{generic_msg.info.name}Msg")
    new_msg = message_class()
    new_msg.ParseFromString(serialized)
    assert new_msg.info.code == msg.info.code
    assert new_msg.data.attempt == msg.data.attempt


def test_extra_dict_on_event(monkeypatch):
    monkeypatch.setenv("DBT_ENV_CUSTOM_ENV_env_key", "env_value")

    reset_metadata_vars()

    event_code = "M020"
    event = RetryExternalCall(attempt=3, max=5)
    msg = msg_from_base_event(event)
    msg_dict = msg_to_dict(msg)
    assert set(msg_dict["info"].keys()) == info_keys
    extra_dict = {"env_key": "env_value"}
    assert msg.info.extra == extra_dict
    serialized = msg.SerializeToString()

    # Extract EventInfo from serialized message
    generic_msg = types_pb2.GenericMessage()
    generic_msg.ParseFromString(serialized)
    assert generic_msg.info.code == event_code
    # get the message class for the real message from the generic message
    message_class = getattr(types_pb2, f"{generic_msg.info.name}Msg")
    new_msg = message_class()
    new_msg.ParseFromString(serialized)
    new_msg_dict = MessageToDict(new_msg)
    assert new_msg_dict["info"]["extra"] == msg.info.extra

    # clean up
    reset_metadata_vars()
