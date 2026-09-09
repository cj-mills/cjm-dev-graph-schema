"""Typed node dataclasses for the dev schema (coarse + fine tier).

Each node carries a deterministic `.id` and a `.to_graph_node()` wire-dict
mapping, mirroring `cjm-transcript-graph-schema`'s shape so the same
`extend_graph` write path applies. The coarse `NoteNode` (one per decomposed
markdown/memory file) + `EntityNode` (a subject) land first; the fine tier
promotes a note's contents into Fact-slots, layered Assertions, and Decisions
(node-hood earned by reference).

The fine-tier identity model: a `FactSlotNode` is `(subject, predicate)`; an
`AssertionNode` is one value claimed for a slot, identified by WHAT is claimed
((slot, canonical value, actor)) so re-claiming the same value is idempotent and a
different value is a new node = the potential conflict. Supersession rides the
layer's SUPERSEDES edges (resolve via `cjm_context_graph_layer.edits.resolve_active`);
the value-space conflict logic lives in `predicates`.
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from cjm_context_graph_layer.grammar import make_edge, SpineRelations
from cjm_context_graph_primitives.locators import FileRef
from cjm_context_graph_primitives.provenance import SourceRef

from .identity import (assertion_node_id, cell_node_id, check_node_id, code_module_node_id,
                       code_symbol_node_id, code_text_node_id, decision_node_id,
                       deliverable_type_node_id, entity_node_id, factslot_node_id, message_node_id,
                       note_node_id, point_node_id, reference_node_id, section_node_id,
                       series_node_id, session_node_id, topic_node_id)
from .predicates import canonical_value, is_typed
from .vocab import DevNodeKinds, DevRelations


@dataclass
class EntityNode:
    """A first-class subject: a repo/lib, stage, capability, person, or term.

    Entities are the mechanical half of slot identity (deterministic id from
    (sub-kind, stable key)) — the durable subjects that Fact-slots hang off and
    that notes/decisions point at via `ABOUT`/`DEPENDS_ON`. Asserted-root: an
    entity is declared knowledge, not ingested content.

    Identity is RENAME-STABLE (A+aliases): `key` is a durable, name-INDEPENDENT
    conceptual slug; `name` is the current display/repo name (itself slot-able);
    `aliases` are prior names + variant link-slugs that resolve to this entity
    (so a fact about a renamed subject keeps one stable home — see `aliases`)."""
    kind: str                                    # Entity sub-kind ("repo" | "stage" | "capability" | "person" | "term")
    key: str                                     # Durable conceptual slug (name-INDEPENDENT; the identity input)
    name: str                                    # Current display / repo name (slot-able; not the identity)
    aliases: List[str] = field(default_factory=list)  # Prior names + variant slugs resolving to this entity
    properties: Dict[str, Any] = field(default_factory=dict)  # Extra entity properties (e.g. repo path, tier)

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from (sub-kind, key))."""
        return entity_node_id(self.kind, self.key)

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the Entity node wire dict (root_kind=asserted; no provenance file)."""
        props: Dict[str, Any] = {
            "entity_kind": self.kind,
            "key": self.key,
            "name": self.name,
            "aliases": list(self.aliases),
            "root_kind": "asserted",
        }
        props.update(self.properties)
        return {
            "id": self.id,
            "label": DevNodeKinds.ENTITY,
            "properties": props,
            "sources": [],
        }

    def depends_on_edges(
        self,
        dep_keys: List[str],  # Stable keys of entities of the SAME sub-kind this one depends on
    ) -> List[Dict[str, Any]]:  # DEPENDS_ON edge wire dicts
        """One `DEPENDS_ON` edge per dependency (same sub-kind), by deterministic id.

        A dependency on an entity not yet emitted still resolves to a stable id
        (the store drops the edge until that entity exists — same dangling
        semantics as note REFERENCES)."""
        return [make_edge(self.id, entity_node_id(self.kind, dk), DevRelations.DEPENDS_ON)
                for dk in dep_keys]


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
    categories: List[str] = field(default_factory=list)  # Normalized category/tag keys -> TAGGED edges to Topic nodes
    series_refs: List[str] = field(default_factory=list)  # Series keys this note belongs to -> IN_SERIES edges
    aliases: List[str] = field(default_factory=list)     # Alternate identities (old URLs/slugs) resolving to this note
    cross_post_refs: List[Tuple[str, str]] = field(default_factory=list)  # (target permalink slug, section anchor) cross-post links -> REFERENCES edges
    sections: List["SectionNode"] = field(default_factory=list)  # The note's body decomposed into ordered Section nodes (when decomposed; emitted by corpus_graph_elements)
    frontmatter_raw: str = ""                    # Verbatim frontmatter prefix (fences + YAML + trailing newline); the lossless round-trip source for the frontmatter. Set in lossless mode (memory); "" otherwise. `frontmatter_raw + concat(sections.raw in order) == file bytes`

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
        if self.categories:
            props["categories"] = list(self.categories)
        if self.series_refs:
            props["series_refs"] = list(self.series_refs)
        if self.aliases:
            props["aliases"] = list(self.aliases)
        if self.metadata:
            props["metadata"] = dict(self.metadata)
        if self.frontmatter_raw:  # only the lossless path carries it; Scope-A Note wire dicts unchanged
            props["frontmatter_raw"] = self.frontmatter_raw
        return {
            "id": self.id,
            "label": DevNodeKinds.NOTE,
            "properties": props,
            "sources": [SourceRef(locator=FileRef(path=self.path),
                                  content_hash=self.content_hash).to_dict()],
        }

    def reference_edges(
        self,
        alias_map: Optional[Dict[str, str]] = None,  # Confirmed {drifted-slug: canonical-slug} aliases
    ) -> List[Dict[str, Any]]:  # REFERENCES edge wire dicts
        """One `REFERENCES` edge per `[[wiki-link]]`, targeting the linked note's id.

        Deterministic per (this note, linked note, REFERENCES); a link to a slug
        that has no file yet still resolves to a stable id (dangling links are a
        legitimate "worth writing later" marker, per the memory convention).

        A drifted link slug in `alias_map` is resolved to its CONFIRMED canonical
        slug first, so a once-dangling reference lands on the real note — the rot
        the flat file still carries is healed on-graph without editing the file."""
        m = alias_map or {}
        return [make_edge(self.id, note_node_id(m.get(ref, ref)), DevRelations.REFERENCES)
                for ref in self.references]

    def cross_post_edges(
        self,
        alias_map: Optional[Dict[str, str]] = None,  # Confirmed {drifted-slug: canonical-slug} aliases
    ) -> List[Dict[str, Any]]:  # REFERENCES edge wire dicts (cross-post markdown links)
        """One `REFERENCES` edge per cross-post markdown link, anchor on the edge.

        Reuses `REFERENCES` (a cross-post link IS a soft cross-reference) but the
        target is a real permalink slug (not a `[[wiki-slug]]`), and the `#section`
        anchor rides as an edge property (`anchor`) — left UNRESOLVED for now: the
        section-node tier (the 272-headings problem) resolves it to a section later.
        A `cross_post` marker distinguishes these from wiki-link REFERENCES.

        An ANCHORED link resolves onto the target post's SECTION node by
        construction — `section_node_id(target note, anchor)` is exactly the id that
        post's heading mints (the anchor slug == the heading slug), so the edge lands
        on the section without a lookup (dangling-safe if that post/section isn't
        ingested; the note-level tie is still recoverable via the section's
        HAS_SECTION). An UN-anchored link targets the note itself."""
        m = alias_map or {}
        edges = []
        for permalink, anchor in self.cross_post_refs:
            target_note = note_node_id(m.get(permalink, permalink))
            props: Dict[str, Any] = {"cross_post": True}
            if anchor:
                props["anchor"] = anchor
                target = section_node_id(target_note, anchor)  # resolve onto the section
            else:
                target = target_note
            edges.append(make_edge(self.id, target, DevRelations.REFERENCES, props))
        return edges

    def tagged_edges(self) -> List[Dict[str, Any]]:  # TAGGED edge wire dicts
        """One `TAGGED` edge per category, targeting the shared Topic node's id.

        Independent notes sharing a category converge on one Topic (deterministic
        id from the normalized key) — the thematic-clustering substrate. The Topic
        node itself is emitted once at corpus level (deduped across notes)."""
        return [make_edge(self.id, topic_node_id(c), DevRelations.TAGGED)
                for c in self.categories]

    def series_edges(self) -> List[Dict[str, Any]]:  # IN_SERIES edge wire dicts
        """One `IN_SERIES` edge per series this note belongs to.

        Membership only (v1): the post declares which series it is in (a callout /
        frontmatter link); the ORDER within the series is known from the series-def
        listing, not the post, so it rides an `order` edge property populated later
        (reserve-up-front: the relation supports ordering, emission is progressive)."""
        return [make_edge(self.id, series_node_id(s), DevRelations.IN_SERIES)
                for s in self.series_refs]


@dataclass
class TopicNode:
    """A category/tag facet — a thematic-clustering subject shared across notes.

    Asserted-root (a curated facet, not ingested content). Identity is the
    normalized key, so every `TAGGED` edge for the same category converges here;
    the corpus driver emits one Topic per distinct key (deduped across notes).
    First-class (not a generic term-subject) because projection enumerates facets:
    `categories ≈ topic facets` is one input to audience-parameterized projection
    (the same mechanism as the visibility/experience-level dial)."""
    key: str                    # Normalized category key (the identity input; e.g. "object-detection")
    name: str = ""              # Display name (defaults to the key when unset)

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from the normalized key)."""
        return topic_node_id(self.key)

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the Topic node wire dict (root_kind=asserted; no provenance file)."""
        return {
            "id": self.id,
            "label": DevNodeKinds.TOPIC,
            "properties": {"key": self.key, "name": self.name or self.key,
                           "root_kind": "asserted"},
            "sources": [],
        }


@dataclass
class SeriesNode:
    """An ordered collection/progression a note belongs to (a Quarto series, …).

    Asserted-root, shared across its member notes via `IN_SERIES` (each member's
    edge converges on this one node by the stable key). First-class because
    `series ≈ ordered progression` is the other audience-projection input
    (a guided path through notes); the member ORDER lives on the IN_SERIES edges
    (populated from the series-def listing, not the members)."""
    key: str                    # Durable series key (the identity input; e.g. "education-notes")
    title: str = ""             # Display title (defaults to the key when unset)

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from the stable key)."""
        return series_node_id(self.key)

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the Series node wire dict (root_kind=asserted; no provenance file)."""
        return {
            "id": self.id,
            "label": DevNodeKinds.SERIES,
            "properties": {"key": self.key, "title": self.title or self.key,
                           "root_kind": "asserted"},
            "sources": [],
        }


@dataclass
class SectionNode:
    """One heading-delimited section of a Note's body — the navigable unit + anchor target.

    The first time body CONTENT comes on-graph (the coarse Note stores only
    frontmatter/relationships): a Note's body decomposes into ordered Sections,
    each carrying its VERBATIM text (faithful at the section grain — Scope A does
    not yet promise whole-file byte-exact round-trip). Identity = (note, anchor
    slug), the same slug a cross-post `#anchor` targets, so inbound anchored
    REFERENCES resolve by construction. Membership rides `HAS_SECTION` (note ->
    section); the heading hierarchy rides the layer's `PART_OF` spine relation
    (section -> enclosing section); document order is the `order` property."""
    note_id: str                                 # Enclosing Note id; identity input
    anchor: str                                  # Heading slug (disambiguated; reserved "_preamble" for the pre-first-heading region); identity input
    level: int                                   # Heading depth (1-6); 0 for the preamble region
    title: str                                   # Heading text ("" for the preamble region)
    text: str = ""                               # Verbatim section body, heading line EXCLUDED (the navigable/anchor-target unit; Scope A)
    order: int = 0                               # Document-order index within the note (content, not identity)
    parent_anchor: Optional[str] = None          # Enclosing section's anchor (None at top level); the PART_OF target
    content_hash: str = ""                       # Content hash over the section's lossless span (`raw` when set, else `text`)
    path: str = ""                               # Source file path (provenance locator)
    raw: str = ""                                # Verbatim span INCLUDING the heading line (heading.start -> next heading.start); the lossless round-trip source. Concatenating every section's `raw` in `order` reproduces the body byte-for-byte (M1). "" in Scope-A mode (posts); set in lossless mode (memory)

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from (note, anchor))."""
        return section_node_id(self.note_id, self.anchor)

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the Section node wire dict (root_kind=asserted; verbatim section text)."""
        props: Dict[str, Any] = {
            "name": self.title or self.anchor,
            "anchor": self.anchor,
            "level": self.level,
            "title": self.title,
            "text": self.text,
            "order": self.order,
            "note_id": self.note_id,
            "path": self.path,
            "root_kind": "asserted",
        }
        if self.raw:  # only the lossless path carries it; keep Scope-A wire dicts unchanged
            props["raw"] = self.raw
        sources = ([SourceRef(locator=FileRef(path=self.path),
                              content_hash=self.content_hash).to_dict()]
                   if self.path and self.content_hash else [])
        return {
            "id": self.id,
            "label": DevNodeKinds.SECTION,
            "properties": props,
            "sources": sources,
        }

    def structural_edges(self) -> List[Dict[str, Any]]:  # HAS_SECTION + PART_OF edge wire dicts
        """The note-membership edge + the heading-hierarchy edge.

        `Note HAS_SECTION self` (membership); `self PART_OF enclosing-section` when
        this heading nests under another (a stable id from (note, parent anchor),
        dangling-safe if the parent isn't emitted). Document order is a property,
        not an edge, to avoid a NEXT edge per heading at 272-headings scale."""
        edges = [make_edge(self.note_id, self.id, DevRelations.HAS_SECTION)]
        if self.parent_anchor:
            edges.append(make_edge(self.id, section_node_id(self.note_id, self.parent_anchor),
                                   SpineRelations.PART_OF))
        return edges


@dataclass
class FactSlotNode:
    """A `(subject, predicate)` slot — the home for layered, supersede-able claims.

    THE slot-identity unlock: one deterministic node per (subject, predicate), so
    independent assertions about the same fact converge here instead of splitting
    into parallel free-floating questions. The slot carries no value itself — its
    effective value is the active (non-superseded) Assertion(s) ON_SLOT it."""
    subject_id: str    # The subject node's id (an Entity, usually)
    predicate: str     # The curated predicate slug
    subject_label: str = ""  # Optional display label for the subject (convenience; not identity)

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from (subject, predicate))."""
        return factslot_node_id(self.subject_id, self.predicate)

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the Fact-slot node wire dict (root_kind=asserted; carries typing)."""
        props: Dict[str, Any] = {
            "subject_id": self.subject_id,
            "predicate": self.predicate,
            "typed": is_typed(self.predicate),
            "root_kind": "asserted",
        }
        if self.subject_label:
            props["subject_label"] = self.subject_label
        return {"id": self.id, "label": DevNodeKinds.FACT_SLOT, "properties": props, "sources": []}

    def about_edge(self) -> Dict[str, Any]:  # ABOUT edge wire dict (slot -> subject)
        """The `ABOUT` edge tying the slot to its subject (traversal anchor)."""
        return make_edge(self.id, self.subject_id, DevRelations.ABOUT)


@dataclass
class AssertionNode:
    """One value claimed for a Fact-slot — identified by WHAT is claimed.

    id = (slot, canonical value, actor): re-asserting the same value (same actor)
    is an idempotent no-op; a DIFFERENT value mints a new node = the potential
    conflict. The why is a separate premise node (`SUPPORTED_BY`); the when is
    `asserted_at`/`last_verified` (content, not identity); the evidence is
    `EVIDENCED_BY` edges (union, not identity). The effective value resolves via
    the layer's SUPERSEDES edges (`resolve_active`)."""
    slot_id: str                       # The Fact-slot this value is claimed for
    value: str                         # The claimed value (raw)
    actor: str                         # Who claimed it (e.g. "human", "agent:session", "procedure:version-oracle/v1")
    predicate: str = ""                # The slot's predicate (carried for value-space conflict checks; convenience)
    subject_id: str = ""               # The slot's subject (carried for contradiction grouping/reporting)
    asserted_at: Optional[float] = None  # When claimed (None = now); content, never identity
    last_verified: Optional[float] = None  # When an oracle last re-verified it (oracle-backed slots)
    method: Optional[str] = None       # How it was derived (e.g. "version-oracle/v1")
    subject_content_hash: Optional[str] = None  # The subject's content hash at assertion time (approval binds to content, design 40622922): joins the identity, so approving CHANGED content is a new claim

    @property
    def canonical(self) -> str:  # The value's canonical form (Assertion identity input)
        """Canonical value under the predicate's value-space."""
        return canonical_value(self.predicate, self.value)

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from (slot, canonical value, actor))."""
        # Approval binds to content (design 40622922): a bound content hash joins the identity,
        # so approving CHANGED content is a new claim (and supersedes the stale one at the
        # verb), while re-asserting the same value on unchanged content stays a no-op.
        bound = f"{self.canonical}@{self.subject_content_hash}" if self.subject_content_hash else self.canonical
        return assertion_node_id(self.slot_id, bound, self.actor)

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the Assertion node wire dict (root_kind=asserted; no file source)."""
        props: Dict[str, Any] = {
            "slot_id": self.slot_id,
            "value": self.value,
            "canonical_value": self.canonical,
            "actor": self.actor,
            "asserted_at": self.asserted_at if self.asserted_at is not None else time.time(),
            "root_kind": "asserted",
        }
        if self.predicate:
            props["predicate"] = self.predicate
        if self.subject_id:
            props["subject_id"] = self.subject_id
        if self.last_verified is not None:
            props["last_verified"] = self.last_verified
        if self.method:
            props["method"] = self.method
        if self.subject_content_hash:
            props["subject_content_hash"] = self.subject_content_hash
        return {"id": self.id, "label": DevNodeKinds.ASSERTION, "properties": props, "sources": []}

    def on_slot_edge(self) -> Dict[str, Any]:  # ON_SLOT edge wire dict (assertion -> slot)
        """The `ON_SLOT` edge tying this assertion to its Fact-slot."""
        return make_edge(self.id, self.slot_id, DevRelations.ON_SLOT)

    def evidenced_by_edges(
        self,
        evidence_ids: List[str],  # Source-note / session / evidence node ids supporting this claim
    ) -> List[Dict[str, Any]]:  # EVIDENCED_BY edge wire dicts
        """One `EVIDENCED_BY` edge per supporting source (the dedup win: ONE claim
        carrying provenance edges to ALL its sources, not N duplicate claims)."""
        return [make_edge(self.id, eid, DevRelations.EVIDENCED_BY) for eid in evidence_ids]

    def supersedes_edge(
        self,
        superseded_id: str,  # The prior assertion id this one replaces
    ) -> Dict[str, Any]:  # SUPERSEDES edge wire dict
        """A `SUPERSEDES` edge: this assertion replaces a prior one (append-only)."""
        return make_edge(self.id, superseded_id, DevRelations.SUPERSEDES)

    def contradicts_edge(
        self,
        other_id: str,  # A conflicting active assertion id
    ) -> Dict[str, Any]:  # CONTRADICTS edge wire dict
        """A `CONTRADICTS` edge recording a detected conflict (warn-record-flag)."""
        return make_edge(self.id, other_id, DevRelations.CONTRADICTS)


