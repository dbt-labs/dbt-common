from _typeshed import Incomplete

SPLIT_RE: Incomplete

class JsonSchemaException(ValueError): ...

class JsonSchemaValueException(JsonSchemaException):
    message: Incomplete
    value: Incomplete
    name: Incomplete
    definition: Incomplete
    rule: Incomplete
    def __init__(
        self,
        message,
        value: Incomplete | None = ...,
        name: Incomplete | None = ...,
        definition: Incomplete | None = ...,
        rule: Incomplete | None = ...,
    ) -> None: ...
    @property
    def path(self): ...
    @property
    def rule_definition(self): ...

class JsonSchemaDefinitionException(JsonSchemaException): ...
