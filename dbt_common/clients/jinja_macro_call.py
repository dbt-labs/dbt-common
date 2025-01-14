import dataclasses
from enum import Enum
from typing import Any, Dict, List, Optional

import jinja2
import jinja2.nodes

from dbt_common.clients.jinja import get_environment, MacroType

PRIMITIVE_TYPES = ["Any", "bool", "float", "int", "str"]
DBT_CLASSES = ["Column", "Relation", "Result"]


class FailureType(Enum):
    TYPE_MISMATCH = "type_mismatch"
    UNKNOWN_TYPE = "unknown_type"
    PARAMETER_COUNT = "param_count"
    EXTRA_ARGUMENT = "extra_arg"
    MISSING_ARGUMENT = "missing_arg"


@dataclasses.dataclass
class TypeCheckFailure:
    type: FailureType
    msg: str


@dataclasses.dataclass
class MacroCallChecker:
    """An instance of this class represents a jinja macro call in a template
    for the purposes of recording information for type checking."""

    name: str
    source: str
    arg_types: List[Optional[MacroType]] = dataclasses.field(default_factory=list)
    kwarg_types: Dict[str, Optional[MacroType]] = dataclasses.field(default_factory=dict)

    @classmethod
    def from_call(cls, call: jinja2.nodes.Call, name: str) -> "MacroCallChecker":
        dbt_call = cls(name, "")
        for arg in call.args:  # type: ignore
            dbt_call.arg_types.append(TypeChecker.get_type(arg))
        for arg in call.kwargs:  # type: ignore
            dbt_call.kwarg_types[arg.key] = TypeChecker.get_type(arg.value)
        return dbt_call

    def check(self, macro_text: str) -> List[TypeCheckFailure]:
        failures: List[TypeCheckFailure] = []

        macro_checker = MacroChecker.from_jinja(macro_text)

        unassigned_args = list(macro_checker.args)

        # Each positional argument in this call should correspond to an expected
        # positional argument with a compatible type.
        for i, arg_type in enumerate(self.arg_types):
            target_name = macro_checker.args[i]
            target_type = macro_checker.arg_types[i]
            unassigned_args.remove(target_name)
            if arg_type is not None and target_type is not None and arg_type != target_type:
                failures.append(
                    TypeCheckFailure(
                        FailureType.TYPE_MISMATCH,
                        f"Expected type {target_type.name} for argument {target_name} but found {arg_type.name}/",
                    )
                )

        # Each keyword argument in this call should correspond to an expected
        # argument that has not already been assigned, and have a compatible type.
        for arg_name, arg_type in self.kwarg_types.items():
            if arg_name not in macro_checker.args:
                failures.append(
                    TypeCheckFailure(
                        FailureType.EXTRA_ARGUMENT, f"Unexpected keyword argument {arg_name}."
                    )
                )
            elif arg_name not in unassigned_args:
                failures.append(
                    TypeCheckFailure(
                        FailureType.EXTRA_ARGUMENT,
                        f"Argument {arg_name} was specified more than once.",
                    )
                )
            else:
                unassigned_args.remove(arg_name)
                expected_type = macro_checker.get_arg_type(arg_name)
                if (
                    arg_type is not None
                    and expected_type is not None
                    and arg_type != expected_type
                ):
                    failures.append(
                        TypeCheckFailure(
                            FailureType.TYPE_MISMATCH,
                            f"Expected type {expected_type.name} for argument {arg_name} but found {arg_type.name}/",
                        )
                    )

        # Any remaining unassigned parameters must have a default.
        for arg_name in unassigned_args:
            if not macro_checker.has_default(arg_name):
                failures.append(
                    TypeCheckFailure(FailureType.MISSING_ARGUMENT, f"Missing argument {arg_name}.")
                )

        # Check that any arguments specified by keyword have the correct type
        for arg_name, arg_type in self.kwarg_types.items():
            expected_type = macro_checker.get_arg_type(arg_name)
            if arg_type is not None and expected_type is not None and arg_type != expected_type:
                failures.append(
                    TypeCheckFailure(
                        FailureType.TYPE_MISMATCH,
                        f"Expected type {expected_type.name} as argument {arg_name} but found {arg_type.name}/",
                    )
                )

        return failures


@dataclasses.dataclass
class MacroChecker:
    _jinja_macro: jinja2.nodes.Macro

    @property
    def args(self) -> List[str]:
        return [a.name for a in self._jinja_macro.args]

    @property
    def arg_types(self) -> List[Optional[MacroType]]:
        return self._jinja_macro.arg_types  # type: ignore

    @property
    def defaults(self) -> List[str]:
        return self._jinja_macro.defaults

    def get_arg_type(self, arg_name: str) -> Optional[MacroType]:
        args = self.args
        if arg_name not in args:
            return None
        else:
            return self.arg_types[args.index(arg_name)]

    def has_default(self, arg_name: str) -> bool:
        args = self.args
        return args.index(arg_name) >= len(self.args) - len(self.defaults)

    @classmethod
    def from_jinja(cls, jinja_text: str) -> "MacroChecker":
        template = get_environment(None, capture_macros=True).parse(jinja_text)
        jinja_macro = template.body[0]

        if not isinstance(jinja_macro, jinja2.nodes.Macro):
            raise Exception("Expected jinja macro.")

        return MacroChecker(jinja_macro)

    def type_check(self) -> List[TypeCheckFailure]:
        # Every annotated parameter of the macro being called must have a valid
        # type.
        failures: List[TypeCheckFailure] = []
        for arg_type in self._jinja_macro.arg_types:  # type: ignore
            failures = TypeChecker.check(arg_type)
            if failures:
                failures.extend(failures)

        return failures


class TypeChecker:
    @staticmethod
    def check(t: Optional[MacroType]) -> List[TypeCheckFailure]:
        if t is None or len(t.type_params) == 0 and t.name in (PRIMITIVE_TYPES + DBT_CLASSES):
            return []

        failures: List[TypeCheckFailure] = []
        if t.name == "Dict":
            if len(t.type_params) != 2:
                failures.append(
                    TypeCheckFailure(
                        FailureType.PARAMETER_COUNT,
                        f"Expected two type parameters for Dict[], found {len(t.type_params)}.",
                    )
                )
            else:
                if t.type_params[0].name not in PRIMITIVE_TYPES:
                    failures.append(
                        TypeCheckFailure(
                            FailureType.TYPE_MISMATCH,
                            "First type parameter of Dict[] must be a primitive type.",
                        )
                    )

                failures.extend(TypeChecker.check(t.type_params[1]))
        elif t.name in ("List", "Optional"):
            if len(t.type_params) != 1:
                failures.append(
                    TypeCheckFailure(
                        FailureType.PARAMETER_COUNT,
                        f"Expected one type parameter for {t.name}[], found {len(t.type_params)}.",
                    )
                )

            failures.extend(TypeChecker.check(t.type_params[0]))
        else:
            failures.append(
                TypeCheckFailure(FailureType.UNKNOWN_TYPE, f"Unknown type {t.name} encountered.")
            )

        return failures

    @staticmethod
    def get_type(param: Any) -> Optional[MacroType]:
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