@dataclass
class DecisionNode:
    """A decision/conclusion, with rationale recorded as edges, not prose.

    Minimal in the cut: a node + `SUPPORTED_BY` edges to premise Assertions +
    `DECIDED_IN` to a Session. Banks the reasoning-graph north star cheaply (record
    the premise edges now; the premise-drift checker is deferred)."""
    statement: str            # The decision statement (its stable key, canonicalized for identity)
    actor: str = "agent:session"  # Who decided

    @property
    def key(self) -> str:  # Canonical statement key
        """Whitespace-normalized statement (the identity input)."""
        return " ".join(self.statement.split())

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from the canonical statement)."""
        return decision_node_id(self.key)

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the Decision node wire dict (root_kind=asserted)."""
        return {"id": self.id, "label": DevNodeKinds.DECISION,
                "properties": {"statement": self.statement, "actor": self.actor,
                               "root_kind": "asserted"},
                "sources": []}

    def supported_by_edges(
        self,
        premise_ids: List[str],  # Premise Assertion ids this decision rests on
    ) -> List[Dict[str, Any]]:  # SUPPORTED_BY edge wire dicts
        """One `SUPPORTED_BY` edge per premise (the reasoning substrate)."""
        return [make_edge(self.id, pid, DevRelations.SUPPORTED_BY) for pid in premise_ids]

    def decided_in_edge(
        self,
        session_id: str,  # The Session this was decided in
    ) -> Dict[str, Any]:  # DECIDED_IN edge wire dict
        """The `DECIDED_IN` edge tying the decision to its session."""
        return make_edge(self.id, session_id, DevRelations.DECIDED_IN)

    def supersedes_edge(
        self,
        superseded_id: str,  # A prior decision id this one replaces
    ) -> Dict[str, Any]:  # SUPERSEDES edge wire dict
        """A `SUPERSEDES` edge: this decision replaces a prior one."""
        return make_edge(self.id, superseded_id, DevRelations.SUPERSEDES)


