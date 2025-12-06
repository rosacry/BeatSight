"""
Collection utilities for working with lists, dicts, and iterables.

Provides utilities for:
- List operations (chunking, flattening, deduplication)
- Dict operations (deep merge, filtering, transformation)
- Grouping and partitioning
- Safe access and manipulation
"""

from collections import Counter, defaultdict
from itertools import chain, groupby, islice, zip_longest
from typing import (
    Any,
    Callable,
    Generator,
    Hashable,
    Iterable,
    Mapping,
    MutableMapping,
    Sequence,
    TypeVar,
)

import structlog

logger = structlog.get_logger(__name__)


# Type variables
T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")
R = TypeVar("R")


# =============================================================================
# List Operations
# =============================================================================


def chunk(items: Sequence[T], size: int) -> Generator[list[T], None, None]:
    """
    Split a sequence into chunks of specified size.

    Args:
        items: Sequence to chunk
        size: Maximum chunk size

    Yields:
        Lists of items with at most `size` elements

    Example:
        >>> list(chunk([1, 2, 3, 4, 5], 2))
        [[1, 2], [3, 4], [5]]
    """
    if size <= 0:
        raise ValueError("Chunk size must be positive")

    for i in range(0, len(items), size):
        yield list(items[i : i + size])


def chunk_iter(iterable: Iterable[T], size: int) -> Generator[list[T], None, None]:
    """
    Split an iterable into chunks (works with generators).

    Args:
        iterable: Iterable to chunk
        size: Maximum chunk size

    Yields:
        Lists of items with at most `size` elements
    """
    if size <= 0:
        raise ValueError("Chunk size must be positive")

    iterator = iter(iterable)
    while True:
        batch = list(islice(iterator, size))
        if not batch:
            break
        yield batch


def flatten(nested: Iterable[Iterable[T]]) -> list[T]:
    """
    Flatten one level of nesting.

    Args:
        nested: Nested iterables

    Returns:
        Flattened list

    Example:
        >>> flatten([[1, 2], [3, 4], [5]])
        [1, 2, 3, 4, 5]
    """
    return list(chain.from_iterable(nested))


def deep_flatten(nested: Any, max_depth: int | None = None) -> list[Any]:
    """
    Recursively flatten nested iterables.

    Args:
        nested: Nested structure
        max_depth: Maximum recursion depth (None for unlimited)

    Returns:
        Fully flattened list

    Example:
        >>> deep_flatten([[1, [2, 3]], [4, [5, [6]]]])
        [1, 2, 3, 4, 5, 6]
    """
    result: list[Any] = []

    def _flatten(item: Any, depth: int) -> None:
        if max_depth is not None and depth > max_depth:
            result.append(item)
            return

        if isinstance(item, (str, bytes)):
            result.append(item)
        elif isinstance(item, Iterable):
            for sub_item in item:
                _flatten(sub_item, depth + 1)
        else:
            result.append(item)

    _flatten(nested, 0)
    return result


def dedupe(items: Iterable[T], key: Callable[[T], Hashable] | None = None) -> list[T]:
    """
    Remove duplicates while preserving order.

    Args:
        items: Items to deduplicate
        key: Optional key function for comparison

    Returns:
        Deduplicated list

    Example:
        >>> dedupe([1, 2, 2, 3, 1, 4])
        [1, 2, 3, 4]
        >>> dedupe(["a", "A", "b"], key=str.lower)
        ['a', 'b']
    """
    seen: set[Hashable] = set()
    result: list[T] = []

    for item in items:
        k = key(item) if key else item
        if k not in seen:
            seen.add(k)
            result.append(item)

    return result


def compact(items: Iterable[T | None]) -> list[T]:
    """
    Remove None values from a sequence.

    Args:
        items: Items potentially containing None

    Returns:
        List without None values

    Example:
        >>> compact([1, None, 2, None, 3])
        [1, 2, 3]
    """
    return [item for item in items if item is not None]


