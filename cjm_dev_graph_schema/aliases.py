"""Rename-stable subject resolution (the A+aliases identity machinery).

An Entity's identity `key` is a durable, name-INDEPENDENT conceptual slug (e.g.
`torch-utils`); the current repo name is a `name` property; prior names + variant
link-slugs are `aliases`. So a fact ABOUT an entity that itself got renamed keeps
one stable subject — the historical "keep cjm-torch-plugin-utils" claim and the
current "cjm-substrate-torch-utils" both resolve to the SAME entity.

This is the CONFIRMED-equivalence resolution structure. A CANDIDATE equivalence
(fuzzy slug-drift) becomes an alias via the propose/confirm worklist, never auto-
guessed here. Pure: builds an index from entity node forms and looks subjects up.
"""

from typing import Any, Dict, Iterable, List, Optional


def _props(node: Any) -> Dict[str, Any]:
    """Properties dict from an entity wire dict / GraphNode (tolerant access)."""
    p = getattr(node, "properties", None)
    if p is None and isinstance(node, dict):
        p = node.get("properties")
    return p or {}


def _node_id(node: Any) -> Optional[str]:
    """A node's id (typed GraphNode or wire dict)."""
    if isinstance(node, dict):
        return node.get("id")
    return getattr(node, "id", None)


def _canon(name: str) -> str:
    """Canonical lookup key for a subject name (case/space-insensitive)."""
    return str(name).strip().lower()


def build_alias_index(
    entities: Iterable[Any],  # Entity node wire dicts / GraphNodes
) -> Dict[str, str]:  # canon(key|name|alias) -> entity node id
    """Index every entity by its key, current name, and each alias.

    First writer wins on a collision (`setdefault`) — the durable `key` is added
    first, so a name shared transiently can't hijack a key-resolution."""
    index: Dict[str, str] = {}
    for e in entities:
        nid = _node_id(e)
        if not nid:
            continue
        p = _props(e)
        names: List[Any] = [p.get("key"), p.get("name")] + list(p.get("aliases") or [])
        for n in names:
            if n:
                index.setdefault(_canon(n), nid)
    return index


def resolve_subject_id(
    index: Dict[str, str],  # An index from `build_alias_index`
    name: str,              # A subject name / key / alias
) -> Optional[str]:  # The entity node id, or None when unresolved
    """Resolve a subject name to its entity id via the alias index (no guessing)."""
    return index.get(_canon(name))
