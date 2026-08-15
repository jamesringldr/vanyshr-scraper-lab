"""
Tests for SequenceRunner.scan() / select_profile(): the FPS-led Phase 1
variant that awaits FPS alone and matches NPD/AnyWho/Zaba against whichever
FPS candidate the user picks, instead of deduplicating all four brokers
up front the way quickscan() does.

Reuses the James Oehring reference case from test_dedup_engine.py: FPS, NPD,
and Zaba all agree on the Cameron address; AnyWho only links to it through its
previous-address field. Rickilinda Oehring -- same address, same landline,
different person -- has to stay excluded by the name gate, the same way
test_dedup_engine.py proves it for the N-way path.
"""

import asyncio
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from data_models import BrokerName, QuickScanInput  # noqa: E402
from sequence_runner import SequenceRunner  # noqa: E402

import targets.anywho.models as anywho_models  # noqa: E402
import targets.fps.models as fps_models  # noqa: E402
import targets.npd.models as npd_models  # noqa: E402
import targets.zaba.models as zaba_models  # noqa: E402

pytestmark = pytest.mark.unit


class FakeOutput:
    """Stands in for a broker's ScrapeOutput."""

    def __init__(self, summary_results):
        self.summary_results = summary_results
        self.status = "success"
        self.error = None


class FakeScraper:
    def __init__(self, summary_results):
        self._output = FakeOutput(summary_results)

    def run(self, params):
        return self._output


def make_runner():
    """A runner wired to fake scrapers for the James Oehring reference case,
    with an AnyWho decoy (his wife, same address+phone) mixed into the
    results select_profile() has to reject."""
    runner = SequenceRunner(api_key="test-dummy")

    runner.scrapers[BrokerName.FPS] = FakeScraper([
        fps_models.SummaryResult(
            resultId="fps_0", fullName="James Oehring",
            address="413 Lovers Ln, Cameron MO 64429", age=61,
            phone="(816) 632-2218", profileUrl="/james-oehring_id_G369",
            relatives="Rickilinda Oehring, Robert Mctarsney, Albert Mcgee",
        ),
    ])
    runner.scrapers[BrokerName.NPD] = FakeScraper([
        npd_models.SummaryResult(
            resultId="npd_0", fullName="James Oehring",
            addressPreview="413 Lovers Ln, Cameron, MO",
            phonePreview="(816) 632-2218, (816) 225-8592",
            profileUrl="/people/o/james-oehring/mo/cameron/",
            ageRange="62", relatives="Rickilinda Oehring",
        ),
    ])
    runner.scrapers[BrokerName.ZABA] = FakeScraper([
        zaba_models.SummaryResult(
            resultId="zaba_0", fullName="James Oehring",
            address="413 Lovers LN, Cameron, Missouri 64429", age=37,
            profileUrl="https://www.zabasearch.com/people/james-oehring/missouri/cameron",
            phone="(816) 225-8592, (816) 632-2218",
            relatives="Rickilinda R Oehring",
        ),
    ])
    runner.scrapers[BrokerName.ANYWHO] = FakeScraper([
        # Decoy first, so a naive "take the first candidate" would fail.
        anywho_models.SummaryResult(
            resultId="anywho_decoy", fullName="Rickilinda Oehring",
            address="413 Lovers Ln, Cameron MO 64429", ageRange="65",
            profileUrl="/people/rickilinda-oehring/x999",
            phone="(816) 632-2218", relatives="James Oehring",
        ),
        anywho_models.SummaryResult(
            resultId="anywho_0", fullName="James A Oehring",
            address="1225 Union Ave, Apt 502, Kansas City, MO", ageRange="37",
            profileUrl="/people/james-oehring/a123",
            phone="(816) 632-2218", relatives="Rickilinda Oehring",
            previousAddresses="413 Lovers Ln, Cameron, MO; 380 W 22nd St, Kansas City, MO",
        ),
    ])
    return runner


@pytest.fixture
def user_input():
    return QuickScanInput(first_name="James", last_name="Oehring", city="Cameron", state="MO")


def test_scan_returns_fps_and_starts_others_in_background(user_input):
    runner = make_runner()
    fps_result, background = asyncio.run(runner.scan(user_input))

    assert fps_result.summaries[0].full_name == "James Oehring"
    assert set(background.keys()) == {BrokerName.NPD, BrokerName.ANYWHO, BrokerName.ZABA}
    # create_task() starts a coroutine running immediately -- scan() must not
    # have merely stashed unstarted coroutines for later.
    assert all(isinstance(t, asyncio.Task) for t in background.values())


def test_select_profile_matches_correct_candidate_per_broker(user_input):
    async def run():
        runner = make_runner()
        fps_result, background = await runner.scan(user_input)
        selected = fps_result.summaries[0]
        return await runner.select_profile(selected, background)

    group = asyncio.run(run())

    assert set(group.get_sources()) == {"fps", "npd", "anywho", "zaba"}

    anywho_member = next(m for m in group.members if m.summary.broker == BrokerName.ANYWHO)
    assert anywho_member.summary.result_id == "anywho_0", (
        "matched the Rickilinda decoy instead of the real AnyWho candidate"
    )


def test_select_profile_excludes_broker_with_no_matching_candidate(user_input):
    async def run():
        runner = make_runner()
        # This time Zaba's result is a stranger, not this person at all.
        runner.scrapers[BrokerName.ZABA] = FakeScraper([
            zaba_models.SummaryResult(
                resultId="zaba_stranger", fullName="Unrelated Person",
                address="1 Nowhere Rd, Topeka KS", age=50,
                profileUrl="https://www.zabasearch.com/people/unrelated-person/kansas/topeka",
            ),
        ])
        fps_result, background = await runner.scan(user_input)
        selected = fps_result.summaries[0]
        return await runner.select_profile(selected, background)

    group = asyncio.run(run())

    assert "zaba" not in group.get_sources()
    assert {"fps", "npd", "anywho"} <= set(group.get_sources())