def compact_falsy(items: Iterable[T]) -> list[T]:
    """
    Remove all falsy values from a sequence.

    Args:
        items: Items potentially containing falsy values

    Returns:
        List without falsy values

    Example:
        >>> compact_falsy([1, 0, 2, "", 3, None, [], False])
        [1, 2, 3]
    """
    return [item for item in items if item]


def take(items: Iterable[T], n: int) -> list[T]:
    """
    Take first n items from an iterable.

    Args:
        items: Source iterable
        n: Number of items to take

    Returns:
        List of first n items

    Example:
        >>> take([1, 2, 3, 4, 5], 3)
        [1, 2, 3]
    """
    return list(islice(items, n))


def drop(items: Sequence[T], n: int) -> list[T]:
    """
    Drop first n items from a sequence.

    Args:
        items: Source sequence
        n: Number of items to drop

    Returns:
        List without first n items

    Example:
        >>> drop([1, 2, 3, 4, 5], 2)
        [3, 4, 5]
    """
    return list(items[n:])


def take_while(
    items: Iterable[T],
    predicate: Callable[[T], bool],
) -> list[T]:
    """
    Take items while predicate is true.

    Args:
        items: Source iterable
        predicate: Function to test each item

    Returns:
        List of items until predicate fails

    Example:
        >>> take_while([1, 2, 3, 4, 1, 2], lambda x: x < 4)
        [1, 2, 3]
    """
    result: list[T] = []
    for item in items:
        if not predicate(item):
            break
        result.append(item)
    return result


def drop_while(
    items: Iterable[T],
    predicate: Callable[[T], bool],
) -> list[T]:
    """
    Drop items while predicate is true.

    Args:
        items: Source iterable
        predicate: Function to test each item

    Returns:
        List starting from first item where predicate fails

    Example:
        >>> drop_while([1, 2, 3, 4, 1, 2], lambda x: x < 3)
        [3, 4, 1, 2]
    """
    iterator = iter(items)
    for item in iterator:
        if not predicate(item):
            return [item] + list(iterator)
    return []


def first(
    items: Iterable[T],
    default: T | None = None,
    predicate: Callable[[T], bool] | None = None,
) -> T | None:
    """
    Get first item matching predicate, or default.

    Args:
        items: Source iterable
        default: Default value if not found
        predicate: Optional filter function

    Returns:
        First matching item or default

    Example:
        >>> first([1, 2, 3])
        1
        >>> first([1, 2, 3], predicate=lambda x: x > 1)
        2
        >>> first([], default=0)
        0
    """
    for item in items:
        if predicate is None or predicate(item):
            return item
    return default


def last(
    items: Sequence[T],
    default: T | None = None,
    predicate: Callable[[T], bool] | None = None,
) -> T | None:
    """
    Get last item matching predicate, or default.

    Args:
        items: Source sequence
        default: Default value if not found
        predicate: Optional filter function

    Returns:
        Last matching item or default

    Example:
        >>> last([1, 2, 3])
        3
        >>> last([1, 2, 3], predicate=lambda x: x < 3)
        2
    """
    if predicate is None:
        return items[-1] if items else default

    result = default
    for item in items:
        if predicate(item):
            result = item
    return result


def find_index(
    items: Sequence[T],
    predicate: Callable[[T], bool],
) -> int | None:
    """
    Find index of first item matching predicate.

    Args:
        items: Source sequence
        predicate: Function to test each item

    Returns:
        Index of first match, or None

    Example:
        >>> find_index([1, 2, 3, 4], lambda x: x > 2)
        2
    """
    for i, item in enumerate(items):
        if predicate(item):
            return i
    return None


