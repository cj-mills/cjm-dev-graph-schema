"""Coarse-tier NoteNode: deterministic identity, wire-dict mapping, REFERENCES edges."""

from cjm_context_graph_layer.grammar import SpineRelations
from cjm_dev_graph_schema.identity import (note_node_id, section_node_id,
                                           series_node_id, topic_node_id)
from cjm_dev_graph_schema.nodes import (NoteNode, SectionNode, SeriesNode,
                                        series_member_edge, site_link_edge, TopicNode,
                                        supports_edge, verified_on_edge)
from cjm_dev_graph_schema.vocab import DevNodeKinds, DevRelations


def _note(**kw):
    base = dict(slug="self-hosting-graph-arc", title="Self Hosting Graph Arc",
                path="memory/project_self_hosting_graph_arc.md", content_hash="sha256:abc",
                description="The arc.", note_type="project", references=["current-arc-status"])
    base.update(kw)
    return NoteNode(**base)


def test_id_is_deterministic_from_slug():
    a, b = _note(), _note(title="Different Title", description="changed")
    # Identity derives from the slug only, never from correctable content.
    assert a.id == b.id == note_node_id("self-hosting-graph-arc")


def test_id_changes_with_slug():
    assert _note(slug="other").id != _note().id


def test_to_graph_node_shape():
    node = _note().to_graph_node()
    assert node["id"] == note_node_id("self-hosting-graph-arc")
    assert node["label"] == DevNodeKinds.NOTE
    assert node["properties"]["root_kind"] == "asserted"
    assert node["properties"]["title"] == "Self Hosting Graph Arc"
    assert node["properties"]["description"] == "The arc."
    assert node["properties"]["note_type"] == "project"
    assert len(node["sources"]) == 1
    assert node["sources"][0]["content_hash"] == "sha256:abc"


def test_reference_edges_target_linked_note_ids():
    edges = _note().reference_edges()
    assert len(edges) == 1
    e = edges[0]
    assert e["source_id"] == note_node_id("self-hosting-graph-arc")
    assert e["target_id"] == note_node_id("current-arc-status")
    assert e["relation_type"] == DevRelations.REFERENCES


def test_no_references_no_edges():
    assert _note(references=[]).reference_edges() == []


def test_optional_fields_omitted_when_empty():
    node = _note(note_type=None, metadata={}).to_graph_node()
    assert "note_type" not in node["properties"]
    assert "metadata" not in node["properties"]
    assert "categories" not in node["properties"]
    assert "site_refs" not in node["properties"]


# --- Increment 2: facet/relationship surface ---------------------------------

def test_tagged_edges_target_shared_topic_ids():
    edges = _note(categories=["pytorch", "object-detection"]).tagged_edges()
    assert [e["relation_type"] for e in edges] == [DevRelations.TAGGED] * 2
    assert {e["target_id"] for e in edges} == {topic_node_id("pytorch"),
                                               topic_node_id("object-detection")}
    # Two notes sharing a category converge on ONE Topic node id.
    other = _note(slug="other", categories=["pytorch"]).tagged_edges()[0]
    assert other["target_id"] == topic_node_id("pytorch")


def test_series_member_edge_carries_the_authored_position():
    # Membership is journaled intent with its position (DEC 72d669c5 (4)): `after` names the
    # member it follows, "" = the first; the id is the triple, so a move re-lands the edge.
    first = series_member_edge(note_node_id("a"), series_node_id("s"))
    second = series_member_edge(note_node_id("b"), series_node_id("s"), after=note_node_id("a"))
    assert first["relation_type"] == second["relation_type"] == DevRelations.IN_SERIES
    assert first["properties"] == {"after": ""}
    assert second["properties"] == {"after": note_node_id("a")}
    moved = series_member_edge(note_node_id("b"), series_node_id("s"))
    assert moved["id"] == second["id"]


def test_site_link_edge_is_a_marked_reference():
    e = site_link_edge(note_node_id("a"), series_node_id("s"))
    assert e["relation_type"] == DevRelations.REFERENCES
    assert e["target_id"] == series_node_id("s") and e["properties"] == {"site_link": True}


def test_site_link_edge_carries_the_anchor():
    # One family for every in-body site link (ruling d31e9ba7): an anchored link to a post
    # lands on the Section it names, the anchor kept on the edge; the kind is the target's
    sec = section_node_id(note_node_id("b"), "using-hardware-acceleration")
    e = site_link_edge(note_node_id("a"), sec, "using-hardware-acceleration")
    assert e["target_id"] == sec
    assert e["properties"] == {"site_link": True, "anchor": "using-hardware-acceleration"}
    # the id is the triple's: the anchor never forks an edge between one note and one target
    assert e["id"] == site_link_edge(note_node_id("a"), sec)["id"]
    assert not hasattr(NoteNode, "cross_post_edges")


def test_facets_stored_on_node_when_present():
    node = _note(categories=["pytorch"], site_refs=["/series/notes/education-notes.html"],
                 aliases=["/posts/old-url/"]).to_graph_node()
    assert node["properties"]["categories"] == ["pytorch"]
    assert node["properties"]["site_refs"] == ["/series/notes/education-notes.html"]
    assert node["properties"]["aliases"] == ["/posts/old-url/"]


