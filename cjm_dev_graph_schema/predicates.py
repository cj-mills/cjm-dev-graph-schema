"""Typed predicates + their value-space metadata (the dedup decidability layer).

A Fact-slot is `(subject, predicate)`. Most predicates stay freetext on coarse
notes; only DEMONSTRABLY-high-value predicates are typed (type only what real
contradictions pull into typing). The cut types exactly two, chosen to exercise
BOTH contradiction modes:

- `rename-disposition` — unordered enum (`keep` | `rename:<target>`). A decision,
  so it should be STABLE; two non-superseded incompatible values = a genuine
  CONTRADICTION (no "newer silently wins"). This is what makes the torch/hf-utils
  "keep vs rename" case detectable.
- `version` — semver, legitimately CHANGES, ORDERED. "Newer supersedes older" is
  automatic, so a version bump is healthy evolution, never a contradiction.
  Oracle-backed (a Procedure refreshes it).

Value-space metadata (type/volatility/ordering) is what lets healthy evolution
NOT read as contradiction. Everything here is PURE — no graph, no queue: the
canonical-value function feeds Assertion identity, and the conflict predicates
feed the write-time check + the `contradictions` query.
"""

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

# Value types.
ENUM = "enum"          # A small closed-ish value space (e.g. keep | rename:<target>)
SEMVER = "semver"      # A dotted numeric version
SLUG = "slug"          # A normalized identifier slug (lowercased; e.g. a note name)
FREETEXT = "freetext"  # Unconstrained text (the untyped default)

# Volatility: does the slot's value legitimately change over time?
STABLE = "stable"      # A decision/attribute that should not flip (a flip is suspicious)
CHANGES = "changes"    # Legitimately evolves (version, status, …)

# Ordering: is there a known "later supersedes earlier" relation on values?
ORDER_NONE = "none"      # No ordering — two distinct values genuinely conflict
ORDER_SEMVER = "semver"  # Semver ordering — the greater value supersedes the lesser
ORDER_ENUM = "enum"      # A fixed lifecycle sequence — a later stage supersedes an earlier (see `order_values`)

# Work-item lifecycle (the readiness spine's authored ground truth): a work-item's
# completion state. `done` supersedes `open` — the healthy forward transition, so
# re-asserting `done` auto-supersedes the prior `open` exactly as a version bump
# does (never a contradiction). `ready`/`blocked` are NEVER asserted here — they
# are DERIVED on read by the readiness projector (the never-hand-maintain-a-derived
# -field rule: there is no write path for them).
TASK_STATE = "task_state"  # The work-item completion predicate
TASK_OPEN = "open"         # Not yet finished
TASK_DONE = "done"         # Finished (human-judged now; oracle-derived later)


@dataclass(frozen=True)
class Predicate:
    """A typed predicate's value-space (the contradiction decidability metadata)."""
    slug: str          # Predicate slug (the controlled vocabulary key)
    value_type: str    # ENUM | SEMVER | SLUG | FREETEXT
    volatility: str    # STABLE | CHANGES
    ordering: str      # ORDER_NONE | ORDER_SEMVER | ORDER_ENUM
    multivalued: bool = False  # A SET slot: many distinct values coexist, never conflict (e.g. aliases)
    order_values: Optional[Tuple[str, ...]] = None  # For ORDER_ENUM: the lifecycle sequence (earliest -> latest)


# The typed-predicate registry (controlled-with-free-reuse: novel predicates stay
# untyped freetext until a real contradiction pulls them in here).
PREDICATES = {
    "rename-disposition": Predicate("rename-disposition", ENUM, STABLE, ORDER_NONE),
    "version": Predicate("version", SEMVER, CHANGES, ORDER_SEMVER),
    # A note's confirmed equivalent slugs (drifted `[[wiki-links]]`). Multivalued:
    # one note legitimately carries many aliases, so distinct values NEVER conflict
    # and never supersede — each `aka` is just another accepted name. Born on-graph
    # by the propose/confirm worklist (never auto-guessed); ingest resolves drifted
    # references through them so the dangling edge heals without editing the file.
    "aka": Predicate("aka", SLUG, STABLE, ORDER_NONE, multivalued=True),
    # The work-item lifecycle: an ordered enum (`done` supersedes `open`), so a task
    # marked done auto-supersedes its prior open state (healthy evolution, never a
    # contradiction) — the version-bump pattern for a closed value-space.
    TASK_STATE: Predicate(TASK_STATE, ENUM, CHANGES, ORDER_ENUM,
                          order_values=(TASK_OPEN, TASK_DONE)),
}


def get_predicate(
    slug: str,  # Predicate slug
) -> Optional[Predicate]:  # The typed predicate, or None when untyped
    """Look up a predicate's value-space; None = an untyped freetext predicate."""
    return PREDICATES.get(slug)


