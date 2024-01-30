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
        "include,exclude,expected_includes",
        [
            ("all", [], True),
            ("*", [], True),
            ("*", ["ItemA"], False),
            (["ItemA"], [], True),
            (["ItemA", "ItemB"], [], True),
        ],
    )
    def test_includes(self, include, exclude, expected_includes):
        include_exclude = IncludeExclude(include=include, exclude=exclude)

        assert include_exclude.includes("ItemA") == expected_includes


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
