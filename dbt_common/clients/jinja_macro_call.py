import dataclasses
from enum import Enum
from typing import Any, Dict, List, Optional

import jinja2

from dbt_common.clients.jinja import get_environment, MacroType

PRIMITIVE_TYPES = ["Any", "bool", "float", "int", "str"]

class FailureType(Enum):
    TYPE_MISMATCH = "mismatch"
    UNKNOWN_TYPE = "unknown"
    PARAMETER_COUNT = "param_count"

@dataclasses.dataclass
class TypeCheckFailure:
    type: FailureType
    msg: str

@dataclasses.dataclass
class DbtMacroCall:
    """An instance of this class represents a jinja macro call in a template
    for the purposes of recording information for type checking."""

    name: str
    source: str
    arg_types: List[Optional[MacroType]] = dataclasses.field(default_factory=list)
    kwarg_types: Dict[str, Optional[MacroType]] = dataclasses.field(default_factory=dict)

    @classmethod
    def from_call(cls, call: jinja2.nodes.Call, name: str) -> "DbtMacroCall":
        dbt_call = cls(name, "")
        for arg in call.args:  # type: ignore
            dbt_call.arg_types.append(cls.get_type(arg))
        for arg in call.kwargs:  # type: ignore
            dbt_call.kwarg_types[arg.key] = cls.get_type(arg.value)
        return dbt_call

    @classmethod
    def get_type(cls, param: Any) -> Optional[MacroType]:
        if isinstance(param, jinja2.nodes.Name):
            return None  # TODO: infer types from variable names

        if isinstance(param, jinja2.nodes.Call):
            return None  # TODO: infer types from function/macro calls

        if isinstance(param, jinja2.nodes.Getattr):
            return None  # TODO: infer types from . operator

        if isinstance(param, jinja2.nodes.Concat):
            return None

        if isinstance(param, jinja2.nodes.Const):
            if isinstance(param.value, str):  # type: ignore
                return MacroType("str")
            elif isinstance(param.value, bool):  # type: ignore
                return MacroType("bool")
            elif isinstance(param.value, int):  # type: ignore
                return MacroType("int")
            elif isinstance(param.value, float):  # type: ignore
                return MacroType("float")
            elif param.value is None:  # type: ignore
                return None
            else:
                return None

        if isinstance(param, jinja2.nodes.Dict):
            return None

        return None

    def check_type(self, t: MacroType) -> List[TypeCheckFailure]:
        if len(t.type_params) == 0 and t.name in PRIMITIVE_TYPES:
            return []

        failures: List[TypeCheckFailure] = []
        if t.name == "Dict":
            if len(t.type_params) != 2:
                failures.append(TypeCheckFailure(FailureType.PARAMETER_COUNT, f"Expected two type parameters for Dict[], found {len(t.type_params)}."))
            else:
                if t.type_params[0].name not in PRIMITIVE_TYPES:
                    failures.append(TypeCheckFailure(FailureType.TYPE_MISMATCH, "First type parameter of Dict[] must be a primitive type."))

                failures.extend(self.check_type(t.type_params[1]))
        elif t.name in ("List", "Optional"):
            if len(t.type_params) != 1:
                failures.append(TypeCheckFailure(FailureType.PARAMETER_COUNT, "Expected one type parameter for {t.name}[], found {len(t.type_params)}."))

            failures.extend(self.check_type(t.type_params[0]))

        return failures

    def check(self, macro_text: str) -> List[TypeCheckFailure]:
        failures: List[TypeCheckFailure] = []
        template = get_environment(None, capture_macros=True).parse(macro_text)
        jinja_macro = template.body[0]

        # This could be arguably be done elsewhere, but check that every
        # parameter passed to the macro has a valid type.
        for arg_type in jinja_macro.arg_types:
            failures = self.check_type(arg_type)
            if failures:
                failures.extend(failures)

        # Check that each positional argument matches the type of the
        for i, arg_type in enumerate(self.arg_types):
            expected_type = jinja_macro.arg_types[i]
            if arg_type != expected_type:
                failures.append(TypeCheckFailure(FailureType.TYPE_MISMATCH, f"Expected type {expected_type.name} as argument {i} but found {arg_type.name}/"))

        # Check whether there were more positional arguments than expected.
        if len(self.arg_types) > len(jinja_macro.arg_types):
            failures.append(TypeCheckFailure(FailureType.PARAMETER_COUNT, f"Expected {len(self.arg_types)} type arguments, got {len(jinja_macro.arg_types)}."))

        return failures
