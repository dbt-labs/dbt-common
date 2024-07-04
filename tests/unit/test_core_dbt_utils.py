import requests
import tarfile
import unittest

from dbt_common.exceptions import ConnectionError
from dbt_common.utils.connection import connection_exception_retry


class TestCommonDbtUtils(unittest.TestCase):
    def test_connection_exception_retry_none(self) -> None:
        Counter._reset()
        connection_exception_retry(lambda: Counter._add(), 5)
        self.assertEqual(1, counter)

    def test_connection_exception_retry_success_requests_exception(self) -> None:
        Counter._reset()
        connection_exception_retry(lambda: Counter._add_with_requests_exception(), 5)
        self.assertEqual(2, counter)  # 2 = original attempt returned None, plus 1 retry

    def test_connection_exception_retry_max(self) -> None:
        Counter._reset()
        with self.assertRaises(ConnectionError):
            connection_exception_retry(lambda: Counter._add_with_exception(), 5)
        self.assertEqual(6, counter)  # 6 = original attempt plus 5 retries

    def test_connection_exception_retry_success_failed_untar(self) -> None:
        Counter._reset()
        connection_exception_retry(lambda: Counter._add_with_untar_exception(), 5)
        self.assertEqual(2, counter)  # 2 = original attempt returned ReadError, plus 1 retry

    def test_connection_exception_retry_success_failed_eofexception(self) -> None:
        Counter._reset()
        connection_exception_retry(lambda: Counter._add_with_eof_exception(), 5)
        self.assertEqual(2, counter)  # 2 = original attempt returned EOFError, plus 1 retry


counter: int = 0


class Counter:
    @classmethod
    def _add(cls) -> None:
        global counter
        counter += 1

    # All exceptions that Requests explicitly raises inherit from
    # requests.exceptions.RequestException so we want to make sure that raises plus one exception
    # that inherit from it for sanity
    @classmethod
    def _add_with_requests_exception(cls) -> None:
        global counter
        counter += 1
        if counter < 2:
            raise requests.exceptions.RequestException

    @classmethod
    def _add_with_exception(cls) -> None:
        global counter
        counter += 1
        raise requests.exceptions.ConnectionError

    @classmethod
    def _add_with_untar_exception(cls) -> None:
        global counter
        counter += 1
        if counter < 2:
            raise tarfile.ReadError

    @classmethod
    def _add_with_eof_exception(cls) -> None:
        global counter
        counter += 1
        if counter < 2:
            raise EOFError

    @classmethod
    def _reset(cls) -> None:
        global counter
        counter = 0
