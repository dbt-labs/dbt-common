from dataclasses import dataclass, field
from dbt_common.dataclass_schema import dbtClassMixin
from typing import List, Dict, Optional, Any
from dbt_common.contracts.config.metadata import ShowBehavior
from dbt_common.contracts.config.base import (
    MergeBehavior,
    CompareBehavior,
    BaseConfig,
    merge_config_dicts,
)


@dataclass
class TableColumnNames(dbtClassMixin):
    first_column: Optional[str] = None
    second_column: Optional[str] = None
    third_column: Optional[str] = None


@dataclass
class SubstituteAdapterConfig(BaseConfig):
    pass


@dataclass
class ThingWithMergeBehavior(BaseConfig):
    default_behavior: Optional[int] = None
    tags: List[str] = field(metadata={"merge": MergeBehavior.Append}, default_factory=list)
    meta: Dict[str, int] = field(metadata={"merge": MergeBehavior.Update}, default_factory=dict)
    clobbered: Optional[str] = field(metadata={"merge": MergeBehavior.Clobber}, default=None)
    grants: Dict[str, Any] = field(
        metadata={"merge": MergeBehavior.DictKeyAppend}, default_factory=dict
    )
    snapshot_table_column_names: TableColumnNames = field(
        metadata={"merge": MergeBehavior.Object}, default_factory=TableColumnNames
    )


def test_merge_behavior_meta() -> None:
    existing = {"foo": "bar"}
    initial_existing = existing.copy()
    assert set(MergeBehavior) == {
        MergeBehavior.Append,
        MergeBehavior.Update,
        MergeBehavior.Clobber,
        MergeBehavior.DictKeyAppend,
        MergeBehavior.Object,
    }
    for behavior in MergeBehavior:
        assert behavior.meta() == {"merge": behavior}
        assert behavior.meta(existing) == {"merge": behavior, "foo": "bar"}
        assert existing == initial_existing


def test_merge_behavior_from_field() -> None:
    fields2 = {name: f for f, name in ThingWithMergeBehavior._get_fields()}
    assert set(fields2) == {
        "default_behavior",
        "tags",
        "meta",
        "clobbered",
        "grants",
        "snapshot_table_column_names",
    }
    assert MergeBehavior.from_field(fields2["default_behavior"]) == MergeBehavior.Clobber
    assert MergeBehavior.from_field(fields2["tags"]) == MergeBehavior.Append
    assert MergeBehavior.from_field(fields2["meta"]) == MergeBehavior.Update
    assert MergeBehavior.from_field(fields2["clobbered"]) == MergeBehavior.Clobber
    assert MergeBehavior.from_field(fields2["grants"]) == MergeBehavior.DictKeyAppend
    assert MergeBehavior.from_field(fields2["snapshot_table_column_names"]) == MergeBehavior.Object


def test_update_from() -> None:
    initial_dct = {
        "default_behavior": 4,
        "tags": ["one", "two"],
        "meta": {"one": 1, "two": 2},
        "clobbered": "initial",
        "grants": {"one": "alt"},
        "snapshot_table_column_names": {"second_column": "dbt_something"},
    }
    initial_obj = ThingWithMergeBehavior.from_dict(initial_dct.copy())
    assert initial_obj
    assert isinstance(initial_obj.snapshot_table_column_names, TableColumnNames)
    update_dct = {
        "default_behavior": 3,
        "tags": ["five"],
        "meta": {"two": 2, "three": 3},
        "clobbered": "later",
        "grants": {"two": "fine", "+one": "some"},
        "snapshot_table_column_names": {"first_column": "dbt_ack", "second_column": "dbt_more"},
    }
    updated_obj = initial_obj.update_from(update_dct.copy(), SubstituteAdapterConfig)

    assert updated_obj.default_behavior == 3
    assert updated_obj.tags == ["one", "two", "five"]
    assert updated_obj.meta == {"one": 1, "two": 2, "three": 3}
    assert updated_obj.clobbered == "later"
    assert updated_obj.grants == {"one": ["alt", "some"], "two": ["fine"]}
    assert updated_obj.snapshot_table_column_names.to_dict() == {
        "first_column": "dbt_ack",
        "second_column": "dbt_more",
        "third_column": None,
    }
    assert updated_obj.snapshot_table_column_names.first_column == "dbt_ack"
    assert updated_obj.snapshot_table_column_names.second_column == "dbt_more"
    assert updated_obj.snapshot_table_column_names.third_column is None

    merge_config_dicts(initial_dct, update_dct)

    expected = {
        "default_behavior": 3,
        "tags": ["one", "two", "five"],
        "meta": {"one": 1, "two": 2, "three": 3},
        "clobbered": "later",
        "grants": {"one": ["alt", "some"], "two": ["fine"]},
        "snapshot_table_column_names": {"first_column": "dbt_ack", "second_column": "dbt_more"},
    }

    assert initial_dct == expected


@dataclass
class ThingWithShowBehavior(dbtClassMixin):
    default_behavior: int
    hidden: str = field(metadata={"show_hide": ShowBehavior.Hide})
    shown: float = field(metadata={"show_hide": ShowBehavior.Show})


def test_show_behavior_meta() -> None:
    existing = {"foo": "bar"}
    initial_existing = existing.copy()
    assert set(ShowBehavior) == {ShowBehavior.Hide, ShowBehavior.Show}
    for behavior in ShowBehavior:
        assert behavior.meta() == {"show_hide": behavior}
        assert behavior.meta(existing) == {"show_hide": behavior, "foo": "bar"}
        assert existing == initial_existing


def test_show_behavior_from_field() -> None:
    fields2 = {name: f for f, name in ThingWithShowBehavior._get_fields()}
    assert set(fields2) == {"default_behavior", "hidden", "shown"}
    assert ShowBehavior.from_field(fields2["default_behavior"]) == ShowBehavior.Show
    assert ShowBehavior.from_field(fields2["hidden"]) == ShowBehavior.Hide
    assert ShowBehavior.from_field(fields2["shown"]) == ShowBehavior.Show


@dataclass
class ThingWithCompareBehavior(dbtClassMixin):
    default_behavior: int
    included: float = field(metadata={"compare": CompareBehavior.Include})
    excluded: str = field(metadata={"compare": CompareBehavior.Exclude})


def test_compare_behavior_meta() -> None:
    existing = {"foo": "bar"}
    initial_existing = existing.copy()
    assert set(CompareBehavior) == {CompareBehavior.Include, CompareBehavior.Exclude}
    for behavior in CompareBehavior:
        assert behavior.meta() == {"compare": behavior}
        assert behavior.meta(existing) == {"compare": behavior, "foo": "bar"}
        assert existing == initial_existing


def test_compare_behavior_from_field() -> None:
    fields2 = {name: f for f, name in ThingWithCompareBehavior._get_fields()}
    assert set(fields2) == {"default_behavior", "included", "excluded"}
    assert CompareBehavior.from_field(fields2["default_behavior"]) == CompareBehavior.Include
    assert CompareBehavior.from_field(fields2["included"]) == CompareBehavior.Include
    assert CompareBehavior.from_field(fields2["excluded"]) == CompareBehavior.Exclude