def find_all_indices(
    items: Sequence[T],
    predicate: Callable[[T], bool],
) -> list[int]:
    """
    Find all indices matching predicate.

    Args:
        items: Source sequence
        predicate: Function to test each item

    Returns:
        List of matching indices

    Example:
        >>> find_all_indices([1, 2, 3, 2, 4], lambda x: x == 2)
        [1, 3]
    """
    return [i for i, item in enumerate(items) if predicate(item)]


def interleave(*iterables: Iterable[T]) -> list[T]:
    """
    Interleave items from multiple iterables.

    Args:
        *iterables: Iterables to interleave

    Returns:
        Interleaved list

    Example:
        >>> interleave([1, 2, 3], ['a', 'b', 'c'])
        [1, 'a', 2, 'b', 3, 'c']
    """
    result: list[T] = []
    sentinel = object()

    for items in zip_longest(*iterables, fillvalue=sentinel):
        for item in items:
            if item is not sentinel:
                result.append(item)  # type: ignore

    return result


def intersperse(items: Iterable[T], separator: T) -> list[T]:
    """
    Insert separator between items.

    Args:
        items: Source items
        separator: Value to insert between items

    Returns:
        List with separators

    Example:
        >>> intersperse([1, 2, 3], 0)
        [1, 0, 2, 0, 3]
    """
    result: list[T] = []
    for i, item in enumerate(items):
        if i > 0:
            result.append(separator)
        result.append(item)
    return result


def rotate(items: Sequence[T], n: int) -> list[T]:
    """
    Rotate items by n positions.

    Args:
        items: Source sequence
        n: Rotation amount (positive = right, negative = left)

    Returns:
        Rotated list

    Example:
        >>> rotate([1, 2, 3, 4, 5], 2)
        [4, 5, 1, 2, 3]
        >>> rotate([1, 2, 3, 4, 5], -2)
        [3, 4, 5, 1, 2]
    """
    if not items:
        return []

    n = n % len(items)
    return list(items[-n:]) + list(items[:-n])


def sliding_window(
    items: Sequence[T],
    size: int,
    step: int = 1,
) -> Generator[list[T], None, None]:
    """
    Generate sliding windows over a sequence.

    Args:
        items: Source sequence
        size: Window size
        step: Step between windows

    Yields:
        Lists representing each window

    Example:
        >>> list(sliding_window([1, 2, 3, 4, 5], 3))
        [[1, 2, 3], [2, 3, 4], [3, 4, 5]]
    """
    if size <= 0 or step <= 0:
        raise ValueError("Size and step must be positive")

    for i in range(0, len(items) - size + 1, step):
        yield list(items[i : i + size])


# =============================================================================
# Grouping and Partitioning
# =============================================================================


def group_by(
    items: Iterable[T],
    key: Callable[[T], K],
) -> dict[K, list[T]]:
    """
    Group items by a key function.

    Args:
        items: Items to group
        key: Function to extract grouping key

    Returns:
        Dict mapping keys to lists of items

    Example:
        >>> group_by([1, 2, 3, 4, 5], lambda x: x % 2)
        {1: [1, 3, 5], 0: [2, 4]}
    """
    result: dict[K, list[T]] = defaultdict(list)
    for item in items:
        result[key(item)].append(item)
    return dict(result)


def group_by_attr(
    items: Iterable[T],
    attr: str,
) -> dict[Any, list[T]]:
    """
    Group items by an attribute.

    Args:
        items: Items to group
        attr: Attribute name

    Returns:
        Dict mapping attribute values to lists of items

    Example:
        >>> from dataclasses import dataclass
        >>> @dataclass
        ... class User:
        ...     role: str
        ...     name: str
        >>> users = [User("admin", "Alice"), User("user", "Bob"), User("admin", "Charlie")]
        >>> result = group_by_attr(users, "role")
        >>> len(result["admin"])
        2
    """
    return group_by(items, lambda x: getattr(x, attr))


