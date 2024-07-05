from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List

from dbt_common.dataclass_schema import dbtClassMixin, ValidationError


class ConstraintType(str, Enum):
    check = "check"
    not_null = "not_null"
    unique = "unique"
    primary_key = "primary_key"
    foreign_key = "foreign_key"
    custom = "custom"

    @classmethod
    def is_valid(cls, item) -> bool:
        try:
            cls(item)
        except ValueError:
            return False
        return True


@dataclass
class ColumnLevelConstraint(dbtClassMixin):
    type: ConstraintType
    name: Optional[str] = None
    # expression is a user-provided field that will depend on the constraint type.
    # It could be a predicate (check type), or a sequence sql keywords (e.g. unique type),
    # so the vague naming of 'expression' is intended to capture this range.
    expression: Optional[str] = None
    warn_unenforced: bool = (
        True  # Warn if constraint cannot be enforced by platform but will be in DDL
    )
    warn_unsupported: bool = (
        True  # Warn if constraint is not supported by the platform and won't be in DDL
    )
    to: Optional[str] = None
    to_column: Optional[str] = None

    @classmethod
    def validate(cls, data):
        super().validate(data)
        if data.get("type") is not ConstraintType.foreign_key:
            if data.get("to") is not None:
                raise ValidationError(f"Only column-level constraint of type {ConstraintType.foreign_key} can specify a 'to' field.")
            if data.get("to_column") is not None:
                raise ValidationError(f"Only column-level constraint of type {ConstraintType.foreign_key} can specify a 'to_column' field.")


@dataclass
class ModelLevelConstraint(ColumnLevelConstraint):
    columns: List[str] = field(default_factory=list)
    to: Optional[str] = None
    to_columns: List[str] = field(default_factory=list)

    @classmethod
    def validate(cls, data):
        super().validate(data)
        if data.get("type") is not ConstraintType.foreign_key:
            if data.get("to") is not None:
                raise ValidationError(f"Only model-level constraint of type {ConstraintType.foreign_key} can specify a 'to' field.")
            if data.get("to_columns") is not None:
                raise ValidationError(f"Only model-level constraint of type {ConstraintType.foreign_key} can specify a 'to_columns' field.")
