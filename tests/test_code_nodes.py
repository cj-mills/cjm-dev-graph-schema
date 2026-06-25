"""Code source-type nodes: deterministic identity, wire shapes, and edges.

The code nodes (`CodeModuleNode`/`CodeSymbolNode`) co-reside with the markdown
`NoteNode` on one graph (same SourceRef provenance) and are first-class
addressable subjects with rename-/cross-graph-stable ids.
"""

from cjm_dev_graph_schema.identity import (cell_node_id, code_module_node_id,
                                           code_symbol_node_id, code_text_node_id,
                                           entity_node_id)
from cjm_dev_graph_schema.nodes import (CellNode, CodeModuleNode, CodeSymbolNode,
                                        CodeTextNode)
from cjm_dev_graph_schema.vocab import DevNodeKinds, DevRelations


def _mod():
    return CodeModuleNode(
        repo_key="cjm-dev-graph-schema",
        module_path="cjm_dev_graph_schema/nodes.py",
        path="/abs/cjm-dev-graph-schema/cjm_dev_graph_schema/nodes.py",
        content_hash="sha256:deadbeef",
        import_name="cjm_dev_graph_schema.nodes",
        docstring="Typed node dataclasses for the dev schema.",
        imports=["cjm_dev_graph_schema.identity", "os"],
    )


def test_module_identity_is_repokey_path():
    m = _mod()
    assert m.id == code_module_node_id("cjm-dev-graph-schema", "cjm_dev_graph_schema/nodes.py")
    # Identity is the DURABLE repo key + repo-relative path, NOT the abs path.
    moved = CodeModuleNode(repo_key="cjm-dev-graph-schema",
                           module_path="cjm_dev_graph_schema/nodes.py",
                           path="/somewhere/else/nodes.py", content_hash="sha256:cafe")
    assert moved.id == m.id  # the file moving does not change identity
    # A different repo decomposing a same-named path is a DIFFERENT node.
    assert CodeModuleNode(repo_key="other-repo",
                          module_path="cjm_dev_graph_schema/nodes.py",
                          path="/x", content_hash="h").id != m.id


def test_module_wire_carries_relevance_fields_and_source():
    node = _mod().to_graph_node()
    assert node["label"] == DevNodeKinds.CODE_MODULE
    p = node["properties"]
    # name + title + description are the relevance/title hooks the projection reads.
    assert p["name"] == "cjm_dev_graph_schema.nodes"
    assert p["title"] == "cjm_dev_graph_schema/nodes.py"
    assert p["description"] == "Typed node dataclasses for the dev schema."
    assert p["root_kind"] == "asserted"
    assert len(node["sources"]) == 1  # FileRef + content-hash provenance, like NoteNode


def test_module_about_targets_repo_entity():
    m = _mod()
    e = m.about_edge()
    assert e["relation_type"] == DevRelations.ABOUT
    # The cross-link into the decision/note neighborhood: targets the repo Entity id.
    assert e["target_id"] == entity_node_id("repo", "cjm-dev-graph-schema")


def test_module_defines_and_imports_edges():
    m = _mod()
    defs = m.defines_edges(["sym-1", "sym-2"])
    assert len(defs) == 2 and all(e["relation_type"] == DevRelations.DEFINES for e in defs)
    assert all(e["source_id"] == m.id for e in defs)
    # IMPORTS only mint for modules present in the corpus map (external/stdlib skipped).
    imp = m.import_edges({"cjm_dev_graph_schema.identity": "MOD-IDENTITY"})
    assert len(imp) == 1
    assert imp[0]["relation_type"] == DevRelations.IMPORTS
    assert imp[0]["target_id"] == "MOD-IDENTITY"


def test_symbol_identity_is_module_qualname():
    m = _mod()
    s = CodeSymbolNode(module_id=m.id, qualname="EntityNode.to_graph_node",
                       symbol_kind="method", path="/x", lineno=56)
    assert s.id == code_symbol_node_id(m.id, "EntityNode.to_graph_node")
    # qualname carries nesting, so a method and a same-named free function differ.
    assert CodeSymbolNode(m.id, "to_graph_node", "function", "/x").id != s.id
    # lineno is content, not identity.
    assert CodeSymbolNode(m.id, "EntityNode.to_graph_node", "method", "/x", lineno=999).id == s.id


def test_symbol_wire_and_call_edges():
    m = _mod()
    s = CodeSymbolNode(module_id=m.id, qualname="reference_edges", symbol_kind="function",
                       path="/x", content_hash="sha256:beef", docstring="One REFERENCES edge per link.",
                       calls=["make_edge", "note_node_id", "some_external"])
    node = s.to_graph_node()
    assert node["label"] == DevNodeKinds.CODE_SYMBOL
    assert node["properties"]["name"] == "reference_edges"
    assert node["properties"]["description"] == "One REFERENCES edge per link."
    assert node["properties"]["symbol_kind"] == "function"
    assert len(node["sources"]) == 1  # has a content hash -> carries provenance
    # CALLS resolves only names present in the corpus map.
    calls = s.calls_edges({"make_edge": "SYM-MAKEEDGE", "note_node_id": "SYM-NOTEID"})
    assert len(calls) == 2 and all(e["relation_type"] == DevRelations.CALLS for e in calls)
    targets = {e["target_id"] for e in calls}
    assert targets == {"SYM-MAKEEDGE", "SYM-NOTEID"}


