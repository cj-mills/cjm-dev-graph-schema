"""Fine-tier nodes: deterministic identity, wire shapes, and alias resolution."""

from cjm_dev_graph_schema.aliases import build_alias_index, resolve_subject_id
from cjm_dev_graph_schema.identity import (assertion_node_id, factslot_node_id)
from cjm_dev_graph_schema.nodes import (AssertionNode, DecisionNode, EntityNode,
                                        FactSlotNode, SessionNode)
from cjm_dev_graph_schema.vocab import DevNodeKinds, DevRelations


def test_factslot_identity_is_subject_predicate():
    s = factslot_node_id("subj-1", "version")
    fs = FactSlotNode(subject_id="subj-1", predicate="version")
    assert fs.id == s
    node = fs.to_graph_node()
    assert node["label"] == DevNodeKinds.FACT_SLOT
    assert node["properties"]["typed"] is True   # version is typed
    assert FactSlotNode("subj-1", "owner").to_graph_node()["properties"]["typed"] is False


def test_assertion_identity_is_slot_value_actor():
    fs = FactSlotNode("subj-1", "version")
    a = AssertionNode(slot_id=fs.id, value="v0.0.51", actor="human", predicate="version")
    # canonical strips the v-prefix -> id stable across "v0.0.51" / "0.0.51".
    assert a.id == assertion_node_id(fs.id, "0.0.51", "human")
    assert AssertionNode(fs.id, "0.0.51", "human", predicate="version").id == a.id
    # different value OR different actor -> different node (the potential conflict).
    assert AssertionNode(fs.id, "0.0.52", "human", predicate="version").id != a.id
    assert AssertionNode(fs.id, "0.0.51", "agent", predicate="version").id != a.id


def test_assertion_wire_and_edges():
    a = AssertionNode("slot-x", "keep", "human", predicate="rename-disposition", subject_id="e1")
    node = a.to_graph_node()
    assert node["label"] == DevNodeKinds.ASSERTION
    assert node["properties"]["canonical_value"] == "keep"
    assert node["properties"]["asserted_at"]  # auto-stamped
    assert a.on_slot_edge()["relation_type"] == DevRelations.ON_SLOT
    assert a.on_slot_edge()["target_id"] == "slot-x"
    ev = a.evidenced_by_edges(["note-1", "note-2"])
    assert len(ev) == 2 and all(e["relation_type"] == DevRelations.EVIDENCED_BY for e in ev)
    assert a.supersedes_edge("old")["relation_type"] == DevRelations.SUPERSEDES
    assert a.contradicts_edge("other")["relation_type"] == DevRelations.CONTRADICTS


def test_decision_and_session():
    d = DecisionNode(statement="rename torch/hf utils into the substrate family")
    assert d.to_graph_node()["label"] == DevNodeKinds.DECISION
    assert DecisionNode("rename  torch/hf  utils into the substrate family").id == d.id  # ws-normalized
    sup = d.supported_by_edges(["a1", "a2"])
    assert len(sup) == 2 and sup[0]["relation_type"] == DevRelations.SUPPORTED_BY
    assert d.decided_in_edge("sess")["relation_type"] == DevRelations.DECIDED_IN
    sn = SessionNode(key="2026-06-22", title="inc3 build")
    assert sn.to_graph_node()["label"] == DevNodeKinds.SESSION
    assert sn.to_graph_node()["properties"]["title"] == "inc3 build"


def test_entity_aliases_resolve_rename_stable():
    # The torch-utils entity: durable key, current name, prior name as alias.
    e = EntityNode(kind="repo", key="torch-utils", name="cjm-substrate-torch-utils",
                   aliases=["cjm-torch-plugin-utils"])
    node = e.to_graph_node()
    assert node["properties"]["key"] == "torch-utils"
    assert node["properties"]["aliases"] == ["cjm-torch-plugin-utils"]
    index = build_alias_index([node])
    # All of key / current name / OLD name resolve to the SAME entity (rename-stable).
    assert resolve_subject_id(index, "torch-utils") == e.id
    assert resolve_subject_id(index, "cjm-substrate-torch-utils") == e.id
    assert resolve_subject_id(index, "CJM-Torch-Plugin-Utils") == e.id  # case-insensitive
    assert resolve_subject_id(index, "nope") is None
