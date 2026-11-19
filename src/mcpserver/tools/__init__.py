"""Tool registration entrypoint.

The only place that knows about the MCP server. Each group -- the three data sources, and the
feedback tool -- is registered only when its flag is on: an unregistered tool is the one kind of
"disabled" the protocol guarantees, unlike tag or visibility filtering, which a later call can undo.

Every tool is a plain function, so none of them carries a registration wrapper. Those that need a
service take it through `Depends`; `send_feedback` needs none.
"""

from fastmcp import FastMCP

from mcp.types import ToolAnnotations

from ..settings import Settings

from .melodi.get_observations_tool import get_melodi_observations
from .melodi.search_datasets_tool import search_melodi_datasets
from .melodi.search_modalities_tool import search_melodi_modalities



# Les tools sont consultatifs, ne modifient pas leur environnement
READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    openWorldHint=False,
    idempotentHint=True,
)

def register_tools(mcp: FastMCP, settings: Settings) -> None:
    """Register the tools."""

    mcp.tool(search_melodi_datasets, annotations=READ_ONLY)
    mcp.tool(get_melodi_observations, annotations=READ_ONLY)
    mcp.tool(search_melodi_modalities, annotations=READ_ONLY)