def test_symbol_uses_edges_superset_dedups_and_skips_self():
    m = _mod()
    s = CodeSymbolNode(module_id=m.id, qualname="Widget", symbol_kind="class",
                       path="/x", content_hash="sha256:beef",
                       refs=["Base", "MyType", "MyType", "Widget", "external"])  # dup + self + unresolved
    node = s.to_graph_node()
    assert node["properties"]["refs"] == ["Base", "MyType", "MyType", "Widget", "external"]
    uses = s.uses_edges({"Base": "SYM-BASE", "MyType": "SYM-MYTYPE", "Widget": s.id})
    assert all(e["relation_type"] == DevRelations.USES for e in uses)
    targets = {e["target_id"] for e in uses}
    assert targets == {"SYM-BASE", "SYM-MYTYPE"}        # dedup'd; self ("Widget"->s.id) skipped


def test_symbol_without_content_hash_has_no_source():
    s = CodeSymbolNode(module_id="m", qualname="f", symbol_kind="function", path="/x")
    assert s.to_graph_node()["sources"] == []


def test_nested_defines():
    m = _mod()
    cls = CodeSymbolNode(module_id=m.id, qualname="EntityNode", symbol_kind="class", path="/x")
    method = CodeSymbolNode(module_id=m.id, qualname="EntityNode.id", symbol_kind="method", path="/x")
    edges = cls.defines_edges([method.id])
    assert len(edges) == 1
    assert edges[0]["source_id"] == cls.id and edges[0]["target_id"] == method.id
    assert edges[0]["relation_type"] == DevRelations.DEFINES


# --- Cell nodes (notebook = CodeModule + verbatim cell substrate) ---

def _nb_mod():
    return CodeModuleNode(repo_key="cjm-foo", module_path="cjm_foo/core.py",
                          path="/abs/nbs/00_core.ipynb", content_hash="sha256:nb")


def test_cell_identity_prefers_nbformat_id_else_index():
    m = _nb_mod()
    c = CellNode(module_id=m.id, cell_key="abc123", cell_type="code", source="x=1\n",
                 content_hash="sha256:c", index=0)
    assert c.id == cell_node_id(m.id, "abc123")
    # the nbformat id is identity; the positional index is not.
    moved = CellNode(m.id, "abc123", "code", "x=1\n", "sha256:c", index=5)
    assert moved.id == c.id


def test_cell_wire_is_verbatim_and_typed():
    m = _nb_mod()
    c = CellNode(module_id=m.id, cell_key="0", cell_type="code", source="def f():\n    return 1\n",
                 content_hash="sha256:c", index=0, path="/abs/nbs/00_core.ipynb",
                 directives=["export"])
    node = c.to_graph_node()
    assert node["label"] == DevNodeKinds.CELL
    assert node["properties"]["source"] == "def f():\n    return 1\n"  # VERBATIM, lossless
    assert node["properties"]["cell_type"] == "code"
    assert node["properties"]["directives"] == ["export"]
    assert len(node["sources"]) == 1  # FileRef + content-hash provenance to the .ipynb


def test_cell_contains_next_documents_references_edges():
    m = _nb_mod()
    md = CellNode(m.id, "c0", "markdown", "# Heading\nSee [[some-note]].", "sha256:0", index=0,
                  title="Heading")
    code = CellNode(m.id, "c1", "code", "def f(): ...", "sha256:1", index=1)
    assert md.contains_edge()["relation_type"] == DevRelations.CONTAINS
    assert md.contains_edge()["source_id"] == m.id and md.contains_edge()["target_id"] == md.id
    nxt = md.next_edge(code.id)
    assert nxt["target_id"] == code.id and nxt["relation_type"] == "NEXT"  # the layer's spine relation
    docs = md.documents_edges(["sym-1", "sym-2"])
    assert len(docs) == 2 and all(e["relation_type"] == DevRelations.DOCUMENTS for e in docs)
    refs = md.reference_edges(["some-note"])
    assert len(refs) == 1 and refs[0]["relation_type"] == DevRelations.REFERENCES


# --- authoring substrate: verbatim symbol body + CodeText regions + CONTAINS ---

def test_top_level_symbol_carries_verbatim_body_and_order():
    m = _mod()
    s = CodeSymbolNode(module_id=m.id, qualname="alpha", symbol_kind="function", path="/x",
                       content_hash="sha256:beef", body="def alpha():\n    return 1",
                       body_hash="sha256:body", order_index=2)
    p = s.to_graph_node()["properties"]
    assert p["body"] == "def alpha():\n    return 1"
    assert p["body_hash"] == "sha256:body" and p["order_index"] == 2


def test_nested_symbol_has_no_body_props():
    m = _mod()
    method = CodeSymbolNode(module_id=m.id, qualname="Thing.method", symbol_kind="method", path="/x")
    p = method.to_graph_node()["properties"]
    assert "body" not in p and "order_index" not in p  # nested = overlay only (coarse v1)


def test_codetext_region_identity_and_wire():
    m = _mod()
    t = CodeTextNode(module_id=m.id, region_key="import os", text="import os\nimport sys",
                     content_hash="sha256:t", order_index=0, path="/x", kind="imports")
    assert t.id == code_text_node_id(m.id, "import os")
    node = t.to_graph_node()
    assert node["label"] == DevNodeKinds.CODE_TEXT
    assert node["properties"]["text"] == "import os\nimport sys"
    assert node["properties"]["order_index"] == 0 and node["properties"]["kind"] == "imports"
    assert len(node["sources"]) == 1  # verbatim region carries content-hash provenance
    # identity = (module, region key); a different lead line is a different region.
    assert CodeTextNode(m.id, "import sys", "x", "sha256:y").id != t.id


def test_module_contains_edges_order_regions():
    m = _mod()
    edges = m.contains_edges(["R0", "R1", "R2"])
    assert [e["target_id"] for e in edges] == ["R0", "R1", "R2"]
    assert all(e["source_id"] == m.id and e["relation_type"] == DevRelations.CONTAINS for e in edges)
