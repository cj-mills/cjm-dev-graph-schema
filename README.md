# cjm-dev-graph-schema

<!-- generated from the context graph by `cjm-context-graph readme` — do not edit by hand; edit the graph (the urge to hand-edit = move it on-graph) -->

Development/decision-provenance schema for context graphs: Decision, Fact-slot/Assertion, Evidence, Thread, Session, Procedure, and Entity node kinds with deterministic identity and overlay/reasoning edges — the dev-domain sibling to cjm-transcript-graph-schema for graphing a project's own evolution.

## Modules

- **`cjm_dev_graph_schema.__init__`**
- **`cjm_dev_graph_schema.aliases`** — Rename-stable subject resolution (the A+aliases identity machinery).
- **`cjm_dev_graph_schema.identity`** — Deterministic node-id helpers for the dev/decision-provenance domain.
- **`cjm_dev_graph_schema.nodes`** — Typed node dataclasses for the dev schema (coarse + fine tier).
- **`cjm_dev_graph_schema.predicates`** — Typed predicates + their value-space metadata (the dedup decidability layer).
- **`cjm_dev_graph_schema.vocab`** — The reserved node-kind and edge-relation vocabulary for the dev/decision-provenance domain.

## API

### `cjm_dev_graph_schema.aliases`

- `build_alias_index` _function_ — Index every entity by its key, current name, and each alias.
- `resolve_subject_id` _function_ — Resolve a subject name to its entity id via the alias index (no guessing).

### `cjm_dev_graph_schema.identity`

- `assertion_node_id` _function_ — Assertion identity = (slot, canonical value, actor).
- `cell_node_id` _function_ — Cell identity = (notebook module, stable cell key).
- `check_node_id` _function_ — Check identity = (its work item, canonical text) — the same wording on two
- `code_module_node_id` _function_ — Code-module identity = (repo_key, module_path).
- `code_symbol_node_id` _function_ — Code-symbol identity = (module at birth, qualified name at birth[, generation]).
- `code_text_node_id` _function_ — Code-text-region identity = (module, region key).
- `decision_node_id` _function_ — Decision identity = its canonical statement (idempotent re-records).
- `deliverable_type_node_id` _function_ — Deliverable-type identity = its slug, so re-minting the profile UPSERTS one node
- `entity_node_id` _function_ — Entity identity = (sub-kind, stable key).
- `factslot_node_id` _function_ — Fact-slot identity = (subject, predicate).
- `message_node_id` _function_ — Message identity = its capture-source record uuid.
- `note_node_id` _function_ — Note identity = its stable slug.
- `point_node_id` _function_ — Point identity = (owner, point key) — never its text, kind, or position.
- `point_set_node_id` _function_ — PointSet identity = (sibling graph key, Source id, unit key) — the source unit whose
- `reference_node_id` _function_ — Reference identity = (sibling graph key, foreign node id).
- `section_node_id` _function_ — Section identity = (enclosing Note, heading anchor slug).
- `series_node_id` _function_ — Series identity = its stable key.
- `session_node_id` _function_ — Session identity = its stable key (so DECIDED_IN/PRODUCED_IN converge).
- `topic_node_id` _function_ — Topic identity = its normalized name slug.

### `cjm_dev_graph_schema.nodes`

