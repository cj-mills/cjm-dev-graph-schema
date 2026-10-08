"""Predicate value-space: canonicalization, ordering, and conflict decisions."""

import pytest

from cjm_dev_graph_schema import predicates as P


def test_typed_predicate_registry():
    assert set(P.PREDICATES) == {"rename-disposition", "version", "aka", "task_state",
                                 "priority", "model-status", "publish_state", "review_verdict",
                                 "derived_from", "deliverable_type", "point_role", "site_path",
                                 "teaches_task", "teaches_stage", "verification_standing",
                                 "claim_state", "revised", "discussion", "content_license",
                                 "code_license", "locator", "citation", "resources", "related_judged",
                                 "design_light_mode", "design_dark_mode", "about_task", "about_stage",
                                 "about_subject", "uses_tool", "uses_model", "facets_judged",
                                 "category_page_min", "home_hubs", "home_recent", "environment_versions",
                                 "traffic"}
    assert P.is_typed("rename-disposition") and P.is_typed("version") and P.is_typed("aka")
    assert P.is_typed("task_state") and P.is_ordered("task_state")  # ordered enum lifecycle
    assert not P.is_typed("status")  # untyped freetext until a real contradiction types it


def test_aka_is_multivalued_slug_set():
    p = P.get_predicate("aka")
    assert p.value_type == P.SLUG and p.ordering == P.ORDER_NONE and p.multivalued
    assert P.is_multivalued("aka")
    assert not P.is_multivalued("rename-disposition") and not P.is_multivalued("version")
    assert not P.is_ordered("aka")  # multivalued, not ordered
    # SLUG canonicalizes case-insensitively, like enum.
    assert P.canonical_value("aka", "Where-Graph-Begins") == "where-graph-begins"


def test_aka_distinct_values_never_conflict():
    # A note legitimately accrues MANY aliases -> distinct values coexist.
    assert not P.values_conflict("aka", "slug-a", "slug-b")
    assert not P.active_contradiction("aka", ["slug-a", "slug-b", "slug-c"])
    assert not P.soft_conflict("aka", ["slug-a", "slug-b"])  # typed -> never a soft signal either


def test_rename_disposition_is_unordered_enum():
    p = P.get_predicate("rename-disposition")
    assert p.value_type == P.ENUM and p.ordering == P.ORDER_NONE and p.volatility == P.STABLE
    assert not P.is_ordered("rename-disposition")


def test_version_is_ordered_semver():
    p = P.get_predicate("version")
    assert p.value_type == P.SEMVER and p.ordering == P.ORDER_SEMVER and p.volatility == P.CHANGES
    assert P.is_ordered("version")


def test_canonical_value_semver_strips_v_prefix():
    assert P.canonical_value("version", "v0.0.51") == P.canonical_value("version", "0.0.51")
    assert P.canonical_value("version", " 0.0.51 ") == "0.0.51"


def test_canonical_value_enum_lowercases():
    assert P.canonical_value("rename-disposition", "Keep") == "keep"
    assert (P.canonical_value("rename-disposition", "rename:Cjm-X")
            == "rename:cjm-x")


def test_canonical_value_untyped_preserves_case():
    assert P.canonical_value("definition", "A Thing") == "A Thing"


def test_ordering_supersedes_semver():
    assert P.ordering_supersedes("version", "0.0.51", "0.0.50") is True   # newer wins
    assert P.ordering_supersedes("version", "0.0.50", "0.0.51") is False  # born superseded
    assert P.ordering_supersedes("version", "0.0.51", "0.0.51") is None   # same -> no supersede
    assert P.ordering_supersedes("version", "weird", "0.0.1") is None     # incomparable
    assert P.ordering_supersedes("rename-disposition", "keep", "rename:x") is None  # unordered


