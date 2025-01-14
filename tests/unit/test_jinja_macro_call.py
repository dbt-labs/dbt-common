from dbt_common.clients.jinja import MacroType
from dbt_common.clients.jinja_macro_call import (
    PRIMITIVE_TYPES,
    DBT_CLASSES,
    FailureType,
    MacroCallChecker,
    MacroChecker,
)

single_param_macro_text = """{% macro call_me(param: TYPE) %}
{% endmacro %}"""


def test_primitive_type_checks() -> None:
    """Test that primitive types can all be used to annotate macro parameters."""
    for type_name in PRIMITIVE_TYPES:
        macro_text = single_param_macro_text.replace("TYPE", type_name)
        call = MacroCallChecker("call_me", "call_me", [MacroType(type_name, [])], {})
        failures = call.check(macro_text)
        assert not failures


def test_dbt_class_type_checks() -> None:
    """Test that 'dbt Classes' like Relation, Column, and Result can all be used
    to annotate macro parameters."""
    for type_name in DBT_CLASSES:
        macro_text = single_param_macro_text.replace("TYPE", type_name)
        call = MacroCallChecker("call_me", "call_me", [MacroType(type_name, [])], {})
        failures = call.check(macro_text)
        assert not failures


def test_type_checks_wrong() -> None:
    """Test that calls to annotated macros with incorrect types fail type checks."""
    for type_name in PRIMITIVE_TYPES + DBT_CLASSES:
        macro_text = single_param_macro_text.replace("TYPE", type_name)
        wrong_type = next(t for t in PRIMITIVE_TYPES if t != type_name)
        call = MacroCallChecker("call_me", "call_me", [MacroType(wrong_type, [])], {})
        failures = call.check(macro_text)
        assert len([f for f in failures if f.type == FailureType.TYPE_MISMATCH]) == 1


def test_list_type_checks() -> None:
    for type_name in PRIMITIVE_TYPES:
        macro_text = single_param_macro_text.replace("TYPE", f"List[{type_name}]")
        expected_type = MacroType("List", [MacroType(type_name)])
        call = MacroCallChecker("call_me", "call_me", [expected_type], {})
        failures = call.check(macro_text)
        assert not failures


def test_dict_type_checks() -> None:
    for type_name in PRIMITIVE_TYPES:
        macro_text = single_param_macro_text.replace("TYPE", f"Dict[{type_name}, {type_name}]")
        expected_type = MacroType("Dict", [MacroType(type_name), MacroType(type_name)])
        call = MacroCallChecker("call_me", "call_me", [expected_type], {})
        assert not any(call.check(macro_text))


kwarg_param_macro_text = """{% macro call_me(arg1: int, arg2: int, arg3: str = "val3", arg4: int = 4, arg5: str = "val5") %}
{% endmacro %}"""


def test_too_few_pos_args() -> None:
    call = MacroCallChecker("call_me", "", [MacroType("int")])
    failures = call.check(kwarg_param_macro_text)
    assert len(failures) == 1
    assert failures[0].type == FailureType.MISSING_ARGUMENT


def test_unknown_kwarg() -> None:
    call = MacroCallChecker(
        "call_me", "", [MacroType("int"), MacroType("int")], {"unk": MacroType("str")}
    )
    failures = call.check(kwarg_param_macro_text)
    assert len(failures) == 1
    assert failures[0].type == FailureType.EXTRA_ARGUMENT


def test_kwarg_type() -> None:
    """Test that annotated kwargs pass type checks when used by name."""
    call = MacroCallChecker(
        "call_me", "", [MacroType("int"), MacroType("int")], {"arg3": MacroType("str")}
    )
    failures = call.check(kwarg_param_macro_text)
    assert not failures


def test_wrong_kwarg_type() -> None:
    """Test that annotated kwargs pass type checks fail when the wrong type is used."""
    call = MacroCallChecker("call_me", "", [], {"arg3": MacroType("int")})
    failures = call.check(kwarg_param_macro_text)
    assert failures[0].type == FailureType.TYPE_MISMATCH


# TODO: Test detection of macro with invalid default value for param type
# TODO: Test detection of macro called with invalid variable parameter, as known from macro parameter annotation.


def test_unknown_type_check() -> None:
    """Test that macro parameter annotations with unknown types fail type checks."""
    macro_text = single_param_macro_text.replace("TYPE", "Invalid")
    checker = MacroChecker.from_jinja(macro_text)
    failures = checker.type_check()
    assert failures
    assert any(f for f in failures if f.type == FailureType.UNKNOWN_TYPE)
