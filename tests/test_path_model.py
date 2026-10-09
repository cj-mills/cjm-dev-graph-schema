"""The path model's schema (design ae698640): the relations with per-pair data and their endpoint
table, the record-landed edges (lineage, PART_OF), the JUDGED family, the environment's versions
and the stage-transition match."""

import json

import pytest

from cjm_context_graph_layer.grammar import SpineRelations
from cjm_dev_graph_schema import predicates as P
from cjm_dev_graph_schema.identity import entity_node_id, note_node_id
from cjm_dev_graph_schema.nodes import judged_edge, lineage_edge, record_part_of_edge, relation_edge
from cjm_dev_graph_schema.vocab import DevRelations


def test_every_relation_is_reserved_and_has_endpoints():
    for rel in ("PRODUCES", "REQUIRES", "TEACHES", "ASSUMES", "COVERS", "EXPLAINS"):
        assert getattr(DevRelations, rel) == rel and rel in DevRelations.all()
        assert rel in P.RELATION_ENDPOINTS
    assert DevRelations.JUDGED in DevRelations.all() and not hasattr(DevRelations, "JUDGED_FACET")
    assert set(P.STRENGTH_RELATIONS) <= set(P.RELATION_ENDPOINTS)
    assert set(P.JUDGEABLE_RELATIONS) <= set(P.RELATION_ENDPOINTS)
    # a setup-role Section may produce; an environment's own requirements are its record's
    assert P.NODE_SECTION in P.RELATION_ENDPOINTS["PRODUCES"][0]
    assert ("REQUIRES", P.ENTITY_ENVIRONMENT) in P.RECORD_RELATIONS


def test_relation_edge_keys_the_pair_per_relation_and_carries_strength():
    step, ckpt = note_node_id("onnx-export"), entity_node_id("artifact", "yolox-hagrid-ckpt")
    req = relation_edge("REQUIRES", step, ckpt)
    again = relation_edge("REQUIRES", step, ckpt, strength="recommended", note="the exported checkpoint")
    prod = relation_edge("PRODUCES", step, ckpt)
    assert req["id"] == again["id"] != prod["id"]
    assert req["properties"] == {"strength": "required"}
    assert again["properties"] == {"strength": "recommended", "note": "the exported checkpoint"}
    assert prod["properties"] == {} and prod["relation_type"] == "PRODUCES"
    with pytest.raises(ValueError, match="carries no strength"):
        relation_edge("TEACHES", step, ckpt, strength="required")
    with pytest.raises(ValueError, match="strength must be one of"):
        relation_edge("ASSUMES", step, ckpt, strength="maybe")
    with pytest.raises(ValueError, match="no relation"):
        relation_edge("USES", step, ckpt)
    env = relation_edge("REQUIRES", entity_node_id("environment", "cuda"),
                        entity_node_id("environment", "nvidia-driver"), record=entity_node_id("environment", "cuda"))
    assert env["properties"]["record"] == entity_node_id("environment", "cuda")


def test_record_landed_edges_name_their_record():
    a, b, c = (entity_node_id("artifact", k) for k in ("onnx", "ckpt", "weights"))
    one, two = lineage_edge(a, b), lineage_edge(a, c)
    assert one["relation_type"] == DevRelations.DERIVED_FROM and one["id"] != two["id"]
    assert one["properties"] == {"record": a}
    concept, subject = entity_node_id("concept", "tracking"), entity_node_id("subject", "computer-vision")
    po = record_part_of_edge(concept, subject, concept)
    assert po["relation_type"] == SpineRelations.PART_OF and po["properties"] == {"record": concept}


def test_judged_edge_keys_source_target_and_form():
    post, concept = note_node_id("bytetrack"), entity_node_id("concept", "tracking")
    t = judged_edge(post, concept, proposes="TEACHES", p=0.9, model="jev", criteria="c", state="s")
    a = judged_edge(post, concept, proposes="ASSUMES", p=0.1, model="jev", criteria="c", state="s")
    t2 = judged_edge(post, concept, proposes="TEACHES", p=0.7, model="jev", criteria="c", state="s2")
    assert t["relation_type"] == DevRelations.JUDGED and t["id"] == t2["id"] != a["id"]
    assert t["properties"]["proposes"] == "TEACHES" and t2["properties"]["p"] == 0.7


