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
- `code_symbol_node_id` _function_ — Code-symbol identity = (enclosing module, qualified name).
- `code_text_node_id` _function_ — Code-text-region identity = (module, region key).
- `decision_node_id` _function_ — Decision identity = its canonical statement (idempotent re-records).
- `entity_node_id` _function_ — Entity identity = (sub-kind, stable key).
- `factslot_node_id` _function_ — Fact-slot identity = (subject, predicate).
- `note_node_id` _function_ — Note identity = its stable slug.
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
- `EntityNode` _class_ — A first-class subject: a repo/lib, stage, capability, person, or term.
- `FactSlotNode` _class_ — A `(subject, predicate)` slot — the home for layered, supersede-able claims.
- `NoteNode` _class_ — The coarse-tier document node: one decomposed markdown/memory file.
- `SectionNode` _class_ — One heading-delimited section of a Note's body — the navigable unit + anchor target.
- `SeriesNode` _class_ — An ordered collection/progression a note belongs to (a Quarto series, …).
- `SessionNode` _class_ — A working session — the home decisions/facts are PRODUCED_IN / DECIDED_IN.
- `TopicNode` _class_ — A category/tag facet — a thematic-clustering subject shared across notes.

### `cjm_dev_graph_schema.predicates`

- `Predicate` _class_ — A typed predicate's value-space (the contradiction decidability metadata).
- `active_contradiction` _function_ — Whether a slot's ACTIVE (non-superseded) values form a hard contradiction.
- `canonical_value` _function_ — Canonicalize a value so equal claims collapse to one Assertion.
- `get_predicate` _function_ — Look up a predicate's value-space; exact entry first, then a prefix FAMILY
- `is_multivalued` _function_ — Whether the predicate is a SET slot (distinct values coexist, never conflict).
- `is_ordered` _function_ — Whether the predicate's values have a "later supersedes earlier" ordering.
- `is_typed` _function_ — Whether the predicate carries a value-space (exact entry OR prefix family).
- `ordering_supersedes` _function_ — For an ordered predicate, does `new_value` supersede `old_value`?
- `soft_conflict` _function_ — Whether an UNTYPED slot's active values disagree (a worklist candidate).
- `values_conflict` _function_ — Whether two values are a HARD contradiction under the value-space.

### `cjm_dev_graph_schema.vocab`

- `DevNodeKinds` _class_ — Node labels of the dev/decision-provenance schema (the locked model).
- `DevRelations` _class_ — Dev-domain edge relations (reserved up front).

## Dependencies

**Depends on:** `cjm-context-graph-layer`, `cjm-context-graph-primitives`
**Used by:** `cjm-context-graph-projection`, `cjm-markdown-decompose-core`, `cjm-notebook-decompose-core`, `cjm-python-decompose-core`