def test_ordering_supersedes_task_state_enum():
    # The work-item lifecycle is an ordered enum (`open` < `in_progress` < `done`):
    # each forward step auto-supersedes the prior state, the version-bump pattern.
    # (6a27c56f: `in_progress` was off-sequence and landed BESIDE `open`.)
    assert P.ordering_supersedes("task_state", "done", "open") is True   # closing wins
    assert P.ordering_supersedes("task_state", "in_progress", "open") is True  # starting wins
    assert P.ordering_supersedes("task_state", "done", "in_progress") is True  # finishing wins
    assert P.ordering_supersedes("task_state", "open", "done") is False  # reopen is born superseded
    assert P.ordering_supersedes("task_state", "open", "in_progress") is False
    assert P.ordering_supersedes("task_state", "done", "done") is None   # same -> no supersede
    assert P.ordering_supersedes("task_state", "DONE", "open") is True    # canonicalized (lowercased)
    assert P.ordering_supersedes("task_state", "wip", "open") is None     # off-sequence -> no supersede
    # task_state is ordered, so distinct values never read as a HARD contradiction.
    assert not P.values_conflict("task_state", "open", "done")
    assert not P.active_contradiction("task_state", ["open", "in_progress", "done"])


def test_values_conflict_only_typed_unordered():
    # rename-disposition: distinct canonical values are a HARD conflict.
    assert P.values_conflict("rename-disposition", "keep", "rename:cjm-substrate-torch-utils")
    assert not P.values_conflict("rename-disposition", "keep", "Keep")
    # version: ordered -> never a hard conflict (newer just supersedes).
    assert not P.values_conflict("version", "0.0.50", "0.0.51")
    # untyped -> soft, not hard.
    assert not P.values_conflict("status", "draft", "final")


def test_active_contradiction_and_soft_conflict():
    assert P.active_contradiction("rename-disposition", ["keep", "rename:x"])
    assert not P.active_contradiction("rename-disposition", ["keep", "Keep"])
    assert not P.active_contradiction("version", ["0.0.50", "0.0.51"])
    # untyped disagreement is SOFT, not a contradiction.
    assert not P.active_contradiction("status", ["draft", "final"])
    assert P.soft_conflict("status", ["draft", "final"])
    assert not P.soft_conflict("rename-disposition", ["keep", "rename:x"])  # typed -> hard, not soft


def test_pin_family_resolves_typed_multivalued_set():
    # `pin.<role>` resolves through the prefix FAMILY: typed, freetext, SET slot.
    p = P.get_predicate("pin.craft")
    assert p is not None and p.slug == "pin.*"
    assert p.value_type == P.FREETEXT and p.ordering == P.ORDER_NONE and p.multivalued
    assert P.is_typed("pin.craft") and P.is_multivalued("pin.doctrine-head")
    # Coexisting pins never conflict — hard or soft (soft would spam the worklist).
    assert not P.values_conflict("pin.craft", "aaaa — one", "bbbb — two")
    assert not P.active_contradiction("pin.craft", ["aaaa — one", "bbbb — two"])
    assert not P.soft_conflict("pin.craft", ["aaaa — one", "bbbb — two"])
    # Freetext canonicalization preserves the id+gloss value (strip only).
    assert P.canonical_value("pin.craft", " abcd1234 — Read before authoring ") == "abcd1234 — Read before authoring"
    # A bare family prefix is NOT a member; unrelated slugs stay untyped.
    assert P.get_predicate("pin.") is None
    assert P.get_predicate("pinned") is None and not P.is_typed("pinned")


def test_priority_and_model_status_are_unordered_flip_guards():
    # Axis F: priority/gating judgments as facts. UNORDERED on purpose — a change
    # must explicitly supersede, so an un-superseded flip is a HARD contradiction
    # (the 367eaaae lesson: no silent newer-wins on judgment predicates).
    for slug in ("priority", "model-status"):
        p = P.get_predicate(slug)
        assert p.value_type == P.ENUM and p.ordering == P.ORDER_NONE and p.volatility == P.CHANGES
        assert not P.is_ordered(slug) and not P.is_multivalued(slug)
    assert P.ordering_supersedes("priority", "early", "demand-gated") is None
    assert P.values_conflict("priority", "early", "demand-gated")
    assert P.active_contradiction("priority", ["early", "demand-gated"])
    assert not P.active_contradiction("priority", ["Early", "early"])  # enum canonicalizes case
    assert P.values_conflict("model-status", "current", "candidate")
    assert not P.active_contradiction("model-status", ["current"])


