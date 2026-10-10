"""Typed predicates + their value-space metadata (the dedup decidability layer).

A Fact-slot is `(subject, predicate)`. Most predicates stay freetext on coarse
notes; only DEMONSTRABLY-high-value predicates are typed (type only what real
contradictions pull into typing). The cut types exactly two, chosen to exercise
BOTH contradiction modes:

- `rename-disposition` — unordered enum (`keep` | `rename:<target>`). A decision,
  so it should be STABLE; two non-superseded incompatible values = a genuine
  CONTRADICTION (no "newer silently wins"). This is what makes the torch/hf-utils
  "keep vs rename" case detectable.
- `version` — semver, legitimately CHANGES, ORDERED. "Newer supersedes older" is
  automatic, so a version bump is healthy evolution, never a contradiction.
  Oracle-backed (a Procedure refreshes it).

Value-space metadata (type/volatility/ordering) is what lets healthy evolution
NOT read as contradiction. Everything here is PURE — no graph, no queue: the
canonical-value function feeds Assertion identity, and the conflict predicates
feed the write-time check + the `contradictions` query.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple

# Value types.
ENUM = "enum"          # A small closed-ish value space (e.g. keep | rename:<target>)
SEMVER = "semver"      # A dotted numeric version
SLUG = "slug"          # A normalized identifier slug (lowercased; e.g. a note name)
FREETEXT = "freetext"  # Unconstrained text (the untyped default)

# Volatility: does the slot's value legitimately change over time?
STABLE = "stable"      # A decision/attribute that should not flip (a flip is suspicious)
CHANGES = "changes"    # Legitimately evolves (version, status, …)

# Ordering: is there a known "later supersedes earlier" relation on values?
ORDER_NONE = "none"      # No ordering — two distinct values genuinely conflict
ORDER_SEMVER = "semver"  # Semver ordering — the greater value supersedes the lesser
ORDER_ENUM = "enum"      # A fixed lifecycle sequence — a later stage supersedes an earlier (see `order_values`)

# Work-item lifecycle (the readiness spine's authored ground truth): a work-item's
# completion state. `open` < `in_progress` < `done` — each forward step is the
# healthy transition, so re-asserting a later state auto-supersedes the prior one
# exactly as a version bump does (never a contradiction; finding 6a27c56f: the
# off-sequence `in_progress` used to land BESIDE `open`, leaving two active).
# `ready`/`blocked` are NEVER asserted here — they are DERIVED on read by the
# readiness projector (the never-hand-maintain-a-derived-field rule: there is no
# write path for them).
TASK_STATE = "task_state"  # The work-item completion predicate
TASK_OPEN = "open"         # Not yet finished
TASK_IN_PROGRESS = "in_progress"  # Actively being worked (between open and done)
TASK_DONE = "done"         # Finished (human-judged now; oracle-derived later)

# Public-facing deliverable lifecycle (ruling 793f025e): asserted `draft` at birth,
# promoted by a human, emitted outward only when `published`. The draft lifecycle
# (ruling a7ca900d (4), item 140981e9): `fixture` sits BELOW draft — a page kept for
# the graph mechanics it exercises, never a promotion candidate, excluded from every
# projection but staging; `retired` is the TERMINAL side-state — an abandoned page
# closed with its provenance kept (asserting it supersedes any active stage; reopening
# is an explicit human `--supersede`). A work's waiting-on-siblings condition is NOT a
# page state — it lives on the work page as a promotion condition (a graph query).
PUBLISH_STATE = "publish_state"  # The deliverable publication predicate
PUBLISH_FIXTURE = "fixture"      # Test fixture: staging only, never promoted
PUBLISH_DRAFT = "draft"          # Born; not reviewed
PUBLISH_REVIEWED = "reviewed"    # A person reviewed it in staging
PUBLISH_PUBLISHED = "published"  # Cleared for the outward emit
PUBLISH_RETIRED = "retired"      # Terminal: abandoned, provenance kept, never emitted

# A page's STANDING (design amendment cbd5f154 (1), amended by 6514869f): the RULING on what a
# page is now, one authored value -- `current` (overhauled by standing rule), `archived` (kept at
# its URL under a historical banner, out of the main navigation: a page cited in volume with no
# repo of its own, or a time capsule), `removed` (ruled off the public site; its EXECUTION is
# publish_state retired plus the destination -- the successor's SUPERSEDES or a RELOCATED_TO edge
# -- landed once the redirect can be projected). Asserted on every archive post, so an archive
# post with none is UNRULED; a born deliverable takes it alike. SUPERSEDED is never a value: it is
# DERIVED at read from a published successor's SUPERSEDES edge.
CURRENCY = "currency"
CURRENCY_CURRENT = "current"
CURRENCY_ARCHIVED = "archived"
CURRENCY_REMOVED = "removed"
CURRENCY_VALUES = (CURRENCY_CURRENT, CURRENCY_ARCHIVED, CURRENCY_REMOVED)
CURRENCY_WITHDRAWN = (CURRENCY_ARCHIVED, CURRENCY_REMOVED)   # standings whose claim support is withdrawn (cbd5f154 (6))

# Review verdicts (design 40622922 (5), item 730e077e): a reviewer's considered "no update
# needed" for ONE upstream change of an approved deliverable — asserted ON the deliverable,
# value = the change KEY the review-frontier projector printed (`<upstream id prefix>@<content
# hash prefix>`, or `@assertion:<id>` / `@edge:<relation>` for the non-content classes). It
# silences exactly that change: the same upstream changing again carries a new key.
REVIEW_VERDICT = "review_verdict"

# A deliverable's TYPE (ruling a7262fe7): the slug of the DeliverableType node whose
# policies govern it (`pure-notes` first). STABLE + unordered: changing a deliverable's
# type is an explicit supersession, never a silent newer-wins.
DELIVERABLE_TYPE = "deliverable_type"

# A deliverable type's KIND and ORIGIN (design amendment c64e07e7): the kind is the site's
# navigation unit (a tutorial and a set of notes sit under different hubs whatever their
# making), the origin how deliverables of the type came to be — `archive` = authored before
# the graph and ingested lossless, public as authored; `born` = produced on the graph, public
# only once its publish_state is `published`. Both are fields of the TYPE, never facts on
# each deliverable, so a post's kind is read through its type.
DELIVERABLE_KINDS = ("tutorial", "notes", "log", "work", "site")
DELIVERABLE_ORIGINS = ("archive", "born")
ORIGIN_ARCHIVE = "archive"
ORIGIN_BORN = "born"

# A Point's ROLE in the deliverables that render it (ruling 96be1528 (1)): `content` (the
# outline), `meta` (topic, motivation, goals, speaker introductions — the standalone type's
# front section), `aside` (excluded by the standalone, kept in source order by the community
# distillation). Asserted on the SHARED substance point — the classification is the point's,
# what each type does with it is the type's role map — proposed by the placement pass and
# confirmed by the human; absent = inherit the parent's, else `content`. Named `point_role`
# because `role` is the register vocabulary (lock / pin / craft …) on Notes.
POINT_ROLE = "point_role"
POINT_ROLE_CONTENT = "content"
POINT_ROLE_META = "meta"
POINT_ROLE_ASIDE = "aside"
POINT_ROLES = (POINT_ROLE_CONTENT, POINT_ROLE_META, POINT_ROLE_ASIDE)

# A Section's ROLE (design ad9bef5a (1), amendment 25a58e0e (2)-(3), ruling 6a203252): what an
# archive tutorial's or log's section DOES for its reader -- the key of a live `section_role`
# vocabulary Entity (intro, setup, step, rationale, how-it-works, background, conclusion) whose
# description and not-for line are the role judge's criteria, so the vocabulary is graph DATA.
# Asserted on a Section of a deliverable whose type declares a `section_roles` map (the
# classification is the Section's, what each role does on the page the type's); an H2 / H3
# Section carries its own, a deeper one INHERITS its nearest ancestor's at read and only an
# override is stored. Proposed by the judge, confirmed by the human; one value, UNORDERED, so a
# changed role is an explicit supersession. Named beside `point_role` (a Point's role).
SECTION_ROLE = "section_role"
ENTITY_SECTION_ROLE = "section_role"

# A deliverable's public PATH on the site (ruling 96aff70e: a URL is a fact with history):
# the active value is where the page lives now, every superseded value is a path it lived at
# before, and the site build projects a redirect from each superseded path to the active one.
# Values are the path verbatim as the site serves it (`/posts/<slug>/`; a pre-Quarto alias as
# its front matter wrote it), never normalized, since normalizing would move the redirect.
# Named `site_path` because a Note's `path` property is its source FILE.
SITE_PATH = "site_path"

# The Tutorials matrix's COVERAGE facts (designs 8cbdc883 / c450133a): what a deliverable
# TEACHES, never what it merely touches -- a training post that loads a public dataset does
# not teach dataset creation. Each value is the key of a vocabulary Entity (sub-kind task or
# stage), so the axes are graph DATA: a task or stage is added, renamed, reordered, merged
# or split by a journaled op, never by a schema release. Multivalued (one post can teach two
# tasks, or two stages); retiring a value is an explicit supersession.
TEACHES_TASK = "teaches_task"
TEACHES_STAGE = "teaches_stage"
ENTITY_TASK = "task"
ENTITY_STAGE = "stage"
COVERAGE_KINDS = {TEACHES_TASK: ENTITY_TASK, TEACHES_STAGE: ENTITY_STAGE}  # predicate -> the Entity sub-kind its values name

# The CATEGORY FACETS' vocabularies (design 0f7fcdcb, amendment 3c5cff97): the TOOLS a post
# teaches or substantially uses (never one it mentions), the SUBJECTS it is about (a field,
# domain or theme spanning tasks and tools) and the MODEL architectures it works with. Each
# entry is an Entity carrying a description and a NOT-FOR line -- the criteria the facet judge
# reads -- so the vocabularies are graph DATA like the matrix's axes: an entry is added,
# renamed, merged, split or retired by a journaled op. Task and stage, the other two chip
# facets, are the matrix's Entities above.
ENTITY_TOOL = "tool"
ENTITY_SUBJECT = "subject"
ENTITY_MODEL = "model"
FACET_KINDS = (ENTITY_TOOL, ENTITY_SUBJECT, ENTITY_MODEL)
# The CONFIRMED category facets (design eefda2dd (4)): what the user confirmed a post is about,
# uses or works with -- SETS of vocabulary keys, checked at write time as teaches_* is (a live,
# unretired entry of the predicate's kind). about_task / about_stage belong to a NON-TUTORIAL
# post only: a tutorial's task and stage chips read teaches_*. Chips render only these facts; a
# judge's proposal (a JUDGED_FACET edge) never reaches a page.
ABOUT_TASK = "about_task"
ABOUT_STAGE = "about_stage"
ABOUT_SUBJECT = "about_subject"
USES_TOOL = "uses_tool"
USES_MODEL = "uses_model"
FACET_PREDICATES = {ABOUT_TASK: ENTITY_TASK, ABOUT_STAGE: ENTITY_STAGE, ABOUT_SUBJECT: ENTITY_SUBJECT,
                    USES_TOOL: ENTITY_TOOL, USES_MODEL: ENTITY_MODEL}  # predicate -> the Entity sub-kind its values name
NON_TUTORIAL_FACETS = (ABOUT_TASK, ABOUT_STAGE)  # refused on a tutorial (its teaches_* say it)

# The verification HARDWARE (design 8cbdc883 (7), amendment c450133a (2)): one Entity per
# compute device (a GPU, a CPU, a board -- never a machine, whose parts change), whatever
# its standing; VERIFIED_ON (deliverable -> device) records what a post actually ran on.
# The device's STANDING is a fact with history: `in-set` backs claims and is the page's
# filter; `fallback` is usable if a project needs it, never claimed; `last-resort` is
# rentable but untried; `capture-only` is a sensor, never a deployment target; `retired`
# is no longer accessible, its past verifications standing as history. Unordered, so a
# change of standing is an explicit supersession and two active standings a hard conflict.
ENTITY_HARDWARE = "hardware"
DEVICE_CLASSES = ("gpu", "cpu", "board", "phone", "sensor", "cloud")
VERIFICATION_STANDING = "verification_standing"
STANDING_IN_SET = "in-set"
VERIFICATION_STANDINGS = (STANDING_IN_SET, "fallback", "last-resort", "capture-only", "retired")
# A verification's evidence BASIS (c450133a (2)): `stated` = the post names the hardware;
# `timeline` = attributed from the user's hardware history (the verification-hardware note).
VERIFICATION_BASES = ("stated", "timeline")

# The CLAIMS (design de808eae (1), amendment 98e99fe5): one Entity per claim the site may make
# about the user's work (sub-kind `claim`, its record = a short statement + a position); a
# deliverable SUPPORTS a claim with a kind on the edge. The claim's STATE is a fact with history:
# `offered` = the site makes the claim (only offered claims reach any public surface);
# `building` = backed work in progress, internal (gap priority, the staging profile);
# `retired` = withdrawn. Unordered, so building -> offered is an explicit supersession and two
# active states a hard conflict. The support KIND says what a deliverable is evidence OF:
# `outcome` (a client result), `method` (how the work is done), `capability` (a tutorial or
# project doing the work), `knowledge` (notes). The BACKING FLOOR (98e99fe5 (3)): an offered
# claim needs a published support whose kind is in BACKING_KINDS -- knowledge never carries
# an offer alone.
ENTITY_CLAIM = "claim"
CLAIM_STATE = "claim_state"
CLAIM_OFFERED = "offered"
CLAIM_STATES = (CLAIM_OFFERED, "building", "retired")
SUPPORT_KINDS = ("outcome", "method", "capability", "knowledge")
BACKING_KINDS = ("outcome", "method", "capability")

# The LIBRARY (design 5de7fae9, design leg 4a4ef27e): what was learned FROM is a `work` Entity
# (a book, a course, a lecture series, a talk, a video, a body of documentation) -- never a
# Series, which is the author's ordering of posts. Its record: a name, a FORM from the closed
# slate below, the author (the citation parts' word), an optional subtitle, published date
# (ISO, at the precision known), ISBN-13 and hand locator -- the date and the ISBN are the
# EDITION READ's until an edition grain exists. A `unit` Entity is one part of a work (a
# chapter, a lecture, a volume -- a volume may carry its own ISBN), minted only
# where an output derives from it; its key is `<work key>/<unit slug>`, so the work is part of
# the unit's identity and the entity op lands the unit's PART_OF edge. An archive deliverable's
# provenance is ONE asserted DERIVED_FROM edge to its unit, or to its work when the work has no
# units. The Library's OUTPUT CLASSES (projects and reproductions, tutorials, standalone
# resources, notes) are `output_class` Entities ordered by position -- the value order as data;
# a DeliverableType names its class in its `output_class` field, beside kind and origin.
ENTITY_WORK = "work"
WORK_FORMS = ("book", "course", "lecture-series", "talk", "video", "documentation")
ENTITY_UNIT = "unit"
UNIT_KEY_SEP = "/"
ENTITY_OUTPUT_CLASS = "output_class"

# The DESIGN SYSTEMS (design 9a7224a7, work item 4765b699): a design system is an Entity of
# sub-kind `design_system`, key = the system's slug, DERIVED by the artifact fold from the
# source journal's captured tokens files (never minted by the entity verb), so a move between
# repos re-keys nothing. A web deliverable's PROFILE (the public site, its staging twin, a
# later audience-scoped site) is a `site_profile` Entity, key `<site>/<profile>`; it renders
# under the system it is STYLED_BY, in the light / dark pair the system's scheme map names
# unless the profile overrides it -- each a slug naming one of the system's own modes, one
# value each, UNORDERED (a change is an explicit supersession).
ENTITY_DESIGN_SYSTEM = "design_system"
ENTITY_SITE_PROFILE = "site_profile"
PROFILE_KEY_SEP = "/"
DESIGN_LIGHT_MODE = "design_light_mode"
DESIGN_DARK_MODE = "design_dark_mode"

# The post page's facts (design 39c51c15, the post page of de808eae (2)):
# REVISED -- a human's statement that a deliverable's content was revised (value = what changed);
# the page's Updated date is the latest one's time, never a commit time (a link fix is no revision).
REVISED = "revised"
# DISCUSSION -- the number of the page's comment thread (a GitHub discussion): the thread keys on
# the deliverable, never on its URL, so a path move keeps its comments (96aff70e).
DISCUSSION = "discussion"
# CONTENT_LICENSE / CODE_LICENSE -- the license of a deliverable class (on the DeliverableType)
# or of one deliverable (an override, on the Note), as an SPDX identifier; a relicensing is a
# dated supersession (c59bba74).
CONTENT_LICENSE = "content_license"
CODE_LICENSE = "code_license"
# LOCATOR -- the public URL of a source a deliverable derives from (on its Reference): the sources
# block renders through it, and a source without one is reported, never an internal id (87aaa212).
LOCATOR = "locator"
# CITATION -- how a source names itself to a reader (on its Reference; amendment 722a8232 (2)): the
# PARTS of its bibliographic citation, never a rendered string -- a work's title, author, part and
# chapter (a book chapter), or the title a source was published under (a video). Observed with the
# locator from the sibling graph that holds the source; a source with no locator renders as its
# citation, a linked one is named by it. The value is `citation_value(parts)`: canonical JSON.
CITATION = "citation"
CITATION_PARTS = ("work", "author", "part", "chapter", "title")
# RESOURCES -- the human-added links a source carries in the sibling graph that holds it (on its
# Reference; capture a2936020 under design 37f82f72 (6)): each link's label, url, role and notes
# slug, observed with the locator and the citation (ruling a7ca900d (3): a human-added link
# attaches upstream, never in a Note body). The value is `resources_value(links)`: canonical JSON.
RESOURCES = "resources"
RESOURCE_FIELDS = ("label", "url", "role", "notes_slug")
# RELATED_JUDGED -- the state a post's related-post judgments were made against (design e09e262b):
# '<question hash>:<judged-state hash>'. A post whose current value differs is STALE -- its
# judgments predate an edit to what was judged, or a change of the question; a re-judge is an
# explicit supersession.
RELATED_JUDGED = "related_judged"
# FACETS_JUDGED -- what a post's facet judgments were made against (design eefda2dd (3)): canonical
# JSON {"criteria": {"<kind>:<key>": <criteria hash>}, "state": <judged-state hash>}, one entry
# per judged (post, vocabulary entry) pair -- the pairs below the store floor included, since
# they leave no edge. A pair is STALE when the post's state or its entry's criteria (with the
# kind's instructions) differ from the record, or it has no entry; a re-judge is an explicit
# supersession.
FACETS_JUDGED = "facets_judged"
# CATEGORY_PAGE_MIN -- how many public posts a category needs for its own page (design a62f2499
# (3)), on the category index's Lens: an entry below it serves a redirect to the category
# listing filtered to it, never a thin page. The value is a positive integer as text; a change
# is an explicit supersession.
CATEGORY_PAGE_MIN = "category_page_min"
# HOME_HUBS / HOME_RECENT -- how many hub pages each map entry of the home page shows, and how many
# recent posts it lists (design e55201e2, amendment 5c3c2662 (5)), on the home Lens: the page's
# numbers are data, never template constants. Each value is a positive integer as text; a change
# is an explicit supersession.
HOME_HUBS = "home_hubs"
HOME_RECENT = "home_recent"

# The PATH MODEL (design ae698640, the walk 57287d1b, the refactor leg ad9bef5a): artifacts,
# environments and concepts are Entity sub-kinds; have / know relations are edges with per-pair
# data; paths, stages, cycles and gaps are DERIVED.
# An ARTIFACT (ae698640 (1)) is one kind for the site and the flywheel: a dataset, a checkpoint, an
# exported or compiled model, predictions, an evaluation report, a Unity package. Its record is its
# own (the owner test): its kind (an `artifact_kind` key), task (a `task` key -- what a model
# artifact does), base model (a `model` key), precision, format, target (a `hardware` or
# `environment` key), license (SPDX), an OBSERVED locator (722a8232), and its LINEAGE -- the
# artifacts it derives from, landed as DERIVED_FROM edges by the entity op. Instance lineage is
# ACYCLIC (a cycle is refused at write time), so a data flywheel is a cycle at the KIND level only.
# Ours vs third-party is derived (an artifact some step on the graph PRODUCES is ours).
ENTITY_ARTIFACT = "artifact"
# ARTIFACT KINDS are vocabulary DATA (ae698640 (2)), the task / stage precedent: added by a
# journaled op, never a schema release. A stage Entity declares its TRANSITIONS over them --
# [{"in": [kinds], "optional": [kinds], "out": kind}] -- so a born step's stage is a MATCH, never
# authored; a transition whose `out` is TRANSITION_ENVIRONMENT produces an environment (Setup).
ENTITY_ARTIFACT_KIND = "artifact_kind"
TRANSITION_ENVIRONMENT = "environment"
TRANSITION_FIELDS = ("in", "optional", "out")
# An ENVIRONMENT (ae698640 (3), ad9bef5a (1)): a named setup state (a Jetson on JetPack 6, a conda
# env with PyTorch + CUDA, the Hailo DFC on x86 Linux, Kaggle API credentials). Its record names
# its PARTS (tool / hardware Entities, each landed PART_OF it), the environments it REQUIRES, and
# its VARIANTS (Mamba / Conda / Google Colab -- ways to one environment, so a page keeps the
# reader's choice). Its versions are a FACT WITH HISTORY on it (ENVIRONMENT_VERSIONS); what a
# deliverable actually ran against stays on VERIFIED_ON's evidence, so staleness is derived.
ENTITY_ENVIRONMENT = "environment"
ENVIRONMENT_PART_KINDS = (ENTITY_TOOL, ENTITY_HARDWARE)
# A CONCEPT (ae698640 (4)): understanding a reader brings, PART_OF one subject Entity (its record's
# `subject`), with a description and a not-for line for the judge (the facet precedent).
ENTITY_CONCEPT = "concept"
# ENVIRONMENT_VERSIONS -- an environment's component versions now, as canonical JSON
# {component: version} (`versions_value`), the shape VERIFIED_ON's evidence carries, so the
# comparison is per component. One value, UNORDERED: an upgrade is an explicit supersession and
# the superseded values are the environment's history.
ENVIRONMENT_VERSIONS = "environment_versions"

# THE EVIDENCE (design 7f315830): traffic and inbound links are dated, sourced OBSERVATIONS on a
# URL node, pulled by one verb, never typed in. A WEB_PATH Entity is one public URL of the site,
# keyed by the site-link resolver's equivalence key (`x.html` = `x`, `dir/` = `dir/index.html` =
# `dir`; query and anchor dropped): traffic belongs to the URL, and a page's share is DERIVED
# through the path ownership (a transferred path keeps its history), never copied. A URL no page
# holds still gets its node, so its traffic is reported, never dropped. An EVIDENCE_SNAPSHOT
# Entity is one pull (key '<source>/<pull date>'): where its raw files live under the evidence
# root and their hashes; every value it yields names it.
ENTITY_WEB_PATH = "web_path"
ENTITY_EVIDENCE_SNAPSHOT = "evidence_snapshot"
# TRAFFIC -- one source's measure of a web_path over one calendar month, as canonical JSON
# (`traffic_value`): the source, the window ('YYYY-MM'), whether the window is complete, and the
# source's own measures (Cloudflare: page loads
# and visits as estimates with a 95% interval and their sample size; Search Console: clicks,
# impressions and the impression-weighted position). The snapshots a measure was computed from are
# EVIDENCED_BY edges from its Assertion (references are edges, 2f8073bb), so an equal re-measure
# from a later pull is the same Assertion with one more edge. A SET slot, one value per (source,
# window): a changed measure supersedes its prior value explicitly, and the superseded values are
# the window's history.
TRAFFIC = "traffic"
TRAFFIC_SOURCES = ("cloudflare", "search-console")
TRAFFIC_KEYS = ("source", "window", "complete")
# THE EVIDENCE ROOT'S SOURCES (the directory under the root, ruling a3c02fb1): the hand exports
# kept as snapshots (a3c02fb1 (4): checks, never measures), the traffic sources, the Search
# Console Links drill-downs read through a signed-in browser (a3c02fb1 (A)) and the verify fetch
# of the linking pages (a3c02fb1 (3)).
EXPORT_SOURCES = ("search-console-export", "cloudflare-export")
LINK_SOURCES = ("search-console-links", "links-fetch")
EVIDENCE_SOURCES = EXPORT_SOURCES + TRAFFIC_SOURCES + LINK_SOURCES
# INBOUND LINKS (design 7f315830 (6), ruling a3c02fb1): the linking page is a web Reference
# (ReferenceNode.WEB; the URL with scheme and host lowercased, the fragment dropped, the query
# kept) and each observation that it links a web_path is a dated REFERENCES edge
# (nodes.inbound_link_edge), one per (reference, web_path, method, date): Google's report
# (method search-console, the Links drill-downs) and the verify fetch (method fetch) are two
# independent observers.
LINK_METHODS = ("search-console", "fetch")
# LINK_OBSERVATION -- one observation of a linking page itself, as canonical JSON
# (`link_observation_value`): the method (search-console-export: listed in a Links export, with
# Google's last crawl where the export states it; fetch: the verify fetch's outcome, status,
# reason and the number of site URLs it found) and the date. A page that refuses the fetch keeps
# Google's edges and gains this; a page no observer targets keeps it alone, never dropped. A SET
# slot: the observations are the page's history, none supersedes another.
LINK_OBSERVATION = "link_observation"
LINK_OBSERVATION_METHODS = ("search-console-export", "fetch")
FETCH_OUTCOMES = ("ok", "gone", "refused", "error", "unreadable")
# INBOUND_COUNT -- a source's count of a web_path's incoming links and linking sites on a date, as
# canonical JSON (`inbound_count_value`): Google's own totals, the check the observed linking
# pages reconcile against. A SET slot, one value per (source, date); an equal count read from a
# drill-down and an export is one Assertion with two EVIDENCED_BY edges.
INBOUND_COUNT = "inbound_count"
INBOUND_COUNT_SOURCES = ("search-console",)

# The relations' ENDPOINTS (ae698640 (5)): relation -> (source kinds, target kinds), each kind an
# Entity sub-kind or one of the node kinds below. The write-time check reads this table, never a
# hand-kept copy. A setup-role Section may PRODUCE its environment (ad9bef5a (1)); an environment's
# own REQUIRES edges land from its record (RECORD_RELATIONS), never from the relate verb.
NODE_DELIVERABLE = "deliverable"   # a deliverable Note
NODE_SECTION = "section"           # a Section of one
NODE_REFERENCE = "reference"       # a Reference node (a web Reference keys a URL)
RELATION_ENDPOINTS = {
    "PRODUCES": ((NODE_DELIVERABLE, NODE_SECTION), (ENTITY_ARTIFACT, ENTITY_ENVIRONMENT)),
    "REQUIRES": ((NODE_DELIVERABLE, ENTITY_ENVIRONMENT), (ENTITY_ARTIFACT, ENTITY_ENVIRONMENT)),
    "TEACHES": ((NODE_DELIVERABLE,), (ENTITY_CONCEPT,)),
    "ASSUMES": ((NODE_DELIVERABLE,), (ENTITY_CONCEPT,)),
    "COVERS": ((ENTITY_UNIT, ENTITY_WORK), (ENTITY_CONCEPT,)),
    "EXPLAINS": ((NODE_DELIVERABLE,), (NODE_DELIVERABLE, ENTITY_ARTIFACT)),
    # A page's DESTINATION (design amendment cbd5f154 (3)/(4)): a published successor SUPERSEDES the
    # page it replaces (superseded is derived from the edge, never stored), and a removed page with
    # no successor is RELOCATED_TO the web Reference of its repo copy's URL. Not path relations.
    "SUPERSEDES": ((NODE_DELIVERABLE,), (NODE_DELIVERABLE,)),
    "RELOCATED_TO": ((NODE_DELIVERABLE,), (NODE_REFERENCE,)),
}
# The PATH MODEL's relations (ae698640 (5)): the ones its reads walk; the destination relations above
# share the endpoint check and the relate verb, never the walk.
PATH_RELATIONS = ("PRODUCES", "REQUIRES", "TEACHES", "ASSUMES", "COVERS", "EXPLAINS")
DESTINATION_RELATIONS = ("SUPERSEDES", "RELOCATED_TO")
RECORD_RELATIONS = {("REQUIRES", ENTITY_ENVIRONMENT)}   # (relation, source kind) landed by the entity record
# A prerequisite's STRENGTH (57287d1b (3)): on the edge, the step's view of the pair.
STRENGTH_REQUIRED = "required"
STRENGTHS = (STRENGTH_REQUIRED, "recommended")
STRENGTH_RELATIONS = ("REQUIRES", "ASSUMES")
# The relations a judge may PROPOSE (ae698640 (5)): the concept judging rides the JUDGED family,
# as the facets do (their `proposes` is the facet predicate).
JUDGEABLE_RELATIONS = ("TEACHES", "ASSUMES", "COVERS")

# The APPROVAL CLASS (the review-frontier's roots): predicate -> the values that count as an
# approval (None = any value). A born `draft` is not an approval; `reviewed`/`published` are.
# Schema DATA, so a future `approved`/`reviewed` predicate joins here, never in the projector.
APPROVAL_CLASS = {PUBLISH_STATE: (PUBLISH_REVIEWED, PUBLISH_PUBLISHED)}


@dataclass(frozen=True)
class Predicate:
    """A typed predicate's value-space (the contradiction decidability metadata)."""
    slug: str          # Predicate slug (the controlled vocabulary key)
    value_type: str    # ENUM | SEMVER | SLUG | FREETEXT
    volatility: str    # STABLE | CHANGES
    ordering: str      # ORDER_NONE | ORDER_SEMVER | ORDER_ENUM
    multivalued: bool = False  # A SET slot: many distinct values coexist, never conflict (e.g. aliases)
    order_values: Optional[Tuple[str, ...]] = None  # For ORDER_ENUM: the lifecycle sequence (earliest -> latest)
    terminal_values: Optional[Tuple[str, ...]] = None  # For ORDER_ENUM: side-states OFF the sequence that close it (a terminal supersedes any active stage; a stage asserted over a terminal is born superseded — reopening is an explicit supersede)


