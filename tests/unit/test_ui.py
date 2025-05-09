from dbt_common.ui import deprecation_tag, warning_tag, error_tag


def test_warning_tag() -> None:
    tagged = warning_tag("hi")
    assert "WARNING" in tagged
    assert "hi" in tagged

    tagged = warning_tag("hi", "MyWarningEvent")
    assert "WARNING" in tagged
    assert "[MyWarningEvent]:" in tagged
    assert "hi" in tagged


def test_error_tag() -> None:
    tagged = error_tag("hi")
    assert "ERROR" in tagged
    assert "hi" in tagged

    tagged = error_tag("hi", "MyErrorEvent")
    assert "ERROR" in tagged
    assert "[MyErrorEvent]:" in tagged
    assert "hi" in tagged


def test_deprecation_tag() -> None:
    tagged = deprecation_tag("hi")
    assert "WARNING" in tagged
    assert "Deprecated functionality" in tagged
    assert "hi" in tagged

    tagged = deprecation_tag("hi", "MyDeprecationEvent")
    assert "WARNING" in tagged
    assert "[MyDeprecationEvent]:" in tagged
    assert "Deprecated functionality" in tagged
    assert "hi" in tagged