@dataclass
class CheckNode:
    """A definition-of-done check on a work item — a derivable gate, not prose.

    DoD-as-graph-objects: a check's done-ness rides the same `task_state` /
    supersession machinery as a work item's (assert `done` with `--evidence`
    pointing at the proof; a regression is a supersession back to `open`). It
    hangs off its item via a dedicated `CHECKS` edge — NOT `GATED_BY`, because a
    DoD gates CLOSING the item, never starting it (checks are satisfied BY doing
    the work). The readiness projector folds checks into derived `closable` /
    `drift` classes; `done` itself stays human-authored (checks VERIFY the
    judgment, they don't replace it — oracle-verified checks are the designed-for
    phase-2 via `method`/`last_verified`)."""
    item_id: str   # The work item this check gates closure of
    text: str      # The check statement (canonicalized for identity)
    actor: str = "agent:session"  # Who attached it

    @property
    def key(self) -> str:  # Canonical text key
        """Whitespace-normalized check text (the identity input)."""
        return " ".join(self.text.split())

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id from (item, canonical text)."""
        return check_node_id(self.item_id, self.key)

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the Check node wire dict (root_kind=asserted)."""
        return {"id": self.id, "label": DevNodeKinds.CHECK,
                "properties": {"text": self.text, "item_id": self.item_id,
                               "actor": self.actor, "root_kind": "asserted"},
                "sources": []}

    def checks_edge(self) -> Dict[str, Any]:  # CHECKS edge wire dict
        """The `CHECKS` edge tying the check to the work item whose closure it gates."""
        return make_edge(self.id, self.item_id, DevRelations.CHECKS)


