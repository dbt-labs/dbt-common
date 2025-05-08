from dbt_common.ui import deprecation_tag, warning_tag, error_tag


def test_warning_tag() -> None:
    tagged = warning_tag("hi")
    assert tagged == "[\x1b[33mWARNING\x1b[0m]: hi"

    tagged = warning_tag("hi", "MyWarningEvent")
    assert tagged == "[\x1b[33mWARNING\x1b[0m][MyWarningEvent]: hi"


def test_error_tag() -> None:
    tagged = error_tag("hi")
    assert tagged == "[\x1b[31mERROR\x1b[0m]: hi"

    tagged = error_tag("hi", "MyErrorEvent")
    assert tagged == "[\x1b[31mERROR\x1b[0m][MyErrorEvent]: hi"


def test_deprecation_tag() -> None:
    tagged = deprecation_tag("hi")
    assert tagged == "[\x1b[33mWARNING\x1b[0m]: Deprecated functionality\n\nhi"

    tagged = deprecation_tag("hi", "MyDeprecationEvent")
    assert tagged == "[\x1b[33mWARNING\x1b[0m][MyDeprecationEvent]: Deprecated functionality\n\nhi"
