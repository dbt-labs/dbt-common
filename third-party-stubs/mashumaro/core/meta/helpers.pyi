from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    Optional,
    Sequence,
    Tuple,
    Type,
)

def get_type_origin(typ: Type[Any]) -> Type[Any]: ...
def get_generic_name(typ: Type[Any], short: bool = ...) -> str: ...
def get_args(typ: Optional[Type[Any]]) -> Tuple[Type[Any], ...]: ...
def get_literal_values(typ: Type[Any]) -> Tuple[Any, ...]: ...
def type_name(
    typ: Optional[Type[Any]],
    short: bool = ...,
    resolved_type_params: Optional[Dict[Type[Any], Type[Any]]] = ...,
    is_type_origin: bool = ...,
    none_type_as_none: bool = ...,
) -> str: ...
def is_special_typing_primitive(typ: Any) -> bool: ...
def is_generic(typ: Type[Any]) -> bool: ...
def is_typed_dict(typ: Type[Any]) -> bool: ...
def is_named_tuple(typ: Type[Any]) -> bool: ...
def is_new_type(typ: Type[Any]) -> bool: ...
def is_union(typ: Type[Any]) -> bool: ...
def is_optional(
    typ: Type[Any], resolved_type_params: Optional[Dict[Type[Any], Type[Any]]] = ...
) -> bool: ...
def is_annotated(typ: Type[Any]) -> bool: ...
def get_type_annotations(typ: Type[Any]) -> Sequence[Any]: ...
def is_literal(typ: Type[Any]) -> bool: ...
def not_none_type_arg(
    type_args: Tuple[Type[Any], ...],
    resolved_type_params: Optional[Dict[Type[Any], Type[Any]]] = ...,
) -> Optional[Type[Any]]: ...
def is_type_var(typ: Type[Any]) -> bool: ...
def is_type_var_any(typ: Type[Any]) -> bool: ...
def is_class_var(typ: Type[Any]) -> bool: ...
def is_final(typ: Type[Any]) -> bool: ...
def is_init_var(typ: Type[Any]) -> bool: ...
def get_class_that_defines_method(method_name: str, cls: Type[Any]) -> Optional[Type[Any]]: ...
def get_class_that_defines_field(field_name: str, cls: Type[Any]) -> Optional[Type[Any]]: ...
def is_dataclass_dict_mixin(typ: Type[Any]) -> bool: ...
def is_dataclass_dict_mixin_subclass(typ: Type[Any]) -> bool: ...
def collect_type_params(typ: Type[Any]) -> Sequence[Type[Any]]: ...
def resolve_type_params(
    typ: Type[Any], type_args: Sequence[Type[Any]] = ..., include_bases: bool = ...
) -> Dict[Type[Any], Dict[Type[Any], Type[Any]]]: ...
def substitute_type_params(
    typ: Type[Any], substitutions: Dict[Type[Any], Type[Any]]
) -> Type[Any]: ...
def get_name_error_name(e: NameError) -> str: ...
def is_dialect_subclass(typ: Type[Any]) -> bool: ...
def is_self(typ: Type[Any]) -> bool: ...
def is_required(typ: Type[Any]) -> bool: ...
def is_not_required(typ: Type[Any]) -> bool: ...
def get_function_arg_annotation(
    function: Callable[[Any], Any],
    arg_name: Optional[str] = ...,
    arg_pos: Optional[int] = ...,
) -> Type[Any]: ...
def get_function_return_annotation(function: Callable[[Any], Any]) -> Type[Any]: ...
def is_unpack(typ: Type[Any]) -> bool: ...
def is_type_var_tuple(typ: Type[Any]) -> bool: ...
def hash_type_args(type_args: Iterable[Type[Any]]) -> str: ...
def iter_all_subclasses(cls: Type[Any]) -> Iterator[Type[Any]]: ...
