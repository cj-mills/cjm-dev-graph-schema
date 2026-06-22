"""EntityNode: deterministic (sub-kind, key) identity, wire-dict, DEPENDS_ON edges."""

from cjm_dev_graph_schema.identity import entity_node_id
from cjm_dev_graph_schema.nodes import EntityNode
from cjm_dev_graph_schema.vocab import DevNodeKinds, DevRelations


def test_id_from_kind_and_key():
    e = EntityNode(kind="repo", key="cjm-dev-graph-schema", name="cjm-dev-graph-schema")
    assert e.id == entity_node_id("repo", "cjm-dev-graph-schema")


def test_same_key_different_kind_differs():
    assert EntityNode("repo", "x", "X").id != EntityNode("stage", "x", "X").id


def test_to_graph_node_shape():
    e = EntityNode(kind="repo", key="cjm-foo", name="cjm-foo", properties={"tier": "active"})
    node = e.to_graph_node()
    assert node["label"] == DevNodeKinds.ENTITY
    assert node["properties"]["entity_kind"] == "repo"
    assert node["properties"]["key"] == "cjm-foo"
    assert node["properties"]["tier"] == "active"
    assert node["properties"]["root_kind"] == "asserted"
    assert node["sources"] == []


def test_depends_on_edges_target_same_kind_ids():
    e = EntityNode(kind="repo", key="cjm-markdown-decompose-core", name="…")
    edges = e.depends_on_edges(["cjm-dev-graph-schema", "cjm-context-graph-layer"])
    assert len(edges) == 2
    assert all(x["relation_type"] == DevRelations.DEPENDS_ON for x in edges)
    assert edges[0]["target_id"] == entity_node_id("repo", "cjm-dev-graph-schema")
    assert edges[0]["source_id"] == e.id
