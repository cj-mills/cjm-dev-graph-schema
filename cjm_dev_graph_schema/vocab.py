"""The reserved node-kind and edge-relation vocabulary for the dev/decision-provenance domain.

The full vocabulary is reserved UP FRONT (reserve-enum-values-up-front): the
coarse tier (`Note` + `REFERENCES`) is implemented first, but the node kinds and
edge relations of the locked schema model are declared here so subscribers wire
forward and the fine tier slots in without a vocabulary churn.

Structural spine relations (NEXT / PART_OF / STARTS_WITH) and the overlay trust
relations (SUPERSEDES / DERIVED_FROM / PRODUCED) are NOT redefined here — they
are domain-neutral and owned by `cjm_context_graph_layer.grammar`. This module
declares only the DEV-DOMAIN relations (the layer's `make_edge` accepts any
relation string; domain relations belong in the schema lib, not the layer).
"""

from cjm_context_graph_layer.grammar import OverlayRelations, SpineRelations


class DevNodeKinds:
    """Node labels of the dev/decision-provenance schema (the locked model).

    `NOTE` is the coarse-tier document node (one per memory/markdown file) that
    lands first; the remaining kinds are reserved for the fine tier, where a
    note's contents are promoted into Decisions, layered Assertions on Fact-slots,
    Evidence, etc. (coarse -> fine, node-hood earned by reference)."""
    NOTE = "Note"            # Coarse tier: one decomposed markdown/memory document
    DECISION = "Decision"    # A decision, with rationale recorded as SUPPORTED_BY edges (not prose)
    FACT_SLOT = "FactSlot"   # A (subject, predicate) slot holding layered, supersede-able assertions
    ASSERTION = "Assertion"  # One provenance-carrying value claimed for a Fact-slot
    EVIDENCE = "Evidence"    # An evidence / finding (the ledger-entry analogue)
    THREAD = "Thread"        # A unit of work bundling decisions + evidence + lifecycle status
    SESSION = "Session"      # A working session (decisions/facts are PRODUCED_IN / DECIDED_IN one)
    PROCEDURE = "Procedure"  # A codified script + methodology; can be an oracle slot's value-source
    ENTITY = "Entity"        # A repo/lib, stage, capability, person, or abstract term (incl. class-subjects)

    @classmethod
    def all(cls) -> list:  # All dev-schema node labels
        """All dev-schema node labels."""
        return [cls.NOTE, cls.DECISION, cls.FACT_SLOT, cls.ASSERTION, cls.EVIDENCE,
                cls.THREAD, cls.SESSION, cls.PROCEDURE, cls.ENTITY]


class DevRelations:
    """Dev-domain edge relations (reserved up front).

    The overlay relations this domain also uses — `SUPERSEDES`, `DERIVED_FROM`,
    `PRODUCED` — are re-exposed via `OverlayRelations` for convenience but remain
    owned by the layer. `REFERENCES` (the `[[wiki-link]]`) lands first."""
    REFERENCES = "REFERENCES"      # Soft cross-reference (the [[wiki-link]]); coarse tier
    ABOUT = "ABOUT"                # Node -> the repo / stage / Thread it concerns (incl. Fact-slot -> its subject)
    ON_SLOT = "ON_SLOT"            # Assertion -> the Fact-slot it claims a value for (fine tier)
    DECIDED_IN = "DECIDED_IN"      # Decision -> the Session it was decided in
    PRODUCED_IN = "PRODUCED_IN"    # Node -> the Session that produced it
    EVIDENCED_BY = "EVIDENCED_BY"  # Claim -> supporting Evidence
    DEPENDS_ON = "DEPENDS_ON"      # Entity/Thread -> what it depends on
    LANDS_AT = "LANDS_AT"          # Thread -> the Stage it lands at
    CONTRADICTS = "CONTRADICTS"    # Assertion <-> conflicting Assertion (the dedup substrate)
    SUPPORTED_BY = "SUPPORTED_BY"  # Decision -> premise Assertion (the reasoning substrate)

    # Overlay relations this domain reuses (owned by the layer; re-exposed for convenience).
    SUPERSEDES = OverlayRelations.SUPERSEDES
    DERIVED_FROM = OverlayRelations.DERIVED_FROM
    PRODUCED = OverlayRelations.PRODUCED

    @classmethod
    def all(cls) -> list:  # All dev-domain relations (excluding the layer-owned spine relations)
        """All dev-domain edge relations, including the reused overlay relations."""
        return [cls.REFERENCES, cls.ABOUT, cls.ON_SLOT, cls.DECIDED_IN, cls.PRODUCED_IN,
                cls.EVIDENCED_BY, cls.DEPENDS_ON, cls.LANDS_AT, cls.CONTRADICTS, cls.SUPPORTED_BY,
                cls.SUPERSEDES, cls.DERIVED_FROM, cls.PRODUCED]


# The dev domain's structural ordering relations are the layer's spine relations
# (a domain declares which it uses; dev-history has several partial orderings —
# temporal/dependency/stage — layered later atop the same NEXT/PART_OF grammar).
DEV_SPINE_RELATIONS = SpineRelations
