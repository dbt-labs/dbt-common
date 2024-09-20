import pytest

from dbt_common.behavior_flags import Behavior
from dbt_common.exceptions.base import CompilationError, DbtInternalError
from tests.unit.utils import EventCatcher


def test_behavior_default() -> None:
    behavior = Behavior(
        [
            {"name": "default_false_flag", "default": False, "description": "This flag is false."},
            {"name": "default_true_flag", "default": True, "description": "This flag is true."},
        ],
        {},
    )

    assert behavior.default_false_flag.setting is False
    assert behavior.default_true_flag.setting is True


def test_behavior_user_override() -> None:
    behavior = Behavior(
        [
            {"name": "flag_default_false", "default": False, "description": "This flag is false."},
            {
                "name": "flag_default_false_override_false",
                "default": False,
                "description": "This flag is false.",
            },
            {
                "name": "flag_default_false_override_true",
                "default": False,
                "description": "This flag is true.",
            },
            {"name": "flag_default_true", "default": True, "description": "This flag is true."},
            {
                "name": "flag_default_true_override_false",
                "default": True,
                "description": "This flag is false.",
            },
            {
                "name": "flag_default_true_override_true",
                "default": True,
                "description": "This flag is true.",
            },
        ],
        {
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


def test_behavior_unregistered_flag_raises_correct_exception() -> None:
    behavior = Behavior(
        [
            {
                "name": "behavior_flag_exists",
                "default": False,
                "description": "This flag is false.",
            },
        ],
        {},
    )

    assert behavior.behavior_flag_exists.setting is False
    with pytest.raises(CompilationError):
        assert behavior.behavior_flag_does_not_exist


def test_behavior_flag_can_be_used_as_conditional() -> None:
    behavior = Behavior(
        [
            {"name": "flag_false", "default": False, "description": "This flag is false."},
            {"name": "flag_true", "default": True, "description": "This flag is true."},
        ],
        {},
    )

    assert False if behavior.flag_false else True
    assert True if behavior.flag_true else False


def test_behavior_flags_emit_behavior_change_event_on_evaluation(
    event_catcher: EventCatcher,
) -> None:
    behavior = Behavior(
        [
            {"name": "flag_false", "default": False, "description": "This flag is false."},
            {"name": "flag_true", "default": True, "description": "This flag is true."},
        ],
        {},
    )

    # trigger the evaluation, no event should fire
    if behavior.flag_true:
        pass
    assert len(event_catcher.caught_events) == 0

    # trigger the evaluation, an event should fire
    if behavior.flag_false:
        pass
    assert len(event_catcher.caught_events) == 1


@pytest.mark.parametrize(
    "flag,event",
    [
        (
            {"name": "flag_false", "default": False, "description": "This flag is false."},
            {
                "flag_name": "flag_false",
                "flag_source": __name__,
                "description": "This flag is false.",
                "docs_url": "https://docs.getdbt.com/reference/global-configs/behavior-changes",
            },
        ),
        (
            {"name": "flag_false", "default": False, "docs_url": "https://docs.getdbt.com"},
            {
                "flag_name": "flag_false",
                "flag_source": __name__,
                "description": "The behavior controlled by `flag_false` is currently turned off.\n",
                "docs_url": "https://docs.getdbt.com",
            },
        ),
    ],
)
def test_behavior_flags_emit_correct_behavior_change_event(
    event_catcher: EventCatcher, flag, event
) -> None:
    behavior = Behavior([flag], {})

    # trigger the evaluation
    if behavior.flag_false:
        pass

    msg = event_catcher.caught_events[0]
    assert msg.info.name == "BehaviorChangeEvent"
    assert msg.data.flag_name == event["flag_name"]
    assert msg.data.flag_source == event["flag_source"]
    assert msg.data.description == event["description"]
    assert msg.data.docs_url == event["docs_url"]


def test_behavior_flags_no_behavior_change_event_on_no_warn(event_catcher: EventCatcher) -> None:
    behavior = Behavior(
        [{"name": "flag_false", "default": False, "description": "This flag is false."}], {}
    )

    # trigger the evaluation with no_warn, no event should fire
    if behavior.flag_false.no_warn:
        pass
    assert len(event_catcher.caught_events) == 0

    # trigger the evaluation, an event should fire
    if behavior.flag_false:
        pass
    assert len(event_catcher.caught_events) == 1


def test_behavior_flag_requires_description_or_docs_url(event_catcher: EventCatcher) -> None:
    with pytest.raises(DbtInternalError):
        Behavior([{"name": "flag_false", "default": False}], {})


def test_behavior_flags_fire_once_per_flag(event_catcher: EventCatcher) -> None:
    behavior = Behavior(
        [
            {"name": "flag_1", "default": False, "description": "This is flag 1."},
            {"name": "flag_2", "default": False, "description": "This is flag 2."},
        ],
        {},
    )

    assert len(event_catcher.caught_events) == 0

    # trigger the evaluation for flag_1, an event should fire
    if behavior.flag_1:
        pass
    assert len(event_catcher.caught_events) == 1

    # trigger the evaluation for flag_1 again, no event should fire
    if behavior.flag_1:
        pass
    assert len(event_catcher.caught_events) == 1

    # trigger the evaluation for flag_2, an event should fire
    if behavior.flag_2:
        pass
    assert len(event_catcher.caught_events) == 2

    # trigger the evaluation for flag_1 again, no event should fire
    if behavior.flag_1:
        pass
    assert len(event_catcher.caught_events) == 2
