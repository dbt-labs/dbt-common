from dbt_common.invocation import get_invocation_id, get_invocation_started_at, reset_invocation_id


def test_invocation_started_at():
    inv_id = get_invocation_id()
    assert inv_id
    inv_start = get_invocation_started_at()
    assert inv_start

    reset_invocation_id()
    inv_start != get_invocation_started_at()
    inv_id != get_invocation_id()