@dataclass
class SessionNode:
    """A working session — the home decisions/facts are PRODUCED_IN / DECIDED_IN.

    Minimal in the cut: a bare keyed node so `decide --session` has a real target
    (the session-on-graph north star lands a richer Session source-type later)."""
    key: str           # Stable session key (e.g. the session id/timestamp)
    title: str = ""    # Optional display title

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from the session key)."""
        return session_node_id(self.key)

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the Session node wire dict (root_kind=asserted)."""
        props: Dict[str, Any] = {"key": self.key, "root_kind": "asserted"}
        if self.title:
            props["title"] = self.title
        return {"id": self.id, "label": DevNodeKinds.SESSION, "properties": props, "sources": []}


@dataclass
class MessageNode:
    """A discourse EVENT on a session spine (DEC 91c47b4a): one user-facing message.

    The scratchpad-v2 unit — a pulled CC-transcript message (either side), an
    editor-born composition part, an agent exchange, a future external-comms
    utterance. One label across capture sources: variability rides `role`/`source`
    properties and birth edges, never new labels (the Segment
    one-label-many-sources pattern). Distinct from `NoteNode` (maintained standing
    resource): a Message is essentially immutable once minted — corrections are
    edit ops or `AMENDS` messages, and "active vs superseded branch" is DERIVED
    from the chain, never stored (DEC 671e9b11 point 8). Anchoring reuses the
    layer spine grammar: PART_OF the Session, NEXT succession along a chain,
    STARTS_WITH from the Session to a chain head."""
    source_uuid: str          # Capture-source record uuid (identity input; the CC record uuid, or a composer-minted uuid)
    role: str                 # "user" | "assistant" (the speaking actor's side)
    text: str                 # The message body — raw markdown source, the authoritative content
    timestamp: str = ""       # ISO-8601 capture time as recorded by the harness
    source: str = ""          # Capture source (e.g. "cc-transcript", "composer"); provenance facet, not identity
    parent_source_uuid: str = ""  # The capture DAG's parentUuid (ground-truth ancestry, property only)
    session_key: str = ""     # The session spine key this message belongs to (display/provenance; the edge carries structure)
    properties: Dict[str, Any] = field(default_factory=dict)  # Extra properties (chain index, actor, ...)

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from the capture-source record uuid)."""
        return message_node_id(self.source_uuid)

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the Message node wire dict (root_kind=asserted)."""
        props: Dict[str, Any] = {"source_uuid": self.source_uuid, "role": self.role,
                                 "text": self.text, "root_kind": "asserted"}
        if self.timestamp:
            props["timestamp"] = self.timestamp
        if self.source:
            props["source"] = self.source
        if self.parent_source_uuid:
            props["parent_source_uuid"] = self.parent_source_uuid
        if self.session_key:
            props["session_key"] = self.session_key
        props.update(self.properties)
        return {"id": self.id, "label": DevNodeKinds.MESSAGE, "properties": props, "sources": []}

    def part_of_edge(
        self,
        session_id: str,  # The Session spine node id this message hangs off
    ) -> Dict[str, Any]:  # PART_OF edge wire dict
        """Message -> Session containment (child -> parent, the spine grammar)."""
        return make_edge(self.id, session_id, SpineRelations.PART_OF)

    def next_edge_from(
        self,
        prev_message_id: str,  # The preceding Message node id on the chain
    ) -> Dict[str, Any]:  # NEXT edge wire dict
        """Chain succession: predecessor -> this message. A rewind fork is simply a
        second NEXT edge out of one predecessor — append-only, active path derived."""
        return make_edge(prev_message_id, self.id, SpineRelations.NEXT)

    def starts_with_edge(
        self,
        session_id: str,  # The Session spine node id
    ) -> Dict[str, Any]:  # STARTS_WITH edge wire dict
        """Session -> chain head (parent -> first child, the spine grammar)."""
        return make_edge(session_id, self.id, SpineRelations.STARTS_WITH)


@dataclass
class CodeModuleNode:
    """The code source-type's coarse node: one decomposed `.py` module.

    Parallel to `NoteNode` (the markdown source-type) — same `FileRef`+content-hash
    `SourceRef` provenance, so code-module and note nodes CO-RESIDE on one graph (the
    seam a future nbdev compositor weaves from a notebook's interleaved code+markdown
    cells). Identity is (repo_key, module_path) keyed on the repo's DURABLE conceptual
    slug (NOT its directory name), so the id is reproducible in any graph that
    decomposes the repo — the cross-graph/federation anchor that lets a different
    project's graph reference this module by its stable id. A module is also a
    first-class subject: a Fact-slot can hang off it (e.g. a module-level known-issue)."""
    repo_key: str                                # Repo's durable conceptual slug (the rename-stable Entity key + federation anchor); identity input
    module_path: str                             # Repo-relative module path (e.g. "cjm_dev_graph_schema/nodes.py"); identity input
    path: str                                    # File path (provenance locator; may move, identity is (repo_key, module_path))
    content_hash: str                            # Content hash over the file bytes ("algo:hexdigest")
    import_name: str = ""                         # Dotted import name (e.g. "cjm_dev_graph_schema.nodes"); display + import resolution, not identity
    docstring: str = ""                          # Module docstring first line (the relevance/description hook)
    imports: List[str] = field(default_factory=list)  # Dotted module names imported (raw; resolved to IMPORTS edges via a corpus map)
    import_bindings: List[Dict[str, Any]] = field(default_factory=list)  # Top-level imports used by MODULE-LEVEL code (imports-as-projection; symbol-level bindings live on the symbols)
    properties: Dict[str, Any] = field(default_factory=dict)  # Extra module properties

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from (repo_key, module_path))."""
        return code_module_node_id(self.repo_key, self.module_path)

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the CodeModule node wire dict (root_kind=asserted; FileRef provenance)."""
        props: Dict[str, Any] = {
            "name": self.import_name or self.module_path,
            "title": self.module_path,
            "repo_key": self.repo_key,
            "module_path": self.module_path,
            "path": self.path,
            "root_kind": "asserted",
        }
        if self.import_name:
            props["import_name"] = self.import_name
        if self.docstring:
            props["description"] = self.docstring
        if self.imports:
            props["imports"] = list(self.imports)
        if self.import_bindings:
            props["import_bindings"] = list(self.import_bindings)
        props.update(self.properties)
        return {
            "id": self.id,
            "label": DevNodeKinds.CODE_MODULE,
            "properties": props,
            "sources": [SourceRef(locator=FileRef(path=self.path),
                                  content_hash=self.content_hash).to_dict()],
        }

    def about_edge(self) -> Dict[str, Any]:  # ABOUT edge (module -> repo Entity)
        """The `ABOUT` edge tying the module to its repo Entity (the cross-link into
        the decision/note neighborhood). Targets `entity_node_id("repo", repo_key)`;
        dangles harmlessly until that repo Entity lands (same as note REFERENCES)."""
        return make_edge(self.id, entity_node_id("repo", self.repo_key), DevRelations.ABOUT)

    def defines_edges(
        self,
        symbol_ids: List[str],  # ids of the top-level CodeSymbols this module declares
    ) -> List[Dict[str, Any]]:  # DEFINES edge wire dicts
        """One `DEFINES` edge per top-level symbol the module declares."""
        return [make_edge(self.id, sid, DevRelations.DEFINES) for sid in symbol_ids]

    def import_edges(
        self,
        import_map: Dict[str, str],  # {dotted-import-name: target CodeModule id} for intra-corpus modules
    ) -> List[Dict[str, Any]]:  # IMPORTS edge wire dicts
        """One `IMPORTS` edge per import that resolves to a module in the corpus map.

        External/stdlib imports (absent from the map) are skipped rather than minting
        phantom targets — the map is the corpus the driver chose to decompose."""
        return [make_edge(self.id, import_map[imp], DevRelations.IMPORTS)
                for imp in self.imports if imp in import_map]

    def contains_edges(
        self,
        region_ids: List[str],  # ids of the module's ordered top-level regions (top-level CodeSymbols + CodeTexts)
    ) -> List[Dict[str, Any]]:  # CONTAINS edge wire dicts
        """One `CONTAINS` edge per ordered top-level region the module is composed of.

        Parallels the notebook compositor's module→Cell CONTAINS: the verbatim
        ASSEMBLY substrate (interleaving def-regions and non-def text-regions, ordered
        by `order_index`) that a graph→`.py` canonical emit walks. DEFINES carries the
        symbol STRUCTURE; CONTAINS carries the verbatim SOURCE order — a class lands in
        both (DEFINES its methods, CONTAINED by its module)."""
        return [make_edge(self.id, rid, DevRelations.CONTAINS) for rid in region_ids]


