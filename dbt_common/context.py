from contextvars import ContextVar
from typing import List, Mapping, Optional

from dbt_common.constants import SECRET_ENV_PREFIX


class InvocationContext:
    def __init__(self, env: Mapping[str, str]):
        self._env = env
        self._env_secrets: Optional[List[str]] = None
        # This class will also eventually manage the invocation_id, flags, event manager, etc.

    @property
    def env(self) -> Mapping[str, str]:
        return self._env

    @property
    def env_secrets(self) -> List[str]:
        if self._env_secrets is None:
            self._env_secrets = [
                v for k, v in self.env.items() if k.startswith(SECRET_ENV_PREFIX) and v.strip()
            ]
        return self._env_secrets


_INVOCATION_CONTEXT_VAR: ContextVar[InvocationContext] = ContextVar("DBT_INVOCATION_CONTEXT_VAR")


def set_invocation_context(env: Mapping[str, str]) -> None:
    _INVOCATION_CONTEXT_VAR.set(InvocationContext(env))


def get_invocation_context() -> InvocationContext:
    ctx = _INVOCATION_CONTEXT_VAR.get()
    return ctx
