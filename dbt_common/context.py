from contextvars import ContextVar
import os
from typing import List, Mapping

from dbt_common.constants import SECRET_ENV_PREFIX


class InvocationContext:
    def __init__(self, env: Mapping[str, str]):
        self._env = env
        self._env_secrets: List[str] = None
        # This class will also eventually manage the invocation_id, flags, event manager, etc.

    @property
    def env(self) -> Mapping[str, str]:
        if self._env is None:
            self._env = os.environ

        return self._env

    @property
    def env_secrets(self) -> List[str]:
        return [v for k, v in self.env.items() if k.startswith(SECRET_ENV_PREFIX) and v.strip()]



_INVOCATION_CONTEXT_VAR: ContextVar[InvocationContext] = ContextVar("DBT_INVOCATION_CONTEXT_VAR")


def set_invocation_context() -> None:
    _INVOCATION_CONTEXT_VAR.set(InvocationContext())


def get_invocation_context() -> InvocationContext:
    ctx = _INVOCATION_CONTEXT_VAR.get()
    return ctx
