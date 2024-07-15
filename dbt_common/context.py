import os
from contextvars import ContextVar, copy_context
from typing import List, Mapping, Optional, Iterator

from dbt_common.constants import PRIVATE_ENV_PREFIX, SECRET_ENV_PREFIX
from dbt_common.record import Recorder


class CaseInsensitiveMapping(Mapping):
    def __init__(self, env: Mapping[str, str]):
        self._env = {k.casefold(): (k, v) for k, v in env.items()}

    def __getitem__(self, key: str) -> str:
        return self._env[key.casefold()][1]

    def __len__(self) -> int:
        return len(self._env)

    def __iter__(self) -> Iterator[str]:
        for item in self._env.items():
            yield item[0]


class InvocationContext:
    def __init__(self, env: Mapping[str, str]):
        self._env: Mapping[str, str]
        if os.name == "nt":
            self._env = CaseInsensitiveMapping({k: v for k, v in env.items() if not k.startswith(PRIVATE_ENV_PREFIX)})
        else:
            self._env = {k: v for k, v in env.items() if not k.startswith(PRIVATE_ENV_PREFIX)}

        self._env_secrets: Optional[List[str]] = None
        self._env_private = {k: v for k, v in env.items() if k.startswith(PRIVATE_ENV_PREFIX)}
        self.recorder: Optional[Recorder] = None
        # This class will also eventually manage the invocation_id, flags, event manager, etc.

    @property
    def env(self) -> Mapping[str, str]:
        return self._env

    @property
    def env_private(self) -> Mapping[str, str]:
        return self._env_private

    @property
    def env_secrets(self) -> List[str]:
        if self._env_secrets is None:
            self._env_secrets = [
                v for k, v in self.env.items() if k.startswith(SECRET_ENV_PREFIX) and v.strip()
            ]
        return self._env_secrets


_INVOCATION_CONTEXT_VAR: ContextVar[InvocationContext] = ContextVar("DBT_INVOCATION_CONTEXT_VAR")


def reliably_get_invocation_var() -> ContextVar[InvocationContext]:
    invocation_var: Optional[ContextVar] = next(
        (cv for cv in copy_context() if cv.name == _INVOCATION_CONTEXT_VAR.name), None
    )

    if invocation_var is None:
        invocation_var = _INVOCATION_CONTEXT_VAR

    return invocation_var


def set_invocation_context(env: Mapping[str, str]) -> None:
    invocation_var = reliably_get_invocation_var()
    invocation_var.set(InvocationContext(env))


def get_invocation_context() -> InvocationContext:
    invocation_var = reliably_get_invocation_var()
    ctx = invocation_var.get()
    return ctx