def test_publish_state_is_an_ordered_lifecycle():
    # Ruling 793f025e: draft < reviewed < published — a human promotion auto-supersedes the
    # prior stage (never a contradiction); a demotion is born superseded; off-sequence = None.
    assert P.is_typed("publish_state") and P.is_ordered("publish_state")
    assert P.get_predicate("publish_state").order_values == ("fixture", "draft", "reviewed", "published")
    assert P.ordering_supersedes("publish_state", "reviewed", "draft") is True
    assert P.ordering_supersedes("publish_state", "published", "reviewed") is True
    assert P.ordering_supersedes("publish_state", "draft", "published") is False
    assert P.ordering_supersedes("publish_state", "retracted", "draft") is None
    # The draft lifecycle (item 140981e9): `fixture` is the floor — re-stating a draft as a
    # fixture is a DEMOTION (born superseded unless the human names the draft explicitly).
    assert P.ordering_supersedes("publish_state", "draft", "fixture") is True
    assert P.ordering_supersedes("publish_state", "fixture", "draft") is False
    assert P.ordering_supersedes("publish_state", "fixture", "published") is False


def test_publish_state_retired_is_a_terminal_side_state():
    # Item 140981e9 (ruling a7ca900d (4)): `retired` closes the lifecycle from ANY stage — it
    # supersedes fixture/draft/reviewed/published alike — and a stage asserted over a retired
    # deliverable is born superseded (reopening is an explicit human --supersede).
    p = P.get_predicate("publish_state")
    assert p.terminal_values == ("retired",) and "retired" not in p.order_values
    assert P.is_terminal("publish_state", "retired") and P.is_terminal("publish_state", "RETIRED")
    assert not P.is_terminal("publish_state", "draft") and not P.is_terminal("publish_state", "fixture")
    assert not P.is_terminal("task_state", "done") and not P.is_terminal("status", "retired")
    for stage in ("fixture", "draft", "reviewed", "published"):
        assert P.ordering_supersedes("publish_state", "retired", stage) is True
        assert P.ordering_supersedes("publish_state", stage, "retired") is False
    assert P.ordering_supersedes("publish_state", "retired", "retired") is None
    assert P.ordering_supersedes("publish_state", "retired", "bogus") is None
    assert P.ordering_supersedes("publish_state", "bogus", "retired") is None
    # `retired` is not an approval: the review frontier never roots on it.
    assert not P.is_approval("publish_state", "retired") and not P.is_approval("publish_state", "fixture")


def test_review_verdict_is_a_multivalued_set_and_approval_class_is_data():
    # design 40622922 (5): acknowledgments coexist (never conflict, never supersede);
    # the approval class is schema DATA — draft is a birth, reviewed/published approve.
    p = P.get_predicate("review_verdict")
    assert p.multivalued and p.ordering == P.ORDER_NONE and P.is_multivalued("review_verdict")
    assert not P.active_contradiction("review_verdict", ["a@1", "b@2"])
    assert P.APPROVAL_CLASS == {"publish_state": ("reviewed", "published")}
    assert not P.is_approval("publish_state", "draft")
    assert P.is_approval("publish_state", "reviewed") and P.is_approval("publish_state", "Published")
    assert not P.is_approval("task_state", "done") and not P.is_approval("review_verdict", "x@y")


def test_derived_from_is_multivalued_freetext_set():
    # Finding 0154f5e4 interim: a born deliverable names MANY foreign nodes it drew on
    # (`<graph-key>:<node-id>`) -> a set slot: distinct values coexist, never conflict,
    # never order.
    p = P.get_predicate("derived_from")
    assert p.value_type == P.FREETEXT and p.ordering == P.ORDER_NONE and p.multivalued
    assert P.is_multivalued("derived_from") and not P.is_ordered("derived_from")
    assert not P.values_conflict("derived_from", "transcription:aaa", "transcription:bbb")
    assert not P.active_contradiction("derived_from", ["transcription:aaa", "transcription:bbb"])
    assert not P.soft_conflict("derived_from", ["transcription:aaa", "transcription:bbb"])
    assert P.canonical_value("derived_from", " transcription:AAA ") == "transcription:AAA"  # freetext: case kept


