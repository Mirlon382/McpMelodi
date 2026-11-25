"""Startup and shutdown: build the clients once, close them on the way out.

The Melodi services are always built. The Elasticsearch client is not: the two search tools read
indices that have to be built first, so a deployment without a cluster is a supported
configuration -- it keeps get_melodi_observations working, which is the tool that calls the public
REST API. The index service is told the client is absent and says so when it is called, rather than
leaving the tools with a dependency that cannot be resolved.

This is the composition root: it is the one place that reads the whole `Settings`, so nothing
below it has to.
"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.lifespan import Lifespan, lifespan

from ..settings import Settings
from .elasticsearch import elasticsearch_lifespan
from .melodi import melodi_lifespan


def build_lifespan(settings: Settings) -> Lifespan:
    """Return the lifespan FastMCP runs, with the clients the settings allow."""

    @lifespan
    async def app_lifespan(_server: FastMCP[Any]) -> AsyncIterator[dict[str, Any]]:
        async with AsyncExitStack() as stack:
            context: dict[str, Any] = {}

            # Built only when a host is configured: construction is cheap, but a client that can
            # never answer is not worth the retries each search would then pay.
            elasticsearch_client = (
                await stack.enter_async_context(
                    elasticsearch_lifespan(
                        host=settings.es_host,
                        tls_verify=settings.es_tls_verify,
                        request_timeout_seconds=settings.es_request_timeout_seconds,
                        max_retries=settings.es_max_retries,
                    )
                )
                if settings.es_host is not None
                else None
            )

            # Unconditional: the REST client needs no cluster, and the tools need a service to call.
            context |= await stack.enter_async_context(
                melodi_lifespan(
                    elasticsearch_client=elasticsearch_client,
                    data_base_url=settings.melodi_data_base_url,
                    request_timeout_seconds=settings.melodi_request_timeout_seconds,
                    connect_timeout_seconds=settings.melodi_connect_timeout_seconds,
                    datasets_index=settings.es_index_melodi_datasets,
                    columns_index=settings.es_index_melodi_columns,
                    column_search_size=settings.melodi_column_search_size,
                )
            )

            yield context

    return app_lifespan
