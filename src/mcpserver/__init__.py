"""MCP server for INSEE's Melodi open-data store."""

from importlib.metadata import PackageNotFoundError, version


def package_version() -> str:
    """The version this build reports, in the handshake and in the outbound User-Agent.

    Read from the installed distribution so a release changes pyproject.toml and nothing else.
    Falls back when the package is imported from a source tree that was never installed.
    """
    try:
        return version("mcpmelodi")
    except PackageNotFoundError:
        return "0.1.0"