def test_site_path_is_unordered_case_preserving_and_hard_conflicts():
    # Ruling 96aff70e: one page, one current URL; a move is an explicit supersession, so two
    # active paths are a HARD contradiction. Paths are case-sensitive and never normalized.
    p = P.get_predicate(P.SITE_PATH)
    assert p is not None and not P.is_ordered(P.SITE_PATH) and not P.is_multivalued(P.SITE_PATH)
    assert P.canonical_value(P.SITE_PATH, " /Notes-on-Advanced-Git-Tools/ ") == "/Notes-on-Advanced-Git-Tools/"
    assert P.values_conflict(P.SITE_PATH, "/posts/x/", "/Notes-on-X/")
    assert not P.values_conflict(P.SITE_PATH, "/posts/x/", "/posts/x/")
    assert P.active_contradiction(P.SITE_PATH, ["/posts/x/", "/posts/y/"])


def test_coverage_predicates_are_multivalued_vocabulary_slug_sets():
    # Designs 8cbdc883 / c450133a: a post teaches a SET of tasks and a SET of stages, each value
    # the key of a vocabulary Entity; distinct values coexist and never conflict.
    for slug, kind in ((P.TEACHES_TASK, P.ENTITY_TASK), (P.TEACHES_STAGE, P.ENTITY_STAGE)):
        p = P.get_predicate(slug)
        assert p.value_type == P.SLUG and p.ordering == P.ORDER_NONE and p.multivalued
        assert P.COVERAGE_KINDS[slug] == kind
        assert not P.values_conflict(slug, "training", "export")
        assert not P.active_contradiction(slug, ["training", "export"])
    assert set(P.COVERAGE_KINDS.values()) == {"task", "stage"}


def test_verification_standing_is_an_unordered_closed_slate():
    # 8cbdc883 (7): a device's standing has history; a change is an explicit supersession, so
    # two active standings are a HARD contradiction (the in-set filter never forks)
    p = P.get_predicate(P.VERIFICATION_STANDING)
    assert p.value_type == P.ENUM and not P.is_ordered(P.VERIFICATION_STANDING)
    assert not P.is_multivalued(P.VERIFICATION_STANDING)
    assert P.active_contradiction(P.VERIFICATION_STANDING, ["in-set", "retired"])
    assert P.STANDING_IN_SET in P.VERIFICATION_STANDINGS and "retired" in P.VERIFICATION_STANDINGS
    assert P.VERIFICATION_BASES == ("stated", "timeline") and "gpu" in P.DEVICE_CLASSES


def test_claim_state_is_an_unordered_closed_slate_and_the_floor_excludes_knowledge():
    # 98e99fe5 (1)/(3): a promotion is an explicit supersession, two active states a HARD
    # contradiction; knowledge never carries an offer alone
    p = P.get_predicate(P.CLAIM_STATE)
    assert p.value_type == P.ENUM and not P.is_ordered(P.CLAIM_STATE)
    assert not P.is_multivalued(P.CLAIM_STATE)
    assert P.active_contradiction(P.CLAIM_STATE, ["building", "offered"])
    assert P.CLAIM_OFFERED in P.CLAIM_STATES and "building" in P.CLAIM_STATES
    assert set(P.BACKING_KINDS) == set(P.SUPPORT_KINDS) - {"knowledge"}


def test_the_post_page_facts():
    # 39c51c15: revisions accumulate (a set, never a conflict); a thread, a license and a
    # locator are one value each, so a change is an explicit supersession
    assert P.is_multivalued(P.REVISED) and not P.active_contradiction(P.REVISED, ["typo pass", "new section"])
    for slug in (P.DISCUSSION, P.CONTENT_LICENSE, P.CODE_LICENSE, P.LOCATOR, P.CITATION, P.RESOURCES,
                 P.RELATED_JUDGED):
        assert P.is_typed(slug) and not P.is_multivalued(slug) and not P.is_ordered(slug)
    assert P.active_contradiction(P.CONTENT_LICENSE, ["cc-by-4.0", "cc-by-nc-sa-4.0"])
    assert P.canonical_value(P.CONTENT_LICENSE, "CC-BY-4.0") == "cc-by-4.0"   # SPDX ids, case-folded