def partition(
    items: Iterable[T],
    predicate: Callable[[T], bool],
) -> tuple[list[T], list[T]]:
    """
    Split items into two groups based on predicate.

    Args:
        items: Items to partition
        predicate: Function to test each item

    Returns:
        Tuple of (matching, not_matching) lists

    Example:
        >>> partition([1, 2, 3, 4, 5], lambda x: x % 2 == 0)
        ([2, 4], [1, 3, 5])
    """
    matching: list[T] = []
    not_matching: list[T] = []

    for item in items:
        if predicate(item):
            matching.append(item)
        else:
            not_matching.append(item)

    return matching, not_matching


def partition_by(
    items: Iterable[T],
    key: Callable[[T], K],
) -> list[list[T]]:
    """
    Partition items when key changes.

    Args:
        items: Items to partition
        key: Function to extract partition key

    Returns:
        List of groups where adjacent items have same key

    Example:
        >>> partition_by([1, 1, 2, 2, 2, 1, 1], lambda x: x)
        [[1, 1], [2, 2, 2], [1, 1]]
    """
    return [list(group) for _, group in groupby(items, key)]


def frequencies(items: Iterable[T]) -> dict[T, int]:
    """
    Count occurrences of each item.

    Args:
        items: Items to count

    Returns:
        Dict mapping items to counts

    Example:
        >>> frequencies([1, 2, 2, 3, 3, 3])
        {1: 1, 2: 2, 3: 3}
    """
    return dict(Counter(items))


def top_n(items: Iterable[T], n: int, key: Callable[[T], Any] | None = None) -> list[T]:
    """
    Get top n items by key.

    Args:
        items: Items to rank
        n: Number of items to return
        key: Optional key function

    Returns:
        Top n items sorted descending

    Example:
        >>> top_n([1, 5, 2, 8, 3], 3)
        [8, 5, 3]
    """
    import heapq

    return heapq.nlargest(n, items, key=key)


def bottom_n(
    items: Iterable[T], n: int, key: Callable[[T], Any] | None = None
) -> list[T]:
    """
    Get bottom n items by key.

    Args:
        items: Items to rank
        n: Number of items to return
        key: Optional key function

    Returns:
        Bottom n items sorted ascending

    Example:
        >>> bottom_n([1, 5, 2, 8, 3], 3)
        [1, 2, 3]
    """
    import heapq

    return heapq.nsmallest(n, items, key=key)


# =============================================================================
# Dict Operations
# =============================================================================


def deep_get(
    data: Mapping[str, Any],
    path: str,
    default: Any = None,
    separator: str = ".",
) -> Any:
    """
    Get a nested value using dot notation.

    Args:
        data: Nested dictionary
        path: Dot-separated path
        default: Default value if not found
        separator: Path separator

    Returns:
        Value at path or default

    Example:
        >>> deep_get({"a": {"b": {"c": 1}}}, "a.b.c")
        1
        >>> deep_get({"a": {"b": 1}}, "a.c", default=0)
        0
    """
    keys = path.split(separator)
    result: Any = data

    for key in keys:
        if isinstance(result, Mapping):
            result = result.get(key)
        elif isinstance(result, Sequence) and not isinstance(result, str):
            try:
                result = result[int(key)]
            except (ValueError, IndexError):
                return default
        else:
            return default

        if result is None:
            return default

    return result


def deep_set(
    data: MutableMapping[str, Any],
    path: str,
    value: Any,
    separator: str = ".",
) -> None:
    """
    Set a nested value using dot notation.

    Args:
        data: Nested dictionary to modify
        path: Dot-separated path
        value: Value to set
        separator: Path separator

    Example:
        >>> d = {}
        >>> deep_set(d, "a.b.c", 1)
        >>> d
        {'a': {'b': {'c': 1}}}
    """
    keys = path.split(separator)
    current: MutableMapping[str, Any] = data

    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    current[keys[-1]] = value