def is_typed(
    slug: str,  # Predicate slug
) -> bool:  # True when the predicate carries a value-space
    """Whether the predicate is in the typed registry."""
    return slug in PREDICATES


def is_ordered(
    slug: str,  # Predicate slug
) -> bool:  # True when the predicate has a known value ordering
    """Whether the predicate's values have a "later supersedes earlier" ordering."""
    p = get_predicate(slug)
    return bool(p) and p.ordering != ORDER_NONE


def is_multivalued(
    slug: str,  # Predicate slug
) -> bool:  # True when the slot legitimately carries many coexisting values
    """Whether the predicate is a SET slot (distinct values coexist, never conflict)."""
    p = get_predicate(slug)
    return bool(p) and p.multivalued


def _parse_semver(
    value: str,  # A version string (optionally "v"-prefixed)
) -> Optional[Tuple[int, ...]]:  # Numeric release tuple, or None when unparseable
    """Parse the numeric release of a semver string; None when not comparable.

    Only the dotted numeric core is used for ordering (a pre-release/build suffix
    makes the tuple unparseable -> incomparable -> handled as no-supersede)."""
    s = value.strip().lstrip("vV").strip()
    if not s:
        return None
    core = s.split("-")[0].split("+")[0]
    parts = core.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def canonical_value(
    slug: str,  # Predicate slug
    value: str,  # Raw asserted value
) -> str:  # Canonical form used in Assertion identity + conflict comparison
    """Canonicalize a value so equal claims collapse to one Assertion.

    Semver: strip a leading "v" + whitespace (so "v0.0.51" == "0.0.51"). Enum:
    lowercased + stripped (repo names are lowercase; "rename:X" normalizes). Other
    (freetext/untyped): whitespace-stripped only, case preserved."""
    p = get_predicate(slug)
    v = str(value).strip()
    if p is None:
        return v
    if p.value_type == SEMVER:
        return v.lstrip("vV").strip()
    if p.value_type in (ENUM, SLUG):
        return v.lower()
    return v


def ordering_supersedes(
    slug: str,   # Predicate slug
    new_value: str,  # The newly asserted value
    old_value: str,  # An existing value
) -> Optional[bool]:
    """For an ordered predicate, does `new_value` supersede `old_value`?

    Returns True (new is later), False (old is later, new is born superseded),
    or None (unordered predicate, equal values, or incomparable -> no auto
    supersession; an unordered conflict is decided by `values_conflict`)."""
    p = get_predicate(slug)
    if p is None or p.ordering == ORDER_NONE:
        return None
    if p.ordering == ORDER_SEMVER:
        a, b = _parse_semver(new_value), _parse_semver(old_value)
        if a is None or b is None or a == b:
            return None
        return a > b
    if p.ordering == ORDER_ENUM:
        seq = p.order_values or ()
        a, b = canonical_value(slug, new_value), canonical_value(slug, old_value)
        if a not in seq or b not in seq or a == b:
            return None  # off-sequence or equal value -> no auto supersession
        return seq.index(a) > seq.index(b)
    return None


def values_conflict(
    slug: str,   # Predicate slug
    value_a: str,  # One value
    value_b: str,  # Another value
) -> bool:  # True only for a HARD (typed, unordered, incompatible) conflict
    """Whether two values are a HARD contradiction under the value-space.

    Only typed UNORDERED predicates produce hard conflicts: distinct canonical
    values disagree (the rename-disposition case). Ordered predicates never
    conflict (newer supersedes); multivalued set predicates never conflict
    (values coexist); untyped predicates are SOFT (worklist, not a hard
    contradiction) so this returns False for them."""
    p = get_predicate(slug)
    if p is None or p.ordering != ORDER_NONE or p.multivalued:
        return False
    return canonical_value(slug, value_a) != canonical_value(slug, value_b)


def active_contradiction(
    slug: str,                  # Predicate slug
    active_values: Iterable[str],  # Canonical-or-raw values of the slot's active assertions
) -> bool:  # True when the active set is a hard contradiction
    """Whether a slot's ACTIVE (non-superseded) values form a hard contradiction.

    Hard = a typed unordered predicate carrying >=2 distinct canonical values."""
    p = get_predicate(slug)
    if p is None or p.ordering != ORDER_NONE or p.multivalued:
        return False
    canon = {canonical_value(slug, v) for v in active_values}
    return len(canon) >= 2


def soft_conflict(
    slug: str,                  # Predicate slug
    active_values: Iterable[str],  # Values of the slot's active assertions
) -> bool:  # True when an UNtyped slot carries >=2 distinct values
    """Whether an UNTYPED slot's active values disagree (a worklist candidate).

    Untyped predicates can't be adjudicated mechanically, so a disagreement is a
    SOFT propose-to-the-worklist signal, never a hard contradiction."""
    if is_typed(slug):
        return False
    canon = {str(v).strip() for v in active_values}
    return len(canon) >= 2
