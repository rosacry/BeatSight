"""Tests for collection utilities."""

from dataclasses import dataclass

import pytest

from app.utils.collections import (
    # List operations
    chunk,
    chunk_iter,
    flatten,
    deep_flatten,
    dedupe,
    compact,
    compact_falsy,
    take,
    drop,
    take_while,
    drop_while,
    first,
    last,
    find_index,
    find_all_indices,
    interleave,
    intersperse,
    rotate,
    sliding_window,
    # Grouping
    group_by,
    group_by_attr,
    partition,
    partition_by,
    frequencies,
    top_n,
    bottom_n,
    # Dict operations
    deep_get,
    deep_set,
    deep_delete,
    deep_merge,
    filter_dict,
    filter_dict_keys,
    exclude_dict_keys,
    map_dict_keys,
    map_dict_values,
    invert_dict,
    invert_dict_multi,
    flatten_dict,
    unflatten_dict,
    pick,
    omit,
    defaults,
    # Comparison
    diff_dicts,
    intersection_dicts,
    # Safe access
    safe_get,
    pluck,
    pluck_attr,
    # Ordering
    sort_by,
    order_by,
    # Reduction
    sum_by,
    count_by,
    min_by,
    max_by,
    # Set operations
    union_lists,
    intersect_lists,
    difference_lists,
    symmetric_difference_lists,
)


class TestChunking:
    """Tests for chunk functions."""

    def test_chunk_basic(self):
        """Test basic chunking."""
        result = list(chunk([1, 2, 3, 4, 5], 2))
        assert result == [[1, 2], [3, 4], [5]]

    def test_chunk_even_split(self):
        """Test chunking with even split."""
        result = list(chunk([1, 2, 3, 4], 2))
        assert result == [[1, 2], [3, 4]]

    def test_chunk_size_larger_than_list(self):
        """Test chunk size larger than list."""
        result = list(chunk([1, 2, 3], 10))
        assert result == [[1, 2, 3]]

    def test_chunk_empty_list(self):
        """Test chunking empty list."""
        result = list(chunk([], 2))
        assert result == []

    def test_chunk_invalid_size(self):
        """Test chunk with invalid size."""
        with pytest.raises(ValueError):
            list(chunk([1, 2, 3], 0))
        with pytest.raises(ValueError):
            list(chunk([1, 2, 3], -1))

    def test_chunk_iter_generator(self):
        """Test chunk_iter with generator."""
        gen = (x for x in range(5))
        result = list(chunk_iter(gen, 2))
        assert result == [[0, 1], [2, 3], [4]]

    def test_chunk_iter_empty(self):
        """Test chunk_iter with empty generator."""
        gen = (x for x in [])
        result = list(chunk_iter(gen, 2))
        assert result == []


class TestFlatten:
    """Tests for flatten functions."""

    def test_flatten_basic(self):
        """Test basic flattening."""
        result = flatten([[1, 2], [3, 4], [5]])
        assert result == [1, 2, 3, 4, 5]

    def test_flatten_empty_sublists(self):
        """Test flattening with empty sublists."""
        result = flatten([[1], [], [2, 3]])
        assert result == [1, 2, 3]

    def test_flatten_empty_input(self):
        """Test flattening empty input."""
        result = flatten([])
        assert result == []

    def test_deep_flatten_nested(self):
        """Test deep flatten with nested lists."""
        result = deep_flatten([[1, [2, 3]], [4, [5, [6]]]])
        assert result == [1, 2, 3, 4, 5, 6]

    def test_deep_flatten_preserves_strings(self):
        """Test deep flatten doesn't break strings."""
        result = deep_flatten([["hello", ["world"]]])
        assert result == ["hello", "world"]

    def test_deep_flatten_max_depth(self):
        """Test deep flatten with max depth."""
        # max_depth=1 means flatten only 1 level deep
        result = deep_flatten([[1, [2, [3]]]], max_depth=1)
        assert result == [1, [2, [3]]]

        # max_depth=2 means flatten 2 levels
        result2 = deep_flatten([[1, [2, [3]]]], max_depth=2)
        assert result2 == [1, 2, [3]]

    def test_deep_flatten_mixed_types(self):
        """Test deep flatten with mixed types."""
        result = deep_flatten([1, [2, (3, 4)], 5])
        assert result == [1, 2, 3, 4, 5]


