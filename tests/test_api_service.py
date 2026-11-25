"""The REST client: request shape on the way out, error contract on the way back.

Every case runs on an `httpx.MockTransport`, so the suite never reaches INSEE. The translations
pinned here are the only thing a caller sees when Melodi fails, which is why each one is asserted
on its code and on the remedy it names.
"""

import httpx
import pytest

from mcpserver.errors import AppToolError, ErrorCode
from mcpserver.services.melodi.api_service import MelodiApiService

BASE_URL = "https://api.insee.fr/melodi/data"


def make_service(handler: httpx.MockTransport) -> MelodiApiService:
    """A service whose client answers with `handler` instead of the network."""
    return MelodiApiService(http_client=httpx.AsyncClient(transport=handler, base_url=BASE_URL))


async def test_returns_the_observations_and_calls_the_dataset_path() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"observations": [{"dimensions": {"TIME_PERIOD": "2024"}}]})

    observations = await make_service(httpx.MockTransport(handler)).fetch_observations(
        dataset_id="DS_DECES",
        column_filters={"FREQ": "A"},
    )

    assert observations == [{"dimensions": {"TIME_PERIOD": "2024"}}]
    assert seen[0].url.path == "/melodi/data/DS_DECES"
    assert seen[0].url.params["FREQ"] == "A"


async def test_quotes_a_dataset_id_so_it_cannot_leave_the_path_segment() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"observations": []})

    # The schema refuses these characters today; the quoting is the second line of defence.
    await make_service(httpx.MockTransport(handler)).fetch_observations(
        dataset_id="DS/../../admin",
        column_filters={},
    )

    path = seen[0].url.raw_path.split(b"?")[0]
    assert path.endswith(b"/DS%2F..%2F..%2Fadmin")
    assert b"/admin" not in path


async def test_no_filter_is_sent_as_no_query_string() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"observations": []})

    await make_service(httpx.MockTransport(handler)).fetch_observations(dataset_id="DS_X", column_filters={})

    assert seen[0].url.query == b""


async def test_a_400_names_the_tool_that_returns_a_valid_value() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="Le paramètre FREQ est inconnu")

    with pytest.raises(AppToolError) as raised:
        await make_service(httpx.MockTransport(handler)).fetch_observations(
            dataset_id="DS_X",
            column_filters={"FREQ": "A"},
        )

    assert raised.value.code is ErrorCode.INVALID_INPUT
    assert "FREQ" in str(raised.value)
    assert "search_melodi_datasets" in str(raised.value)
    assert "search_melodi_modalities" in str(raised.value)


async def test_a_404_names_the_dataset_and_the_lookup_tool() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    with pytest.raises(AppToolError) as raised:
        await make_service(httpx.MockTransport(handler)).fetch_observations(dataset_id="DS_NOPE", column_filters={})

    assert raised.value.code is ErrorCode.NOT_FOUND
    assert "DS_NOPE" in str(raised.value)


async def test_a_5xx_is_reported_as_upstream_and_retryable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    with pytest.raises(AppToolError) as raised:
        await make_service(httpx.MockTransport(handler)).fetch_observations(dataset_id="DS_X", column_filters={})

    assert raised.value.code is ErrorCode.UPSTREAM_ERROR
    assert raised.value.retryable is True
    assert "503" in str(raised.value)


async def test_a_timeout_is_retryable_and_says_so() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("too slow")

    with pytest.raises(AppToolError) as raised:
        await make_service(httpx.MockTransport(handler)).fetch_observations(dataset_id="DS_X", column_filters={})

    assert raised.value.code is ErrorCode.BACKEND_UNAVAILABLE
    assert raised.value.retryable is True


async def test_a_non_json_body_is_a_parse_error_not_a_crash() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>maintenance</html>")

    with pytest.raises(AppToolError) as raised:
        await make_service(httpx.MockTransport(handler)).fetch_observations(dataset_id="DS_X", column_filters={})

    assert raised.value.code is ErrorCode.PARSE_ERROR


async def test_json_without_an_observations_list_is_a_parse_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": []})

    with pytest.raises(AppToolError) as raised:
        await make_service(httpx.MockTransport(handler)).fetch_observations(dataset_id="DS_X", column_filters={})

    assert raised.value.code is ErrorCode.PARSE_ERROR
    assert "observations" in str(raised.value)
