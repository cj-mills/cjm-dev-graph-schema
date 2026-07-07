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
- **`tests.test_code_nodes`** — Code source-type nodes: deterministic identity, wire shapes, and edges.
- **`tests.test_entity`** — EntityNode: deterministic (sub-kind, key) identity, wire-dict, DEPENDS_ON edges.
- **`tests.test_fine_nodes`** — Fine-tier nodes: deterministic identity, wire shapes, and alias resolution.
- **`tests.test_nodes`** — Coarse-tier NoteNode: deterministic identity, wire-dict mapping, REFERENCES edges.
- **`tests.test_predicates`** — Predicate value-space: canonicalization, ordering, and conflict decisions.

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
- `get_predicate` _function_ — Look up a predicate's value-space; None = an untyped freetext predicate.
- `is_multivalued` _function_ — Whether the predicate is a SET slot (distinct values coexist, never conflict).
- `is_ordered` _function_ — Whether the predicate's values have a "later supersedes earlier" ordering.
- `is_typed` _function_ — Whether the predicate is in the typed registry.
- `ordering_supersedes` _function_ — For an ordered predicate, does `new_value` supersede `old_value`?
- `soft_conflict` _function_ — Whether an UNTYPED slot's active values disagree (a worklist candidate).
- `values_conflict` _function_ — Whether two values are a HARD contradiction under the value-space.

### `cjm_dev_graph_schema.vocab`

- `DevNodeKinds` _class_ — Node labels of the dev/decision-provenance schema (the locked model).
- `DevRelations` _class_ — Dev-domain edge relations (reserved up front).

### `tests.test_code_nodes`

- `test_cell_contains_next_documents_references_edges` _function_
- `test_cell_identity_prefers_nbformat_id_else_index` _function_
- `test_cell_wire_is_verbatim_and_typed` _function_
- `test_codetext_region_identity_and_wire` _function_
- `test_module_about_targets_repo_entity` _function_
- `test_module_contains_edges_order_regions` _function_
- `test_module_defines_and_imports_edges` _function_
- `test_module_identity_is_repokey_path` _function_
- `test_module_wire_carries_relevance_fields_and_source` _function_
- `test_nested_defines` _function_
- `test_nested_symbol_has_no_body_props` _function_
- `test_symbol_identity_is_module_qualname` _function_
- `test_symbol_uses_edges_superset_dedups_and_skips_self` _function_
- `test_symbol_wire_and_call_edges` _function_
- `test_symbol_without_content_hash_has_no_source` _function_
- `test_top_level_symbol_carries_verbatim_body_and_order` _function_

### `tests.test_entity`

- `test_depends_on_edges_target_same_kind_ids` _function_
- `test_id_from_kind_and_key` _function_
- `test_same_key_different_kind_differs` _function_
- `test_to_graph_node_shape` _function_

### `tests.test_fine_nodes`

- `test_assertion_identity_is_slot_value_actor` _function_
- `test_assertion_wire_and_edges` _function_
- `test_decision_and_session` _function_
- `test_entity_aliases_resolve_rename_stable` _function_
- `test_factslot_identity_is_subject_predicate` _function_

### `tests.test_nodes`

- `test_cross_post_alias_resolution` _function_
- `test_cross_post_edges_anchor_resolves_to_section_id` _function_
- `test_facets_stored_on_node_when_present` _function_
- `test_id_changes_with_slug` _function_
- `test_id_is_deterministic_from_slug` _function_
- `test_no_references_no_edges` _function_
- `test_optional_fields_omitted_when_empty` _function_
- `test_reference_edges_target_linked_note_ids` _function_
- `test_section_identity_and_anchor_resolution_by_construction` _function_
- `test_section_node_shape_carries_verbatim_text` _function_
- `test_section_structural_edges_membership_and_hierarchy` _function_
- `test_series_edges_membership` _function_
- `test_series_node_shape_and_identity` _function_
- `test_tagged_edges_target_shared_topic_ids` _function_
- `test_to_graph_node_shape` _function_
- `test_topic_node_shape_and_identity` _function_

### `tests.test_predicates`

- `test_active_contradiction_and_soft_conflict` _function_
- `test_aka_distinct_values_never_conflict` _function_
- `test_aka_is_multivalued_slug_set` _function_
- `test_canonical_value_enum_lowercases` _function_
- `test_canonical_value_semver_strips_v_prefix` _function_
- `test_canonical_value_untyped_preserves_case` _function_
- `test_ordering_supersedes_semver` _function_
- `test_ordering_supersedes_task_state_enum` _function_
- `test_rename_disposition_is_unordered_enum` _function_
- `test_typed_predicate_registry` _function_
- `test_values_conflict_only_typed_unordered` _function_
- `test_version_is_ordered_semver` _function_

## Dependencies

**Used by:** `cjm-context-graph-projection`, `cjm-markdown-decompose-core`, `cjm-notebook-decompose-core`, `cjm-python-decompose-core`
