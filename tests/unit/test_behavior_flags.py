import pytest
from pytest_mock import MockerFixture  # type: ignore

from dbt_common.behavior_flags import register
from dbt_common.events.event_manager import EventManager
from dbt_common.events.event_manager_client import add_callback_to_manager

from tests.unit.utils import EventCatcher


def test_behavior_default():
    behavior = register(
        behavior_flags=[
            {"name": "default_false_flag", "default": False},
            {"name": "default_true_flag", "default": True},
        ],
        user_flags={},
    )

    assert behavior.default_false_flag.setting is False
    assert behavior.default_true_flag.setting is True


def test_behavior_user_override():
    behavior = register(
        behavior_flags=[
            {"name": "flag_default_false", "default": False},
            {"name": "flag_default_false_override_false", "default": False},
            {"name": "flag_default_false_override_true", "default": False},
            {"name": "flag_default_true", "default": True},
            {"name": "flag_default_true_override_false", "default": True},
            {"name": "flag_default_true_override_true", "default": True},
        ],
        user_flags={
            "flag_default_false_override_false": False,
            "flag_default_false_override_true": True,
            "flag_default_true_override_false": False,
            "flag_default_true_override_true": True,
        },
    )

    assert behavior.flag_default_false.setting is False
    assert behavior.flag_default_false_override_false.setting is False
    assert behavior.flag_default_false_override_true.setting is True
    assert behavior.flag_default_true.setting is True
    assert behavior.flag_default_true_override_false.setting is False
    assert behavior.flag_default_true_override_true.setting is True


def test_behavior_flag_can_be_used_as_conditional():
    behavior = register(
        behavior_flags=[
            {"name": "flag_false", "default": False},
            {"name": "flag_true", "default": True},
        ],
        user_flags={},
    )

    assert False if behavior.flag_false else True
    assert True if behavior.flag_true else False


@pytest.fixture(scope="function")
def event_catcher(mocker: MockerFixture) -> EventCatcher:
    # mock out the global event manager so the callback doesn't get added to all other tests
    mocker.patch("dbt_common.events.event_manager_client._EVENT_MANAGER", EventManager())
    catcher = EventCatcher()
    add_callback_to_manager(catcher.catch)
    return catcher


def test_behavior_flags_emit_deprecation_event_on_evaluation(event_catcher) -> None:
    behavior = register(
        behavior_flags=[
            {"name": "flag_false", "default": False},
            {"name": "flag_true", "default": True},
        ],
        user_flags={},
    )

    # trigger the evaluation, no event should fire
    if behavior.flag_true:
        pass
    assert len(event_catcher.caught_events) == 0

    # trigger the evaluation, an event should fire
    if behavior.flag_false:
        pass
    assert len(event_catcher.caught_events) == 1


def test_behavior_flags_emit_correct_deprecation(event_catcher) -> None:
    behavior = register(
        behavior_flags=[{"name": "flag_false", "default": False}],
        user_flags={},
    )

    # trigger the evaluation
    if behavior.flag_false:
        pass

    msg = event_catcher.caught_events[0]
    assert msg.info.name == "BehaviorDeprecationEvent"
    assert msg.data.flag_name == "flag_false"
    assert msg.data.flag_source == __name__  # defaults to the calling module


def test_behavior_flags_no_deprecation_event_on_no_warn(event_catcher) -> None:
    behavior = register(
        behavior_flags=[
            {"name": "flag_false", "default": False},
        ],
        user_flags={},
    )

    # trigger the evaluation with no_warn, no event should fire
    if behavior.flag_false.no_warn:
        pass
    assert len(event_catcher.caught_events) == 0

    # trigger the evaluation, an event should fire
    if behavior.flag_false:
        pass
    assert len(event_catcher.caught_events) == 1
