import functools
from gzip import BadGzipFile
from tarfile import ReadError

import pytest
from requests.exceptions import RequestException
from dbt_common.exceptions import ConnectionError, PackageTooLargeError
from dbt_common.utils.connection import connection_exception_retry


def no_retry_fn() -> str:
    return "success"


class TestNoRetries:
    def test_no_retry(self) -> None:
        fn_to_retry = functools.partial(no_retry_fn)
        result = connection_exception_retry(fn_to_retry, 3)

        expected = "success"

        assert result == expected


def no_success_fn() -> str:
    raise RequestException("You'll never pass")
    return "failure"


class TestMaxRetries:
    def test_no_retry(self) -> None:
        fn_to_retry = functools.partial(no_success_fn)

        with pytest.raises(ConnectionError):
            connection_exception_retry(fn_to_retry, 3)


counter = 0


def single_retry_fn() -> str:
    global counter
    if counter == 0:
        counter += 1
        raise RequestException("You won't pass this one time")
    elif counter == 1:
        counter += 1
        return "success on 2"

    return "How did we get here?"


class TestSingleRetry:
    def test_no_retry(self) -> None:
        global counter
        counter = 0

        fn_to_retry = functools.partial(single_retry_fn)
        result = connection_exception_retry(fn_to_retry, 3)
        expected = "success on 2"

        # We need to test the return value here, not just that it did not throw an error.
        # If the value is not being passed it causes cryptic errors
        assert result == expected
        assert counter == 2


class TestPackageTooLargeNotRetried:
    def test_package_too_large_passes_through_without_retry(self, mocker) -> None:
        sleep = mocker.patch("dbt_common.utils.connection.time.sleep")
        calls = []

        def too_large() -> None:
            calls.append(1)
            raise PackageTooLargeError("entry count", 11, 10, "DBT_PACKAGE_MAX_FILES")

        with pytest.raises(PackageTooLargeError):
            connection_exception_retry(too_large, 5)

        assert len(calls) == 1
        sleep.assert_not_called()

    def test_package_too_large_is_not_a_retryable_type(self) -> None:
        for retryable in (RequestException, ReadError, EOFError, BadGzipFile):
            assert not issubclass(PackageTooLargeError, retryable)
