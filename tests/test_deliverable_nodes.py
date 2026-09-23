"""Deliverable-type substance nodes (ruling a7262fe7): Point identity is (OWNER, opaque key) —
never text / kind / position — where the owner is the source unit's PointSet for a substance
point and the deliverable for its own section / research points (ruling 96be1528 (P)); the
deliverable's per-point overlay rides the PLACED edge; the DeliverableType profile upserts by slug."""

from cjm_dev_graph_schema.identity import (deliverable_type_node_id, note_node_id,
                                           point_node_id, point_set_node_id, reference_node_id)
from cjm_dev_graph_schema.nodes import (DeliverableTypeNode, POINT_KIND_GLOSSES, PointNode,
                                        PointSetNode, RECOMMENDED_POINT_KINDS, ReferenceNode,
                                        placed_edge)
from cjm_dev_graph_schema.predicates import (DELIVERABLE_TYPE, POINT_ROLE, POINT_ROLES,
                                             active_contradiction, canonical_value, is_ordered,
                                             is_typed, values_conflict)
from cjm_dev_graph_schema.vocab import DevNodeKinds, DevRelations


def test_point_identity_is_owner_and_key_never_content():
    """Ruling 96be1528 (P): a point is keyed on its OWNER — the PointSet of its source unit
    for a substance point, the deliverable Note for the deliverable's own — and its key."""
    owner = point_set_node_id("transcription", "src-1", "")
    a = PointNode(owner_id=owner, key="p-1", kind="claim", text="School teaches confusion.", ordinal=3)
    assert a.id == point_node_id(owner, "p-1")
    # re-render / re-order / a text edit / a re-kind keep the node
    assert PointNode(owner, "p-1", "definition", "Different text.", ordinal=9).id == a.id
    # a different key, or the same key under another owner, is another point
    assert PointNode(owner, "p-2", "claim", a.text).id != a.id
    assert PointNode(note_node_id("other"), "p-1", "claim", a.text).id != a.id
    # a re-home (note -> set) changes the id and nothing else: every cross-point field names a KEY
    homed = PointNode(note_node_id("post"), "p-1", "claim", a.text, parent_key="p-0", refers_to=["p-9"])
    assert homed.id != a.id and homed.parent_key == "p-0" and homed.refers_to == ["p-9"]
    # the wire carries the OWNER and nothing else names it (the transitional `note_id` of 14cafef6 is gone:
    # the projection reads `owner_id` — the re-home build of 81d6e669)
    w = a.to_graph_node()["properties"]
    assert w["owner_id"] == owner and "note_id" not in w
    assert a.has_point_edge()["source_id"] == owner