def test_topic_node_shape_and_identity():
    t = TopicNode(key="object-detection")
    node = t.to_graph_node()
    assert t.id == topic_node_id("object-detection")
    assert node["label"] == DevNodeKinds.TOPIC
    assert node["properties"] == {"key": "object-detection", "name": "object-detection",
                                  "root_kind": "asserted"}
    assert TopicNode(key="x", name="Display X").to_graph_node()["properties"]["name"] == "Display X"


def test_series_node_shape_and_identity():
    s = SeriesNode(key="education-notes", title="Education Notes")
    node = s.to_graph_node()
    assert s.id == series_node_id("education-notes")
    assert node["label"] == DevNodeKinds.SERIES
    assert node["properties"]["title"] == "Education Notes"
    assert "description" not in node["properties"] and "image" not in node["properties"]
    page = SeriesNode(key="k", title="T", description="D", image="./preview-images/k.png",
                      date="2023-10-19").to_graph_node()["properties"]
    assert (page["description"], page["image"], page["date"]) == ("D", "./preview-images/k.png",
                                                                 "2023-10-19")


# --- Increment 4: Section nodes (body content on-graph) -----------------------

def test_section_identity_and_anchor_resolution_by_construction():
    nid = note_node_id("pytorch-train-object-detector-yolox-tutorial")
    sec = SectionNode(note_id=nid, anchor="loading-the-model", level=2, title="Loading the Model")
    # Identity = (note, anchor) — the SAME id a cross-post #anchor REFERENCES targets.
    assert sec.id == section_node_id(nid, "loading-the-model")


def test_section_node_shape_carries_verbatim_text():
    nid = note_node_id("x")
    node = SectionNode(note_id=nid, anchor="intro", level=1, title="Intro",
                       text="The body.\n", order=0, path="/c/posts/x/index.md",
                       content_hash="sha256:abc").to_graph_node()
    assert node["label"] == DevNodeKinds.SECTION
    assert node["properties"]["text"] == "The body.\n"
    assert node["properties"]["level"] == 1 and node["properties"]["order"] == 0
    assert node["properties"]["anchor"] == "intro"
    assert node["sources"][0]["content_hash"] == "sha256:abc"


def test_section_structural_edges_membership_and_hierarchy():
    nid = note_node_id("x")
    top = SectionNode(note_id=nid, anchor="setup", level=1, title="Setup")
    child = SectionNode(note_id=nid, anchor="install", level=2, title="Install",
                        parent_anchor="setup")
    # Top-level: only HAS_SECTION (note -> section), no PART_OF.
    te = top.structural_edges()
    assert len(te) == 1
    assert te[0]["source_id"] == nid and te[0]["relation_type"] == DevRelations.HAS_SECTION
    assert te[0]["target_id"] == top.id
    # Nested: HAS_SECTION + PART_OF -> the enclosing section.
    ce = child.structural_edges()
    assert {e["relation_type"] for e in ce} == {DevRelations.HAS_SECTION, SpineRelations.PART_OF}
    part_of = [e for e in ce if e["relation_type"] == SpineRelations.PART_OF][0]
    assert part_of["target_id"] == section_node_id(nid, "setup")


def test_verified_on_edge_keys_the_os_and_carries_the_evidence():
    # 8cbdc883 (7): the device is the node, the OS is the edge's -- one GPU under two OSes is two
    # verifications; a re-verification under the same OS re-lands the edge with fresh evidence
    from cjm_dev_graph_schema.identity import entity_node_id
    gpu = entity_node_id("hardware", "rtx-4090")
    linux = verified_on_edge(note_node_id("a"), gpu, os="Ubuntu 24.04", date="2024-11-11",
                             basis="timeline", versions={"tensorrt": "10.4"})
    win = verified_on_edge(note_node_id("a"), gpu, os="Windows 11", date="2023-10-20")
    again = verified_on_edge(note_node_id("a"), gpu, os="Ubuntu 24.04", date="2025-01-02")
    assert linux["relation_type"] == DevRelations.VERIFIED_ON and DevRelations.VERIFIED_ON in DevRelations.all()
    assert linux["id"] != win["id"] and linux["id"] == again["id"]
    assert linux["properties"] == {"os": "Ubuntu 24.04", "date": "2024-11-11", "basis": "timeline",
                                   "versions": {"tensorrt": "10.4"}, "note": ""}


def test_supports_edge_keys_the_pair_and_carries_the_kind():
    # 98e99fe5 (2): the kind is the edge's; one kind per (deliverable, claim), a restatement
    # re-lands the same edge with the new kind
    from cjm_dev_graph_schema.identity import entity_node_id
    claim = entity_node_id("claim", "cv-train-to-deploy")
    cap = supports_edge(note_node_id("a"), claim, kind="capability", note="trains a detector")
    know = supports_edge(note_node_id("a"), claim, kind="knowledge")
    other = supports_edge(note_node_id("a"), entity_node_id("claim", "gpu-performance"), kind="capability")
    assert cap["relation_type"] == DevRelations.SUPPORTS and DevRelations.SUPPORTS in DevRelations.all()
    assert cap["id"] == know["id"] and cap["id"] != other["id"]
    assert cap["properties"] == {"kind": "capability", "note": "trains a detector"}