def test_a_citation_is_its_parts_as_canonical_json():
    # 722a8232 (2): the parts are stored, never a rendered string; equal parts are one value
    a = P.citation_value({"work": "The Learning Game", "author": "Ana Lorena Fábrega", "part": 1, "chapter": 2})
    b = P.citation_value({"chapter": 2, "part": 1, "author": "Ana Lorena Fábrega", "work": "The Learning Game",
                          "title": ""})
    assert a == b == '{"author":"Ana Lorena Fábrega","chapter":2,"part":1,"work":"The Learning Game"}'
    assert P.citation_parts(a) == {"author": "Ana Lorena Fábrega", "chapter": 2, "part": 1, "work": "The Learning Game"}
    assert P.citation_parts("not json") == {} and P.citation_parts("[1]") == {}
    with pytest.raises(ValueError):
        P.citation_value({"publisher": "x"})          # the parts are the vocabulary
    with pytest.raises(ValueError):
        P.citation_value({"title": ""})               # a citation names something


def test_resources_are_the_links_as_canonical_json():
    # a2936020: a source's human-added links, one value for the whole set, equal sets one value
    a = P.resources_value([{"label": "Newsletter", "url": "https://n", "role": "author-post"},
                           {"label": "Book page", "url": "https://b", "role": "publisher-page", "notes_slug": ""}])
    b = P.resources_value([{"role": "publisher-page", "url": "https://b", "label": "Book page"},
                           {"url": "https://n", "label": "Newsletter", "role": "author-post"}])
    assert a == b and a.startswith('[{"label":"Newsletter"')          # role, then label order
    assert P.resources_links(a)[1] == {"label": "Book page", "role": "publisher-page", "url": "https://b"}
    assert P.resources_value([]) == "[]" and P.resources_links("[]") == []
    assert P.resources_links("not json") == [] and P.resources_links('{"a": 1}') == []
    with pytest.raises(ValueError):
        P.resources_value([{"label": "x", "url": "https://x", "id": "n1"}])   # the fields are the vocabulary
    with pytest.raises(ValueError):
        P.resources_value([{"label": "x"}])                                   # a link leads somewhere


def test_the_confirmed_facets_are_vocabulary_key_sets():
    # eefda2dd (4): each confirmed facet names its vocabulary kind and is a set of keys, like teaches_*
    assert P.FACET_PREDICATES == {"about_task": "task", "about_stage": "stage", "about_subject": "subject",
                                  "uses_tool": "tool", "uses_model": "model"}
    for pred in P.FACET_PREDICATES:
        p = P.get_predicate(pred)
        assert p.value_type == P.SLUG and p.ordering == P.ORDER_NONE and p.multivalued
        assert not P.values_conflict(pred, "pytorch", "onnx")
    assert set(P.NON_TUTORIAL_FACETS) == {"about_task", "about_stage"}
    # the judge's record is one value, so a re-judge is an explicit supersession
    r = P.get_predicate(P.FACETS_JUDGED)
    assert r.value_type == P.FREETEXT and not r.multivalued and r.ordering == P.ORDER_NONE


def test_traffic_is_a_set_slot_of_canonical_measures():
    # design 7f315830 (4): one value per (source, window); equal measures are one Assertion however written
    assert P.is_multivalued(P.TRAFFIC) and not P.is_ordered(P.TRAFFIC)
    m = {"source": "cloudflare", "window": "2026-09", "complete": True,
         "visits": {"estimate": 230, "lower": 140.8, "upper": 319.2, "sample_size": 23}}
    v = P.traffic_value(m)
    assert v == P.traffic_value(dict(reversed(list(m.items()))))
    assert P.canonical_value(P.TRAFFIC, '  ' + v.replace(",", ", ") + ' ') == v
    assert P.traffic_of(v) == m and P.traffic_of("not json") == {} and P.traffic_of('{"source": "x"}') == {}


@pytest.mark.parametrize("bad", [
    {"source": "ga", "window": "2026-09", "complete": True},
    {"source": "cloudflare", "window": "2026-13", "complete": True},
    {"source": "cloudflare", "window": "2026-09-01", "complete": True},
    {"source": "cloudflare", "window": "2026-09", "complete": "yes"},
    {"source": "cloudflare", "window": "2026-09"},
])
def test_a_traffic_measure_refuses_what_it_cannot_name(bad):
    with pytest.raises(ValueError):
        P.traffic_value(bad)
