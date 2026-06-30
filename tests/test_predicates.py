"""Predicate value-space: canonicalization, ordering, and conflict decisions."""

from cjm_dev_graph_schema import predicates as P


def test_typed_predicate_registry():
    assert set(P.PREDICATES) == {"rename-disposition", "version", "aka", "task_state"}
    assert P.is_typed("rename-disposition") and P.is_typed("version") and P.is_typed("aka")
    assert P.is_typed("task_state") and P.is_ordered("task_state")  # ordered enum lifecycle
    assert not P.is_typed("status")  # untyped freetext until a real contradiction types it


def test_aka_is_multivalued_slug_set():
    p = P.get_predicate("aka")
    assert p.value_type == P.SLUG and p.ordering == P.ORDER_NONE and p.multivalued
    assert P.is_multivalued("aka")
    assert not P.is_multivalued("rename-disposition") and not P.is_multivalued("version")
    assert not P.is_ordered("aka")  # multivalued, not ordered
    # SLUG canonicalizes case-insensitively, like enum.
    assert P.canonical_value("aka", "Where-Graph-Begins") == "where-graph-begins"


def test_aka_distinct_values_never_conflict():
    # A note legitimately accrues MANY aliases -> distinct values coexist.
    assert not P.values_conflict("aka", "slug-a", "slug-b")
    assert not P.active_contradiction("aka", ["slug-a", "slug-b", "slug-c"])
    assert not P.soft_conflict("aka", ["slug-a", "slug-b"])  # typed -> never a soft signal either


def test_rename_disposition_is_unordered_enum():
    p = P.get_predicate("rename-disposition")
    assert p.value_type == P.ENUM and p.ordering == P.ORDER_NONE and p.volatility == P.STABLE
    assert not P.is_ordered("rename-disposition")


def test_version_is_ordered_semver():
    p = P.get_predicate("version")
    assert p.value_type == P.SEMVER and p.ordering == P.ORDER_SEMVER and p.volatility == P.CHANGES
    assert P.is_ordered("version")


def test_canonical_value_semver_strips_v_prefix():
    assert P.canonical_value("version", "v0.0.51") == P.canonical_value("version", "0.0.51")
    assert P.canonical_value("version", " 0.0.51 ") == "0.0.51"


def test_canonical_value_enum_lowercases():
    assert P.canonical_value("rename-disposition", "Keep") == "keep"
    assert (P.canonical_value("rename-disposition", "rename:Cjm-X")
            == "rename:cjm-x")


def test_canonical_value_untyped_preserves_case():
    assert P.canonical_value("definition", "A Thing") == "A Thing"


def test_ordering_supersedes_semver():
    assert P.ordering_supersedes("version", "0.0.51", "0.0.50") is True   # newer wins
    assert P.ordering_supersedes("version", "0.0.50", "0.0.51") is False  # born superseded
    assert P.ordering_supersedes("version", "0.0.51", "0.0.51") is None   # same -> no supersede
    assert P.ordering_supersedes("version", "weird", "0.0.1") is None     # incomparable
    assert P.ordering_supersedes("rename-disposition", "keep", "rename:x") is None  # unordered


def test_ordering_supersedes_task_state_enum():
    # The work-item lifecycle is an ordered enum: `done` supersedes `open` (a task
    # marked done auto-supersedes its prior open state, the version-bump pattern).
    assert P.ordering_supersedes("task_state", "done", "open") is True   # closing wins
    assert P.ordering_supersedes("task_state", "open", "done") is False  # reopen is born superseded
    assert P.ordering_supersedes("task_state", "done", "done") is None   # same -> no supersede
    assert P.ordering_supersedes("task_state", "DONE", "open") is True    # canonicalized (lowercased)
    assert P.ordering_supersedes("task_state", "wip", "open") is None     # off-sequence -> no supersede
    # task_state is ordered, so distinct values never read as a HARD contradiction.
    assert not P.values_conflict("task_state", "open", "done")
    assert not P.active_contradiction("task_state", ["open", "done"])


def test_values_conflict_only_typed_unordered():
    # rename-disposition: distinct canonical values are a HARD conflict.
    assert P.values_conflict("rename-disposition", "keep", "rename:cjm-substrate-torch-utils")
    assert not P.values_conflict("rename-disposition", "keep", "Keep")
    # version: ordered -> never a hard conflict (newer just supersedes).
    assert not P.values_conflict("version", "0.0.50", "0.0.51")
    # untyped -> soft, not hard.
    assert not P.values_conflict("status", "draft", "final")


def test_active_contradiction_and_soft_conflict():
    assert P.active_contradiction("rename-disposition", ["keep", "rename:x"])
    assert not P.active_contradiction("rename-disposition", ["keep", "Keep"])
    assert not P.active_contradiction("version", ["0.0.50", "0.0.51"])
    # untyped disagreement is SOFT, not a contradiction.
    assert not P.active_contradiction("status", ["draft", "final"])
    assert P.soft_conflict("status", ["draft", "final"])
    assert not P.soft_conflict("rename-disposition", ["keep", "rename:x"])  # typed -> hard, not soft