# The typed-predicate registry (controlled-with-free-reuse: novel predicates stay
# untyped freetext until a real contradiction pulls them in here).
PREDICATES = {
    "rename-disposition": Predicate("rename-disposition", ENUM, STABLE, ORDER_NONE),
    "version": Predicate("version", SEMVER, CHANGES, ORDER_SEMVER),
    # A note's confirmed equivalent slugs (drifted `[[wiki-links]]`). Multivalued:
    # one note legitimately carries many aliases, so distinct values NEVER conflict
    # and never supersede — each `aka` is just another accepted name. Born on-graph
    # by the propose/confirm worklist (never auto-guessed); ingest resolves drifted
    # references through them so the dangling edge heals without editing the file.
    "aka": Predicate("aka", SLUG, STABLE, ORDER_NONE, multivalued=True),
    # The work-item lifecycle: an ordered enum (`open` < `in_progress` < `done`), so
    # a task moved forward auto-supersedes its prior state (healthy evolution, never
    # a contradiction) — the version-bump pattern for a closed value-space.
    TASK_STATE: Predicate(TASK_STATE, ENUM, CHANGES, ORDER_ENUM,
                          order_values=(TASK_OPEN, TASK_IN_PROGRESS, TASK_DONE)),
    # Public-facing deliverable lifecycle (user ruling 793f025e, 2026-09-03: DRAFT AT
    # BIRTH): every non-code deliverable born on-graph is asserted `draft` in the same
    # invocation that mints it; `draft` < `reviewed` < `published` is an ordered enum so
    # a human promotion auto-supersedes the prior stage, and every outward emit (the
    # website root first — item 6eba8815) is gated on a single active `published`.
    # The draft lifecycle (ruling a7ca900d (4), item 140981e9): `fixture` BELOW draft (a
    # re-statement draft -> fixture is a demotion, so it is born superseded unless the human
    # names the draft with --supersede — the explicit-demotion path); `retired` TERMINAL.
    PUBLISH_STATE: Predicate(PUBLISH_STATE, ENUM, CHANGES, ORDER_ENUM,
                             order_values=(PUBLISH_FIXTURE, PUBLISH_DRAFT, PUBLISH_REVIEWED, PUBLISH_PUBLISHED),
                             terminal_values=(PUBLISH_RETIRED,)),
    # A page's standing (cbd5f154 (1), 6514869f): a closed slate, UNORDERED, so a re-ruling is an
    # explicit supersession and two active standings are a HARD contradiction.
    CURRENCY: Predicate(CURRENCY, ENUM, CHANGES, ORDER_NONE),
    # Review verdicts (design 40622922 (5)): a SET of acknowledged change keys on an approved
    # deliverable — many coexist and never conflict; retiring one is an explicit supersession.
    # Freetext (the key is derived by the projector, never typed by hand from memory).
    REVIEW_VERDICT: Predicate(REVIEW_VERDICT, FREETEXT, STABLE, ORDER_NONE, multivalued=True),
    # The deliverable-type binding (ruling a7262fe7): a slug naming the DeliverableType node.
    # Typed so a disagreement is a HARD contradiction (one deliverable, one type) and a
    # re-type is an explicit supersession.
    DELIVERABLE_TYPE: Predicate(DELIVERABLE_TYPE, SLUG, STABLE, ORDER_NONE),
    # A point's role (ruling 96be1528 (1)): a closed slate, UNORDERED so a re-role is an explicit
    # supersession — an un-superseded flip (content beside aside) is a HARD contradiction.
    POINT_ROLE: Predicate(POINT_ROLE, ENUM, CHANGES, ORDER_NONE),
    # A Section's role (6a203252): one vocabulary key, UNORDERED, so a change is an explicit
    # supersession and two active roles are a HARD contradiction.
    SECTION_ROLE: Predicate(SECTION_ROLE, SLUG, CHANGES, ORDER_NONE),
    # A deliverable's public path (ruling 96aff70e): it legitimately CHANGES (a move), but
    # UNORDERED, so a move is an explicit supersession and two active paths are a HARD
    # contradiction (one page, one current URL; the redirect projection must never fork).
    # A back-filled prior path is written born superseded (`--superseded-by`).
    SITE_PATH: Predicate(SITE_PATH, FREETEXT, CHANGES, ORDER_NONE),
    # Coverage (designs 8cbdc883 / c450133a): SETS of vocabulary keys -- distinct values
    # coexist and never conflict; dropping one is an explicit supersession.
    TEACHES_TASK: Predicate(TEACHES_TASK, SLUG, STABLE, ORDER_NONE, multivalued=True),
    TEACHES_STAGE: Predicate(TEACHES_STAGE, SLUG, STABLE, ORDER_NONE, multivalued=True),
    # The confirmed category facets (eefda2dd (4)): sets of vocabulary keys like coverage.
    ABOUT_TASK: Predicate(ABOUT_TASK, SLUG, STABLE, ORDER_NONE, multivalued=True),
    ABOUT_STAGE: Predicate(ABOUT_STAGE, SLUG, STABLE, ORDER_NONE, multivalued=True),
    ABOUT_SUBJECT: Predicate(ABOUT_SUBJECT, SLUG, STABLE, ORDER_NONE, multivalued=True),
    USES_TOOL: Predicate(USES_TOOL, SLUG, STABLE, ORDER_NONE, multivalued=True),
    USES_MODEL: Predicate(USES_MODEL, SLUG, STABLE, ORDER_NONE, multivalued=True),
    # A device's verification standing (8cbdc883 (7)): a closed slate, UNORDERED, so a change
    # is an explicit supersession (the Arc A770's exit from the set is a dated assertion).
    VERIFICATION_STANDING: Predicate(VERIFICATION_STANDING, ENUM, CHANGES, ORDER_NONE),
    # A claim's state (98e99fe5 (1)): a closed slate, UNORDERED, so a promotion is an explicit
    # supersession (building -> offered is a dated assertion) and two active states conflict.
    CLAIM_STATE: Predicate(CLAIM_STATE, ENUM, CHANGES, ORDER_NONE),
    # The post page's facts (39c51c15): revisions ACCUMULATE (a set -- each a dated statement,
    # never a conflict); a thread, a license and a locator are one value each, UNORDERED, so a
    # change is an explicit supersession and two active values are a HARD contradiction.
    REVISED: Predicate(REVISED, FREETEXT, STABLE, ORDER_NONE, multivalued=True),
    DISCUSSION: Predicate(DISCUSSION, FREETEXT, CHANGES, ORDER_NONE),
    CONTENT_LICENSE: Predicate(CONTENT_LICENSE, SLUG, CHANGES, ORDER_NONE),
    CODE_LICENSE: Predicate(CODE_LICENSE, SLUG, CHANGES, ORDER_NONE),
    # A site profile's light / dark override (9a7224a7 (3)): one mode each, UNORDERED.
    DESIGN_LIGHT_MODE: Predicate(DESIGN_LIGHT_MODE, SLUG, CHANGES, ORDER_NONE),
    DESIGN_DARK_MODE: Predicate(DESIGN_DARK_MODE, SLUG, CHANGES, ORDER_NONE),
    LOCATOR: Predicate(LOCATOR, FREETEXT, CHANGES, ORDER_NONE),
    # A source's citation (722a8232 (2)): one value, UNORDERED, so a corrected citation is an
    # explicit supersession and two active citations are a HARD contradiction.
    CITATION: Predicate(CITATION, FREETEXT, CHANGES, ORDER_NONE),
    # A source's human-added links (a2936020): one value (the whole set), UNORDERED, so a changed
    # set is an explicit supersession and two active sets are a HARD contradiction.
    RESOURCES: Predicate(RESOURCES, FREETEXT, CHANGES, ORDER_NONE),
    # A post's judged state (e09e262b): one value, UNORDERED, so a re-judge is an explicit
    # supersession and two active values are a HARD contradiction.
    RELATED_JUDGED: Predicate(RELATED_JUDGED, FREETEXT, CHANGES, ORDER_NONE),
    # A post's facet record (eefda2dd (3)): one value, UNORDERED, as related_judged.
    FACETS_JUDGED: Predicate(FACETS_JUDGED, FREETEXT, CHANGES, ORDER_NONE),
    # The category page threshold (a62f2499 (3)): one value, UNORDERED, as related_judged.
    CATEGORY_PAGE_MIN: Predicate(CATEGORY_PAGE_MIN, FREETEXT, CHANGES, ORDER_NONE),
    # The home page's numbers (e55201e2, 5c3c2662 (5)): one value each, UNORDERED, as category_page_min.
    HOME_HUBS: Predicate(HOME_HUBS, FREETEXT, CHANGES, ORDER_NONE),
    HOME_RECENT: Predicate(HOME_RECENT, FREETEXT, CHANGES, ORDER_NONE),
    # An environment's versions (ae698640 (3)): one value, UNORDERED, so an upgrade is an explicit
    # supersession and the superseded values are its history.
    ENVIRONMENT_VERSIONS: Predicate(ENVIRONMENT_VERSIONS, FREETEXT, CHANGES, ORDER_NONE),
    TRAFFIC: Predicate(TRAFFIC, FREETEXT, CHANGES, ORDER_NONE, multivalued=True),
    # Inbound-link evidence (ruling a3c02fb1): SET slots of dated observations, as traffic.
    LINK_OBSERVATION: Predicate(LINK_OBSERVATION, FREETEXT, CHANGES, ORDER_NONE, multivalued=True),
    INBOUND_COUNT: Predicate(INBOUND_COUNT, FREETEXT, CHANGES, ORDER_NONE, multivalued=True),
    # Cross-graph derivation (finding 0154f5e4; the INTERIM form until the federation seam
    # carries a typed cross-graph reference edge): a born deliverable names the FOREIGN
    # nodes it drew on as `<graph-key>:<node-id>` values — a SET (one deliverable derives
    # from many strata / segments / sources; values coexist, never conflict; retiring one
    # is an explicit supersession). Replayable and predicate-queryable, so provenance across
    # a db boundary is on-graph rather than prose; converts mechanically to the edge form
    # once it exists (same subject, same foreign ids).
    "derived_from": Predicate("derived_from", FREETEXT, STABLE, ORDER_NONE, multivalued=True),
    # Priority/gating judgments on work items (axis F: the lead's sequencing prose
    # becomes asserted, filterable facts). Deliberately UNORDERED: a priority
    # change must explicitly supersede, so an un-superseded flip is a HARD
    # contradiction instead of a silent newer-wins.
    "priority": Predicate("priority", ENUM, CHANGES, ORDER_NONE),
    # Model-artifact lifecycle for register rendering (current | candidate |
    # retired). Unordered for the same reason: promotion/demotion is an explicit
    # supersession, never automatic.
    "model-status": Predicate("model-status", ENUM, CHANGES, ORDER_NONE),
}

