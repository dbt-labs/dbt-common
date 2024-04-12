from dbt_common.ui import warning_tag, error_tag


def test_warning_tag():
    tagged = warning_tag("hi")
    assert "WARNING" in tagged


def test_error_tag():
    tagged = error_tag("hi")
    assert "ERROR" in tagged
