import json
from inspect import Traceback
from typing import Any, Callable, Dict, List, Optional, Type

import pytest
from dbt_common.record import Diff

Case = List[Dict[str, Any]]


@pytest.fixture
def current_query() -> Case:
    return [
        {
            "params": {
                "a": 1,
            },
            "result": {
                "this": "key",
                "table": '[{"a": 5},{"b": 7}]',
            },
        }
    ]


@pytest.fixture
def query_modified_order() -> Case:
    return [
        {
            "params": {
                "a": 1,
            },
            "result": {
                "this": "key",
                "table": '[{"b": 7},{"a": 5}]',
            },
        }
    ]


@pytest.fixture
def query_modified_value() -> Case:
    return [
        {
            "params": {
                "a": 1,
            },
            "result": {
                "this": "key",
                "table": '[{"a": 5},{"b": 10}]',
            },
        }
    ]


@pytest.fixture
def current_simple() -> Case:
    return [
        {
            "params": {
                "a": 1,
            },
            "result": {
                "this": "cat",
            },
        }
    ]


@pytest.fixture
def current_simple_modified() -> Case:
    return [
        {
            "params": {
                "a": 1,
            },
            "result": {
                "this": "dog",
            },
        }
    ]


@pytest.fixture
def env_record() -> Case:
    return [
        {
            "params": {},
            "result": {
                "env": {
                    "DBT_RECORDER_FILE_PATH": "record.json",
                    "ANOTHER_ENV_VAR": "dogs",
                },
            },
        }
    ]


@pytest.fixture
def modified_env_record() -> Case:
    return [
        {
            "params": {},
            "result": {
                "env": {
                    "DBT_RECORDER_FILE_PATH": "another_record.json",
                    "ANOTHER_ENV_VAR": "cats",
                },
            },
        }
    ]


def test_diff_query_records_no_diff(current_query: Case, query_modified_order: Case) -> None:
    # Setup: Create an instance of Diff
    diff_instance = Diff(
        current_recording_path="path/to/current", previous_recording_path="path/to/previous"
    )
    result = diff_instance.diff_query_records(current_query, query_modified_order)
    # the order changed but the diff should be empty
    expected_result: Dict[str, Any] = {}
    assert result == expected_result  # Replace expected_result with what you actually expect


def test_diff_query_records_with_diff(current_query: Case, query_modified_value: Case) -> None:
    diff_instance = Diff(
        current_recording_path="path/to/current", previous_recording_path="path/to/previous"
    )
    result = diff_instance.diff_query_records(current_query, query_modified_value)
    # the values changed this time
    expected_result: Dict[str, Any] = {
        "values_changed": {"root[0]['result']['table'][1]['b']": {"new_value": 7, "old_value": 10}}
    }
    assert result == expected_result


def test_diff_env_records(env_record: Case, modified_env_record: Case) -> None:
    diff_instance = Diff(
        current_recording_path="path/to/current", previous_recording_path="path/to/previous"
    )
    result = diff_instance.diff_env_records(env_record, modified_env_record)
    expected_result = {
        "values_changed": {
            "root[0]['result']['env']['ANOTHER_ENV_VAR']": {
                "new_value": "dogs",
                "old_value": "cats",
            }
        }
    }
    assert result == expected_result


def test_diff_default_no_diff(current_simple: Case) -> None:
    diff_instance = Diff(
        current_recording_path="path/to/current", previous_recording_path="path/to/previous"
    )
    # use the same list to ensure no diff
    result = diff_instance.diff_default(current_simple, current_simple)
    expected_result: Dict[str, Any] = {}
    assert result == expected_result


def test_diff_default_with_diff(current_simple: Case, current_simple_modified: Case) -> None:
    diff_instance = Diff(
        current_recording_path="path/to/current", previous_recording_path="path/to/previous"
    )
    result = diff_instance.diff_default(current_simple, current_simple_modified)
    expected_result = {
        "values_changed": {"root[0]['result']['this']": {"new_value": "cat", "old_value": "dog"}}
    }
    assert result == expected_result


# Mock out reading the files so we don't have to
class MockFile:
    def __init__(self, json_data: Any) -> None:
        self.json_data = json_data

    def __enter__(self) -> "MockFile":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[Exception]],
        exc_val: Optional[Exception],
        exc_tb: Optional[Traceback],
    ) -> None:
        pass

    def read(self) -> str:
        return json.dumps(self.json_data)


# Create a Mock Open Function
def mock_open(mock_files: Dict[str, Any]) -> Callable[..., MockFile]:
    def open_mock(file: str, *args: Any, **kwargs: Any) -> MockFile:
        if file in mock_files:
            return MockFile(mock_files[file])
        raise FileNotFoundError(f"No mock file found for {file}")

    return open_mock


def test_calculate_diff_no_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock data for the files
    current_recording_data = {
        "GetEnvRecord": [
            {
                "params": {
                    "a": 1,
                },
                "result": {
                    "this": "dog",
                },
            }
        ],
        "DefaultKey": [
            {
                "params": {
                    "a": 1,
                },
                "result": {
                    "this": "dog",
                },
            }
        ],
    }
    previous_recording_data = {
        "GetEnvRecord": [
            {
                "params": {
                    "a": 1,
                },
                "result": {
                    "this": "dog",
                },
            }
        ],
        "DefaultKey": [
            {
                "params": {
                    "a": 1,
                },
                "result": {
                    "this": "dog",
                },
            }
        ],
    }
    current_recording_path = "/path/to/current_recording.json"
    previous_recording_path = "/path/to/previous_recording.json"
    mock_files = {
        current_recording_path: current_recording_data,
        previous_recording_path: previous_recording_data,
    }
    monkeypatch.setattr("builtins.open", mock_open(mock_files))

    # test the diff
    diff_instance = Diff(
        current_recording_path=current_recording_path,
        previous_recording_path=previous_recording_path,
    )
    result = diff_instance.calculate_diff()
    expected_result: Dict[str, Any] = {"GetEnvRecord": {}, "DefaultKey": {}}
    assert result == expected_result


def test_calculate_diff_with_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    # Mock data for the files
    current_recording_data = {
        "GetEnvRecord": [
            {
                "params": {
                    "a": 1,
                },
                "result": {
                    "this": "dog",
                },
            }
        ]
    }
    previous_recording_data = {
        "GetEnvRecord": [
            {
                "params": {
                    "a": 1,
                },
                "result": {
                    "this": "cats",
                },
            }
        ]
    }
    current_recording_path = "/path/to/current_recording.json"
    previous_recording_path = "/path/to/previous_recording.json"
    mock_files = {
        current_recording_path: current_recording_data,
        previous_recording_path: previous_recording_data,
    }
    monkeypatch.setattr("builtins.open", mock_open(mock_files))

    # test the diff
    diff_instance = Diff(
        current_recording_path=current_recording_path,
        previous_recording_path=previous_recording_path,
    )
    result = diff_instance.calculate_diff()
    expected_result = {
        "GetEnvRecord": {
            "values_changed": {
                "root[0]['result']['this']": {"new_value": "dog", "old_value": "cats"}
            }
        }
    }
    assert result == expected_result
