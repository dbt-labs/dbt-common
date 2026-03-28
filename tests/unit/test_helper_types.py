from dbt_common.events.types import BehaviorChangeEvent
import pytest
from typing import List, Union

from dbt_common.helper_types import IncludeExclude, WarnErrorOptions, WarnErrorOptionsV2
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

    # NOTE: BehaviorChangeEvent is a deprecation event
    @pytest.mark.parametrize(
        "include,exclude,silence,expected_includes",
        [
            ([], [], [], False),
            (["BehaviorChangeEvent"], [], ["BehaviorChangeEvent"], False),
            (["BehaviorChangeEvent"], [], [], True),
            ("*", ["BehaviorChangeEvent"], ["BehaviorChangeEvent"], False),
            ("*", [], ["BehaviorChangeEvent"], False),
            ("*", ["BehaviorChangeEvent"], [], False),
            ("*", [], [], True),
            ("*", ["ItemB"], [], True),
            ("*", [], ["ItemB"], True),
            (["BehaviorChangeEvent"], [], ["Deprecations"], True),
            (["Deprecations"], [], ["BehaviorChangeEvent"], False),
            (["Deprecations"], ["BehaviorChangeEvent"], [], False),
            (["Deprecations"], [], [], True),
            ("*", ["Deprecations"], [], False),
            ("*", [], ["Deprecations"], False),
            (["Deprecations"], ["Deprecations"], ["Deprecations"], False),
        ],
    )
    def test_includes(
        self,
        include: Union[str, List[str]],
        exclude: List[str],
        silence: List[str],
        expected_includes: bool,
    ) -> None:
        include_exclude = WarnErrorOptions(
            include=include,
            exclude=exclude,
            silence=silence,
            valid_error_names={"BehaviorChangeEvent", "ItemB"},
        )

        assert include_exclude.includes(BehaviorChangeEvent()) == expected_includes

    # NOTE: BehaviorChangeEvent is a deprecation event
    @pytest.mark.parametrize(
        "include,exclude,silence,expected_silence",
        [
            (["BehaviorChangeEvent"], [], ["BehaviorChangeEvent"], True),
            ("all", ["BehaviorChangeEvent"], ["BehaviorChangeEvent"], True),
            ([], [], ["BehaviorChangeEvent"], True),
            ("*", [], ["BehaviorChangeEvent"], True),
            (["BehaviorChangeEvent"], [], [], False),
            ("*", [], [], False),
            ("*", ["BehaviorChangeEvent"], [], False),
            ([], [], [], False),
            (["BehaviorChangeEvent"], [], ["Deprecations"], False),
            ([], ["BehaviorChangeEvent"], ["Deprecations"], False),
            (["Deprecations"], [], ["BehaviorChangeEvent"], True),
            ([], [], ["Deprecations"], True),
            ("*", [], ["Deprecations"], True),
            (["Deprecations"], ["Deprecations"], ["Deprecations"], True),
        ],
    )
    def test_silenced(
        self,
        include: Union[str, List[str]],
        exclude: List[str],
        silence: List[str],
        expected_silence: bool,
    ) -> None:
        my_options = WarnErrorOptions(
            include=include,
            exclude=exclude,
            silence=silence,
            valid_error_names={"BehaviorChangeEvent", "ItemB"},
        )
        assert my_options.silenced(BehaviorChangeEvent()) == expected_silence

    def test_dictification(self) -> None:
        my_options = WarnErrorOptions(include=[], exclude=[])
        assert my_options.to_dict() == {"include": [], "exclude": []}


