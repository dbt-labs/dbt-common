import json
from dbt_common.events.logger import LoggerConfig, _TextLogger, _JsonLogger
from dbt_common.events.base_types import EventLevel, msg_from_base_event
from dbt_common.events.types import PrintEvent


def test_create_print_line():
    # No format, still fired even when error is the level
    config = LoggerConfig(name="test_logger", level=EventLevel.ERROR)
    logger = _TextLogger(config)
    msg = msg_from_base_event(PrintEvent(msg="This is a print event"))
    expected_line = "This is a print event"
    actual_line = logger.create_line(msg)
    assert actual_line == expected_line


def test_create_print_json():
    # JSON format still have event level being info
    config = LoggerConfig(name="test_logger", level=EventLevel.ERROR)
    logger = _JsonLogger(config)
    msg = msg_from_base_event(PrintEvent(msg="This is a print event"))
    expected_json = {
        "data": {"msg": "This is a print event"},
        "info": {
            "category": "",
            "code": "Z052",
            "extra": {},
            "level": "info",
            "msg": "This is a print event",
            "name": "PrintEvent",
            "thread": "MainThread",
        },
    }
    actual_line = logger.create_line(msg)
    actual_json = json.loads(actual_line)
    assert "info" in actual_json
    actual_json["info"].pop("invocation_id")
    actual_json["info"].pop("ts")
    actual_json["info"].pop("pid")
    assert actual_json == expected_json
