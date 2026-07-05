from datetime import datetime, timezone

import httpx
import pytest
import respx

from models import NewsItem
from summary_enrichment import enrich_missing_summaries, extract_meta_description


def _item(key: str, summary: str | None = None, link: str | None = "https://example.test/a") -> NewsItem:
    return NewsItem(
        key=key,
        title=key,
        summary=summary,
        source="Test",
        link=link,
        published_utc=datetime.now(timezone.utc),
    )


def test_extract_meta_description_finds_name_description():
    html = '<html><head><meta name="description" content="A short blurb."></head></html>'
    assert extract_meta_description(html) == "A short blurb."


def test_extract_meta_description_finds_og_description():
    html = '<html><head><meta property="og:description" content="OG blurb."></head></html>'
    assert extract_meta_description(html) == "OG blurb."


def test_extract_meta_description_handles_reversed_attribute_order():
    html = '<html><head><meta content="Reversed order blurb." name="description"></head></html>'
    assert extract_meta_description(html) == "Reversed order blurb."


def test_extract_meta_description_returns_none_when_absent():
    html = "<html><head><title>No meta here</title></head></html>"
    assert extract_meta_description(html) is None


def test_extract_meta_description_does_not_raise_on_malformed_html():
    html = "<html><head><meta name=description content=oops<<<broken"
    assert extract_meta_description(html) is None or isinstance(extract_meta_description(html), str)


@pytest.mark.asyncio
@respx.mock
async def test_item_with_existing_summary_is_not_fetched():
    item = _item("has-summary", summary="Already have one")
    result = await enrich_missing_summaries([item])
    assert result == [item]
    assert not respx.calls  # no HTTP request made


@pytest.mark.asyncio
@respx.mock
async def test_item_without_summary_gets_enriched_on_success():
    respx.get("https://example.test/a").mock(
        return_value=httpx.Response(200, html='<meta name="description" content="Fetched blurb.">')
    )
    item = _item("no-summary", summary=None)
    result = await enrich_missing_summaries([item])
    assert result[0].summary == "Fetched blurb."


@pytest.mark.asyncio
@respx.mock
async def test_fetch_failure_leaves_summary_none():
    respx.get("https://example.test/a").mock(side_effect=httpx.ConnectTimeout("timed out"))
    item = _item("no-summary", summary=None)
    result = await enrich_missing_summaries([item])
    assert result[0].summary is None


@pytest.mark.asyncio
@respx.mock
async def test_item_without_link_is_skipped():
    item = _item("no-link", summary=None, link=None)
    result = await enrich_missing_summaries([item])
    assert result[0].summary is None
    assert not respx.calls
