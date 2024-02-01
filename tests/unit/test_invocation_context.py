from dbt_common.constants import SECRET_ENV_PREFIX
from dbt_common.context import InvocationContext


def test_invocation_context_env():
    test_env = {"VAR_1": "value1", "VAR_2": "value2"}
    ic = InvocationContext(env=test_env)
    assert ic.env == test_env


def test_invocation_context_secrets():
    test_env = {
        f"{SECRET_ENV_PREFIX}_VAR_1": "secret1",
        f"{SECRET_ENV_PREFIX}VAR_2": "secret2",
        f"NON_SECRET": "nonsecret",
        f"foo{SECRET_ENV_PREFIX}": "nonsecret",
    }
    ic = InvocationContext(env=test_env)
    assert set(ic.env_secrets) == set(["secret1", "secret2"])
