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
