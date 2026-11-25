"""What the Melodi tools need at runtime."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from elasticsearch import AsyncElasticsearch
from fastmcp import Context
from fastmcp.dependencies import CurrentContext
from httpx import AsyncClient, Timeout

from .. import package_version
from ..services.melodi.api_service import MelodiApiService
from ..services.melodi.index_service import MelodiIndexService

logger = logging.getLogger(__name__)

# Honest identity -- these APIs need no browser spoofing.
USER_AGENT = f"McpMelodi/{package_version()}"


@asynccontextmanager
async def melodi_lifespan(
    elasticsearch_client: AsyncElasticsearch | None,
    data_base_url: str,
    request_timeout_seconds: int,
    connect_timeout_seconds: int,
    datasets_index: str,
    columns_index: str,
    column_search_size: int,
) -> AsyncIterator[dict[str, Any]]:
    """Build the Melodi services and close the API client on shutdown.

    `elasticsearch_client` is None when ES_HOST is unset. The index service is still built, so the
    search tools get a dependency that answers with a readable error instead of one that cannot be
    resolved at all.
    """
    http_client = AsyncClient(
        base_url=data_base_url,
        headers={"User-Agent": USER_AGENT},
        timeout=Timeout(
            request_timeout_seconds,
            connect=connect_timeout_seconds,
        ),
    )
    logger.info("MELODI client initialized for %s", data_base_url)
    if elasticsearch_client is None:
        logger.warning(
            "ES_HOST is not set: the two Melodi search tools will answer with an error. "
            "get_melodi_observations does not need Elasticsearch and works regardless."
        )
    try:
        yield {
            "melodi_index_service": MelodiIndexService(
                elasticsearch_client=elasticsearch_client,
                datasets_index=datasets_index,
                columns_index=columns_index,
                column_search_size=column_search_size,
            ),
            "melodi_api_service": MelodiApiService(http_client=http_client),
        }
    finally:
        await http_client.aclose()


def get_melodi_index_service(ctx: Context = CurrentContext()) -> MelodiIndexService:
    """Return the Melodi Elasticsearch service built at startup."""
    return ctx.lifespan_context["melodi_index_service"]


def get_melodi_api_service(ctx: Context = CurrentContext()) -> MelodiApiService:
    """Return the Melodi REST API service built at startup."""
    return ctx.lifespan_context["melodi_api_service"]