class TestDedupe:
    """Tests for deduplication."""

    def test_dedupe_basic(self):
        """Test basic deduplication."""
        result = dedupe([1, 2, 2, 3, 1, 4])
        assert result == [1, 2, 3, 4]

    def test_dedupe_preserves_order(self):
        """Test dedupe preserves first occurrence order."""
        result = dedupe([3, 1, 2, 1, 3, 4])
        assert result == [3, 1, 2, 4]

    def test_dedupe_with_key(self):
        """Test dedupe with key function."""
        result = dedupe(["a", "A", "b", "B"], key=str.lower)
        assert result == ["a", "b"]

    def test_dedupe_empty(self):
        """Test dedupe on empty list."""
        result = dedupe([])
        assert result == []


class TestCompact:
    """Tests for compact functions."""

    def test_compact_basic(self):
        """Test basic compact."""
        result = compact([1, None, 2, None, 3])
        assert result == [1, 2, 3]

    def test_compact_all_none(self):
        """Test compact with all None."""
        result = compact([None, None, None])
        assert result == []

    def test_compact_falsy_basic(self):
        """Test compact_falsy."""
        result = compact_falsy([1, 0, 2, "", 3, None, [], False])
        assert result == [1, 2, 3]

    def test_compact_preserves_zero(self):
        """Test compact preserves zero (compact only removes None)."""
        result = compact([1, 0, None, 2])
        assert result == [1, 0, 2]


class TestTakeAndDrop:
    """Tests for take and drop functions."""

    def test_take_basic(self):
        """Test basic take."""
        result = take([1, 2, 3, 4, 5], 3)
        assert result == [1, 2, 3]

    def test_take_more_than_available(self):
        """Test take more than available."""
        result = take([1, 2], 5)
        assert result == [1, 2]

    def test_take_from_generator(self):
        """Test take from generator."""
        gen = (x for x in range(10))
        result = take(gen, 3)
        assert result == [0, 1, 2]

    def test_drop_basic(self):
        """Test basic drop."""
        result = drop([1, 2, 3, 4, 5], 2)
        assert result == [3, 4, 5]

    def test_drop_all(self):
        """Test drop all elements."""
        result = drop([1, 2, 3], 5)
        assert result == []

    def test_take_while_basic(self):
        """Test take_while."""
        result = take_while([1, 2, 3, 4, 1, 2], lambda x: x < 4)
        assert result == [1, 2, 3]

    def test_take_while_all(self):
        """Test take_while takes all."""
        result = take_while([1, 2, 3], lambda x: x < 10)
        assert result == [1, 2, 3]

    def test_drop_while_basic(self):
        """Test drop_while."""
        result = drop_while([1, 2, 3, 4, 1, 2], lambda x: x < 3)
        assert result == [3, 4, 1, 2]

    def test_drop_while_all(self):
        """Test drop_while drops all."""
        result = drop_while([1, 2, 3], lambda x: x < 10)
        assert result == []


class TestFirstAndLast:
    """Tests for first and last functions."""

    def test_first_basic(self):
        """Test basic first."""
        assert first([1, 2, 3]) == 1

    def test_first_empty(self):
        """Test first on empty list."""
        assert first([]) is None

    def test_first_with_default(self):
        """Test first with default."""
        assert first([], default=0) == 0

    def test_first_with_predicate(self):
        """Test first with predicate."""
        result = first([1, 2, 3, 4], predicate=lambda x: x > 2)
        assert result == 3

    def test_first_predicate_no_match(self):
        """Test first with predicate no match."""
        result = first([1, 2, 3], predicate=lambda x: x > 10, default=-1)
        assert result == -1

    def test_last_basic(self):
        """Test basic last."""
        assert last([1, 2, 3]) == 3

    def test_last_empty(self):
        """Test last on empty list."""
        assert last([]) is None

    def test_last_with_predicate(self):
        """Test last with predicate."""
        result = last([1, 2, 3, 4], predicate=lambda x: x < 3)
        assert result == 2


class TestFindIndex:
    """Tests for index finding functions."""

    def test_find_index_basic(self):
        """Test basic find_index."""
        result = find_index([1, 2, 3, 4], lambda x: x > 2)
        assert result == 2

    def test_find_index_not_found(self):
        """Test find_index not found."""
        result = find_index([1, 2, 3], lambda x: x > 10)
        assert result is None

    def test_find_all_indices_basic(self):
        """Test find_all_indices."""
        result = find_all_indices([1, 2, 3, 2, 4], lambda x: x == 2)
        assert result == [1, 3]

    def test_find_all_indices_none(self):
        """Test find_all_indices with no matches."""
        result = find_all_indices([1, 2, 3], lambda x: x > 10)
        assert result == []


