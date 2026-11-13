import unittest

from dbt_common.utils.dict import deep_merge, merge, filter_null_values


class TestDeepMergeExtended(unittest.TestCase):
    def test_nested_dicts(self):
        a = {"top": {"a": 1, "b": 2}}
        b = {"top": {"b": 3, "c": 4}}
        result = deep_merge(a, b)
        assert result == {"top": {"a": 1, "b": 3, "c": 4}}

    def test_empty_dicts(self):
        assert deep_merge({}, {}) == {}

    def test_no_args(self):
        assert deep_merge() is None

    def test_single_arg(self):
        d = {"a": 1}
        result = deep_merge(d)
        assert result == d
        assert result is not d  # should be a copy

    def test_overlapping_list_values(self):
        a = {"x": [1, 2]}
        b = {"x": [3, 4]}
        result = deep_merge(a, b)
        # lists prepend source onto destination
        assert result == {"x": [3, 4, 1, 2]}

    def test_does_not_mutate_inputs(self):
        a = {"nested": {"k": "original"}}
        b = {"nested": {"k": "override"}}
        deep_merge(a, b)
        assert a["nested"]["k"] == "original"


class TestMergeShallow(unittest.TestCase):
    def test_no_args(self):
        assert merge() is None

    def test_single(self):
        assert merge({"a": 1}) == {"a": 1}

    def test_override(self):
        assert merge({"a": 1}, {"a": 2}) == {"a": 2}


class TestFilterNullValues(unittest.TestCase):
    def test_removes_nones(self):
        assert filter_null_values({"a": 1, "b": None}) == {"a": 1}

    def test_empty(self):
        assert filter_null_values({}) == {}
