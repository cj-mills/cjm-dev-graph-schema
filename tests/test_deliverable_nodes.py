"""Deliverable-type substance nodes (ruling a7262fe7): Point identity is (note, opaque key) —
never text / kind / position — and the DeliverableType profile upserts by slug."""

from cjm_dev_graph_schema.identity import (deliverable_type_node_id, note_node_id,
                                           point_node_id)
from cjm_dev_graph_schema.nodes import (DeliverableTypeNode, POINT_KIND_GLOSSES, PointNode,
                                        RECOMMENDED_POINT_KINDS)
from cjm_dev_graph_schema.predicates import (DELIVERABLE_TYPE, active_contradiction,
                                             canonical_value, is_typed, values_conflict)
from cjm_dev_graph_schema.vocab import DevNodeKinds, DevRelations


def test_point_identity_is_note_and_key_never_content():
    nid = note_node_id("the-learning-game/ch01")
    a = PointNode(note_id=nid, key="p-1", kind="claim", text="School teaches confusion.", ordinal=3)
    assert a.id == point_node_id(nid, "p-1")
    # re-render / re-order / a text edit / a re-kind keep the node
    assert PointNode(nid, "p-1", "definition", "Different text.", ordinal=9).id == a.id
    # a different key, or the same key on another deliverable, is another point
    assert PointNode(nid, "p-2", "claim", a.text).id != a.id
    assert PointNode(note_node_id("other"), "p-1", "claim", a.text).id != a.id


def test_point_wire_and_edges():
    nid = note_node_id("post")
    p = PointNode(note_id=nid, key="k", kind="quotation", text="I teach confusion.", ordinal=1,
                  lead="Gatto", heading="Lesson 1. Confusion", heading_index=1,
                  segment_ids=["s1", "s2"], start_time=138.0, end_time=183.3,
                  attribution="John Taylor Gatto", data={}, unit={"source_id": "src", "chapter": 1})
    w = p.to_graph_node()
    assert w["label"] == DevNodeKinds.POINT and w["properties"]["root_kind"] == "derived"
    assert w["properties"]["segment_ids"] == ["s1", "s2"] and w["properties"]["heading_index"] == 1
    assert w["properties"]["attribution"] == "John Taylor Gatto" and "data" not in w["properties"]
    assert w["properties"]["title"].startswith("quotation: Gatto — I teach")
    e = p.has_point_edge()
    assert e["source_id"] == nid and e["target_id"] == p.id and e["relation_type"] == DevRelations.HAS_POINT
    d = p.derived_from_edges(["r1", "r2"])
    assert [x["target_id"] for x in d] == ["r1", "r2"]
    assert all(x["relation_type"] == DevRelations.DERIVED_FROM for x in d)
    assert [x["properties"]["order"] for x in d] == [0, 1]


def test_deliverable_type_upserts_by_slug_and_kind_slate_is_glossed():
    t = DeliverableTypeNode(key="pure-notes", title="Pure notes",
                            information_policy={"exclude_strata": ["tangent"]},
                            presentation_policy={"kinds": dict(POINT_KIND_GLOSSES)},
                            production_procedure=["pack", "propose", "accept", "render"])
    assert t.id == deliverable_type_node_id("pure-notes")
    assert DeliverableTypeNode(key="pure-notes", title="renamed").id == t.id   # upsert identity
    w = t.to_graph_node()
    assert w["label"] == DevNodeKinds.DELIVERABLE_TYPE
    assert w["properties"]["information_policy"]["exclude_strata"] == ["tangent"]
    assert w["properties"]["production_procedure"][-1] == "render"
    assert set(RECOMMENDED_POINT_KINDS) == set(POINT_KIND_GLOSSES)
    assert "quotation" in RECOMMENDED_POINT_KINDS and "comparison" in RECOMMENDED_POINT_KINDS
    assert DevNodeKinds.POINT in DevNodeKinds.all() and DevNodeKinds.DELIVERABLE_TYPE in DevNodeKinds.all()
    assert DevRelations.HAS_POINT in DevRelations.all()


def test_deliverable_type_predicate_is_a_stable_slug_and_hard_conflicts():
    assert is_typed(DELIVERABLE_TYPE)
    assert canonical_value(DELIVERABLE_TYPE, " Pure-Notes ") == "pure-notes"
    assert values_conflict(DELIVERABLE_TYPE, "pure-notes", "research-report")
    assert not values_conflict(DELIVERABLE_TYPE, "pure-notes", "Pure-Notes")
    assert active_contradiction(DELIVERABLE_TYPE, ["pure-notes", "essay"])