@dataclass
class CodeSymbolNode:
    """A definition within a module: a function, class, or method.

    A first-class addressable subject (deterministic id) — so a Fact-slot can hang
    off a symbol (a `known-issue`/perf-debt assertion), a Decision can point at the
    symbol that implements it, and a different project's graph can reference it by
    its reproducible id. Structural home is its module (module DEFINES symbol);
    nesting is another DEFINES (class DEFINES method).

    The AUTHORING-on-graph substrate: a TOP-LEVEL symbol additionally carries its
    VERBATIM `body` (the exact source span — decorators + any leading comment block
    through the end of the def) + `body_hash` + an `order_index` among the module's
    top-level regions. This is the per-symbol verbatim storage of the B source-of-truth
    model (NOT an AST-as-graph decomposition — the round-trip trap): the body is the
    authoring unit a graph→`.py` canonical emit reassembles. v1 is COARSE — a class is
    ONE verbatim body (its methods stay DEFINES overlay symbols with no independent
    body; method-level authoring is the standing coarse→fine promotion). Nested symbols
    leave `body`/`order_index` empty."""
    module_id: str                               # Enclosing CodeModule node id; identity input (with qualname)
    qualname: str                                # Qualified name within the module (e.g. "EntityNode.to_graph_node"); identity input
    symbol_kind: str                             # "function" | "class" | "method"
    path: str                                    # File path (provenance locator)
    content_hash: str = ""                        # Content hash over the file bytes (the symbol shares its module's source file)
    lineno: Optional[int] = None                 # 1-based start line (provenance; content, not identity)
    docstring: str = ""                          # Symbol docstring first line (the relevance/description hook)
    calls: List[str] = field(default_factory=list)  # Names this symbol CALLS (raw; resolved to CALLS edges via a corpus map)
    refs: List[str] = field(default_factory=list)   # Names this symbol REFERENCES (superset of calls; resolved to USES edges via the corpus map)
    import_bindings: List[Dict[str, Any]] = field(default_factory=list)  # Top-level imports this symbol's refs use (travel with it on a move; imports-as-projection)
    body: str = ""                               # VERBATIM source of a TOP-LEVEL symbol (decorators+leading comments..end); the authoring unit ("" for nested)
    body_hash: str = ""                          # Content hash over `body` ("algo:hexdigest"); the authoring slot's content address
    order_index: Optional[int] = None            # Position among the module's top-level regions (emit order; content, not identity; None for nested)
    properties: Dict[str, Any] = field(default_factory=dict)  # Extra symbol properties

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from (module, qualname))."""
        return code_symbol_node_id(self.module_id, self.qualname)

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the CodeSymbol node wire dict (root_kind=asserted)."""
        props: Dict[str, Any] = {
            "name": self.qualname,
            "title": self.qualname,
            "module_id": self.module_id,
            "qualname": self.qualname,
            "symbol_kind": self.symbol_kind,
            "path": self.path,
            "root_kind": "asserted",
        }
        if self.lineno is not None:
            props["lineno"] = self.lineno
        if self.docstring:
            props["description"] = self.docstring
        if self.calls:
            props["calls"] = list(self.calls)
        if self.refs:
            props["refs"] = list(self.refs)
        if self.import_bindings:
            props["import_bindings"] = list(self.import_bindings)
        if self.body:
            props["body"] = self.body
            props["body_hash"] = self.body_hash
        if self.order_index is not None:
            props["order_index"] = self.order_index
        props.update(self.properties)
        sources = ([SourceRef(locator=FileRef(path=self.path),
                              content_hash=self.content_hash).to_dict()]
                   if self.content_hash else [])
        return {"id": self.id, "label": DevNodeKinds.CODE_SYMBOL, "properties": props,
                "sources": sources}

    def defines_edges(
        self,
        child_ids: List[str],  # ids of nested CodeSymbols (e.g. a class's methods)
    ) -> List[Dict[str, Any]]:  # DEFINES edge wire dicts
        """One `DEFINES` edge per nested symbol (class -> its methods)."""
        return [make_edge(self.id, cid, DevRelations.DEFINES) for cid in child_ids]

    def calls_edges(
        self,
        call_map: Dict[str, str],  # {called-name: target CodeSymbol id} for intra-corpus symbols
    ) -> List[Dict[str, Any]]:  # CALLS edge wire dicts
        """One `CALLS` edge per call that resolves to a symbol in the corpus map.

        Unresolved names (external calls, builtins, locals) are skipped — call
        resolution is best-effort name matching, not a full scope analysis."""
        return [make_edge(self.id, call_map[c], DevRelations.CALLS)
                for c in self.calls if c in call_map]

    def uses_edges(
        self,
        call_map: Dict[str, str],  # {referenced-name: target CodeSymbol id} for intra-corpus symbols
    ) -> List[Dict[str, Any]]:  # USES edge wire dicts
        """One `USES` edge per reference that resolves to a symbol in the corpus map.

        The superset of `calls_edges` — includes base classes, type annotations,
        decorators, and bare-name loads, not just call-callees. Unresolved names
        (external, builtins, locals) are skipped (best-effort name matching)."""
        seen: set = set()
        out: List[Dict[str, Any]] = []
        for r in self.refs:
            tgt = call_map.get(r)
            if tgt and tgt != self.id and tgt not in seen:  # skip self-reference + dups
                seen.add(tgt)
                out.append(make_edge(self.id, tgt, DevRelations.USES))
        return out


