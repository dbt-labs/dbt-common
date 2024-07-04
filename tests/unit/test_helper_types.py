import pytest
from typing import List, Union

from dbt_common.helper_types import IncludeExclude, WarnErrorOptions
from dbt_common.dataclass_schema import ValidationError


class TestIncludeExclude:
    def test_init_invalid(self) -> None:
        with pytest.raises(ValidationError):
            IncludeExclude(include="invalid")

        with pytest.raises(ValidationError):
            IncludeExclude(include=["ItemA"], exclude=["ItemB"])

    @pytest.mark.parametrize(
        "include,exclude,expected_includes",
        [
            ("all", [], True),
            ("*", [], True),
            ("*", ["ItemA"], False),
            (["ItemA"], [], True),
            (["ItemA", "ItemB"], [], True),
        ],
    )
    def test_includes(
        self, include: Union[str, List[str]], exclude: List[str], expected_includes: bool
    ) -> None:
        include_exclude = IncludeExclude(include=include, exclude=exclude)

        assert include_exclude.includes("ItemA") == expected_includes


class TestWarnErrorOptions:
    def test_init_invalid_error(self) -> None:
        with pytest.raises(ValidationError):
            WarnErrorOptions(include=["InvalidError"], valid_error_names=set(["ValidError"]))

        with pytest.raises(ValidationError):
            WarnErrorOptions(
                include="*", exclude=["InvalidError"], valid_error_names=set(["ValidError"])
            )

    def test_init_invalid_error_default_valid_error_names(self) -> None:
        with pytest.raises(ValidationError):
            WarnErrorOptions(include=["InvalidError"])

        with pytest.raises(ValidationError):
            WarnErrorOptions(include="*", exclude=["InvalidError"])

    def test_init_valid_error(self) -> None:
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

    def test_init_default_silence(self) -> None:
        my_options = WarnErrorOptions(include="*")
        assert my_options.silence == []

    def test_init_invalid_silence_event(self) -> None:
        with pytest.raises(ValidationError):
            WarnErrorOptions(include="*", silence=["InvalidError"])

    def test_init_valid_silence_event(self) -> None:
        all_events = ["MySilencedEvent"]
        my_options = WarnErrorOptions(
            include="*", silence=all_events, valid_error_names=set(all_events)
        )
        assert my_options.silence == all_events

    @pytest.mark.parametrize(
        "include,silence,expected_includes",
        [
            (["ItemA"], ["ItemA"], False),
            ("*", ["ItemA"], False),
            ("*", ["ItemB"], True),
        ],
    )
    def test_includes(
        self, include: Union[str, List[str]], silence: List[str], expected_includes: bool
    ) -> None:
        include_exclude = WarnErrorOptions(
            include=include, silence=silence, valid_error_names={"ItemA", "ItemB"}
        )

        assert include_exclude.includes("ItemA") == expected_includes

    def test_silenced(self) -> None:
        my_options = WarnErrorOptions(include="*", silence=["ItemA"], valid_error_names={"ItemA"})
        assert my_options.silenced("ItemA")
        assert not my_options.silenced("ItemB")
