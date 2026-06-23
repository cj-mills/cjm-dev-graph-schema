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
from typing import Any, Dict, List, Optional

from cjm_context_graph_layer.grammar import make_edge
from cjm_context_graph_primitives.locators import FileRef
from cjm_context_graph_primitives.provenance import SourceRef

from .identity import (assertion_node_id, code_module_node_id, code_symbol_node_id,
                       decision_node_id, entity_node_id, factslot_node_id,
                       note_node_id, session_node_id)
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


@dataclass
class CodeSymbolNode:
    """A definition within a module: a function, class, or method.

    A first-class addressable subject (deterministic id) — so a Fact-slot can hang
    off a symbol (a `known-issue`/perf-debt assertion), a Decision can point at the
    symbol that implements it, and a different project's graph can reference it by
    its reproducible id. Structural home is its module (module DEFINES symbol);
    nesting is another DEFINES (class DEFINES method)."""
    module_id: str                               # Enclosing CodeModule node id; identity input (with qualname)
    qualname: str                                # Qualified name within the module (e.g. "EntityNode.to_graph_node"); identity input
    symbol_kind: str                             # "function" | "class" | "method"
    path: str                                    # File path (provenance locator)
    content_hash: str = ""                        # Content hash over the file bytes (the symbol shares its module's source file)
    lineno: Optional[int] = None                 # 1-based start line (provenance; content, not identity)
    docstring: str = ""                          # Symbol docstring first line (the relevance/description hook)
    calls: List[str] = field(default_factory=list)  # Names this symbol references/calls (raw; resolved to CALLS edges via a corpus map)
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