class TestWarnErrorOptionsV2:
    def test_init_invalid_error(self) -> None:
        with pytest.raises(ValidationError):
            WarnErrorOptionsV2(error=["InvalidError"], valid_error_names=set(["ValidError"]))

        with pytest.raises(ValidationError):
            WarnErrorOptionsV2(
                error="*", warn=["InvalidError"], valid_error_names=set(["ValidError"])
            )

    def test_init_invalid_error_default_valid_error_names(self) -> None:
        with pytest.raises(ValidationError):
            WarnErrorOptionsV2(error=["InvalidError"])

        with pytest.raises(ValidationError):
            WarnErrorOptionsV2(error="*", warn=["InvalidError"])

    def test_init_valid_error(self) -> None:
        warn_error_options = WarnErrorOptionsV2(
            error=["ValidError"], valid_error_names=set(["ValidError"])
        )
        assert warn_error_options.error == ["ValidError"]
        assert warn_error_options.warn == []

        warn_error_options = WarnErrorOptionsV2(
            error="*", warn=["ValidError"], valid_error_names=set(["ValidError"])
        )
        assert warn_error_options.error == "*"
        assert warn_error_options.warn == ["ValidError"]

    def test_init_default_silence(self) -> None:
        my_options = WarnErrorOptionsV2(error="*")
        assert my_options.silence == []

    def test_init_invalid_silence_event(self) -> None:
        with pytest.raises(ValidationError):
            WarnErrorOptionsV2(error="*", silence=["InvalidError"])

    def test_init_valid_silence_event(self) -> None:
        all_events = ["MySilencedEvent"]
        my_options = WarnErrorOptionsV2(
            error="*", silence=all_events, valid_error_names=set(all_events)
        )
        assert my_options.silence == all_events

    # NOTE: BehaviorChangeEvent is a deprecation event
    @pytest.mark.parametrize(
        "error,warn,silence,expected_errors",
        [
            ([], [], [], False),
            (["BehaviorChangeEvent"], [], ["BehaviorChangeEvent"], False),
            (["BehaviorChangeEvent"], [], [], True),
            ("*", ["BehaviorChangeEvent"], ["BehaviorChangeEvent"], False),
            ("*", [], ["BehaviorChangeEvent"], False),
            ("*", ["BehaviorChangeEvent"], [], False),
            ("*", [], [], True),
            ("*", ["ItemB"], [], True),
            ("*", [], ["ItemB"], True),
            (["BehaviorChangeEvent"], [], ["Deprecations"], True),
            (["Deprecations"], [], ["BehaviorChangeEvent"], False),
            (["Deprecations"], ["BehaviorChangeEvent"], [], False),
            (["Deprecations"], [], [], True),
            ("*", ["Deprecations"], [], False),
            ("*", [], ["Deprecations"], False),
            (["Deprecations"], ["Deprecations"], ["Deprecations"], False),
        ],
    )
    def test_errors(
        self,
        error: Union[str, List[str]],
        warn: List[str],
        silence: List[str],
        expected_errors: bool,
    ) -> None:
        error_warn = WarnErrorOptionsV2(
            error=error,
            warn=warn,
            silence=silence,
            valid_error_names={"BehaviorChangeEvent", "ItemB"},
        )

        assert error_warn.errors(BehaviorChangeEvent()) == expected_errors

    # NOTE: BehaviorChangeEvent is a deprecation event
    @pytest.mark.parametrize(
        "error,warn,silence,expected_silence",
        [
            (["BehaviorChangeEvent"], [], ["BehaviorChangeEvent"], True),
            ("all", ["BehaviorChangeEvent"], ["BehaviorChangeEvent"], True),
            ([], [], ["BehaviorChangeEvent"], True),
            ("*", [], ["BehaviorChangeEvent"], True),
            (["BehaviorChangeEvent"], [], [], False),
            ("*", [], [], False),
            ("*", ["BehaviorChangeEvent"], [], False),
            ([], [], [], False),
            (["BehaviorChangeEvent"], [], ["Deprecations"], False),
            ([], ["BehaviorChangeEvent"], ["Deprecations"], False),
            (["Deprecations"], [], ["BehaviorChangeEvent"], True),
            ([], [], ["Deprecations"], True),
            ("*", [], ["Deprecations"], True),
            (["Deprecations"], ["Deprecations"], ["Deprecations"], True),
        ],
    )
    def test_silenced(
        self,
        error: Union[str, List[str]],
        warn: List[str],
        silence: List[str],
        expected_silence: bool,
    ) -> None:
        my_options = WarnErrorOptionsV2(
            error=error,
            warn=warn,
            silence=silence,
            valid_error_names={"BehaviorChangeEvent", "ItemB"},
        )
        assert my_options.silenced(BehaviorChangeEvent()) == expected_silence

    def test_dictification(self) -> None:
        my_options = WarnErrorOptionsV2(error=[], warn=[], silence=[])
        assert my_options.to_dict() == {"error": [], "warn": [], "silence": []}

    def test_discriminated_validation_accepts_valid_entry(self) -> None:
        WarnErrorOptionsV2(
            silence=["BehaviorChangeEvent:anything"],
            valid_error_names={"BehaviorChangeEvent"},
        )
        WarnErrorOptionsV2(
            error=["BehaviorChangeEvent:use_mat_v2"],
            valid_error_names={"BehaviorChangeEvent"},
        )

    def test_discriminated_empty_discriminator_raises(self) -> None:
        with pytest.raises(ValidationError, match="missing a discriminator value"):
            WarnErrorOptionsV2(silence=["BehaviorChangeEvent:"])

    def test_discriminated_warn_allowed_without_broad_error(self) -> None:
        # ClassName:<discriminator> in warn should not require error=all/* or Deprecations
        WarnErrorOptionsV2(
            error=["BehaviorChangeEvent"],
            warn=["BehaviorChangeEvent:use_mat_v2"],
            silence=[],
            valid_error_names={"BehaviorChangeEvent"},
        )

    def test_non_discriminated_warn_still_requires_broad_error(self) -> None:
        with pytest.raises(ValidationError, match="`warn` can only be specified"):
            WarnErrorOptionsV2(
                error=["BehaviorChangeEvent"],
                warn=["SomeOtherEvent"],
                silence=[],
                valid_error_names={"BehaviorChangeEvent", "SomeOtherEvent"},
            )

    # Per-flag BehaviorChange targeting in errors()
    @pytest.mark.parametrize(
        "error,warn,silence,flag_name,expected_errors",
        [
            # flag-level error fires when not overridden
            (["BehaviorChangeEvent:use_mat_v2"], [], [], "use_mat_v2", True),
            # flag-level silence beats flag-level error
            (
                ["BehaviorChangeEvent:use_mat_v2"],
                [],
                ["BehaviorChangeEvent:use_mat_v2"],
                "use_mat_v2",
                False,
            ),
            # flag-level silence beats class-level error
            (["BehaviorChangeEvent"], [], ["BehaviorChangeEvent:use_mat_v2"], "use_mat_v2", False),
            # flag-level silence beats Deprecations error
            (["Deprecations"], [], ["BehaviorChangeEvent:use_mat_v2"], "use_mat_v2", False),
            # different flag name — flag-level error does not fire
            (["BehaviorChangeEvent:other_flag"], [], [], "use_mat_v2", False),
            # flag-level warn overrides class-level error
            (["BehaviorChangeEvent"], ["BehaviorChangeEvent:use_mat_v2"], [], "use_mat_v2", False),
            # same flag in both error and silence: silence wins (silence > warn > error)
            (
                ["BehaviorChangeEvent:use_mat_v2"],
                [],
                ["BehaviorChangeEvent:use_mat_v2"],
                "use_mat_v2",
                False,
            ),
        ],
    )
    def test_errors_per_flag(
        self,
        error: Union[str, List[str]],
        warn: List[str],
        silence: List[str],
        flag_name: str,
        expected_errors: bool,
    ) -> None:
        event = BehaviorChangeEvent(
            flag_name=flag_name,
            flag_source="dbt_common",
            description="test",
            docs_url="https://docs.getdbt.com",
        )
        error_warn = WarnErrorOptionsV2(
            error=error,
            warn=warn,
            silence=silence,
            valid_error_names={"BehaviorChangeEvent", "ItemB"},
        )
        assert error_warn.errors(event) == expected_errors

    # Per-flag BehaviorChange targeting in silenced()
    @pytest.mark.parametrize(
        "error,warn,silence,flag_name,expected_silence",
        [
            # primary use case: flag-level silence fires
            ([], [], ["BehaviorChangeEvent:use_mat_v2"], "use_mat_v2", True),
            # flag-level error beats class-level silence
            (["BehaviorChangeEvent:use_mat_v2"], [], ["BehaviorChangeEvent"], "use_mat_v2", False),
            # flag-level silence beats class-level error
            (["BehaviorChangeEvent"], [], ["BehaviorChangeEvent:use_mat_v2"], "use_mat_v2", True),
            # different flag not silenced
            ([], [], ["BehaviorChangeEvent:other_flag"], "use_mat_v2", False),
            # same flag in both error and silence: silence wins (silence > warn > error)
            (
                ["BehaviorChangeEvent:use_mat_v2"],
                [],
                ["BehaviorChangeEvent:use_mat_v2"],
                "use_mat_v2",
                True,
            ),
        ],
    )
    def test_silenced_per_flag(
        self,
        error: Union[str, List[str]],
        warn: List[str],
        silence: List[str],
        flag_name: str,
        expected_silence: bool,
    ) -> None:
        event = BehaviorChangeEvent(
            flag_name=flag_name,
            flag_source="dbt_common",
            description="test",
            docs_url="https://docs.getdbt.com",
        )
        my_options = WarnErrorOptionsV2(
            error=error,
            warn=warn,
            silence=silence,
            valid_error_names={"BehaviorChangeEvent", "ItemB"},
        )
        assert my_options.silenced(event) == expected_silence