class TestInterleave:
    """Tests for interleave and intersperse."""

    def test_interleave_basic(self):
        """Test basic interleave."""
        result = interleave([1, 2, 3], ["a", "b", "c"])
        assert result == [1, "a", 2, "b", 3, "c"]

    def test_interleave_unequal_lengths(self):
        """Test interleave with unequal lengths."""
        result = interleave([1, 2], ["a", "b", "c"])
        assert result == [1, "a", 2, "b", "c"]

    def test_interleave_three_lists(self):
        """Test interleave with three lists."""
        result = interleave([1, 2], ["a", "b"], ["x", "y"])
        assert result == [1, "a", "x", 2, "b", "y"]

    def test_intersperse_basic(self):
        """Test basic intersperse."""
        result = intersperse([1, 2, 3], 0)
        assert result == [1, 0, 2, 0, 3]

    def test_intersperse_single_element(self):
        """Test intersperse with single element."""
        result = intersperse([1], 0)
        assert result == [1]

    def test_intersperse_empty(self):
        """Test intersperse with empty list."""
        result = intersperse([], 0)
        assert result == []


class TestRotate:
    """Tests for rotate function."""

    def test_rotate_right(self):
        """Test rotate right."""
        result = rotate([1, 2, 3, 4, 5], 2)
        assert result == [4, 5, 1, 2, 3]

    def test_rotate_left(self):
        """Test rotate left."""
        result = rotate([1, 2, 3, 4, 5], -2)
        assert result == [3, 4, 5, 1, 2]

    def test_rotate_full_cycle(self):
        """Test rotate full cycle."""
        result = rotate([1, 2, 3], 3)
        assert result == [1, 2, 3]

    def test_rotate_empty(self):
        """Test rotate empty list."""
        result = rotate([], 2)
        assert result == []


class TestSlidingWindow:
    """Tests for sliding_window function."""

    def test_sliding_window_basic(self):
        """Test basic sliding window."""
        result = list(sliding_window([1, 2, 3, 4, 5], 3))
        assert result == [[1, 2, 3], [2, 3, 4], [3, 4, 5]]

    def test_sliding_window_with_step(self):
        """Test sliding window with step."""
        result = list(sliding_window([1, 2, 3, 4, 5], 2, step=2))
        assert result == [[1, 2], [3, 4]]

    def test_sliding_window_size_equals_length(self):
        """Test window size equals list length."""
        result = list(sliding_window([1, 2, 3], 3))
        assert result == [[1, 2, 3]]

    def test_sliding_window_invalid_params(self):
        """Test invalid window parameters."""
        with pytest.raises(ValueError):
            list(sliding_window([1, 2, 3], 0))
        with pytest.raises(ValueError):
            list(sliding_window([1, 2, 3], 2, step=0))


class TestGroupBy:
    """Tests for group_by functions."""

    def test_group_by_basic(self):
        """Test basic group_by."""
        result = group_by([1, 2, 3, 4, 5], lambda x: x % 2)
        assert result == {1: [1, 3, 5], 0: [2, 4]}

    def test_group_by_strings(self):
        """Test group_by with strings."""
        result = group_by(["apple", "banana", "apricot"], lambda x: x[0])
        assert result == {"a": ["apple", "apricot"], "b": ["banana"]}

    def test_group_by_attr(self):
        """Test group_by_attr."""

        @dataclass
        class User:
            role: str
            name: str

        users = [
            User("admin", "Alice"),
            User("user", "Bob"),
            User("admin", "Charlie"),
        ]
        result = group_by_attr(users, "role")
        assert len(result["admin"]) == 2
        assert len(result["user"]) == 1


class TestPartition:
    """Tests for partition functions."""

    def test_partition_basic(self):
        """Test basic partition."""
        evens, odds = partition([1, 2, 3, 4, 5], lambda x: x % 2 == 0)
        assert evens == [2, 4]
        assert odds == [1, 3, 5]

    def test_partition_empty_group(self):
        """Test partition with empty group."""
        matching, not_matching = partition([1, 3, 5], lambda x: x % 2 == 0)
        assert matching == []
        assert not_matching == [1, 3, 5]

    def test_partition_by_basic(self):
        """Test partition_by."""
        result = partition_by([1, 1, 2, 2, 2, 1, 1], lambda x: x)
        assert result == [[1, 1], [2, 2, 2], [1, 1]]