def test_point_wire_and_edges():
    nid = note_node_id("post")
    p = PointNode(owner_id=nid, key="k", kind="quotation", text="I teach confusion.", ordinal=1,
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
    assert p.elaborates_edge() is None and p.parent_id == "" and "parent_key" not in w["properties"]
    # ruling 1798a796: the fold's provenance and the overlap judgements ride the point (absent when empty)
    assert "origins" not in w["properties"] and "judged" not in w["properties"]
    q = PointNode(owner_id=nid, key="k2", kind="claim", text="x", origins=[{"cell": "blind/opus", "how": "shown"}],
                  judged=[{"key": "k", "verdict": "different"}])
    assert q.to_graph_node()["properties"]["origins"] == [{"cell": "blind/opus", "how": "shown"}]
    assert q.to_graph_node()["properties"]["judged"] == [{"key": "k", "verdict": "different"}]
    assert q.id == PointNode(nid, "k2", "claim", "x").id                                    # neither is identity


def test_point_one_level_nesting_rides_parent_key_and_elaborates():
    """Ruling e1fd4d64 (H): a child Point names its parent by KEY (same owner); the
    ELABORATES edge is child -> parent, deterministic; identity ignores the parent."""
    nid = note_node_id("post")
    parent = PointNode(owner_id=nid, key="k-parent", kind="claim", text="Confusion.", ordinal=1)
    child = PointNode(owner_id=nid, key="k-child", kind="example", text="Trig without a house.",
                      ordinal=2, parent_key="k-parent")
    assert child.parent_id == parent.id
    assert child.to_graph_node()["properties"]["parent_key"] == "k-parent"
    e = child.elaborates_edge()
    assert e["source_id"] == child.id and e["target_id"] == parent.id and e["relation_type"] == DevRelations.ELABORATES
    assert PointNode(nid, "k-child", "example", "x", parent_key="").id == child.id   # re-parenting keeps the node
    assert DevRelations.ELABORATES in DevRelations.all()


def test_point_set_owns_the_source_units_points_and_a_note_renders_it():
    """Ruling 96be1528 (P): PointSet identity = (graph, Source, unit); a deliverable RENDERS
    from it; the same address converges on one node whatever the title."""
    s = PointSetNode(graph="transcription", source_id="src-1", unit="ch01", title="Chapter 1",
                     unit_address={"source_id": "src-1", "unit": "ch01", "chapter": 1})
    assert s.id == point_set_node_id("transcription", "src-1", "ch01")
    assert PointSetNode("transcription", "src-1", "ch01", title="renamed").id == s.id
    assert PointSetNode("transcription", "src-1").id != s.id            # the whole source is another unit
    assert PointSetNode("transcription", "src-1").unit == ""
    w = s.to_graph_node()
    assert w["label"] == DevNodeKinds.POINT_SET and w["properties"]["root_kind"] == "derived"
    assert w["properties"]["unit_address"]["chapter"] == 1 and w["properties"]["title"] == "points: Chapter 1"
    nid = note_node_id("post")
    e = s.renders_edge(nid)
    assert e["source_id"] == nid and e["target_id"] == s.id and e["relation_type"] == DevRelations.RENDERS
    p = PointNode(owner_id=s.id, key="k", kind="claim", text="x")
    assert p.has_point_edge()["source_id"] == s.id
    assert DevNodeKinds.POINT_SET in DevNodeKinds.all() and DevRelations.RENDERS in DevRelations.all()


def test_section_point_nests_by_parent_and_the_placed_overlay_rides_the_deliverable():
    """Rulings 96be1528 (2) as amended, (3), (7): a `section` point nests by naming its parent
    section and its heading depth is DERIVED from that chain — never a stored level; a move
    and the cross-reference verdicts ride the PLACED edge to the deliverable-owned section,
    never the shared substance point."""
    nid = note_node_id("post")
    sec = PointNode(owner_id=nid, key="sec-1", kind="section", text="The port library by library")
    sub = PointNode(owner_id=nid, key="sec-1a", kind="section", text="Thrust containers", parent_key="sec-1")
    assert sub.parent_id == sec.id and sub.elaborates_edge()["target_id"] == sec.id
    assert "level" not in sub.to_graph_node()["properties"] and not hasattr(sub, "level")
    assert PointNode(owner_id=nid, key="sec-1a", kind="section", text="retitled", parent_key="").id == sub.id  # a re-parent or retitle keeps the node
    setid = point_set_node_id("transcription", "src-1")
    q = PointNode(owner_id=setid, key="q-7", kind="question", text="Why CUB over cooperative groups?", refers_to=["k-3", "k-9"])
    e = placed_edge(q.id, sec.id, after="k-3", refs_shown=["k-3"])
    assert e["source_id"] == q.id and e["target_id"] == sec.id and e["relation_type"] == DevRelations.PLACED
    assert e["properties"] == {"after": "k-3", "refs_shown": ["k-3"]}
    assert placed_edge(q.id, sec.id)["properties"] == {}                       # no move, no verdict: the derived slot
    assert placed_edge(q.id, sec.id, after="")["properties"] == {"after": ""}  # the section's end
    assert "refs_shown" not in q.to_graph_node()["properties"]
    assert DevRelations.PLACED in DevRelations.all()


def test_research_point_carries_citations_and_derives_from_a_captured_page():
    """Ruling 96be1528 (4): a research point is owned by the deliverable, has no segment run,
    carries the citation contract, expands a source point in the rendered set, and its
    DERIVED_FROM lands on a WEB Reference — the same edge as a segment run."""
    nid, setid = note_node_id("post"), point_set_node_id("transcription", "src-1")
    page = ReferenceNode(graph=ReferenceNode.WEB, foreign_id="https://github.com/NVIDIA/cccl/blob/abc123/README.md",
                         title="cccl README", observed_hash="sha256:deadbeef", observed_at=1790000000.0,
                         archive_url="https://web.archive.org/web/2026/https://github.com/NVIDIA/cccl")
    assert page.id == reference_node_id("web", page.foreign_id)
    assert page.to_graph_node()["properties"]["archive_url"].startswith("https://web.archive.org/")
    assert ReferenceNode.from_observation(page.observation()) == page
    assert "archive_url" not in ReferenceNode(graph="transcription", foreign_id="seg-1").observation()
    r = PointNode(owner_id=nid, key="r-1", kind="claim", text="CCCL 2.4 shipped cuda::std::mdspan.",
                  provenance="research", expands="k-12",
                  citations=[{"url": page.foreign_id, "location": "L40", "snippet": "mdspan", "retrieved_at": 1790000000.0,
                              "reference_id": page.id}])
    w = r.to_graph_node()["properties"]
    assert w["provenance"] == "research" and w["expands"] == "k-12" and w["citations"][0]["reference_id"] == page.id
    assert w["segment_ids"] == [] and "start_time" not in w
    assert "provenance" not in PointNode(owner_id=setid, key="k-12", kind="claim", text="x").to_graph_node()["properties"]
    x = r.expands_edge(target_owner_id=setid)
    assert x["target_id"] == point_node_id(setid, "k-12") and x["relation_type"] == DevRelations.REFERENCES
    assert x["properties"] == {"role": "expands"}
    assert PointNode(owner_id=nid, key="r-2", kind="claim", text="y").expands_edge() is None
    d = r.derived_from_edges([page.id])
    assert d[0]["target_id"] == page.id and d[0]["relation_type"] == DevRelations.DERIVED_FROM
    # a deliverable-owned point leaning on set points resolves its back-links under the set
    a = PointNode(owner_id=nid, key="r-3", kind="claim", text="z", refers_to=["k-1"])
    assert a.refers_to_edges(target_owner_id=setid)[0]["target_id"] == point_node_id(setid, "k-1")
    assert a.refers_to_edges()[0]["target_id"] == point_node_id(nid, "k-1")


def test_point_role_is_a_closed_unordered_slate_on_the_shared_point():
    """Ruling 96be1528 (1): `point_role` (content | meta | aside) is a typed enum whose flip
    is an explicit supersession, named apart from the register `role` on Notes."""
    assert POINT_ROLE == "point_role" and POINT_ROLE != "role"
    assert POINT_ROLES == ("content", "meta", "aside")
    assert is_typed(POINT_ROLE) and not is_ordered(POINT_ROLE)
    assert values_conflict(POINT_ROLE, "content", "aside")
    assert not values_conflict(POINT_ROLE, "meta", "meta")
    assert active_contradiction(POINT_ROLE, ["content", "aside"])


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
