"""Pydantic schemas for Melodi tools."""

from typing import Annotated, Any

from pydantic import BaseModel, Field

from ..settings import load_tool_limits

from .common import MAX_SEARCH_TEXT_CHARS, MAX_YEAR, MIN_YEAR, SearchText, Year


# ----------------------------------------------------------------------------------------------------------------------
# Schema bounds --------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
# Budgets an operator tunes: the MELODI_DEFAULT_* and MELODI_MAX_* settings, read once at import because
# the schema is built from them (see ToolLimits in settings.py).
_tool_limits = load_tool_limits()
DEFAULT_OBSERVATIONS = _tool_limits.melodi_default_observations
MAX_OBSERVATIONS = _tool_limits.melodi_max_observations
DEFAULT_DATASETS = _tool_limits.melodi_default_datasets
MAX_DATASETS = _tool_limits.melodi_max_datasets
DEFAULT_MODALITIES = _tool_limits.melodi_default_modalities
MAX_MODALITIES = _tool_limits.melodi_max_modalities

# Dataset id and column id are quite short.
MAX_CODE_CHARS = 100
# Modality codes are a little longer than column ids, never much.
MAX_MODALITY_CHARS = 200
# More columns than any Melodi dataset has.
MAX_COLUMNS = 20
# One entry per distinct year the range can hold.
MAX_YEARS = MAX_YEAR - MIN_YEAR + 1

# Whitelist for those codes. The dataset id becomes a path segment of the API URL, so `/`, `.`, `?`, `#`
# or `%` would let a caller walk out of the dataset endpoint (`../../other`) or add query parameters.
# Letters, digits, `_` and `-` are all a code needs, and none of them can do that. Modality codes go
# into the query string, which httpx encodes, so they are not restricted: their alphabet is not ours.
CODE_PATTERN = r"^[A-Za-z0-9_-]+$"

# ----------------------------------------------------------------------------------------------------------------------
# Tool parameters ------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

# --- shared by every Melodi tool ---



ColumnId = Annotated[str, Field(min_length=1, max_length=MAX_CODE_CHARS, pattern=CODE_PATTERN)]
ModalityCode = Annotated[str, Field(min_length=1, max_length=MAX_MODALITY_CHARS)]

DatasetId = Annotated[
    str,
    Field(
        description=(f"Identifier of the Melodi dataset (from search_melodi_datasets), at most {MAX_CODE_CHARS} characters."),
        min_length=1,
        max_length=MAX_CODE_CHARS,
        pattern=CODE_PATTERN,
        examples=[
            "DS_DECES_MORTALITE_SERIES",
            "DD_CNA_BRANCHES",
        ],
    ),
]

# --- get_melodi_observations ---

Years = Annotated[
    list[Year],
    Field(
        default_factory=list,
        max_length=MAX_YEARS,
        description=(
            "Years to keep in the result set. Leave empty (the default) to "
            "return all available years. Pass e.g. [2020, 2021, 2022] to keep "
            f"only those years. Each is between {MIN_YEAR} and {MAX_YEAR}."
        ),
        examples=[
            [],
            [2020, 2021, 2022],
        ],
    ),
]

ColumnFilters = Annotated[
    dict[ColumnId, ModalityCode],
    Field(
        default_factory=dict,
        max_length=MAX_COLUMNS,
        description=(
            "Filters based on modality codes of columns. Leave empty to "
            "return all rows. Keys are column ids (e.g. 'PRICES', 'GEO'); "
            "values are the exact modality codes returned by "
            f"`search_melodi_modalities`. At most {MAX_COLUMNS} columns."
        ),
        examples=[
            {"PRICES": "D"},
            {"PCS": "6", "GEO": "2025-FRANCE-FM"},
        ],
    ),
]

NumberOfObservations = Annotated[
    int,
    Field(description=f"Maximum number of datasets to return, ordered by relevance, from 1 to {MAX_OBSERVATIONS}.",
          ge=1, 
          le=MAX_OBSERVATIONS,
    ),
]

# --- search_melodi_datasets ---

DatasetQuery = Annotated[
    SearchText,
    Field(
        description=(
            "Explicit French description of the statistical dataset to search. "
            "Mention the phenomenon (inflation, births, unemployment), "
            "geographic level, population or product if known. "
            f"Do NOT provide codes. At mpst {MAX_SEARCH_TEXT_CHARS} chars."
        ),
        examples=[
            "indice des prix a la consommation",
            "deces par departement",
            "prenoms des nouveau-nes",
            "population communale",
            "salaires des enseignants",
        ],
    ),
]

StartYear = Annotated[
    Year,
    Field(description=f"Dataset must contain data from at least this year ({MIN_YEAR} to {MAX_YEAR})."),
]

EndYear = Annotated[
    Year,
    Field(description=f"Dataset must contain data up to at least this year ({MIN_YEAR} to {MAX_YEAR}) and not earlier than start_year."),
]

NumberOfDatasets = Annotated[
    int,
    Field(description="Maximum number of datasets to return, ordered by relevance. From 1 to 20.", ge=1, le=20),
]

# --- search_melodi_modalities ---

ColumnIds = Annotated[
    list[ColumnId],
    Field(
        description=f"Identifiers of the columns within the dataset to search. At most {MAX_COLUMNS}.",
        max_length=MAX_COLUMNS,
        examples=[
            ["PRICES"],
            ["PRICES", "GEO"],
        ],
    ),
]

ModalityQuery = Annotated[
    SearchText,
    Field(
        description=(
            "Natural-language French query describing the modalities to "
            "retrieve (e.g. 'cote de boeuf', 'Ile-de-France', 'female Maria')."
            f"At most {MAX_SEARCH_TEXT_CHARS} chars."
        ),
        examples=[
            "prix",
            "boissons non alcoolisees",
        ],
    ),
]

NumberOfModalities = Annotated[
    int,
    Field(description=f"Maximum number of modalities to return per column, from 1 to {MAX_MODALITIES}.", 
          ge=1, 
          le=MAX_MODALITIES,
    ),
]


# ----------------------------------------------------------------------------------------------------------------------
# Result models --------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------

# --- get_melodi_observations ---


class ObservationsOutput(BaseModel):
    dataset_id: str
    observations: list[dict[str, Any]]
    count: int


# --- search_melodi_datasets ---


class DatasetDescription(BaseModel):
    content: str
    lang: str


class DatasetSearchResult(BaseModel):
    dataset_id: str
    dataset_columns: str = Field(
        description=("Pipe-separated list of available columns formatted as 'COLUMN_ID Label'.")
    )
    dataset_description: DatasetDescription
    dataset_score: float


class DatasetsOutput(BaseModel):
    results: list[DatasetSearchResult]


# --- search_melodi_modalities ---


class Modality(BaseModel):
    code: str
    label_en: str
    label_fr: str
    score: float


class ColumnResult(BaseModel):
    column_code: str
    column_metadata: str
    matching_modalities: list[Modality]


class ModalitiesOutput(BaseModel):
    results: list[ColumnResult]
