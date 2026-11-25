"""The Elasticsearch-backed service: hit mapping, and the absence of a client.

The stub below answers `.search()` with the envelope async Elasticsearch returns, so the mapping
from hits to the tool models runs for real without a cluster. The `None` client case is the one a
default deployment is in, so its message is asserted rather than left to chance.
"""

from types import SimpleNamespace

import pytest

from mcpserver.errors import AppToolError, ErrorCode
from mcpserver.services.melodi.index_service import MelodiIndexService, parse_first_description, parse_modality


class StubClient:
    """An Elasticsearch client that answers every search with one canned envelope."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    async def search(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(body=self.payload)


def make_service(payload: dict, columns_index: str = "melodi_columns") -> tuple[MelodiIndexService, StubClient]:
    stub = StubClient(payload)
    service = MelodiIndexService(
        elasticsearch_client=stub,
        datasets_index="melodi_datasets",
        columns_index=columns_index,
        column_search_size=20,
    )
    return service, stub


async def test_dataset_hits_become_tool_results() -> None:
    payload = {
        "hits": {
            "hits": [
                {
                    "_id": "DS_DECES",
                    "_score": 3.5,
                    "_source": {
                        "columns": "GEO | FREQ",
                        "metadata": {"description": [{"content": "Deces par departement", "lang": "fr"}]},
                    },
                }
            ]
        }
    }
    service, stub = make_service(payload)

    results = await service.search_datasets(
        query="deces",
        start_year=2000,
        end_year=2020,
        number_of_datasets=5,
    )

    assert len(results) == 1
    assert results[0].dataset_id == "DS_DECES"
    assert results[0].dataset_columns == "GEO | FREQ"
    assert results[0].dataset_description.content == "Deces par departement"
    assert results[0].dataset_score == 3.5
    # The index the service was built with is the one searched, not a hardcoded default.
    assert stub.calls[0]["index"] == ["melodi_datasets"]


async def test_column_hits_keep_only_the_modalities_elasticsearch_scored() -> None:
    payload = {
        "hits": {
            "hits": [
                {
                    "_id": "col-1",
                    "_score": 4.0,
                    "_source": {"code": "GEO", "text": "GEO - geography"},
                    "inner_hits": {
                        "modalities": {
                            "hits": {
                                "total": {"value": 1},
                                "hits": [
                                    {"_score": 2.25, "_source": {"code": "75", "label": {"fr": "Paris", "en": "Paris"}}}
                                ],
                            }
                        }
                    },
                }
            ]
        }
    }
    service, stub = make_service(payload)

    results = await service.search_columns(
        dataset_id="DS_PRICES",
        column_ids=["GEO"],
        query="paris",
        number_of_modalities=3,
    )

    assert len(results) == 1
    assert results[0].column_code == "GEO"
    assert results[0].column_metadata == "GEO - geography"
    assert [(m.code, m.label_fr, m.score) for m in results[0].matching_modalities] == [("75", "Paris", 2.25)]
    assert stub.calls[0]["index"] == ["melodi_columns"]


async def test_a_column_hit_without_inner_hits_carries_no_modality() -> None:
    payload = {"hits": {"hits": [{"_id": "c", "_score": 1.0, "_source": {"code": "GEO", "text": "GEO"}}]}}
    service, _ = make_service(payload)

    results = await service.search_columns(dataset_id="DS_X", column_ids=[], query="geo", number_of_modalities=5)

    assert results[0].matching_modalities == []


async def test_without_a_client_both_searches_name_es_host_and_the_way_out() -> None:
    service = MelodiIndexService(
        elasticsearch_client=None,
        datasets_index="melodi_datasets",
        columns_index="melodi_columns",
        column_search_size=20,
    )

    for call in (
        service.search_datasets(query="deces", start_year=0, end_year=0, number_of_datasets=5),
        service.search_columns(dataset_id="DS_X", column_ids=[], query="paris", number_of_modalities=5),
    ):
        with pytest.raises(AppToolError) as raised:
            await call
        assert raised.value.code is ErrorCode.BACKEND_UNAVAILABLE
        assert "ES_HOST" in str(raised.value)
        # The caller is told what still works, not just what does not.
        assert "observations" in str(raised.value)


def test_description_defaults_to_an_empty_french_one() -> None:
    assert parse_first_description(SimpleNamespace(metadata=SimpleNamespace())).content == ""
    assert parse_first_description(SimpleNamespace()).lang == "fr"


def test_description_accepts_an_object_as_well_as_a_list() -> None:
    single = SimpleNamespace(metadata=SimpleNamespace(description=SimpleNamespace(content="one", lang="en")))

    parsed = parse_first_description(single)

    assert (parsed.content, parsed.lang) == ("one", "en")


def test_modality_without_a_score_scores_zero() -> None:
    modality = parse_modality(
        SimpleNamespace(code="75", label=SimpleNamespace(fr="Paris"), meta=SimpleNamespace(score=None))
    )

    assert modality.score == 0.0
    assert modality.label_en == ""
