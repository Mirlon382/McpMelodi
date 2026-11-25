"""get_melodi_observations: the year filter, and the truncation the tool adds on top of the API.

The API returns every row of a dataset, so what the tool does with that list is the only thing
between a caller and a 4 MB payload. Both helpers are pure, and the tool function is a plain
function, so it runs with a stub service and no network.
"""

from typing import Any

from mcpserver.tools.melodi.get_observations_tool import (
    get_melodi_observations,
    keep_requested_years,
    read_observation_year,
)


def observations(*periods: str | None) -> list[dict[str, Any]]:
    return [{"dimensions": {"TIME_PERIOD": period} if period else {}} for period in periods]


class StubApiService:
    """Returns a fixed row list and records the arguments the tool passed down."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[dict[str, Any]] = []

    async def fetch_observations(self, dataset_id: str, column_filters: dict[str, str]) -> list[dict[str, Any]]:
        self.calls.append({"dataset_id": dataset_id, "column_filters": column_filters})
        return self.rows


def test_a_period_yields_its_year() -> None:
    assert read_observation_year({"dimensions": {"TIME_PERIOD": "2023-01"}}) == "2023"
    assert read_observation_year({"dimensions": {"TIME_PERIOD": "2023"}}) == "2023"


def test_a_missing_period_yields_an_empty_year_and_is_never_matched() -> None:
    assert read_observation_year({"dimensions": {}}) == ""
    assert read_observation_year({}) == ""
    assert keep_requested_years(observations(None), [2024]) == []


def test_no_requested_year_keeps_everything() -> None:
    rows = observations("2020", "2024")

    assert keep_requested_years(rows, []) == rows


def test_only_the_requested_years_survive() -> None:
    rows = observations("2019-12", "2020-01", "2020-08", "2021-01")

    kept = keep_requested_years(rows, [2020])

    assert [row["dimensions"]["TIME_PERIOD"] for row in kept] == ["2020-01", "2020-08"]


async def test_the_tool_truncates_after_filtering_and_reports_the_count() -> None:
    service = StubApiService(observations("2020", "2021", "2022"))

    result = await get_melodi_observations(
        dataset_id="DS_DECES_MORTALITE_SERIES",
        years=[2020, 2021],
        column_filters={"FREQ": "A"},
        number_of_observations=1,
        melodi_api_service=service,
    )

    assert result.dataset_id == "DS_DECES_MORTALITE_SERIES"
    assert result.count == 1
    assert [row["dimensions"]["TIME_PERIOD"] for row in result.observations] == ["2020"]
    # Every year is fetched, then filtered here: the API's own period filter would drop monthly rows.
    assert service.calls == [{"dataset_id": "DS_DECES_MORTALITE_SERIES", "column_filters": {"FREQ": "A"}}]


async def test_an_empty_result_set_is_not_an_error() -> None:
    result = await get_melodi_observations(
        dataset_id="DS_X",
        years=[2024],
        column_filters={},
        number_of_observations=10,
        melodi_api_service=StubApiService([]),
    )

    assert result.observations == []
    assert result.count == 0
