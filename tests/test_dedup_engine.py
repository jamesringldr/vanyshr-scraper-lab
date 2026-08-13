"""
Tests for dedup_engine: does it group one person's records, and keep two
people apart?

The reference case throughout is James Oehring, because the four brokers
disagree about him in exactly the ways that make this hard:

    field     fps        npd        anywho          zaba
    age       61         63         37              37
    address   Cameron    Cameron    Kansas City     Cameron

All four are the same person, provable from three signals the scrapers now
extract: the phone (816) 632-2218 appears in all four, the relative
"Rickilinda" appears in all four, and 413 Lovers Ln is the current address for
three of them and sits in AnyWho's *address history*. Age is the only field
that disagrees, which is why it must never be a matching key.

The opposite risk is the household: James and Rickilinda Oehring share an
address and a landline. Weighting address and phone highly -- which is right
for matching one person across brokers -- is exactly what merges spouses, so
the name has to gate the result rather than just contribute to it.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from data_models import BrokerName, ScrapeResult, SummaryResult  # noqa: E402
from dedup_engine import DedupEngine  # noqa: E402

pytestmark = pytest.mark.unit


@pytest.fixture
def engine():
    return DedupEngine()


def summary(broker, name, address="", age=None, age_range="", phone="",
            relatives="", previous_addresses=""):
    return SummaryResult(
        broker=broker, full_name=name, address=address, age=age,
        age_range=age_range, phone=phone, relatives=relatives,
        previous_addresses=previous_addresses,
    )


# The four records as the scrapers actually produce them
FPS = summary(BrokerName.FPS, "James Oehring", "413 Lovers Ln, Cameron MO 64429",
              age=61, phone="(816) 632-2218",
              relatives="Rickilinda Oehring, Robert Mctarsney, Albert Mcgee")
NPD = summary(BrokerName.NPD, "James Oehring", "413 Lovers Ln, Cameron, MO",
              age_range="62", phone="(816) 632-2218, (816) 225-8592",
              relatives="Rickilinda Oehring")
ANYWHO = summary(BrokerName.ANYWHO, "James A Oehring",
                 "1225 Union Ave, Apt 502, Kansas City, MO",
                 age_range="37", phone="(816) 632-2218",
                 relatives="Rickilinda Oehring",
                 previous_addresses="413 Lovers Ln, Cameron, MO; 380 W 22nd St, Kansas City, MO")
ZABA = summary(BrokerName.ZABA, "James Oehring", "413 Lovers LN, Cameron, Missouri 64429",
               age=37, phone="(816) 225-8592, (816) 632-2218",
               relatives="Rickilinda R Oehring")

# Same address, same landline, different person
RICKILINDA = summary(BrokerName.ANYWHO, "Rickilinda Oehring",
                     "413 Lovers Ln, Cameron MO 64429",
                     age_range="65", phone="(816) 632-2218",
                     relatives="James Oehring")


class TestAddressParsing:
    """
    Each broker formats addresses differently, and the old comma-split
    heuristic assumed "City, ST". Once the scrapers began returning full street
    addresses it produced city='413 Lovers Ln'.
    """

    @pytest.mark.parametrize("raw,city,state", [
        ("413 Lovers Ln, Cameron MO 64429",          "cameron",     "mo"),
        ("413 Lovers Ln, Cameron, MO",               "cameron",     "mo"),
        ("1225 Union Ave, Apt 502, Kansas City, MO", "kansas city", "mo"),
        ("413 Lovers LN, Cameron, Missouri 64429",   "cameron",     "mo"),
        ("Cameron, MO",                              "cameron",     "mo"),
    ])
    def test_city_and_state(self, engine, raw, city, state):
        parsed = engine._parse_address(raw)
        assert parsed["city"] == city
        assert parsed["state"] == state

    def test_street_is_kept_separate(self, engine):
        assert "lovers" in engine._parse_address("413 Lovers Ln, Cameron MO 64429")["street"]

    def test_city_is_never_the_street(self, engine):
        for raw in ("413 Lovers Ln, Cameron MO 64429",
                    "1225 Union Ave, Apt 502, Kansas City, MO"):
            assert not engine._parse_address(raw)["city"][:1].isdigit()

    def test_empty_address(self, engine):
        parsed = engine._parse_address("")
        assert parsed["city"] == "" and parsed["state"] == ""


class TestSamePersonGroups:
    """All four records are James, and must score as a merge."""

    @pytest.mark.parametrize("other,label", [
        (NPD, "fps/npd"), (ANYWHO, "fps/anywho"), (ZABA, "fps/zaba"),
    ])
    def test_pairs_merge(self, engine, other, label):
        score = engine.calculate_match_score(FPS, other)
        assert score >= engine.MERGE_THRESHOLD, f"{label} scored {score}"

    def test_anywho_matches_on_address_history(self, engine):
        """
        AnyWho lists a different current address; only its history contains
        413 Lovers Ln. Without history matching this pair loses its strongest
        location signal.
        """
        no_history = summary(
            BrokerName.ANYWHO, ANYWHO.full_name, ANYWHO.address,
            age_range="37", phone="", relatives="",
        )
        assert engine.calculate_match_score(FPS, ANYWHO) > \
               engine.calculate_match_score(FPS, no_history)

    def test_deduplicate_yields_one_group(self, engine):
        results = {
            b.value: ScrapeResult(broker=b, summaries=[s], status="success")
            for b, s in ((BrokerName.FPS, FPS), (BrokerName.NPD, NPD),
                         (BrokerName.ANYWHO, ANYWHO), (BrokerName.ZABA, ZABA))
        }
        groups = engine.deduplicate(results)
        assert len(groups) == 1, f"expected one person, got {len(groups)} groups"
        assert len(groups[0].members) == 4


class TestDifferentPeopleStayApart:
    """The household case: same address, same landline, different person."""

    def test_spouse_does_not_merge(self, engine):
        score = engine.calculate_match_score(FPS, RICKILINDA)
        assert score < engine.MERGE_THRESHOLD, (
            f"James and Rickilinda scored {score}; they share an address and a "
            f"landline, so only the name keeps them apart"
        )

    def test_incompatible_first_name_gates_the_match(self, engine):
        """Even with every other signal identical, a different person is a different person."""
        twin = summary(BrokerName.NPD, "Deena Oehring", FPS.address,
                       age=61, phone=FPS.phone, relatives=FPS.relatives)
        assert engine.calculate_match_score(FPS, twin) < engine.MERGE_THRESHOLD

    def test_unrelated_people_score_low(self, engine):
        other = summary(BrokerName.FPS, "Lucas Clark", "7935 Holmes Rd, Kansas City MO 64131",
                        age=34, phone="(816) 263-0393")
        assert engine.calculate_match_score(FPS, other) < engine.GROUP_THRESHOLD

    def test_deduplicate_keeps_household_separate(self, engine):
        results = {
            BrokerName.FPS.value: ScrapeResult(broker=BrokerName.FPS, summaries=[FPS], status="success"),
            BrokerName.ANYWHO.value: ScrapeResult(broker=BrokerName.ANYWHO, summaries=[RICKILINDA], status="success"),
        }
        assert len(engine.deduplicate(results)) == 2


class TestSignalContribution:
    """Phone and relatives were extracted but never scored."""

    def test_shared_phone_raises_the_score(self, engine):
        without = summary(BrokerName.NPD, NPD.full_name, NPD.address, age_range="62")
        with_phone = summary(BrokerName.NPD, NPD.full_name, NPD.address,
                             age_range="62", phone="(816) 632-2218")
        assert engine.calculate_match_score(FPS, with_phone) > \
               engine.calculate_match_score(FPS, without)

    def test_shared_relative_raises_the_score(self, engine):
        without = summary(BrokerName.NPD, NPD.full_name, NPD.address, age_range="62")
        with_rel = summary(BrokerName.NPD, NPD.full_name, NPD.address,
                           age_range="62", relatives="Rickilinda Oehring")
        assert engine.calculate_match_score(FPS, with_rel) > \
               engine.calculate_match_score(FPS, without)

    def test_age_disagreement_does_not_block_a_match(self, engine):
        """61 vs 37 for the same person is real, observed data."""
        assert engine.calculate_match_score(FPS, ZABA) >= engine.MERGE_THRESHOLD

    def test_no_unconditional_bonus(self, engine):
        """
        Every pair used to receive a flat +10 "broker credibility" score, which
        pushed unrelated people toward the threshold for free.
        """
        nothing_in_common = summary(BrokerName.NPD, "Zqxjv Wkltmr", "1 Nowhere St, Nowhere AK 99999")
        assert engine.calculate_match_score(FPS, nothing_in_common) < 10
