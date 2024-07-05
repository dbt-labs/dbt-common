from dbt_common.constants import PRIVATE_ENV_PREFIX, SECRET_ENV_PREFIX
from dbt_common.context import InvocationContext


def test_invocation_context_env() -> None:
    test_env = {"VAR_1": "value1", "VAR_2": "value2"}
    ic = InvocationContext(env=test_env)
    assert ic.env == test_env


def test_invocation_context_secrets() -> None:
    test_env = {
        f"{SECRET_ENV_PREFIX}_VAR_1": "secret1",
        f"{SECRET_ENV_PREFIX}VAR_2": "secret2",
        "NON_SECRET": "non-secret",
        f"foo{SECRET_ENV_PREFIX}": "non-secret",
    }
    ic = InvocationContext(env=test_env)
    assert set(ic.env_secrets) == {"secret1", "secret2"}


def test_invocation_context_private() -> None:
    test_env = {
        f"{PRIVATE_ENV_PREFIX}_VAR_1": "private1",
        f"{PRIVATE_ENV_PREFIX}VAR_2": "private2",
        f"{PRIVATE_ENV_PREFIX}": "private3",
        "NON_PRIVATE": "non-private-1",
        f"foo{PRIVATE_ENV_PREFIX}": "non-private-2",
    }
    ic = InvocationContext(env=test_env)
    assert ic.env_secrets == []
    assert ic.env_private == {
        f"{PRIVATE_ENV_PREFIX}_VAR_1": "private1",
        f"{PRIVATE_ENV_PREFIX}VAR_2": "private2",
        f"{PRIVATE_ENV_PREFIX}": "private3",
    }
    assert ic.env == {"NON_PRIVATE": "non-private-1", f"foo{PRIVATE_ENV_PREFIX}": "non-private-2"}
