import httpx
import pytest
import respx

from fetcher import fetch_all
from models import NewsSource

_A = NewsSource(name="A", url="https://a.test/rss")
_B = NewsSource(name="B", url="https://b.test/rss")


@pytest.mark.asyncio
@respx.mock
async def test_all_sources_succeed():
    respx.get(_A.url).mock(return_value=httpx.Response(200, content=b"<rss>a</rss>"))
    respx.get(_B.url).mock(return_value=httpx.Response(200, content=b"<rss>b</rss>"))

    results = await fetch_all([_A, _B])

    assert {r.source.name: r.content for r in results} == {"A": b"<rss>a</rss>", "B": b"<rss>b</rss>"}
    assert all(r.error is None for r in results)


@pytest.mark.asyncio
@respx.mock
async def test_one_source_failing_does_not_block_others():
    respx.get(_A.url).mock(side_effect=httpx.ConnectTimeout("timed out"))
    respx.get(_B.url).mock(return_value=httpx.Response(200, content=b"<rss>b</rss>"))

    results = await fetch_all([_A, _B])
    by_name = {r.source.name: r for r in results}

    assert by_name["A"].content is None
    assert by_name["A"].error is not None
    assert by_name["B"].content == b"<rss>b</rss>"
    assert by_name["B"].error is None


@pytest.mark.asyncio
@respx.mock
async def test_http_error_status_is_treated_as_failure():
    respx.get(_A.url).mock(return_value=httpx.Response(503))

    results = await fetch_all([_A])

    assert results[0].content is None
    assert results[0].error is not None


@pytest.mark.asyncio
@respx.mock
async def test_all_sources_fail():
    respx.get(_A.url).mock(side_effect=httpx.ConnectError("refused"))
    respx.get(_B.url).mock(side_effect=httpx.ConnectError("refused"))

    results = await fetch_all([_A, _B])

    assert all(r.content is None for r in results)