class TestFrequencies:
    """Tests for frequency and ranking functions."""

    def test_frequencies_basic(self):
        """Test basic frequencies."""
        result = frequencies([1, 2, 2, 3, 3, 3])
        assert result == {1: 1, 2: 2, 3: 3}

    def test_top_n_basic(self):
        """Test basic top_n."""
        result = top_n([1, 5, 2, 8, 3], 3)
        assert result == [8, 5, 3]

    def test_top_n_with_key(self):
        """Test top_n with key function."""
        data = [{"v": 1}, {"v": 5}, {"v": 3}]
        result = top_n(data, 2, key=lambda x: x["v"])
        assert result == [{"v": 5}, {"v": 3}]

    def test_bottom_n_basic(self):
        """Test basic bottom_n."""
        result = bottom_n([1, 5, 2, 8, 3], 3)
        assert result == [1, 2, 3]


class TestDeepGet:
    """Tests for deep_get function."""

    def test_deep_get_simple(self):
        """Test simple deep_get."""
        data = {"a": {"b": {"c": 1}}}
        assert deep_get(data, "a.b.c") == 1

    def test_deep_get_not_found(self):
        """Test deep_get not found."""
        data = {"a": {"b": 1}}
        assert deep_get(data, "a.c") is None
        assert deep_get(data, "a.c", default=0) == 0

    def test_deep_get_list_index(self):
        """Test deep_get with list index."""
        data = {"items": [1, 2, 3]}
        assert deep_get(data, "items.1") == 2

    def test_deep_get_custom_separator(self):
        """Test deep_get with custom separator."""
        data = {"a": {"b": 1}}
        assert deep_get(data, "a/b", separator="/") == 1


class TestDeepSet:
    """Tests for deep_set function."""

    def test_deep_set_simple(self):
        """Test simple deep_set."""
        data: dict = {}
        deep_set(data, "a.b.c", 1)
        assert data == {"a": {"b": {"c": 1}}}

    def test_deep_set_existing(self):
        """Test deep_set on existing structure."""
        data = {"a": {"b": 1}}
        deep_set(data, "a.c", 2)
        assert data == {"a": {"b": 1, "c": 2}}

    def test_deep_set_overwrite(self):
        """Test deep_set overwrites value."""
        data = {"a": {"b": 1}}
        deep_set(data, "a.b", 2)
        assert data == {"a": {"b": 2}}


class TestDeepDelete:
    """Tests for deep_delete function."""

    def test_deep_delete_simple(self):
        """Test simple deep_delete."""
        data = {"a": {"b": {"c": 1}}}
        result = deep_delete(data, "a.b.c")
        assert result is True
        assert data == {"a": {"b": {}}}

    def test_deep_delete_not_found(self):
        """Test deep_delete not found."""
        data = {"a": {"b": 1}}
        result = deep_delete(data, "a.c")
        assert result is False


class TestDeepMerge:
    """Tests for deep_merge function."""

    def test_deep_merge_basic(self):
        """Test basic deep merge."""
        base = {"a": 1, "b": {"c": 2}}
        override = {"b": {"d": 3}, "e": 4}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}

    def test_deep_merge_overwrite(self):
        """Test deep merge overwrites non-dict values."""
        base = {"a": {"b": 1}}
        override = {"a": {"b": 2}}
        result = deep_merge(base, override)
        assert result == {"a": {"b": 2}}

    def test_deep_merge_preserves_original(self):
        """Test deep merge preserves original."""
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        deep_merge(base, override)
        assert base == {"a": {"b": 1}}


class TestDictFiltering:
    """Tests for dict filtering functions."""

    def test_filter_dict_basic(self):
        """Test basic filter_dict."""
        result = filter_dict({"a": 1, "b": 2, "c": 3}, lambda k, v: v > 1)
        assert result == {"b": 2, "c": 3}

    def test_filter_dict_keys(self):
        """Test filter_dict_keys."""
        result = filter_dict_keys({"a": 1, "b": 2, "c": 3}, {"a", "c"})
        assert result == {"a": 1, "c": 3}

    def test_exclude_dict_keys(self):
        """Test exclude_dict_keys."""
        result = exclude_dict_keys({"a": 1, "b": 2, "c": 3}, {"b"})
        assert result == {"a": 1, "c": 3}


