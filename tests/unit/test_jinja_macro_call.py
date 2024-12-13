from dbt_common.clients.jinja import MacroType
from dbt_common.clients.jinja_macro_call import PRIMITIVE_TYPES, DbtMacroCall


single_param_macro_text = """{% macro call_me(param: TYPE) %}
{% endmacro %}"""


def test_primitive_type_checks() -> None:
    for type_name in PRIMITIVE_TYPES:
        macro_text = single_param_macro_text.replace("TYPE", type_name)
        call = DbtMacroCall("call_me", "call_me", [MacroType(type_name, [])], {})
        assert not any(call.check(macro_text))


def test_primitive_type_checks_wrong() -> None:
    for type_name in PRIMITIVE_TYPES:
        macro_text = single_param_macro_text.replace("TYPE", type_name)
        wrong_type = next(t for t in PRIMITIVE_TYPES if t != type_name)
        call = DbtMacroCall("call_me", "call_me", [MacroType(wrong_type, [])], {})
        assert any(call.check(macro_text))


def test_list_type_checks() -> None:
    for type_name in PRIMITIVE_TYPES:
        macro_text = single_param_macro_text.replace("TYPE", f"List[{type_name}]")
        expected_type = MacroType("List", [MacroType(type_name)])
        call = DbtMacroCall("call_me", "call_me", [expected_type], {})
        assert not any(call.check(macro_text))


def test_dict_type_checks() -> None:
    for type_name in PRIMITIVE_TYPES:
        macro_text = single_param_macro_text.replace("TYPE", f"Dict[{type_name}, {type_name}]")
        expected_type = MacroType("Dict", [MacroType(type_name), MacroType(type_name)])
        call = DbtMacroCall("call_me", "call_me", [expected_type], {})
        assert not any(call.check(macro_text))


def test_too_few_args() -> None:
    macro_text = "{% macro call_me(one: str, two: str, three: str) %}"


def test_too_many_args() -> None:
    pass


kwarg_param_macro_text = """{% macro call_me(param: int = 10, arg_one = "val1", arg_two: int = 2, arg_three: str = "val3" ) %}
{% endmacro %}"""


# Better structured exceptions
# Test detection of macro called with too few positional args
# Test detection of macro called with too many positional args
# Test detection of macro called with keyword arg having wrong type
# Test detection of macro called with non-existent keyword arg
# Test detection of macro with invalid default value for param type