# Predicate FAMILIES (prefix-typed): a slug with no exact entry resolves to its
# family's value-space. `pin.<role>` (axis F): role-typed pins asserted FROM an
# anchor — subject = the anchor, value = "<node-id> — <gloss>" (first token is the
# pinned node id; the gloss carries the push-hook lesson: a terse COMPLETE
# resident line, because a node's description buries the actionable point).
# Multivalued: an anchor legitimately holds many pins per role — they coexist,
# never conflict; retiring a pin is an explicit supersession.
PREDICATE_FAMILIES = {
    "pin.": Predicate("pin.*", FREETEXT, CHANGES, ORDER_NONE, multivalued=True),
}


def get_predicate(
    slug: str,  # Predicate slug
) -> Optional[Predicate]:  # The typed predicate, or None when untyped
    """Look up a predicate's value-space; exact entry first, then a prefix FAMILY
    (`pin.<role>` -> the `pin.` family); None = an untyped freetext predicate."""
    p = PREDICATES.get(slug)
    if p is not None:
        return p
    for prefix, family in PREDICATE_FAMILIES.items():
        if slug.startswith(prefix) and len(slug) > len(prefix):
            return family
    return None


def is_typed(
    slug: str,  # Predicate slug
) -> bool:  # True when the predicate carries a value-space
    """Whether the predicate carries a value-space (exact entry OR prefix family).

    Family members MUST count as typed: `soft_conflict` fires on untyped slots
    with disagreeing values, so a `pin.<role>` SET slot reading as untyped would
    spam the worklist with every multi-pin anchor."""
    return get_predicate(slug) is not None