def deep_delete(
    data: MutableMapping[str, Any],
    path: str,
    separator: str = ".",
) -> bool:
    """
    Delete a nested value using dot notation.

    Args:
        data: Nested dictionary to modify
        path: Dot-separated path
        separator: Path separator

    Returns:
        True if value was deleted, False if not found

    Example:
        >>> d = {"a": {"b": {"c": 1}}}
        >>> deep_delete(d, "a.b.c")
        True
        >>> d
        {'a': {'b': {}}}
    """
    keys = path.split(separator)
    current: MutableMapping[str, Any] = data

    for key in keys[:-1]:
        if key not in current:
            return False
        current = current[key]
        if not isinstance(current, MutableMapping):
            return False

    if keys[-1] in current:
        del current[keys[-1]]
        return True
    return False


def deep_merge(
    base: dict[str, Any],
    override: dict[str, Any],
    *,
    deep_copy: bool = True,
) -> dict[str, Any]:
    """
    Deep merge two dictionaries.

    Args:
        base: Base dictionary
        override: Dictionary with override values
        deep_copy: Whether to deep copy values

    Returns:
        Merged dictionary

    Example:
        >>> base = {"a": 1, "b": {"c": 2}}
        >>> override = {"b": {"d": 3}, "e": 4}
        >>> deep_merge(base, override)
        {'a': 1, 'b': {'c': 2, 'd': 3}, 'e': 4}
    """
    import copy

    if deep_copy:
        result = copy.deepcopy(base)
    else:
        result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value, deep_copy=deep_copy)
        elif deep_copy:
            result[key] = copy.deepcopy(value)
        else:
            result[key] = value

    return result


def filter_dict(
    data: dict[K, V],
    predicate: Callable[[K, V], bool],
) -> dict[K, V]:
    """
    Filter dictionary by predicate.

    Args:
        data: Dictionary to filter
        predicate: Function taking (key, value) returning bool

    Returns:
        Filtered dictionary

    Example:
        >>> filter_dict({"a": 1, "b": 2, "c": 3}, lambda k, v: v > 1)
        {'b': 2, 'c': 3}
    """
    return {k: v for k, v in data.items() if predicate(k, v)}


def filter_dict_keys(
    data: dict[K, V],
    keys: set[K] | list[K],
) -> dict[K, V]:
    """
    Filter dictionary to only specified keys.

    Args:
        data: Dictionary to filter
        keys: Keys to keep

    Returns:
        Filtered dictionary

    Example:
        >>> filter_dict_keys({"a": 1, "b": 2, "c": 3}, {"a", "c"})
        {'a': 1, 'c': 3}
    """
    key_set = set(keys)
    return {k: v for k, v in data.items() if k in key_set}


def exclude_dict_keys(
    data: dict[K, V],
    keys: set[K] | list[K],
) -> dict[K, V]:
    """
    Filter dictionary excluding specified keys.

    Args:
        data: Dictionary to filter
        keys: Keys to exclude

    Returns:
        Filtered dictionary

    Example:
        >>> exclude_dict_keys({"a": 1, "b": 2, "c": 3}, {"b"})
        {'a': 1, 'c': 3}
    """
    key_set = set(keys)
    return {k: v for k, v in data.items() if k not in key_set}


def map_dict_keys(
    data: dict[K, V],
    func: Callable[[K], R],
) -> dict[R, V]:
    """
    Transform dictionary keys.

    Args:
        data: Dictionary to transform
        func: Function to apply to keys

    Returns:
        Dictionary with transformed keys

    Example:
        >>> map_dict_keys({"a": 1, "b": 2}, str.upper)
        {'A': 1, 'B': 2}
    """
    return {func(k): v for k, v in data.items()}


def map_dict_values(
    data: dict[K, V],
    func: Callable[[V], R],
) -> dict[K, R]:
    """
    Transform dictionary values.

    Args:
        data: Dictionary to transform
        func: Function to apply to values

    Returns:
        Dictionary with transformed values

    Example:
        >>> map_dict_values({"a": 1, "b": 2}, lambda x: x * 2)
        {'a': 2, 'b': 4}
    """
    return {k: func(v) for k, v in data.items()}


