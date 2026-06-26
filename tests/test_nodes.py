"""Coarse-tier NoteNode: deterministic identity, wire-dict mapping, REFERENCES edges."""

from cjm_dev_graph_schema.identity import (note_node_id, series_node_id,
                                           topic_node_id)
from cjm_dev_graph_schema.nodes import NoteNode, SeriesNode, TopicNode
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
    assert "series_refs" not in node["properties"]


# --- Increment 2: facet/relationship surface ---------------------------------

def test_tagged_edges_target_shared_topic_ids():
    edges = _note(categories=["pytorch", "object-detection"]).tagged_edges()
    assert [e["relation_type"] for e in edges] == [DevRelations.TAGGED] * 2
    assert {e["target_id"] for e in edges} == {topic_node_id("pytorch"),
                                               topic_node_id("object-detection")}
    # Two notes sharing a category converge on ONE Topic node id.
    other = _note(slug="other", categories=["pytorch"]).tagged_edges()[0]
    assert other["target_id"] == topic_node_id("pytorch")


def test_series_edges_membership():
    edges = _note(series_refs=["education-notes"]).series_edges()
    assert len(edges) == 1
    assert edges[0]["relation_type"] == DevRelations.IN_SERIES
    assert edges[0]["target_id"] == series_node_id("education-notes")


def test_cross_post_edges_carry_anchor_and_marker():
    note = _note(cross_post_refs=[("google-colab-getting-started-tutorial", "using-hardware-acceleration"),
                                  ("mamba-getting-started-tutorial-windows", "")])
    edges = note.cross_post_edges()
    assert all(e["relation_type"] == DevRelations.REFERENCES for e in edges)
    by_target = {e["target_id"]: e for e in edges}
    anchored = by_target[note_node_id("google-colab-getting-started-tutorial")]
    assert anchored["properties"] == {"cross_post": True, "anchor": "using-hardware-acceleration"}
    plain = by_target[note_node_id("mamba-getting-started-tutorial-windows")]
    assert plain["properties"] == {"cross_post": True}  # no anchor key when empty


def test_cross_post_alias_resolution():
    note = _note(cross_post_refs=[("old-permalink", "")])
    e = note.cross_post_edges({"old-permalink": "new-permalink"})[0]
    assert e["target_id"] == note_node_id("new-permalink")


def test_facets_stored_on_node_when_present():
    node = _note(categories=["pytorch"], series_refs=["education-notes"],
                 aliases=["/posts/old-url/"]).to_graph_node()
    assert node["properties"]["categories"] == ["pytorch"]
    assert node["properties"]["series_refs"] == ["education-notes"]
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
