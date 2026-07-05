import calendar
import time

from models import NewsSource
from parser import _clean_summary, _entry_published, parse_feed

_SOURCE = NewsSource(name="TestFeed", url="https://example.test/rss")

_WELL_FORMED_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Bitcoin hits new high</title>
      <link>https://example.test/a</link>
      <guid>https://example.test/a</guid>
      <description>&lt;p&gt;Bitcoin surged past $100k amid strong ETF inflows.&lt;/p&gt;</description>
      <pubDate>Sun, 05 Jul 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>  Ethereum upgrade ships  </title>
      <link>https://example.test/b</link>
      <pubDate>Sun, 05 Jul 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

_MALFORMED_RSS = b"<rss version=\"2.0\"><channel><item><title>Broken</item></channel>"

_MISSING_DATE_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>No date here</title>
      <guid>https://example.test/c</guid>
    </item>
  </channel>
</rss>
"""


def test_well_formed_feed_parses_into_items():
    items = parse_feed(_WELL_FORMED_RSS, _SOURCE)
    assert len(items) == 2
    assert items[0].title == "Bitcoin hits new high"
    assert items[0].key == "https://example.test/a"  # uses <guid> verbatim
    assert items[0].source == "TestFeed"


def test_html_description_is_cleaned_into_summary():
    items = parse_feed(_WELL_FORMED_RSS, _SOURCE)
    assert items[0].summary == "Bitcoin surged past $100k amid strong ETF inflows."


def test_entry_without_description_has_no_summary():
    items = parse_feed(_WELL_FORMED_RSS, _SOURCE)
    second = items[1]
    assert second.title == "Ethereum upgrade ships"
    assert second.summary is None


def test_entry_without_guid_falls_back_to_source_scoped_title_hash():
    items = parse_feed(_WELL_FORMED_RSS, _SOURCE)
    second = items[1]
    assert second.key.startswith("TestFeed::titlehash:")


def test_malformed_feed_does_not_raise(capsys):
    items = parse_feed(_MALFORMED_RSS, _SOURCE)
    assert items == []
    assert "malformed" in capsys.readouterr().err


def test_entry_without_date_is_skipped():
    items = parse_feed(_MISSING_DATE_RSS, _SOURCE)
    assert items == []


def test_published_uses_timegm_not_mktime():
    struct = time.struct_time((2026, 7, 5, 12, 0, 0, 0, 0, 0))  # interpreted as UTC noon
    result = _entry_published({"published_parsed": struct})
    assert result is not None
    assert result.hour == 12  # would differ under time.mktime on a non-UTC host
    assert result.timestamp() == calendar.timegm(struct)


def test_clean_summary_truncates_long_text():
    long_text = "word " * 100
    cleaned = _clean_summary(long_text)
    assert cleaned is not None
    assert len(cleaned) <= 200
    assert cleaned.endswith("…")


def test_clean_summary_returns_none_for_empty_input():
    assert _clean_summary("") is None
    assert _clean_summary("   ") is None