def invert_dict(data: dict[K, V]) -> dict[V, K]:
    """
    Swap keys and values.

    Args:
        data: Dictionary to invert

    Returns:
        Inverted dictionary

    Example:
        >>> invert_dict({"a": 1, "b": 2})
        {1: 'a', 2: 'b'}
    """
    return {v: k for k, v in data.items()}


def invert_dict_multi(data: dict[K, V]) -> dict[V, list[K]]:
    """
    Swap keys and values, handling duplicate values.

    Args:
        data: Dictionary to invert

    Returns:
        Inverted dictionary with lists of keys

    Example:
        >>> invert_dict_multi({"a": 1, "b": 1, "c": 2})
        {1: ['a', 'b'], 2: ['c']}
    """
    result: dict[V, list[K]] = defaultdict(list)
    for k, v in data.items():
        result[v].append(k)
    return dict(result)


def flatten_dict(
    data: dict[str, Any],
    separator: str = ".",
    prefix: str = "",
) -> dict[str, Any]:
    """
    Flatten nested dictionary.

    Args:
        data: Nested dictionary
        separator: Key separator
        prefix: Prefix for keys

    Returns:
        Flattened dictionary

    Example:
        >>> flatten_dict({"a": {"b": 1, "c": {"d": 2}}})
        {'a.b': 1, 'a.c.d': 2}
    """
    result: dict[str, Any] = {}

    for key, value in data.items():
        new_key = f"{prefix}{separator}{key}" if prefix else key

        if isinstance(value, dict):
            result.update(flatten_dict(value, separator, new_key))
        else:
            result[new_key] = value

    return result


def unflatten_dict(
    data: dict[str, Any],
    separator: str = ".",
) -> dict[str, Any]:
    """
    Unflatten dictionary from dot notation.

    Args:
        data: Flattened dictionary
        separator: Key separator

    Returns:
        Nested dictionary

    Example:
        >>> unflatten_dict({"a.b": 1, "a.c.d": 2})
        {'a': {'b': 1, 'c': {'d': 2}}}
    """
    result: dict[str, Any] = {}

    for key, value in data.items():
        deep_set(result, key, value, separator)

    return result


def pick(data: dict[K, V], *keys: K) -> dict[K, V]:
    """
    Pick specific keys from dictionary.

    Args:
        data: Source dictionary
        *keys: Keys to pick

    Returns:
        Dictionary with only specified keys

    Example:
        >>> pick({"a": 1, "b": 2, "c": 3}, "a", "c")
        {'a': 1, 'c': 3}
    """
    return {k: data[k] for k in keys if k in data}


def omit(data: dict[K, V], *keys: K) -> dict[K, V]:
    """
    Omit specific keys from dictionary.

    Args:
        data: Source dictionary
        *keys: Keys to omit

    Returns:
        Dictionary without specified keys

    Example:
        >>> omit({"a": 1, "b": 2, "c": 3}, "b")
        {'a': 1, 'c': 3}
    """
    excluded = set(keys)
    return {k: v for k, v in data.items() if k not in excluded}


def defaults(data: dict[K, V], *defaults_dicts: dict[K, V]) -> dict[K, V]:
    """
    Fill in missing keys from defaults.

    Args:
        data: Primary dictionary
        *defaults_dicts: Default dictionaries

    Returns:
        Dictionary with defaults applied

    Example:
        >>> defaults({"a": 1}, {"a": 0, "b": 2}, {"c": 3})
        {'a': 1, 'b': 2, 'c': 3}
    """
    result = {}
    for d in reversed(defaults_dicts):
        result.update(d)
    result.update(data)
    return result


