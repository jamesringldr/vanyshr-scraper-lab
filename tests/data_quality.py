"""
Shared data-quality assertions for broker scraper tests.

These check that extracted values are *complete*, not merely present. The bug
class these exist to catch: a broker page stores sensitive values in blurred
`data-content` attributes, and a parser that reads only visible text silently
yields a half-value like "(816) 632-" that still looks populated in a CSV.
"""

import re

FULL_PHONE = re.compile(r"^\(\d{3}\) \d{3}-\d{4}$")
FULL_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]{2,}@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
STREET_ADDRESS = re.compile(r"^\d+\s+\S")


def split_multi(value):
    """Split a comma-separated multi-value field into its parts."""
    return [p.strip() for p in (value or "").split(",") if p.strip()]


def assert_phones_complete(value, label=""):
    """Every phone must be a full 10-digit number, not a blur-truncated stub."""
    for phone in split_multi(value):
        assert not phone.endswith("-"), f"{label}: phone truncated at blur boundary: {phone!r}"
        assert FULL_PHONE.match(phone), f"{label}: phone not fully formed: {phone!r}"


def assert_emails_complete(value, label=""):
    """
    Every email must keep its local part. A blurred local part collapses
    'jastudly@hotmail.com' to 'j@hotmail.com', which is still a valid-looking
    address -- so a format check alone is not enough, the local part must be
    longer than the single surviving character.
    """
    for email in split_multi(value):
        local = email.split("@")[0]
        assert len(local) >= 2, f"{label}: email local part truncated to {local!r} in {email!r}"
        assert FULL_EMAIL.match(email), f"{label}: email not fully formed: {email!r}"


def assert_no_blur_artifacts(value, label=""):
    """Values must not carry the placeholder glyphs the blur renders."""
    for glyph in ("•••", "••", "…"):
        assert glyph not in (value or ""), f"{label}: unresolved blur artifact in {value!r}"


MORE_AFFORDANCE = re.compile(r'^\+?\s*\d*\s*more$', re.IGNORECASE)


def assert_no_ui_artifacts(value, label=""):
    """
    A truncated broker list ends with a "show more" affordance ("+ 6 more").
    Split on the same separator as the real items, it lands in the data as if
    it were a person's name -- a relative called "+ 1 more" reaching the DB.
    """
    for item in split_multi(value):
        assert not MORE_AFFORDANCE.match(item), f"{label}: UI affordance stored as data: {item!r}"


def assert_capped(value, limit=5, label=""):
    """Multi-value fields carry at most `limit` entries."""
    count = len(split_multi(value))
    assert count <= limit, f"{label}: {count} values exceeds cap of {limit}: {value!r}"


def assert_street_address(value, label=""):
    """A street address must retain its house number."""
    assert STREET_ADDRESS.match(value or ""), f"{label}: address missing street number: {value!r}"


def assert_summary_quality(summary, label="", expect_phone=True, expect_email=True):
    """Run every completeness check that applies to a SummaryResult."""
    label = label or getattr(summary, "fullName", "result")
    assert_phones_complete(getattr(summary, "phone", ""), label)
    assert_emails_complete(getattr(summary, "email", ""), label)
    for field in ("address", "phone", "email", "aliases", "relatives"):
        assert_no_blur_artifacts(getattr(summary, field, ""), f"{label}.{field}")
    for field in ("phone", "email", "aliases", "relatives"):
        assert_no_ui_artifacts(getattr(summary, field, ""), f"{label}.{field}")
        assert_capped(getattr(summary, field, ""), 5, f"{label}.{field}")
    if expect_phone:
        assert getattr(summary, "phone", ""), f"{label}: expected a phone number"
    if expect_email:
        assert getattr(summary, "email", ""), f"{label}: expected an email"
