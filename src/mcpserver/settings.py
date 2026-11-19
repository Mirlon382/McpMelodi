"""Every value this server can be configured with."""
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from textwrap import dedent

# (default, maximum) pairs of ToolLimits, checked together at startup.
DEFAULT_AND_MAXIMUM_FIELDS = (
    ("melodi_default_observations", "melodi_max_observations"),
    ("melodi_default_datasets", "melodi_max_datasets"),
    ("melodi_default_modalities", "melodi_max_modalities"),
)

class ToolLimits(BaseSettings):
    """The budgets written into the published tool schemas: defaults and maximums of the tool parameters.

    Kept apart from the rest because a tool's schema is built when its model module is imported, before
    server.py builds `Settings`. The models read this part on their own, through `load_tool_limits`.
    `Settings` inherits it, so every variable is still typed, overridable and documented in one place.
    Changing one changes the schema the tools advertise, after a restart like any other setting.
    """


    # Melodi tools -----------------------------------------------------------------------------------------------------
    melodi_default_observations: int = Field(default=100, ge=1)
    melodi_max_observations: int = Field(default=1000, ge=1)
    melodi_default_datasets: int = Field(default=5, ge=1)
    melodi_max_datasets: int = Field(default=20, ge=1)
    melodi_default_modalities: int = Field(default=10, ge=1)
    melodi_max_modalities: int = Field(default=50, ge=1)

    @model_validator(mode="after")
    def keep_defaults_within_maximums(self) -> "ToolLimits":
        """FastMCP never validates a parameter's default, so a default above its maximum would be used as is."""
        for default_field, maximum_field in DEFAULT_AND_MAXIMUM_FIELDS:
            default, maximum = getattr(self, default_field), getattr(self, maximum_field)
            if default > maximum:
                raise ValueError(
                    f"{default_field.upper()} ({default}) is above {maximum_field.upper()} ({maximum}). "
                    "Lower the default or raise the maximum."
                )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

class Settings(ToolLimits):

    server_name:str = "INSEE-mcp-melodi"
    instructions:str = dedent("""
    This server exposes INSEE (French national statistics) data through three sources:

    - MELODI -- the dataset catalogue and the observations themselves

    Rules that apply to every tool:

    - Never guess a dataset id, a modality code, a document URL or a graph URI. Each is opaque and must come
      from a discovery call first.
    - The data is French. Search with French keywords and rich synonyms.
    - An empty result is a valid answer, not a failure. It usually means the filters were too narrow.
    - A tool description may point you at a tool from another source. Only the tools in your tool list exist
      here; if a description names one you do not have, ignore it and use what you have.
    """).strip()

    # HTTP server ------------------------------------------------------------------------------------------------------
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000
    # JSON list of the hostnames clients use to reach this server, checked against the Host
    # header. "*" accepts any host, which disables the check.
    allowed_hosts: list[str] = ["*"]
    # JSON list of browser origins allowed to call the server. Empty rejects every cross-origin
    # browser request, which is right until a browser-based client needs in.
    allowed_origins: list[str] = []
    # Peers whose X-Forwarded-For header is believed; anything else keeps its real socket address.
    # Accepts addresses, CIDR networks and literals. Widening this lets callers forge their own address.
    trusted_proxy_hosts: list[str] = ["127.0.0.1"]

    # Elasticsearch ----------------------------------------------------------------------------------------------------
    # Only Melodi tools search Elasticsearch; rmes runs without it, so the
    # host is genuinely absent rather than empty when they are disabled.
    es_host: str | None = None
    es_index_melodi_datasets: str = "melodi_datasets"
    es_index_melodi_columns: str = "melodi_columns"
    # Elasticsearch is often internal with a self-signed certificate.
    es_tls_verify: bool = True
    es_request_timeout_seconds: int = 30
    # Retries the client makes itself before a search fails. Raising it hides brief outages;
    # lowering it surfaces them sooner.
    es_max_retries: int = 2

    # INSEE services ---------------------------------------------------------------------------------------------------
    melodi_data_base_url: str = "https://api.insee.fr/melodi/data"
    melodi_request_timeout_seconds: int = 30
    melodi_connect_timeout_seconds: int = 10

    # search_melodi_modalities reads this many columns, then keeps number_of_modalities in each.
    melodi_column_search_size: int = Field(default=20, ge=1)
    # Rate limiting ----------------------------------------------------------------------------------------------------
    rate_limit_max_requests: int = 100
    rate_limit_window_minutes: int = 1

    # Logging ----------------------------------------------------------------------------------------------------------
    log_level: str = "INFO"

#    @model_validator(mode="after")
#    def require_elasticsearch_when_it_is_searched(self) -> "Settings":
#        """Fail at startup rather than on the first search that needs a host."""
#        if self.es_host is None and self.enable_melodi_tools:
#            raise ValueError(
#                "ES_HOST is required because the Melodi tools are enabled. "
#                "Set it, or disable them with ENABLE_MELODI_TOOLS=false."
#            )
#        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


def load_settings() -> Settings:
    return Settings()


def load_tool_limits() -> ToolLimits:
    return ToolLimits()

