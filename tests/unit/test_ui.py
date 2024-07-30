from dbt_common.ui import warning_tag, error_tag


def test_warning_tag() -> None:
    tagged = warning_tag("hi")
    assert "WARNING" in tagged


def test_error_tag() -> None:
    tagged = error_tag("hi")
    assert "ERROR" in tagged
