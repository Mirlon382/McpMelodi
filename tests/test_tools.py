"""What a client actually receives: the tool list, the schemas, and the error text.

Runs against the real `mcp` object over FastMCP's in-memory transport, so the registration, the
settings-derived budgets and the error masking are all exercised. No test here touches the network:
the fields asserted are the ones a model reads before it decides what to call.
"""

import pytest
from fastmcp import Client

from mcpserver.server import mcp

EXPECTED_TOOLS = {"search_melodi_datasets", "get_melodi_observations", "search_melodi_modalities"}


async def list_tools() -> dict:
    async with Client(mcp) as client:
        tools = await client.list_tools()
    return {tool.name: tool for tool in tools}


async def test_the_three_tools_are_published() -> None:
    assert set(await list_tools()) == EXPECTED_TOOLS


@pytest.mark.parametrize("name", sorted(EXPECTED_TOOLS))
async def test_every_tool_is_marked_read_only(name: str) -> None:
    tool = (await list_tools())[name]

    assert tool.annotations is not None
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.destructive_hint is False


async def test_the_dataset_schema_restricts_the_id_to_a_path_segment() -> None:
    properties = (await list_tools())["get_melodi_observations"].input_schema["properties"]

    assert properties["dataset_id"]["pattern"] == "^[A-Za-z0-9_-]+$"
    assert "search_melodi_datasets" in properties["dataset_id"]["description"]


async def test_the_schemas_carry_the_budgets_from_the_settings() -> None:
    tools = await list_tools()

    observations = tools["get_melodi_observations"].input_schema["properties"]["number_of_observations"]
    assert observations["default"] == 100
    assert observations["maximum"] == 1000

    datasets = tools["search_melodi_datasets"].input_schema["properties"]["number_of_datasets"]
    assert datasets["default"] == 5
    assert datasets["maximum"] == 20


async def test_a_search_without_elasticsearch_returns_an_actionable_error() -> None:
    """The default deployment has no ES_HOST, which is supported: it must read as a message, not a trace."""
    async with Client(mcp) as client:
        result = await client.call_tool(
            "search_melodi_datasets",
            {"query": "deces par departement"},
            raise_on_error=False,
        )

    assert result.is_error is True
    text = result.content[0].text
    assert "ES_HOST" in text
    assert "catalogue-donnees.insee.fr" in text