def is_ordered(
    slug: str,  # Predicate slug
) -> bool:  # True when the predicate has a known value ordering
    """Whether the predicate's values have a "later supersedes earlier" ordering."""
    p = get_predicate(slug)
    return bool(p) and p.ordering != ORDER_NONE


def is_multivalued(
    slug: str,  # Predicate slug
) -> bool:  # True when the slot legitimately carries many coexisting values
    """Whether the predicate is a SET slot (distinct values coexist, never conflict)."""
    p = get_predicate(slug)
    return bool(p) and p.multivalued


def _parse_semver(
    value: str,  # A version string (optionally "v"-prefixed)
) -> Optional[Tuple[int, ...]]:  # Numeric release tuple, or None when unparseable
    """Parse the numeric release of a semver string; None when not comparable.

    Only the dotted numeric core is used for ordering (a pre-release/build suffix
    makes the tuple unparseable -> incomparable -> handled as no-supersede)."""
    s = value.strip().lstrip("vV").strip()
    if not s:
        return None
    core = s.split("-")[0].split("+")[0]
    parts = core.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def canonical_value(
    slug: str,  # Predicate slug
    value: str,  # Raw asserted value
) -> str:  # Canonical form used in Assertion identity + conflict comparison
    """Canonicalize a value so equal claims collapse to one Assertion.

    Semver: strip a leading "v" + whitespace (so "v0.0.51" == "0.0.51"). Enum:
    lowercased + stripped (repo names are lowercase; "rename:X" normalizes). Other
    (freetext/untyped): whitespace-stripped only, case preserved."""
    p = get_predicate(slug)
    v = str(value).strip()
    if p is None:
        return v
    if p.value_type == SEMVER:
        return v.lstrip("vV").strip()
    if p.value_type in (ENUM, SLUG):
        return v.lower()
    if slug == ENVIRONMENT_VERSIONS:   # a component map: equal maps are one Assertion however written
        try:
            return versions_value(json.loads(v))
        except (ValueError, AttributeError):
            return v
    if slug == TRAFFIC:   # a measure: equal measures are one Assertion however written
        try:
            return traffic_value(json.loads(v))
        except (ValueError, TypeError, AttributeError):
            return v
    if slug in (LINK_OBSERVATION, INBOUND_COUNT):   # an observation: equal ones are one Assertion
        try:
            m = json.loads(v)
            return link_observation_value(m) if slug == LINK_OBSERVATION else inbound_count_value(m)
        except (ValueError, TypeError, AttributeError):
            return v
    return v