@dataclass
class CellNode:
    """One VERBATIM notebook cell — the lossless source substrate of a notebook module.

    A notebook is a `CodeModule` whose authored source is an ORDERED sequence of cells.
    Storing each cell verbatim + content-hashed is the round-trip / source-of-truth-B
    substrate (a notebook is itself a projection composing markdown + code nodes, so the
    cells must regenerate it faithfully). Code cells additionally get a `CodeSymbol`
    overlay (the module DEFINES them, each tagged with its `cell_key`); markdown cells
    carry their prose inline (title/description) and DOCUMENTS the symbols they precede.
    Identity = (notebook module, stable cell key) — the nbformat cell `id` when present,
    else the positional index. Outputs are intentionally NOT stored (derived, not source)."""
    module_id: str                               # The enclosing notebook CodeModule id; identity input
    cell_key: str                                # Stable cell key (nbformat `id`, else str(index)); identity input
    cell_type: str                               # "code" | "markdown" | "raw"
    source: str                                  # The cell's VERBATIM source text (the lossless store)
    content_hash: str                            # Content hash over the cell source
    index: Optional[int] = None                  # Positional index in the notebook (content/order, not identity)
    path: str = ""                               # Notebook file path (provenance locator)
    directives: List[str] = field(default_factory=list)  # nbdev `#|` directives on the cell (e.g. "export", "hide")
    calls: List[str] = field(default_factory=list)        # Bare names a NON-export code cell calls (the test-cell -> symbol TESTS substrate)
    title: str = ""                              # Markdown cells: first heading/line (relevance/title hook)
    description: str = ""                         # Markdown cells: a prose snippet (relevance hook)

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from (notebook module, cell key))."""
        return cell_node_id(self.module_id, self.cell_key)

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the Cell node wire dict (root_kind=asserted; verbatim source + provenance)."""
        props: Dict[str, Any] = {
            "name": self.title or f"{self.cell_type} cell {self.index}",
            "cell_type": self.cell_type,
            "cell_key": self.cell_key,
            "module_id": self.module_id,
            "source": self.source,
            "path": self.path,
            "root_kind": "asserted",
        }
        if self.index is not None:
            props["index"] = self.index
        if self.directives:
            props["directives"] = list(self.directives)
        if self.calls:
            props["calls"] = list(self.calls)
        if self.title:
            props["title"] = self.title
        if self.description:
            props["description"] = self.description
        sources = ([SourceRef(locator=FileRef(path=self.path),
                              content_hash=self.content_hash).to_dict()]
                   if self.content_hash and self.path else [])
        return {"id": self.id, "label": DevNodeKinds.CELL, "properties": props, "sources": sources}

    def contains_edge(self) -> Dict[str, Any]:  # CONTAINS edge (notebook module -> this cell)
        """The `CONTAINS` edge from the notebook module to this cell (the substrate link)."""
        return make_edge(self.module_id, self.id, DevRelations.CONTAINS)

    def next_edge(
        self,
        next_cell_id: str,  # The id of the cell that follows this one
    ) -> Dict[str, Any]:  # NEXT edge wire dict (cell ordering; the layer's spine relation)
        """A `NEXT` edge to the following cell (cells are a linear spine, like a transcript)."""
        return make_edge(self.id, next_cell_id, SpineRelations.NEXT)

    def documents_edges(
        self,
        symbol_ids: List[str],  # CodeSymbol ids this markdown cell precedes/documents
    ) -> List[Dict[str, Any]]:  # DOCUMENTS edge wire dicts
        """One `DOCUMENTS` edge per symbol this (markdown) cell precedes — the interleaving
        nbdev only has as proximity, made queryable."""
        return [make_edge(self.id, sid, DevRelations.DOCUMENTS) for sid in symbol_ids]

    def reference_edges(
        self,
        note_slugs: List[str],  # `[[wiki-link]]` slugs found in a markdown cell's prose
    ) -> List[Dict[str, Any]]:  # REFERENCES edge wire dicts (cell -> note)
        """One `REFERENCES` edge per `[[wiki-link]]` in a markdown cell (cell -> note id)."""
        return [make_edge(self.id, note_node_id(s), DevRelations.REFERENCES) for s in note_slugs]


@dataclass
class CodeTextNode:
    """A non-def top-level region of a plain-`.py` module — the verbatim substrate BETWEEN symbols.

    A faithful `.py` round-trip needs more than the def/class bodies: imports, the module
    docstring, constants, `__all__`, and `if __name__` blocks are top-level source too. A
    `CodeText` holds one such contiguous non-def region VERBATIM + content-hashed, with an
    `order_index` placing it among the module's top-level regions. It is the plain-`.py`
    analogue of a notebook `Cell` (the lossless source substrate) for the regions that are
    not symbols — so the module's CONTAINS sequence (symbols + texts, ordered) reassembles
    the source. Identity = (module, region key) where the key anchors on the region's first
    statement, so it survives edits that don't change what the region leads with."""
    module_id: str                               # The enclosing CodeModule id; identity input
    region_key: str                              # Stable key anchoring on the region's first statement; identity input
    text: str                                    # The region's VERBATIM source text (the lossless store + authoring slot)
    content_hash: str                            # Content hash over `text` ("algo:hexdigest")
    order_index: Optional[int] = None            # Position among the module's top-level regions (emit order; content, not identity)
    path: str = ""                               # Module file path (provenance locator)
    kind: str = ""                               # Coarse region flavor for relevance/render ("imports" | "docstring" | "code")

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from (module, region key))."""
        return code_text_node_id(self.module_id, self.region_key)

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the CodeText node wire dict (root_kind=asserted; verbatim source + provenance)."""
        props: Dict[str, Any] = {
            "name": self.kind or "code text",
            "region_key": self.region_key,
            "module_id": self.module_id,
            "text": self.text,
            "path": self.path,
            "root_kind": "asserted",
        }
        if self.order_index is not None:
            props["order_index"] = self.order_index
        if self.kind:
            props["kind"] = self.kind
        sources = ([SourceRef(locator=FileRef(path=self.path),
                              content_hash=self.content_hash).to_dict()]
                   if self.content_hash and self.path else [])
        return {"id": self.id, "label": DevNodeKinds.CODE_TEXT, "properties": props, "sources": sources}


# A foreign reference token: `<graph key>:<node id>` — the key names a `sibling_graphs` entry
# in the addressing graph's config; the id is verbatim (prefix-shaped ids resolve in the
# sibling at write time). The same shape the interim `derived_from` facts carried
# (`transcription:<id>`), so those convert mechanically.
_FOREIGN_REF_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):([0-9A-Fa-f][0-9A-Fa-f-]{5,35})$")


def parse_foreign_ref(
    token: str,  # A candidate `<graph key>:<node id or unique prefix>` token
) -> Optional[Tuple[str, str]]:  # (graph key, foreign id/prefix), or None when the token is not foreign-shaped
    """Split a `<graph key>:<id>` reference token; None for a plain local id / anything else.

    Local ids are bare UUIDs (no key), so the colon form is unambiguous — `link` uses it
    to route a target into the sibling graph named by the key instead of the local db."""
    m = _FOREIGN_REF_RE.match(token.strip())
    return (m.group(1), m.group(2)) if m else None


def foreign_content_hash(
    node: Dict[str, Any],  # A foreign node's wire dict ({id, label, properties, sources, ...})
) -> str:  # "sha256:<hex>" over the node's label + canonical-JSON properties
    """The content a Reference OBSERVES: the foreign node's label + its properties, canonically
    serialized (sorted keys, no whitespace). Any property change — a stratum re-accepted,
    relabeled, re-spanned, a status flip — moves the hash, which is exactly what the review
    frontier must see; the row timestamps (`created_at`/`updated_at`) and `sources` are
    left out so a re-ingest that reproduces the same content stays unchanged."""
    props = node.get("properties") if isinstance(node, dict) else None
    if props is None:
        props = getattr(node, "properties", {}) or {}
    label = node.get("label") if isinstance(node, dict) else getattr(node, "label", "")
    canon = json.dumps({"label": label or "", "properties": props}, sort_keys=True,
                       separators=(",", ":"), default=str)
    return SourceRef.compute_hash(canon.encode("utf-8"))