def test_environment_versions_value_and_ordering():
    v = P.versions_value({"torch": "2.4.1", "cuda": "12.4", "": ""})
    assert v == '{"cuda":"12.4","torch":"2.4.1"}' and P.versions_of(v) == {"cuda": "12.4", "torch": "2.4.1"}
    assert P.versions_of("not json") == {} and P.versions_of("[1]") == {}
    with pytest.raises(ValueError):
        P.versions_value({})
    with pytest.raises(ValueError):
        P.versions_value({"torch": 2})
    k = P.version_key
    assert k("2.4") < k("2.4.1") < k("2.10") and k("v1.13.0") == k("1.13.0")
    assert k("JetPack 6.0") < k("JetPack 6.1") and k("r36.3") < k("r36.4") and k("latest") is None
    pred = P.get_predicate(P.ENVIRONMENT_VERSIONS)
    assert pred.ordering == P.ORDER_NONE and not pred.multivalued
    # equal maps are one Assertion however written; a malformed value passes through for the writer to refuse
    assert P.canonical_value(P.ENVIRONMENT_VERSIONS, '{ "torch": "2.4.1", "cuda":"12.4" }') == v
    assert P.canonical_value(P.ENVIRONMENT_VERSIONS, "torch 2.4") == "torch 2.4"


def test_transition_match_is_a_set_rule():
    training = {"in": ["dataset"], "optional": ["checkpoint"], "out": "checkpoint"}
    assert P.transition_matches(training, ["dataset"], ["checkpoint"])
    assert P.transition_matches(training, ["dataset", "checkpoint"], ["checkpoint"])   # class extension
    assert not P.transition_matches(training, ["checkpoint"], ["checkpoint"])          # no dataset
    assert not P.transition_matches(training, ["dataset", "predictions"], ["checkpoint"])
    setup = {"in": [], "out": P.TRANSITION_ENVIRONMENT}
    assert P.transition_matches(setup, [], [P.TRANSITION_ENVIRONMENT])
    assert not P.transition_matches(setup, ["dataset"], [P.TRANSITION_ENVIRONMENT])


def test_the_standing_slate_and_the_destination_relations():
    # cbd5f154 (1) amended by 6514869f: one unordered standing fact, superseded never a value
    assert P.CURRENCY_VALUES == ("current", "archived", "removed") and "superseded" not in P.CURRENCY_VALUES
    assert set(P.CURRENCY_WITHDRAWN) == {"archived", "removed"}
    cur = P.get_predicate(P.CURRENCY)
    assert cur.ordering == P.ORDER_NONE and not cur.multivalued
    # the destination relations share the endpoint table, never the path walk
    assert P.RELATION_ENDPOINTS["SUPERSEDES"] == ((P.NODE_DELIVERABLE,), (P.NODE_DELIVERABLE,))
    assert P.RELATION_ENDPOINTS["RELOCATED_TO"] == ((P.NODE_DELIVERABLE,), (P.NODE_REFERENCE,))
    assert set(P.PATH_RELATIONS) | set(P.DESTINATION_RELATIONS) == set(P.RELATION_ENDPOINTS)
    assert not set(P.PATH_RELATIONS) & set(P.DESTINATION_RELATIONS)
    assert DevRelations.RELOCATED_TO in DevRelations.all()
    old, new = note_node_id("fastai-timm"), note_node_id("pytorch-timm")
    e = relation_edge("SUPERSEDES", new, old, note="the PyTorch timm series")
    assert (e["source_id"], e["target_id"], e["relation_type"]) == (new, old, "SUPERSEDES")
    with pytest.raises(ValueError):
        relation_edge("RELOCATED_TO", old, new, strength="recommended")