class TestDictMapping:
    """Tests for dict mapping functions."""

    def test_map_dict_keys(self):
        """Test map_dict_keys."""
        result = map_dict_keys({"a": 1, "b": 2}, str.upper)
        assert result == {"A": 1, "B": 2}

    def test_map_dict_values(self):
        """Test map_dict_values."""
        result = map_dict_values({"a": 1, "b": 2}, lambda x: x * 2)
        assert result == {"a": 2, "b": 4}

    def test_invert_dict(self):
        """Test invert_dict."""
        result = invert_dict({"a": 1, "b": 2})
        assert result == {1: "a", 2: "b"}

    def test_invert_dict_multi(self):
        """Test invert_dict_multi."""
        result = invert_dict_multi({"a": 1, "b": 1, "c": 2})
        assert result == {1: ["a", "b"], 2: ["c"]}


class TestFlattenDict:
    """Tests for flatten/unflatten dict."""

    def test_flatten_dict_basic(self):
        """Test basic flatten_dict."""
        result = flatten_dict({"a": {"b": 1, "c": {"d": 2}}})
        assert result == {"a.b": 1, "a.c.d": 2}

    def test_flatten_dict_custom_separator(self):
        """Test flatten_dict with custom separator."""
        result = flatten_dict({"a": {"b": 1}}, separator="/")
        assert result == {"a/b": 1}

    def test_unflatten_dict_basic(self):
        """Test basic unflatten_dict."""
        result = unflatten_dict({"a.b": 1, "a.c.d": 2})
        assert result == {"a": {"b": 1, "c": {"d": 2}}}

    def test_flatten_unflatten_roundtrip(self):
        """Test flatten/unflatten roundtrip."""
        original = {"a": {"b": 1, "c": {"d": 2}}}
        flattened = flatten_dict(original)
        unflattened = unflatten_dict(flattened)
        assert unflattened == original


class TestPickOmit:
    """Tests for pick and omit functions."""

    def test_pick_basic(self):
        """Test basic pick."""
        result = pick({"a": 1, "b": 2, "c": 3}, "a", "c")
        assert result == {"a": 1, "c": 3}

    def test_pick_missing_keys(self):
        """Test pick with missing keys."""
        result = pick({"a": 1}, "a", "b")
        assert result == {"a": 1}

    def test_omit_basic(self):
        """Test basic omit."""
        result = omit({"a": 1, "b": 2, "c": 3}, "b")
        assert result == {"a": 1, "c": 3}

    def test_defaults_basic(self):
        """Test basic defaults."""
        result = defaults({"a": 1}, {"a": 0, "b": 2}, {"c": 3})
        assert result == {"a": 1, "b": 2, "c": 3}


class TestDictComparison:
    """Tests for dict comparison functions."""

    def test_diff_dicts_basic(self):
        """Test basic diff_dicts."""
        result = diff_dicts({"a": 1, "b": 2}, {"b": 3, "c": 4})
        assert result == {
            "added": {"c": 4},
            "removed": {"a": 1},
            "changed": {"b": {"old": 2, "new": 3}},
        }

    def test_diff_dicts_identical(self):
        """Test diff_dicts with identical dicts."""
        result = diff_dicts({"a": 1}, {"a": 1})
        assert result == {"added": {}, "removed": {}, "changed": {}}

    def test_intersection_dicts_basic(self):
        """Test basic intersection_dicts."""
        result = intersection_dicts({"a": 1, "b": 2}, {"a": 1, "c": 3})
        assert result == {"a": 1}

    def test_intersection_dicts_multiple(self):
        """Test intersection of multiple dicts."""
        result = intersection_dicts(
            {"a": 1, "b": 2},
            {"a": 1, "b": 2, "c": 3},
            {"a": 1},
        )
        assert result == {"a": 1}


