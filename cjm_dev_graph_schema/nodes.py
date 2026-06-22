"""Typed node dataclasses for the dev schema (coarse tier).

Each node carries a deterministic `.id` and a `.to_graph_node()` wire-dict
mapping, mirroring `cjm-transcript-graph-schema`'s shape so the same
`extend_graph` write path applies. The coarse `NoteNode` (one per decomposed
markdown/memory file) lands first; fine-tier nodes (Decision, Assertion, …) are
added as the schema is refined.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from cjm_context_graph_layer.grammar import make_edge
from cjm_context_graph_primitives.locators import FileRef
from cjm_context_graph_primitives.provenance import SourceRef

from .identity import note_node_id
from .vocab import DevNodeKinds, DevRelations


@dataclass
class NoteNode:
    """The coarse-tier document node: one decomposed markdown/memory file.

    Asserted-root knowledge (a human-authored document), identified by its stable
    slug. Its `[[wiki-links]]` become `REFERENCES` edges to other notes' ids; its
    body is NOT exploded into fine nodes yet (node-hood earned by reference — the
    fine tier promotes a note's contents into Decisions/Assertions later)."""
    slug: str                                    # Stable slug (frontmatter `name`, else corpus-relative path); the identity input
    title: str                                   # Display title (derived from the slug when no explicit title exists)
    path: str                                    # Corpus-relative or absolute file path (provenance locator; may move, identity is the slug)
    content_hash: str                            # Content hash over the file bytes ("algo:hexdigest")
    description: str = ""                         # One-line summary (frontmatter `description`); the relevance/index hook
    note_type: Optional[str] = None              # Memory category if present (user | feedback | project | reference)
    references: List[str] = field(default_factory=list)  # Slugs this note links to (`[[link]]`)
    metadata: Dict[str, Any] = field(default_factory=dict)  # Extra frontmatter carried verbatim

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from the stable slug)."""
        return note_node_id(self.slug)

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the Note node wire dict (root_kind=asserted; FileRef provenance)."""
        props: Dict[str, Any] = {
            "title": self.title,
            "slug": self.slug,
            "description": self.description,
            "path": self.path,
            "root_kind": "asserted",
        }
        if self.note_type:
            props["note_type"] = self.note_type
        if self.metadata:
            props["metadata"] = dict(self.metadata)
        return {
            "id": self.id,
            "label": DevNodeKinds.NOTE,
            "properties": props,
            "sources": [SourceRef(locator=FileRef(path=self.path),
                                  content_hash=self.content_hash).to_dict()],
        }

    def reference_edges(self) -> List[Dict[str, Any]]:  # REFERENCES edge wire dicts
        """One `REFERENCES` edge per `[[wiki-link]]`, targeting the linked note's id.

        Deterministic per (this note, linked note, REFERENCES); a link to a slug
        that has no file yet still resolves to a stable id (dangling links are a
        legitimate "worth writing later" marker, per the memory convention)."""
        return [make_edge(self.id, note_node_id(ref), DevRelations.REFERENCES)
                for ref in self.references]
