"""
Contract tests for SequenceRunner._scrape_broker.

Each broker module defines its own SummaryResult with different field names:

    fps     address          phone         age (int)
    npd     addressPreview   phonePreview  ageRange
    anywho  address          phone         ageRange
    zaba    address          phone         age (int)

_scrape_broker flattens all three into the shared data_models.SummaryResult
using a chain of getattr fallbacks. That chain has no type checking behind it:
rename a field in one broker's model and the getattr default quietly yields ""
-- the scrape still "succeeds", the CSV still has a column, and the row is just
blank. This is the last hop before data reaches the database, so every field is
asserted to survive the crossing.
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


@pytest.fixture(scope="module")
def runner():
    return SequenceRunner(api_key="test-dummy")


@pytest.fixture(scope="module")
def user_input():
    return QuickScanInput(first_name="James", last_name="Oehring", city="Cameron", state="MO")


def scrape(runner, broker, summary, user_input):
    result = asyncio.run(runner._scrape_broker(broker, FakeScraper([summary]), user_input))
    assert result.summaries, f"{broker}: summary was dropped entirely"
    return result.summaries[0]


# Each broker's own model, populated with the values it really produces.
BROKERS = {
    BrokerName.FPS: fps_models.SummaryResult(
        resultId="fps_0",
        fullName="James Oehring",
        address="413 Lovers Ln, Cameron MO 64429",
        age=61,
        phone="(816) 632-2218",
        profileUrl="/james-oehring_id_G369",
        email="ja_studly@hotmail.com",
        aliases="James A Oehring",
        relatives="Rickilinda Oehring",
    ),
    BrokerName.NPD: npd_models.SummaryResult(
        resultId="npd_0",
        fullName="James Oehring",
        addressPreview="413 Lovers Ln, Cameron, MO",
        phonePreview="(816) 632-2218",
        profileUrl="/people/o/james-oehring/mo/cameron/",
        ageRange="62",
        email="ja_studly@hotmail.com",
        aliases="James A Oehring",
        relatives="Rickilinda Oehring",
    ),
    BrokerName.ZABA: zaba_models.SummaryResult(
        resultId="zaba_0",
        fullName="James Oehring",
        address="413 Lovers LN, Cameron, Missouri 64429",
        age=37,
        profileUrl="https://www.zabasearch.com/people/james-oehring/missouri/cameron",
        phone="(816) 632-2218",
        email="rickioehring@yahoo.com",
        aliases="james O oehring",
        relatives="Rickilinda R Oehring",
    ),
    BrokerName.ANYWHO: anywho_models.SummaryResult(
        resultId="anywho_0",
        fullName="James A Oehring",
        address="1225 Union Ave, Apt 502, Kansas City, MO",
        ageRange="37",
        profileUrl="/people/james-oehring/a123",
        phone="(816) 632-2218",
        email="jastudly@hotmail.com",
        aliases="James Allen Oehring Jr.",
        relatives="Rickilinda Oehring",
    ),
}


@pytest.mark.parametrize("broker", list(BROKERS))
class TestFieldsSurviveTheCrossing:
    """No populated broker field may arrive empty on the shared model."""

    def test_name(self, runner, broker, user_input):
        assert scrape(runner, broker, BROKERS[broker], user_input).full_name

    def test_address(self, runner, broker, user_input):
        got = scrape(runner, broker, BROKERS[broker], user_input)
        assert got.address, f"{broker}: address lost (addressPreview vs address mismatch?)"
        assert any(
            street in got.address for street in ("Lovers Ln", "Lovers LN", "Union Ave")
        ), f"{broker}: unexpected address {got.address!r}" 

    def test_phone(self, runner, broker, user_input):
        got = scrape(runner, broker, BROKERS[broker], user_input)
        assert got.phone == "(816) 632-2218", f"{broker}: phone lost or altered ({got.phone!r})"

    def test_email(self, runner, broker, user_input):
        assert "@" in scrape(runner, broker, BROKERS[broker], user_input).email

    def test_aliases(self, runner, broker, user_input):
        assert scrape(runner, broker, BROKERS[broker], user_input).aliases

    def test_relatives(self, runner, broker, user_input):
        assert scrape(runner, broker, BROKERS[broker], user_input).relatives

    def test_result_id_carried(self, runner, broker, user_input):
        # Zaba matches a summary back to the full profile it returned in the
        # same Phase 1 call, so the broker's own id has to survive the crossing
        assert scrape(runner, broker, BROKERS[broker], user_input).result_id

    def test_profile_url(self, runner, broker, user_input):
        assert scrape(runner, broker, BROKERS[broker], user_input).profile_url

    def test_age_available_in_some_form(self, runner, broker, user_input):
        # FPS supplies an int `age`; NPD and AnyWho supply a string `ageRange`.
        # The CSV falls back from one to the other, so at least one must land.
        got = scrape(runner, broker, BROKERS[broker], user_input)
        assert got.age or got.age_range, f"{broker}: no age in either field"


class TestFailureHandling:
    def test_broker_exception_is_reported_not_swallowed(self, runner, user_input):
        class Boom:
            def run(self, params):
                raise RuntimeError("broker exploded")

        result = asyncio.run(runner._scrape_broker(BrokerName.FPS, Boom(), user_input))
        assert result.status == "failed"
        assert "broker exploded" in (result.error or "")
        assert result.summaries == []

    def test_empty_broker_result_is_not_a_fake_row(self, runner, user_input):
        result = asyncio.run(runner._scrape_broker(BrokerName.NPD, FakeScraper([]), user_input))
        assert result.summaries == []