# =============================================================================
# Comparison and Diff
# =============================================================================


def diff_dicts(
    dict1: dict[K, V],
    dict2: dict[K, V],
) -> dict[str, Any]:
    """
    Find differences between two dictionaries.

    Args:
        dict1: First dictionary
        dict2: Second dictionary

    Returns:
        Dictionary with keys: added, removed, changed

    Example:
        >>> diff_dicts({"a": 1, "b": 2}, {"b": 3, "c": 4})
        {'added': {'c': 4}, 'removed': {'a': 1}, 'changed': {'b': {'old': 2, 'new': 3}}}
    """
    keys1 = set(dict1.keys())
    keys2 = set(dict2.keys())

    added = {k: dict2[k] for k in keys2 - keys1}
    removed = {k: dict1[k] for k in keys1 - keys2}
    changed = {
        k: {"old": dict1[k], "new": dict2[k]}
        for k in keys1 & keys2
        if dict1[k] != dict2[k]
    }

    return {"added": added, "removed": removed, "changed": changed}


def intersection_dicts(*dicts: dict[K, V]) -> dict[K, V]:
    """
    Find common key-value pairs across dictionaries.

    Args:
        *dicts: Dictionaries to intersect

    Returns:
        Dictionary with common key-value pairs

    Example:
        >>> intersection_dicts({"a": 1, "b": 2}, {"a": 1, "c": 3})
        {'a': 1}
    """
    if not dicts:
        return {}

    result = dict(dicts[0])
    for d in dicts[1:]:
        result = {k: v for k, v in result.items() if k in d and d[k] == v}

    return result


# =============================================================================
# Safe Access
# =============================================================================


def safe_get(
    items: Sequence[T],
    index: int,
    default: T | None = None,
) -> T | None:
    """
    Safely get item by index.

    Args:
        items: Source sequence
        index: Index to get
        default: Default if index out of range

    Returns:
        Item at index or default

    Example:
        >>> safe_get([1, 2, 3], 1)
        2
        >>> safe_get([1, 2, 3], 10, default=0)
        0
    """
    try:
        return items[index]
    except IndexError:
        return default


def pluck(
    items: Iterable[Mapping[K, V]],
    key: K,
    default: V | None = None,
) -> list[V | None]:
    """
    Extract a key from each item.

    Args:
        items: Iterable of mappings
        key: Key to extract
        default: Default if key not found

    Returns:
        List of extracted values

    Example:
        >>> pluck([{"a": 1}, {"a": 2}, {"b": 3}], "a")
        [1, 2, None]
    """
    return [item.get(key, default) for item in items]


def pluck_attr(
    items: Iterable[Any],
    attr: str,
    default: Any = None,
) -> list[Any]:
    """
    Extract an attribute from each item.

    Args:
        items: Iterable of objects
        attr: Attribute to extract
        default: Default if attribute not found

    Returns:
        List of extracted values
    """
    return [getattr(item, attr, default) for item in items]


# =============================================================================
# Ordering
# =============================================================================


def sort_by(
    items: Iterable[T],
    *keys: Callable[[T], Any],
    reverse: bool = False,
) -> list[T]:
    """
    Sort by multiple keys.

    Args:
        items: Items to sort
        *keys: Key functions in order of priority
        reverse: Sort descending

    Returns:
        Sorted list

    Example:
        >>> data = [{"a": 2, "b": 1}, {"a": 1, "b": 2}, {"a": 1, "b": 1}]
        >>> sort_by(data, lambda x: x["a"], lambda x: x["b"])
        [{'a': 1, 'b': 1}, {'a': 1, 'b': 2}, {'a': 2, 'b': 1}]
    """
    return sorted(items, key=lambda x: tuple(k(x) for k in keys), reverse=reverse)


