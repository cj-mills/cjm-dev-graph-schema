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

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from cjm_context_graph_layer.grammar import SpineRelations, make_edge
from cjm_context_graph_primitives.locators import FileRef
from cjm_context_graph_primitives.provenance import SourceRef

from .identity import (assertion_node_id, cell_node_id, check_node_id,
                       code_module_node_id, code_symbol_node_id, code_text_node_id,
                       decision_node_id, entity_node_id, factslot_node_id,
                       note_node_id, section_node_id, series_node_id,
                       session_node_id, topic_node_id)
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

    @property
    def canonical(self) -> str:  # The value's canonical form (Assertion identity input)
        """Canonical value under the predicate's value-space."""
        return canonical_value(self.predicate, self.value)

    @property
    def id(self) -> str:  # Deterministic node id
        """Deterministic node id (from (slot, canonical value, actor))."""
        return assertion_node_id(self.slot_id, self.canonical, self.actor)

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