def foreign_display_title(
    node: Dict[str, Any],  # A foreign node's wire dict
) -> str:  # A short human handle read off the foreign node's own properties (best effort)
    """Best-effort display handle for a foreign node: title/name/text-ish fields first,
    then a payload category/operation (the transcription strata carry those), else its
    label + id prefix. Captured at observation time so the local graph can render the
    Reference without opening the sibling."""
    props = (node.get("properties") if isinstance(node, dict) else getattr(node, "properties", None)) or {}
    label = (node.get("label") if isinstance(node, dict) else getattr(node, "label", "")) or "?"
    nid = (node.get("id") if isinstance(node, dict) else getattr(node, "id", "")) or ""
    for f in ("display_title", "title", "name", "slug", "key"):
        v = props.get(f)
        if isinstance(v, str) and v.strip():
            return v.strip()[:120]
    payload = props.get("payload") if isinstance(props.get("payload"), dict) else {}
    bits = [str(props.get("correction_type") or ""), str(payload.get("operation") or ""),
            str(payload.get("category") or "")]
    bits = [b for b in bits if b]
    if bits:
        return f"{label}: {' / '.join(bits)}"
    text = props.get("text")
    if isinstance(text, str) and text.strip():
        return text.strip()[:80]
    return f"{label} {nid[:8]}"


@dataclass
class ReferenceNode:
    """A LOCAL stand-in for a node in a sibling graph — the cross-graph reference (0154f5e4).

    A deliverable on one graph (a born post on the notes graph) derives from nodes that
    live in another (strata, segments, Sources in the transcription workflow db). The
    store drops an edge to a foreign id, so the deliverable's DERIVED_FROM lands on THIS
    node, which carries the foreign address (`graph` key + `foreign_id`) and what was
    OBSERVED there at write time (`observed_hash` over the foreign node's label +
    properties, `observed_at`, the foreign label + a display title). The observation is
    journaled with the link op, so a rebuild reproduces the Reference WITHOUT opening the
    sibling graph — the foreign graph is never written and never needed for replay. The
    review frontier opens the sibling read-only and compares the foreign node's live hash
    against the observation the approval saw. Identity = (graph key, foreign id)."""
    graph: str                                   # The sibling graph's config key (`sibling_graphs` name); identity input
    foreign_id: str                              # The node id in that graph (verbatim); identity input
    foreign_label: str = ""                      # The foreign node's label at observation (display + audit; content, not identity)
    title: str = ""                              # Display handle read off the foreign node at observation
    observed_hash: str = ""                      # `foreign_content_hash` of the foreign node at observation ("sha256:…")
    observed_at: Optional[float] = None          # When the observation was taken (verb time; replay carries the journaled one)

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from (graph key, foreign id))."""
        return reference_node_id(self.graph, self.foreign_id)

    @classmethod
    def observe(
        cls,
        graph: str,                 # The sibling graph key
        node: Dict[str, Any],       # The foreign node's wire dict as read from the sibling
        observed_at: Optional[float] = None,  # Observation time (None = now)
    ) -> "ReferenceNode":  # The Reference carrying this observation
        """Build the Reference from a live read of the foreign node (hash + label + title)."""
        nid = (node.get("id") if isinstance(node, dict) else getattr(node, "id", "")) or ""
        label = (node.get("label") if isinstance(node, dict) else getattr(node, "label", "")) or ""
        return cls(graph=graph, foreign_id=str(nid), foreign_label=str(label),
                   title=foreign_display_title(node), observed_hash=foreign_content_hash(node),
                   observed_at=observed_at if observed_at is not None else time.time())

    def observation(self) -> Dict[str, Any]:  # The journal-carried observation (what replay needs)
        """The observation fields a `link` op journals so replay never opens the sibling."""
        return {"graph": self.graph, "foreign_id": self.foreign_id, "foreign_label": self.foreign_label,
                "title": self.title, "observed_hash": self.observed_hash, "observed_at": self.observed_at}

    @classmethod
    def from_observation(cls, obs: Dict[str, Any]) -> "ReferenceNode":  # Rebuild from a journaled observation
        """The replay dual of `observation()`."""
        return cls(graph=str(obs.get("graph") or ""), foreign_id=str(obs.get("foreign_id") or ""),
                   foreign_label=str(obs.get("foreign_label") or ""), title=str(obs.get("title") or ""),
                   observed_hash=str(obs.get("observed_hash") or ""),
                   observed_at=(float(obs["observed_at"]) if obs.get("observed_at") is not None else None))

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the Reference node wire dict (root_kind=reference; no local provenance file)."""
        props: Dict[str, Any] = {
            "graph": self.graph,
            "foreign_id": self.foreign_id,
            "foreign_label": self.foreign_label,
            "title": (self.title or f"{self.foreign_label or 'node'} {self.foreign_id[:8]}") + f" @ {self.graph}",
            "name": self.title or f"{self.foreign_label or 'node'} {self.foreign_id[:8]}",
            "observed_hash": self.observed_hash,
            "root_kind": "reference",
        }
        if self.observed_at is not None:
            props["observed_at"] = self.observed_at
        return {"id": self.id, "label": DevNodeKinds.REFERENCE, "properties": props, "sources": []}


# The pure-notes type's STARTER point-kind slate (ruling a7262fe7 (2)): an OPEN vocabulary
# — a proposer may mint a new kebab-case kind, it lands as data on the Point — with glosses
# rendered into every notes pack so a cold proposer reads the same kind semantics the human
# confirms against (the RECOMMENDED_STRATUM_CLASSES doctrine). `quotation` is the ONLY kind
# carrying verbatim text; `comparison` always renders as a table, `step`/`sequence` always as
# ordered lists; `citation` is what the SOURCE names, distinct from a research-mark.
RECOMMENDED_POINT_KINDS = (
    "claim",       # a statement the source makes, in the source's framing
    "definition",  # a term the source defines or characterizes
    "step",        # one item of a procedure the source lays out (consecutive steps render as one ordered list)
    "example",     # a concrete instance the source gives for a point it makes
    "quotation",   # someone's words quoted verbatim by the source (carries the exact text + attribution)
    "datum",       # a number, measurement, date or count the source states
    "comparison",  # entities compared on named properties (renders as a table; `data.columns` + `data.rows`)
    "sequence",    # an ordered / dated series the source recounts (renders as an ordered list of its `event` children; legacy `data.items`)
    "citation",    # an external work, person or source the source itself names
    "event",       # one item of a sequence, as a CHILD point (`data.when` + text); its support nests beneath it
    "synopsis",    # the ONE unit-spanning row: what the unit argues, under ~30 words; renders as the description
)

POINT_KIND_GLOSSES: Dict[str, str] = {
    "claim": "a statement the source makes, kept in the source's own framing — telegraphic, no interpretation",
    "definition": "a term the source defines or characterizes; lead = the term",
    "step": "one item of a procedure the source lays out; consecutive steps render as ONE ordered list",
    "example": "a concrete instance the source gives for a point it makes",
    "quotation": "someone's words quoted verbatim by the source — the exact words, with who is quoted (`attribution`)",
    "datum": "a number, measurement, date or count the source states; keep the unit and the source's precision",
    "comparison": "two or more things compared on named properties — give `data.columns` and `data.rows`; renders as a table",
    "sequence": "an ordered or dated series the source recounts — give `data.items` as [{when, what}]; renders as an ordered list",
    "citation": "an external work, person, or source the SOURCE names (what it cites), not what a research pass would follow",
    "event": "one item of a `sequence`, as a CHILD point of it (`parent` = the sequence row): `data.when` + the text; its own support nests beneath it (ruling on the second staging read, 2026-09-08)",
    "synopsis": "ONE row per unit, written last, spanning the whole unit (the only kind that may cross headers): one or two sentences under ~30 words on what the unit argues — never a heading list; renders as the description",
}