def order_by(
    items: Iterable[T],
    order: Sequence[Any],
    key: Callable[[T], Any] | None = None,
) -> list[T]:
    """
    Sort items by a custom order.

    Args:
        items: Items to sort
        order: Desired order of values
        key: Optional key function

    Returns:
        Sorted list

    Example:
        >>> order_by(["c", "a", "b"], ["a", "b", "c"])
        ['a', 'b', 'c']
    """
    order_map = {v: i for i, v in enumerate(order)}
    return sorted(
        items,
        key=lambda x: order_map.get(key(x) if key else x, len(order)),
    )


# =============================================================================
# Reduction
# =============================================================================


def sum_by(items: Iterable[T], key: Callable[[T], int | float]) -> int | float:
    """
    Sum values extracted by key function.

    Args:
        items: Items to sum
        key: Function to extract numeric value

    Returns:
        Sum of extracted values

    Example:
        >>> sum_by([{"a": 1}, {"a": 2}, {"a": 3}], lambda x: x["a"])
        6
    """
    return sum(key(item) for item in items)


def count_by(
    items: Iterable[T],
    predicate: Callable[[T], bool],
) -> int:
    """
    Count items matching predicate.

    Args:
        items: Items to count
        predicate: Function to test each item

    Returns:
        Number of matching items

    Example:
        >>> count_by([1, 2, 3, 4, 5], lambda x: x % 2 == 0)
        2
    """
    return sum(1 for item in items if predicate(item))


def min_by(
    items: Iterable[T],
    key: Callable[[T], Any],
    default: T | None = None,
) -> T | None:
    """
    Find minimum by key function.

    Args:
        items: Items to search
        key: Function to extract comparison value
        default: Default if empty

    Returns:
        Item with minimum key value
    """
    try:
        return min(items, key=key)
    except ValueError:
        return default


def max_by(
    items: Iterable[T],
    key: Callable[[T], Any],
    default: T | None = None,
) -> T | None:
    """
    Find maximum by key function.

    Args:
        items: Items to search
        key: Function to extract comparison value
        default: Default if empty

    Returns:
        Item with maximum key value
    """
    try:
        return max(items, key=key)
    except ValueError:
        return default


# =============================================================================
# Set Operations
# =============================================================================


def union_lists(*lists: list[T]) -> list[T]:
    """
    Union of multiple lists (preserving order).

    Args:
        *lists: Lists to union

    Returns:
        List with all unique items

    Example:
        >>> union_lists([1, 2], [2, 3], [3, 4])
        [1, 2, 3, 4]
    """
    return dedupe(chain.from_iterable(lists))


def intersect_lists(*lists: list[T]) -> list[T]:
    """
    Intersection of multiple lists.

    Args:
        *lists: Lists to intersect

    Returns:
        List with common items

    Example:
        >>> intersect_lists([1, 2, 3], [2, 3, 4], [3, 4, 5])
        [3]
    """
    if not lists:
        return []

    result_set = set(lists[0])
    for lst in lists[1:]:
        result_set &= set(lst)

    # Preserve order from first list
    return [item for item in lists[0] if item in result_set]


def difference_lists(list1: list[T], list2: list[T]) -> list[T]:
    """
    Items in list1 not in list2.

    Args:
        list1: First list
        list2: Second list

    Returns:
        List of items in list1 but not list2

    Example:
        >>> difference_lists([1, 2, 3, 4], [2, 4])
        [1, 3]
    """
    set2 = set(list2)
    return [item for item in list1 if item not in set2]


def symmetric_difference_lists(list1: list[T], list2: list[T]) -> list[T]:
    """
    Items in either list but not both.

    Args:
        list1: First list
        list2: Second list

    Returns:
        List of items exclusive to each list

    Example:
        >>> sorted(symmetric_difference_lists([1, 2, 3], [2, 3, 4]))
        [1, 4]
    """
    set1 = set(list1)
    set2 = set(list2)
    symmetric = set1 ^ set2
    return [item for item in chain(list1, list2) if item in symmetric]
