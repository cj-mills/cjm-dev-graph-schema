"""Deterministic node-id helpers for the dev/decision-provenance domain.

Thin domain-specific wrappers over the layer's `derive_node_id` (UUIDv5 over a
kind + identity tuple). A node's id derives from what makes it THE same node
across re-derivation (its stable slug/key), never from its correctable content —
so re-decomposing the same corpus reproduces ids and `extend_graph` collides
re-emissions into verified no-ops instead of duplicating.

The coarse-tier `note_node_id` lands first. Fine-tier id helpers (decisions,
fact-slots keyed on (subject, predicate), sessions, …) are added as those kinds
are implemented.
"""

from cjm_context_graph_layer.identity import derive_node_id


def note_node_id(
    slug: str,  # Stable note slug (memory frontmatter `name`, else the corpus-relative path)
) -> str:  # Deterministic Note node id
    """Note identity = its stable slug.

    For memory files the slug is the frontmatter `name` (already kebab-case and
    stable across edits); for general markdown without a `name` it is the
    corpus-relative path. Either way the slug is what `[[wiki-links]]` resolve
    against, so a `REFERENCES` edge can target a note's id without first reading
    the target file."""
    return derive_node_id("note", slug)


def entity_node_id(
    kind: str,  # Entity sub-kind discriminator (e.g. "repo", "stage", "capability", "term")
    key: str,   # Stable key within that sub-kind (e.g. the repo name, the stage number)
) -> str:  # Deterministic Entity node id
    """Entity identity = (sub-kind, stable key).

    Subject identity is mechanical — deterministic ids on entities/stages/etc.
    are the half of the slot-identity unlock that needs no resolution (the other
    half, the predicate vocabulary, is curated). Reserved here; used as the fine
    tier introduces Fact-slots whose subject is an Entity."""
    return derive_node_id("entity", kind, key)


def factslot_node_id(
    subject_id: str,       # The subject node's id (an Entity, usually)
    predicate_slug: str,   # The curated predicate slug
) -> str:  # Deterministic Fact-slot node id
    """Fact-slot identity = (subject, predicate).

    THE slot-identity unlock made mechanical: the same subject + predicate always
    derives the same slot id, so independent assertions about one fact converge on
    one slot (rather than splintering into parallel free-floating questions)."""
    return derive_node_id("factslot", subject_id, predicate_slug)


def assertion_node_id(
    slot_id: str,          # The Fact-slot this value is claimed for
    canonical_value: str,  # The value's canonical form (see `predicates.canonical_value`)
    actor: str,            # Who claimed it (the assertion is identified by WHAT is claimed, by whom)
) -> str:  # Deterministic Assertion node id
    """Assertion identity = (slot, canonical value, actor).

    An assertion is identified by WHAT is claimed, NOT by its why/when/evidence —
    so re-asserting the same value (same actor) is an idempotent no-op, while a
    DIFFERENT value mints a new node (the potential conflict). The when
    (`asserted_at`) and evidence (edges) are content, never identity."""
    return derive_node_id("assertion", slot_id, canonical_value, actor)


def decision_node_id(
    statement_key: str,  # The decision's canonical statement (its stable key)
) -> str:  # Deterministic Decision node id
    """Decision identity = its canonical statement (idempotent re-records)."""
    return derive_node_id("decision", statement_key)


def session_node_id(
    key: str,  # Stable session key (e.g. the session timestamp/id)
) -> str:  # Deterministic Session node id
    """Session identity = its stable key (so DECIDED_IN/PRODUCED_IN converge)."""
    return derive_node_id("session", key)