@dataclass
class PointNode:
    """A typed deliverable's SUBSTANCE atom (ruling a7262fe7): the smallest statement
    attributable to the source without interpretation, in the source's own framing.

    The structural inversion behind the pure-notes type: a deliverable Note keeps its
    publish state and authored frontmatter, but its body Sections are RENDERED from Points
    at emit time, never authored. A Point carries telegraphic `text` of one `kind` (open
    vocabulary; `RECOMMENDED_POINT_KINDS` is the starter slate), the segment run it derives
    from (`segment_ids` + source times, copied at accept so ordering and timestamps need no
    sibling read), the heading it falls under (the read-aloud section header the apparatus
    strata name, captured from the pack), and an optional `lead` term (the only emphasis a
    rendering applies), and — ruling e1fd4d64 (H) — an optional `parent_key` naming the
    Point it elaborates (ONE level: an `ELABORATES` edge child -> parent; the renderer nests
    the child as a sub-item; a parent never carries a parent of its own). Fidelity is by
    construction — a Point exists only as derived, and its DERIVED_FROM edges land on
    cross-graph References to the segments. Identity = (deliverable Note, opaque key) so
    re-render / re-order / re-parent / text edits keep the node."""
    note_id: str                                 # The deliverable Note this point belongs to; identity input
    key: str                                     # Opaque stable key (the accepted proposal id); identity input
    kind: str                                    # Point kind (open vocabulary; starter slate RECOMMENDED_POINT_KINDS)
    text: str                                    # The telegraphic statement (verbatim for `quotation`)
    ordinal: int = 0                             # Source-order position (pack position at accept; content, not identity)
    lead: str = ""                               # Optional lead term (rendered bold — the one permitted emphasis)
    heading: str = ""                            # The source section header the point falls under ("" = the unit's top)
    heading_index: int = 0                       # Order of that header within the unit (0 = before any header)
    segment_ids: List[str] = field(default_factory=list)  # The sibling-graph Segment ids the point derives from (spine order)
    start_time: Optional[float] = None           # Run start (source seconds), copied from the segments
    end_time: Optional[float] = None             # Run end (source seconds)
    attribution: str = ""                        # `quotation`: who is quoted (as the source names them)
    data: Dict[str, Any] = field(default_factory=dict)  # Kind-specific structure (`comparison`: columns/rows; `sequence`: items)
    unit: Dict[str, Any] = field(default_factory=dict)  # The source structure unit address ({source_id, unit, title, part, chapter…})
    parent_key: str = ""                         # The key of the Point this one elaborates ("" = top level; one level only)
    actor: str = "agent:session"                 # Who proposed the text (the accept records the confirming actor on the op)

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from (note, key))."""
        return point_node_id(self.note_id, self.key)

    @property
    def parent_id(self) -> str:  # The parent Point's deterministic id ("" when top level)
        """The parent Point's node id — same deliverable, the parent's key."""
        return point_node_id(self.note_id, self.parent_key) if self.parent_key else ""

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the Point node wire dict (root_kind=derived — substance derived from segments)."""
        props: Dict[str, Any] = {
            "name": (self.lead or self.text)[:80],
            "title": f"{self.kind}: {(self.lead + ' — ' if self.lead else '') + self.text}"[:160],
            "note_id": self.note_id,
            "key": self.key,
            "kind": self.kind,
            "text": self.text,
            "ordinal": int(self.ordinal),
            "heading": self.heading,
            "heading_index": int(self.heading_index),
            "segment_ids": list(self.segment_ids),
            "actor": self.actor,
            "root_kind": "derived",
        }
        if self.lead:
            props["lead"] = self.lead
        if self.start_time is not None:
            props["start_time"] = float(self.start_time)
        if self.end_time is not None:
            props["end_time"] = float(self.end_time)
        if self.attribution:
            props["attribution"] = self.attribution
        if self.data:
            props["data"] = dict(self.data)
        if self.unit:
            props["unit"] = dict(self.unit)
        if self.parent_key:
            props["parent_key"] = self.parent_key
        return {"id": self.id, "label": DevNodeKinds.POINT, "properties": props, "sources": []}

    def has_point_edge(self) -> Dict[str, Any]:  # HAS_POINT edge wire dict (note -> point)
        """The membership edge from the deliverable Note (order rides the Point, not the edge)."""
        return make_edge(self.note_id, self.id, DevRelations.HAS_POINT)

    def elaborates_edge(self) -> Optional[Dict[str, Any]]:  # ELABORATES edge wire dict (child -> parent), None at top level
        """The one-level nesting edge to the parent Point (the renderer's sub-item structure)."""
        if not self.parent_key:
            return None
        return make_edge(self.id, self.parent_id, DevRelations.ELABORATES)

    def derived_from_edges(
        self,
        reference_ids: List[str],  # The local Reference stand-ins for the point's segments (cross-graph seam)
    ) -> List[Dict[str, Any]]:  # DERIVED_FROM edge wire dicts, spine order on the `order` property
        """One `DERIVED_FROM` edge per segment Reference — the provenance the review frontier follows."""
        return [make_edge(self.id, rid, DevRelations.DERIVED_FROM, properties={"order": i})
                for i, rid in enumerate(reference_ids)]


@dataclass
class DeliverableTypeNode:
    """A deliverable TYPE's profile as graph DATA (ruling a7262fe7 (1)) — the display-rule
    doctrine applied to deliverables: one node per type, upserted by its slug.

    Three policies ride it. `information_policy` is a STRATUM QUERY over the source
    (which segments a deliverable of this type draws on: unclassified + the named
    strata; which strata give structure; which exclude a segment; which classes are
    never carried). `presentation_policy` names the renderings and their rules plus the
    kind slate (kind -> gloss). `production_procedure` is the lane's ordered steps. A
    deliverable Note binds to the type by a `deliverable_type` fact (supersedable), so
    the lane's verbs and the review frontier read the rules off the graph, never code."""
    key: str                                                 # Durable slug (e.g. "pure-notes"); identity input
    title: str = ""                                          # Display title
    description: str = ""                                    # One line on what the type is for
    information_policy: Dict[str, Any] = field(default_factory=dict)  # {include_unclassified, include_strata, structure_strata, exclude_strata, never_carry}
    presentation_policy: Dict[str, Any] = field(default_factory=dict)  # {renderings: {name: rules}, kinds: {kind: gloss}, emphasis, section_length_target}
    production_procedure: List[str] = field(default_factory=list)      # The lane's ordered steps (prose, one per step)
    actor: str = "agent:session"                             # Who minted / last updated the profile

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from the slug)."""
        return deliverable_type_node_id(self.key)

    def to_graph_node(self) -> Dict[str, Any]:  # Node wire dict
        """Build the DeliverableType node wire dict (root_kind=asserted; a declared profile)."""
        props: Dict[str, Any] = {
            "name": self.key,
            "key": self.key,
            "title": self.title or self.key,
            "description": self.description,
            "information_policy": dict(self.information_policy),
            "presentation_policy": dict(self.presentation_policy),
            "production_procedure": list(self.production_procedure),
            "actor": self.actor,
            "root_kind": "asserted",
        }
        return {"id": self.id, "label": DevNodeKinds.DELIVERABLE_TYPE, "properties": props,
                "sources": []}
