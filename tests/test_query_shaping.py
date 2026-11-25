"""The two Elasticsearch query bodies, asserted without a cluster.

`AsyncSearch` is valid on its own -- no client, no index, no I/O -- so what the service will send
is pinned here. If a field name or a filter pair changes, this fails before an operator discovers
it against a real index.
"""

from mcpserver.services.melodi.index_service import build_column_search, build_dataset_search


def test_dataset_search_ranks_the_four_fields_in_order() -> None:
    body = build_dataset_search(
        query="deces par departement",
        start_year=2000,
        end_year=2020,
        number_of_datasets=3,
    ).to_dict()

    should = body["query"]["bool"]["should"]
    assert [clause["nested"]["path"] for clause in should[:3]] == [
        "metadata.title",
        "metadata.abstract",
        "metadata.description",
    ]
    assert [
        clause["nested"]["query"]["match"][f"{clause['nested']['path']}.content"]["boost"] for clause in should[:3]
    ] == [
        10,
        6,
        3,
    ]
    assert should[3]["match"]["variables_text"]["boost"] == 5
    assert body["size"] == 3


def test_dataset_search_turns_years_into_range_filters() -> None:
    body = build_dataset_search(query="pib", start_year=1990, end_year=2024, number_of_datasets=1).to_dict()

    filters = body["query"]["bool"]["filter"]
    assert filters == [
        {"range": {"metadata.temporal.endPeriod": {"gte": "1990-01-01"}}},
        {"range": {"metadata.temporal.startPeriod": {"lte": "2024-12-31"}}},
    ]


def test_dataset_search_treats_year_zero_as_unbounded() -> None:
    body = build_dataset_search(query="pib", start_year=0, end_year=0, number_of_datasets=1).to_dict()

    assert "filter" not in body["query"]["bool"]


def test_column_search_filters_one_dataset_and_keeps_the_best_modalities() -> None:
    body = build_column_search(
        dataset_id="DS_PRICES",
        column_ids=["PRICES", "GEO"],
        query="cote de boeuf",
        number_of_modalities=4,
        column_search_size=7,
    ).to_dict()

    assert body["query"]["bool"]["filter"] == [
        {"term": {"dataset_id": "DS_PRICES"}},
        {"terms": {"code": ["PRICES", "GEO"]}},
    ]
    nested = body["query"]["bool"]["should"][1]["nested"]
    assert nested["path"] == "modalities"
    assert nested["inner_hits"] == {"size": 4, "sort": [{"_score": "desc"}]}
    assert nested["query"]["multi_match"]["fields"] == [
        "modalities.code^5",
        "modalities.label.en^3",
        "modalities.label.fr^3",
    ]
    assert nested["query"]["multi_match"]["fuzziness"] == "AUTO"
    # The column page is the outer size, never the modalities budget.
    assert body["size"] == 7


def test_column_search_sends_no_terms_filter_when_no_column_is_named() -> None:
    body = build_column_search(
        dataset_id="DS_PRICES",
        column_ids=[],
        query="prix",
        number_of_modalities=2,
        column_search_size=5,
    ).to_dict()

    assert body["query"]["bool"]["filter"] == [{"term": {"dataset_id": "DS_PRICES"}}]
