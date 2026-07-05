from datetime import datetime, timedelta, timezone

from formatter import format_item, format_timestamp, render_digest
from models import NewsItem


def _item(title: str, minutes_ago: float = 0.0, link: str | None = None, summary: str | None = None) -> NewsItem:
    return NewsItem(
        key=title,
        title=title,
        summary=summary,
        source="Test",
        link=link,
        published_utc=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )


def test_empty_items_render_to_empty_string():
    assert render_digest([]) == ""


def test_header_shows_count_and_only_appears_with_items():
    digest = render_digest([_item("A"), _item("B")])
    assert "Crypto News Digest" in digest
    assert "2 berita baru" in digest


def test_items_are_numbered_newest_first():
    older = _item("Older", minutes_ago=120)
    newer = _item("Newer", minutes_ago=1)
    digest = render_digest([older, newer])
    assert "1. " in digest
    assert digest.index("1. Newer") < digest.index("2. Older")


def test_format_timestamp_uses_indonesian_month_abbreviation():
    dt = datetime(2026, 7, 5, 11, 42, tzinfo=timezone.utc)  # 18:42 WIB
    assert format_timestamp(dt) == "05 Jul 18:42 WIB"


def test_format_timestamp_disambiguates_id_vs_en_months():
    dt = datetime(2026, 12, 5, 11, 0, tzinfo=timezone.utc)  # December -> WIB same day
    assert "Des" in format_timestamp(dt)


def test_title_with_link_is_wrapped_as_markdown_hyperlink():
    item = _item("Bitcoin hits new high", link="https://example.test/a")
    formatted = format_item(item, 1)
    assert "1. [Bitcoin hits new high](https://example.test/a)" in formatted


def test_title_without_link_is_plain_text():
    item = _item("No link here", link=None)
    formatted = format_item(item, 1)
    assert "1. No link here" in formatted
    assert "[" not in formatted


def test_source_timestamp_line_has_no_stray_special_characters():
    # Regression: a bare "(source)" outside the link construct broke
    # Telegram's MarkdownV2 parser ("character '(' is reserved"). Source/
    # timestamp must live on their own line, separated by "·", never parens.
    item = _item("Some headline", link="https://example.test/a")
    formatted = format_item(item, 1)
    source_line = formatted.splitlines()[1]
    assert source_line == "   Test · " + format_timestamp(item.published_utc)
    assert "(" not in source_line and ")" not in source_line


def test_item_with_summary_appends_third_line():
    item = _item("Headline", summary="A short summary of the story.")
    formatted = format_item(item, 1)
    lines = formatted.splitlines()
    assert lines[2] == "   A short summary of the story."


def test_item_without_summary_has_only_two_lines():
    item = _item("Headline", summary=None)
    formatted = format_item(item, 1)
    assert len(formatted.splitlines()) == 2


def test_no_separate_url_line():
    item = _item("Headline", link="https://example.test/a", summary="Summary text")
    formatted = format_item(item, 1)
    # the link lives inside the title line only, not as a trailing bare URL line
    assert formatted.splitlines()[-1] == "   Summary text"
