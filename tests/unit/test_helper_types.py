import pytest

from dbt_common.helper_types import IncludeExclude, WarnErrorOptions
from dbt_common.dataclass_schema import ValidationError


class TestIncludeExclude:
    def test_init_invalid(self):
        with pytest.raises(ValidationError):
            IncludeExclude(include="invalid")

        with pytest.raises(ValidationError):
            IncludeExclude(include=["ItemA"], exclude=["ItemB"])

    @pytest.mark.parametrize(
        "include,exclude,silence,expected_includes",
        [
            ("all", [], [], True),
            ("*", [], [], True),
            ("*", ["ItemA"], [], False),
            (["ItemA"], [], [], True),
            (["ItemA", "ItemB"], [], [], True),
            (["ItemA"], [], ["ItemA"], False),
            ("*", [], ["ItemA"], False),
            ("*", [], ["ItemB"], True),
        ],
    )
    def test_includes(self, include, exclude, silence, expected_includes):
        include_exclude = IncludeExclude(include=include, exclude=exclude, silence=silence)

        assert include_exclude.includes("ItemA") == expected_includes

    def test_silenced(self):
        my_options = IncludeExclude(include="*", silence=["ItemA"])
        assert my_options.silenced("ItemA")
        assert not my_options.silenced("ItemB")


class TestWarnErrorOptions:
    def test_init_invalid_error(self):
        with pytest.raises(ValidationError):
            WarnErrorOptions(include=["InvalidError"], valid_error_names=set(["ValidError"]))

        with pytest.raises(ValidationError):
            WarnErrorOptions(
                include="*", exclude=["InvalidError"], valid_error_names=set(["ValidError"])
            )

    def test_init_invalid_error_default_valid_error_names(self):
        with pytest.raises(ValidationError):
            WarnErrorOptions(include=["InvalidError"])

        with pytest.raises(ValidationError):
            WarnErrorOptions(include="*", exclude=["InvalidError"])

    def test_init_valid_error(self):
        warn_error_options = WarnErrorOptions(
            include=["ValidError"], valid_error_names=set(["ValidError"])
        )
        assert warn_error_options.include == ["ValidError"]
        assert warn_error_options.exclude == []

        warn_error_options = WarnErrorOptions(
            include="*", exclude=["ValidError"], valid_error_names=set(["ValidError"])
        )
        assert warn_error_options.include == "*"
        assert warn_error_options.exclude == ["ValidError"]

    def test_init_default_silence(self):
        my_options = WarnErrorOptions(include="*")
        assert my_options.silence == []

    def test_init_invalid_silence_event(self):
        with pytest.raises(ValidationError):
            WarnErrorOptions(include="*", silence=["InvalidError"])

    def test_init_valid_silence_event(self):
        all_events = ["MySilencedEvent"]
        my_options = WarnErrorOptions(
            include="*", silence=all_events, valid_error_names=all_events
        )
        assert my_options.silence == all_events
