import datetime
import decimal
import json
import unittest

from dbt_common.utils.encoding import md5, JSONEncoder, ForgivingJSONEncoder


class TestMd5(unittest.TestCase):
    def test_deterministic(self):
        assert md5("hello") == md5("hello")

    def test_different_inputs(self):
        assert md5("hello") != md5("world")

    def test_known_value(self):
        assert md5("") == "d41d8cd98f00b204e9800998ecf8427e"


class TestJSONEncoder(unittest.TestCase):
    def _dumps(self, obj):
        return json.dumps(obj, cls=JSONEncoder)

    def test_decimal(self):
        assert self._dumps(decimal.Decimal("1.5")) == "1.5"

    def test_datetime(self):
        dt = datetime.datetime(2024, 1, 15, 12, 0, 0)
        assert json.loads(self._dumps(dt)) == "2024-01-15T12:00:00"

    def test_date(self):
        d = datetime.date(2024, 1, 15)
        assert json.loads(self._dumps(d)) == "2024-01-15"

    def test_exception(self):
        result = json.loads(self._dumps(ValueError("test")))
        assert "ValueError" in result

    def test_unserializable_raises(self):
        with self.assertRaises(TypeError):
            self._dumps(object())


class TestForgivingJSONEncoder(unittest.TestCase):
    def test_fallback_to_str(self):
        result = json.loads(json.dumps(object(), cls=ForgivingJSONEncoder))
        assert "object" in result