def citation_value(
    parts: Dict[str, Any],  # A citation's parts (keys from CITATION_PARTS; blanks dropped)
) -> str:  # The `citation` value: canonical JSON, so equal parts are one Assertion
    """A citation's parts as the fact's value -- sorted keys, compact separators, blanks dropped;
    a key outside CITATION_PARTS refuses (the parts are the vocabulary, never free keys)."""
    unknown = sorted(set(parts) - set(CITATION_PARTS))
    if unknown:
        raise ValueError(f"citation parts outside {CITATION_PARTS}: {unknown}")
    kept = {k: v for k, v in parts.items() if v not in (None, "")}
    if not kept:
        raise ValueError("a citation needs at least one part")
    return json.dumps(kept, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def citation_parts(
    value: str,  # A `citation` fact's value
) -> Dict[str, Any]:  # Its parts ({} for a value that is not a citation)
    """The inverse of `citation_value`; a malformed value reads as no parts."""
    try:
        parts = json.loads(value)
    except (TypeError, ValueError):
        return {}
    if not isinstance(parts, dict):
        return {}
    return {k: v for k, v in parts.items() if k in CITATION_PARTS}


def resources_value(
    links: Iterable[Dict[str, Any]],  # A source's human-added links (keys from RESOURCE_FIELDS; blanks dropped)
) -> str:  # The `resources` value: canonical JSON, the links in role then label order
    """A source's links as the fact's value -- each link's fields sorted, the links in role then
    label order, so an equal set is one Assertion; a key outside RESOURCE_FIELDS, or a link with
    no label or nothing to follow (neither url nor notes slug), refuses. No links = '[]'."""
    rows = []
    for link in links:
        unknown = sorted(set(link) - set(RESOURCE_FIELDS))
        if unknown:
            raise ValueError(f"resource fields outside {RESOURCE_FIELDS}: {unknown}")
        kept = {k: v for k, v in link.items() if v not in (None, "")}
        if not kept.get("label") or not (kept.get("url") or kept.get("notes_slug")):
            raise ValueError(f"a resource link needs a label and a url or notes slug: {link}")
        rows.append(kept)
    rows.sort(key=lambda r: (str(r.get("role") or ""), str(r["label"]), str(r.get("url") or "")))
    return json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def resources_links(
    value: str,  # A `resources` fact's value
) -> list:  # Its links ([] for a value that is not a link list)
    """The inverse of `resources_value`; a malformed value reads as no links."""
    try:
        rows = json.loads(value)
    except (TypeError, ValueError):
        return []
    if not isinstance(rows, list):
        return []
    return [{k: v for k, v in r.items() if k in RESOURCE_FIELDS} for r in rows if isinstance(r, dict)]


def versions_value(
    versions: Dict[str, Any],  # An environment's component versions ({component: version}; blanks dropped)
) -> str:  # The `environment_versions` value: canonical JSON, so an equal map is one Assertion
    """An environment's versions as the fact's value -- sorted keys, compact separators, blanks
    dropped; an empty map or a non-text version refuses."""
    kept = {str(k).strip(): v.strip() for k, v in versions.items()
            if isinstance(v, str) and v.strip() and str(k).strip()}
    if len(kept) != len([v for v in versions.values() if v not in (None, "")]):
        raise ValueError(f"environment versions are text keyed by component: {versions}")
    if not kept:
        raise ValueError("environment versions need at least one component")
    return json.dumps(kept, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def versions_of(
    value: str,  # An `environment_versions` fact's value
) -> Dict[str, str]:  # Its map ({} for a value that is not one)
    """The inverse of `versions_value`; a malformed value reads as no versions."""
    try:
        m = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return {str(k): str(v) for k, v in m.items()} if isinstance(m, dict) else {}


def traffic_value(
    measure: Dict[str, Any],  # One source's measure of a web_path over one month (TRAFFIC_KEYS + the source's measures)
) -> str:  # The `traffic` value: canonical JSON, so an equal measure is one Assertion
    """A traffic measure as the fact's value -- sorted keys, compact separators. Refuses a missing
    key, a source outside TRAFFIC_SOURCES, a window that is not a calendar month ('YYYY-MM') or a
    non-boolean `complete`."""
    missing = [k for k in TRAFFIC_KEYS if k not in measure]
    if missing:
        raise ValueError(f"a traffic measure needs {TRAFFIC_KEYS}: missing {missing}")
    if measure["source"] not in TRAFFIC_SOURCES:
        raise ValueError(f"traffic source outside {TRAFFIC_SOURCES}: {measure['source']!r}")
    w = str(measure["window"])
    if not (len(w) == 7 and w[4] == "-" and w[:4].isdigit() and w[5:].isdigit() and 1 <= int(w[5:]) <= 12):
        raise ValueError(f"a traffic window is a calendar month 'YYYY-MM': {w!r}")
    if not isinstance(measure["complete"], bool):
        raise ValueError(f"traffic `complete` is a boolean: {measure['complete']!r}")
    return json.dumps(measure, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def traffic_of(
    value: str,  # A `traffic` fact's value
) -> Dict[str, Any]:  # Its measure ({} for a value that is not one)
    """The inverse of `traffic_value`; a malformed value reads as no measure."""
    try:
        m = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return m if isinstance(m, dict) and all(k in m for k in TRAFFIC_KEYS) else {}


def version_key(
    version: str,  # A component version as written ("2.4.1", "6.0", "12.4", "r36.3", "v1.13.0")
) -> Optional[tuple]:  # A comparable key, or None when it carries no number
    """A component version's ordering key for staleness: its runs of digits and letters in order,
    a number below any word at one position (so 2.4 < 2.4.1 < 2.4.rc1 is never claimed -- a word
    only compares with a word). A leading `v` is dropped; a version with no digit is incomparable."""
    import re
    s = version.strip().lower()
    if s.startswith("v") and s[1:2].isdigit():
        s = s[1:]
    toks = re.findall(r"\d+|[a-z]+", s)
    if not any(t.isdigit() for t in toks):
        return None
    return tuple((0, int(t), "") if t.isdigit() else (1, 0, t) for t in toks)


def transition_matches(
    transition: Dict[str, Any],  # A stage's transition ({in, optional, out})
    inputs: Iterable[str],       # A step's input artifact kinds
    outputs: Iterable[str],      # A step's output kinds (artifact kinds, or TRANSITION_ENVIRONMENT)
) -> bool:
    """Does a step match a stage's transition (ae698640 (2))? Its outputs include the transition's
    `out`, its inputs include every `in` kind, and every input kind is `in` or `optional`."""
    ins, outs = set(inputs), set(outputs)
    need, may = set(transition.get("in") or ()), set(transition.get("optional") or ())
    return transition.get("out") in outs and need <= ins and ins <= need | may


def ordering_supersedes(
    slug: str,   # Predicate slug
    new_value: str,  # The newly asserted value
    old_value: str,  # An existing value
) -> Optional[bool]:
    """For an ordered predicate, does `new_value` supersede `old_value`?

    Returns True (new is later), False (old is later, new is born superseded),
    or None (unordered predicate, equal values, or incomparable -> no auto
    supersession; an unordered conflict is decided by `values_conflict`)."""
    p = get_predicate(slug)
    if p is None or p.ordering == ORDER_NONE:
        return None
    if p.ordering == ORDER_SEMVER:
        a, b = _parse_semver(new_value), _parse_semver(old_value)
        if a is None or b is None or a == b:
            return None
        return a > b
    if p.ordering == ORDER_ENUM:
        seq = p.order_values or ()
        term = p.terminal_values or ()
        a, b = canonical_value(slug, new_value), canonical_value(slug, old_value)
        if a == b:
            return None
        # Terminal side-states (item 140981e9): closing supersedes ANY active stage (or another
        # terminal); a stage asserted OVER a terminal is born superseded — reopening a retired
        # deliverable is an explicit human `--supersede`, never an accident of ordering.
        if a in term:
            return True if (b in seq or b in term) else None
        if b in term:
            return False if a in seq else None
        if a not in seq or b not in seq:
            return None  # off-sequence value -> no auto supersession
        return seq.index(a) > seq.index(b)
    return None


def is_terminal(
    slug: str,   # Predicate slug
    value: str,  # A value on that predicate
) -> bool:
    """Whether `value` is a TERMINAL side-state of an ordered enum (item 140981e9): off the
    lifecycle sequence, it closes the slot — `publish_state=retired` today. False for
    untyped predicates, unordered ones, and in-sequence stages."""
    p = get_predicate(slug)
    if p is None or p.ordering != ORDER_ENUM or not p.terminal_values:
        return False
    return canonical_value(slug, value) in p.terminal_values


def values_conflict(
    slug: str,   # Predicate slug
    value_a: str,  # One value
    value_b: str,  # Another value
) -> bool:  # True only for a HARD (typed, unordered, incompatible) conflict
    """Whether two values are a HARD contradiction under the value-space.

    Only typed UNORDERED predicates produce hard conflicts: distinct canonical
    values disagree (the rename-disposition case). Ordered predicates never
    conflict (newer supersedes); multivalued set predicates never conflict
    (values coexist); untyped predicates are SOFT (worklist, not a hard
    contradiction) so this returns False for them."""
    p = get_predicate(slug)
    if p is None or p.ordering != ORDER_NONE or p.multivalued:
        return False
    return canonical_value(slug, value_a) != canonical_value(slug, value_b)


def active_contradiction(
    slug: str,                  # Predicate slug
    active_values: Iterable[str],  # Canonical-or-raw values of the slot's active assertions
) -> bool:  # True when the active set is a hard contradiction
    """Whether a slot's ACTIVE (non-superseded) values form a hard contradiction.

    Hard = a typed unordered predicate carrying >=2 distinct canonical values."""
    p = get_predicate(slug)
    if p is None or p.ordering != ORDER_NONE or p.multivalued:
        return False
    canon = {canonical_value(slug, v) for v in active_values}
    return len(canon) >= 2


def soft_conflict(
    slug: str,                  # Predicate slug
    active_values: Iterable[str],  # Values of the slot's active assertions
) -> bool:  # True when an UNtyped slot carries >=2 distinct values
    """Whether an UNTYPED slot's active values disagree (a worklist candidate).

    Untyped predicates can't be adjudicated mechanically, so a disagreement is a
    SOFT propose-to-the-worklist signal, never a hard contradiction."""
    if is_typed(slug):
        return False
    canon = {str(v).strip() for v in active_values}
    return len(canon) >= 2


def is_approval(
    slug: str,   # Predicate slug
    value: str,  # The asserted value
) -> bool:  # True when an active (slug, value) assertion is an APPROVAL the review frontier walks from
    """Whether an assertion is approval-class (`APPROVAL_CLASS` — schema data, design 40622922).

    `publish_state=draft` is a birth, not an approval; `reviewed`/`published` are. A
    predicate listed with `None` counts at any value. Values compare canonically."""
    allowed = APPROVAL_CLASS.get(slug, ())
    if slug not in APPROVAL_CLASS:
        return False
    if allowed is None:
        return True
    return canonical_value(slug, value) in {canonical_value(slug, v) for v in allowed}


def _observation_date(value: Any, what: str) -> str:  # A 'YYYY-MM-DD' date, or a ValueError naming the field
    import datetime
    d = str(value)
    try:
        if len(d) != 10 or datetime.date.fromisoformat(d).isoformat() != d:
            raise ValueError
    except ValueError:
        raise ValueError(f"{what} is a date 'YYYY-MM-DD': {value!r}") from None
    return d


def link_observation_value(
    obs: Dict[str, Any],  # One observation of a linking page: method, date and its findings
) -> str:  # The `link_observation` value: canonical JSON, so an equal observation is one Assertion
    """A linking page's observation as the fact's value (ruling a3c02fb1 (1)) -- sorted keys, compact
    separators. Refuses a method outside LINK_OBSERVATION_METHODS, a date that is not 'YYYY-MM-DD',
    and a fetch without an outcome in FETCH_OUTCOMES."""
    if obs.get("method") not in LINK_OBSERVATION_METHODS:
        raise ValueError(f"a link observation's method is one of {LINK_OBSERVATION_METHODS}: {obs.get('method')!r}")
    _observation_date(obs.get("date"), "a link observation's date")
    if obs["method"] == "fetch" and obs.get("outcome") not in FETCH_OUTCOMES:
        raise ValueError(f"a fetch observation's outcome is one of {FETCH_OUTCOMES}: {obs.get('outcome')!r}")
    return json.dumps(obs, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def inbound_count_value(
    count: Dict[str, Any],  # A source's totals for one web_path on a date: source, date, links, sites
) -> str:  # The `inbound_count` value: canonical JSON
    """A source's inbound-link totals as the fact's value (ruling a3c02fb1). Refuses a source outside
    INBOUND_COUNT_SOURCES, a date that is not 'YYYY-MM-DD' and counts that are not whole numbers."""
    if count.get("source") not in INBOUND_COUNT_SOURCES:
        raise ValueError(f"an inbound count's source is one of {INBOUND_COUNT_SOURCES}: {count.get('source')!r}")
    _observation_date(count.get("date"), "an inbound count's date")
    for k in ("links", "sites"):
        if not isinstance(count.get(k), int) or isinstance(count.get(k), bool) or count[k] < 0:
            raise ValueError(f"an inbound count's {k} is a whole number: {count.get(k)!r}")
    return json.dumps(count, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def observation_of(
    value: str,  # A `link_observation` or `inbound_count` value
) -> Dict[str, Any]:  # Its observation ({} for a value that is not one)
    """The inverse of `link_observation_value` / `inbound_count_value`; a malformed value reads as none."""
    try:
        m = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return m if isinstance(m, dict) and m.get("date") else {}