class TestSafeAccess:
    """Tests for safe access functions."""

    def test_safe_get_valid(self):
        """Test safe_get with valid index."""
        assert safe_get([1, 2, 3], 1) == 2

    def test_safe_get_invalid(self):
        """Test safe_get with invalid index."""
        assert safe_get([1, 2, 3], 10) is None
        assert safe_get([1, 2, 3], 10, default=0) == 0

    def test_safe_get_negative(self):
        """Test safe_get with negative index."""
        assert safe_get([1, 2, 3], -1) == 3

    def test_pluck_basic(self):
        """Test basic pluck."""
        result = pluck([{"a": 1}, {"a": 2}, {"b": 3}], "a")
        assert result == [1, 2, None]

    def test_pluck_with_default(self):
        """Test pluck with default."""
        result = pluck([{"a": 1}, {"b": 2}], "a", default=0)
        assert result == [1, 0]

    def test_pluck_attr(self):
        """Test pluck_attr."""

        @dataclass
        class Item:
            value: int

        items = [Item(1), Item(2), Item(3)]
        result = pluck_attr(items, "value")
        assert result == [1, 2, 3]


class TestOrdering:
    """Tests for ordering functions."""

    def test_sort_by_single_key(self):
        """Test sort_by with single key."""
        data = [{"a": 2}, {"a": 1}, {"a": 3}]
        result = sort_by(data, lambda x: x["a"])
        assert result == [{"a": 1}, {"a": 2}, {"a": 3}]

    def test_sort_by_multiple_keys(self):
        """Test sort_by with multiple keys."""
        data = [
            {"a": 2, "b": 1},
            {"a": 1, "b": 2},
            {"a": 1, "b": 1},
        ]
        result = sort_by(data, lambda x: x["a"], lambda x: x["b"])
        assert result == [
            {"a": 1, "b": 1},
            {"a": 1, "b": 2},
            {"a": 2, "b": 1},
        ]

    def test_sort_by_reverse(self):
        """Test sort_by with reverse."""
        data = [{"a": 1}, {"a": 2}, {"a": 3}]
        result = sort_by(data, lambda x: x["a"], reverse=True)
        assert result == [{"a": 3}, {"a": 2}, {"a": 1}]

    def test_order_by_custom(self):
        """Test order_by with custom order."""
        result = order_by(["c", "a", "b"], ["a", "b", "c"])
        assert result == ["a", "b", "c"]

    def test_order_by_with_key(self):
        """Test order_by with key function."""
        data = [{"v": "c"}, {"v": "a"}, {"v": "b"}]
        result = order_by(data, ["a", "b", "c"], key=lambda x: x["v"])
        assert result == [{"v": "a"}, {"v": "b"}, {"v": "c"}]


class TestReduction:
    """Tests for reduction functions."""

    def test_sum_by_basic(self):
        """Test basic sum_by."""
        result = sum_by([{"a": 1}, {"a": 2}, {"a": 3}], lambda x: x["a"])
        assert result == 6

    def test_count_by_basic(self):
        """Test basic count_by."""
        result = count_by([1, 2, 3, 4, 5], lambda x: x % 2 == 0)
        assert result == 2

    def test_min_by_basic(self):
        """Test basic min_by."""
        data = [{"v": 3}, {"v": 1}, {"v": 2}]
        result = min_by(data, lambda x: x["v"])
        assert result == {"v": 1}

    def test_min_by_empty(self):
        """Test min_by on empty list."""
        result = min_by([], lambda x: x, default=None)
        assert result is None

    def test_max_by_basic(self):
        """Test basic max_by."""
        data = [{"v": 3}, {"v": 1}, {"v": 2}]
        result = max_by(data, lambda x: x["v"])
        assert result == {"v": 3}


class TestSetOperations:
    """Tests for set operations on lists."""

    def test_union_lists_basic(self):
        """Test basic union_lists."""
        result = union_lists([1, 2], [2, 3], [3, 4])
        assert result == [1, 2, 3, 4]

    def test_intersect_lists_basic(self):
        """Test basic intersect_lists."""
        result = intersect_lists([1, 2, 3], [2, 3, 4], [3, 4, 5])
        assert result == [3]

    def test_intersect_lists_preserves_order(self):
        """Test intersect_lists preserves order."""
        result = intersect_lists([3, 2, 1], [2, 3, 4])
        assert result == [3, 2]

    def test_difference_lists_basic(self):
        """Test basic difference_lists."""
        result = difference_lists([1, 2, 3, 4], [2, 4])
        assert result == [1, 3]

    def test_symmetric_difference_lists_basic(self):
        """Test basic symmetric_difference_lists."""
        result = symmetric_difference_lists([1, 2, 3], [2, 3, 4])
        assert sorted(result) == [1, 4]
