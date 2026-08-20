from app.schemas.dining import ExternalDiningRequest
from app.services.external_dining import recommend_external


def test_personal_external_returns_three_distinct_meal_formats(session) -> None:
    response = recommend_external(
        session,
        1,
        ExternalDiningRequest(audience="personal", party_size=1),
    )

    assert len(response.suggestions) == 3
    assert len({item.key for item in response.suggestions}) == 3
    assert len({item.meal_format for item in response.suggestions}) == 3


def test_personal_external_rotates_six_distinct_items_across_two_batches(session) -> None:
    first = recommend_external(
        session,
        1,
        ExternalDiningRequest(audience="personal", party_size=1),
    )
    second = recommend_external(
        session,
        1,
        ExternalDiningRequest(
            audience="personal",
            party_size=1,
            exclude_keys=[item.key for item in first.suggestions],
        ),
    )

    keys = [item.key for item in first.suggestions + second.suggestions]
    assert len(first.suggestions) == 3
    assert len(second.suggestions) == 3
    assert len(set(keys)) == 6
