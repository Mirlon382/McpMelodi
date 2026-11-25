"""Tool registration entrypoint.

The only place that knows about the MCP server. Every tool is a plain function, so none of them
carries a registration wrapper; those that need a service take it through `Depends`.
"""

from fastmcp import FastMCP
from mcp.types import ToolAnnotations

from ..settings import Settings
from .melodi.get_observations_tool import get_melodi_observations
from .melodi.search_datasets_tool import search_melodi_datasets
from .melodi.search_modalities_tool import search_melodi_modalities

# The tools are advisory: they read public statistics and change nothing.
# snake_case here, because that is the field name in the SDK; it serialises to camelCase on the wire.
READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    open_world_hint=False,
    idempotent_hint=True,
)


def register_tools(mcp: FastMCP, settings: Settings) -> None:
    """Register the tools."""
    mcp.tool(search_melodi_datasets, annotations=READ_ONLY)
    mcp.tool(get_melodi_observations, annotations=READ_ONLY)
    mcp.tool(search_melodi_modalities, annotations=READ_ONLY)