- `AssertionNode` _class_ — One value claimed for a Fact-slot — identified by WHAT is claimed.
- `CellNode` _class_ — One VERBATIM notebook cell — the lossless source substrate of a notebook module.
- `CheckNode` _class_ — A definition-of-done check on a work item — a derivable gate, not prose.
- `CodeModuleNode` _class_ — The code source-type's coarse node: one decomposed `.py` module.
- `CodeSymbolNode` _class_ — A definition within a module: a function, class, or method.
- `CodeTextNode` _class_ — A non-def top-level region of a plain-`.py` module — the verbatim substrate BETWEEN symbols.
- `DecisionNode` _class_ — A decision/conclusion, with rationale recorded as edges, not prose.
- `DeliverableTypeNode` _class_ — A deliverable TYPE's profile as graph DATA (ruling a7262fe7 (1)) — the display-rule
- `EntityNode` _class_ — A first-class subject: a repo/lib, stage, capability, person, or term.
- `FactSlotNode` _class_ — A `(subject, predicate)` slot — the home for layered, supersede-able claims.
- `MessageNode` _class_ — A discourse EVENT on a session spine (DEC 91c47b4a): one user-facing message.
- `NoteNode` _class_ — The coarse-tier document node: one decomposed markdown/memory file.
- `PointNode` _class_ — A typed deliverable's SUBSTANCE atom (ruling a7262fe7): the smallest statement
- `PointSetNode` _class_ — A Source unit's POINT STORE (ruling 96be1528 (P)): the node that OWNS the substance
- `ReferenceNode` _class_ — A LOCAL stand-in for a node in a sibling graph — the cross-graph reference (0154f5e4).
- `SectionNode` _class_ — One heading-delimited section of a Note's body — the navigable unit + anchor target.
- `SeriesNode` _class_ — An ordered collection/progression a note belongs to (a Quarto series, …).
- `SessionNode` _class_ — A working session — the home decisions/facts are PRODUCED_IN / DECIDED_IN.
- `TopicNode` _class_ — A category/tag facet — a thematic-clustering subject shared across notes.
- `foreign_content_hash` _function_ — The content a Reference OBSERVES: the foreign node's label + its properties, canonically
- `foreign_display_title` _function_ — Best-effort display handle for a foreign node: title/name/text-ish fields first,
- `judged_edge` _function_ — One judgment of the JUDGED family (design ae698640 (5), generalizing eefda2dd (3)'s facet
- `judged_related_edge` _function_ — One judged related-post pair (design e09e262b). The pair is ORDERED -- relatedness is
- `lineage_edge` _function_ — One step of an artifact's LINEAGE (design ae698640 (1)): the ONNX export from the checkpoint,
- `parse_foreign_ref` _function_ — Split a `<graph key>:<id>` reference token; None for a plain local id / anything else.
- `placed_edge` _function_ — The deliverable's PER-POINT OVERLAY on a point it renders (ruling 96be1528 (3)/(7)).
- `record_part_of_edge` _function_ — A PART_OF landed by an Entity record (design ae698640 (3) / (4)): a concept under its
- `relation_edge` _function_ — One path-model relation with its per-pair data (design ae698640 (5)). A pair holds one edge
- `series_member_edge` _function_ — One series membership with its AUTHORED position (DEC 72d669c5 (4)).
- `site_link_edge` _function_ — An in-body site link, RESOLVED (DEC 72d669c5 (1)): the post-replay resolve pass mints
- `supports_edge` _function_ — One support of a claim with its kind (design de808eae (1), amendment 98e99fe5 (2)).
- `unit_part_of_edge` _function_ — A unit's membership in its work (design leg 4a4ef27e (2)), landed by the `entity` op
- `verified_on_edge` _function_ — One verification with its evidence (design 8cbdc883 (7), amendment c450133a (2)).
- `work_member_edge` _function_ — A metabolized source's place in its work (design 5de7fae9 (4), design leg 4a4ef27e (2)):
- `work_provenance_edge` _function_ — An archive deliverable's provenance (design 5de7fae9 (3), design leg 4a4ef27e (2)): ONE

### `cjm_dev_graph_schema.predicates`

- `Predicate` _class_ — A typed predicate's value-space (the contradiction decidability metadata).
- `active_contradiction` _function_ — Whether a slot's ACTIVE (non-superseded) values form a hard contradiction.
- `canonical_value` _function_ — Canonicalize a value so equal claims collapse to one Assertion.
- `citation_parts` _function_ — The inverse of `citation_value`; a malformed value reads as no parts.
- `citation_value` _function_ — A citation's parts as the fact's value -- sorted keys, compact separators, blanks dropped;
- `get_predicate` _function_ — Look up a predicate's value-space; exact entry first, then a prefix FAMILY
- `is_approval` _function_ — Whether an assertion is approval-class (`APPROVAL_CLASS` — schema data, design 40622922).
- `is_multivalued` _function_ — Whether the predicate is a SET slot (distinct values coexist, never conflict).
- `is_ordered` _function_ — Whether the predicate's values have a "later supersedes earlier" ordering.
- `is_terminal` _function_ — Whether `value` is a TERMINAL side-state of an ordered enum (item 140981e9): off the
- `is_typed` _function_ — Whether the predicate carries a value-space (exact entry OR prefix family).
- `ordering_supersedes` _function_ — For an ordered predicate, does `new_value` supersede `old_value`?
- `resources_links` _function_ — The inverse of `resources_value`; a malformed value reads as no links.
- `resources_value` _function_ — A source's links as the fact's value -- each link's fields sorted, the links in role then
- `soft_conflict` _function_ — Whether an UNTYPED slot's active values disagree (a worklist candidate).
- `traffic_of` _function_ — The inverse of `traffic_value`; a malformed value reads as no measure.
- `traffic_value` _function_ — A traffic measure as the fact's value -- sorted keys, compact separators. Refuses a missing
- `transition_matches` _function_ — Does a step match a stage's transition (ae698640 (2))? Its outputs include the transition's
- `values_conflict` _function_ — Whether two values are a HARD contradiction under the value-space.
- `version_key` _function_ — A component version's ordering key for staleness: its runs of digits and letters in order,
- `versions_of` _function_ — The inverse of `versions_value`; a malformed value reads as no versions.
- `versions_value` _function_ — An environment's versions as the fact's value -- sorted keys, compact separators, blanks

### `cjm_dev_graph_schema.vocab`

- `DevNodeKinds` _class_ — Node labels of the dev/decision-provenance schema (the locked model).
- `DevRelations` _class_ — Dev-domain edge relations (reserved up front).

## Dependencies

**Depends on:** `cjm-context-graph-layer`, `cjm-context-graph-primitives`
**Used by:** `cjm-context-graph-projection`, `cjm-markdown-decompose-core`, `cjm-notebook-decompose-core`, `cjm-python-decompose-core`
