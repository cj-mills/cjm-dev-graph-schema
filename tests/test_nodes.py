"""Coarse-tier NoteNode: deterministic identity, wire-dict mapping, REFERENCES edges."""

from cjm_dev_graph_schema.identity import note_node_id
from cjm_dev_graph_schema.nodes import NoteNode
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
