import unittest

from dataclasses import dataclass
from dbt_common.contracts.util import Mergeable
from typing import List, Optional


@dataclass
class ExampleMergableClass(Mergeable):
    attr_a: str
    attr_b: Optional[int]
    attr_c: Optional[List[str]]


class TestMergableClass(unittest.TestCase):
    def test_mergeability(self) -> None:
        mergeable1 = ExampleMergableClass(
            attr_a="loses", attr_b=None, attr_c=["I'll", "still", "exist"]
        )
        mergeable2 = ExampleMergableClass(attr_a="Wins", attr_b=1, attr_c=None)
        merge_result: ExampleMergableClass = mergeable1.merged(mergeable2)
        assert (
            merge_result.attr_a == mergeable2.attr_a
        )  # mergeable2's attr_a is the "last" non None value
        assert merge_result.attr_b == mergeable2.attr_b  # mergeable1's attrb_b value was None
        assert merge_result.attr_c == mergeable1.attr_c  # mergeable2's attr_c value was None
