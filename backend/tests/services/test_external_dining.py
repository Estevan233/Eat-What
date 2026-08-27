from sqlmodel import select

from app.models.recommendation_event import RecommendationEvent
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


def test_personal_external_uses_server_history_for_ten_fresh_batches(session) -> None:
    """换一换不应只靠前端记住两批；同一用户十轮覆盖 30 个方向。"""
    batches = [
        recommend_external(
            session,
            1,
            ExternalDiningRequest(
                audience="personal",
                party_size=1,
                request_id=f"external-history-{index}",
            ),
        )
        for index in range(10)
    ]

    keys = [item.key for batch in batches for item in batch.suggestions]
    assert all(len(batch.suggestions) == 3 for batch in batches)
    assert all(
        len({item.meal_format for item in batch.suggestions}) == 3
        for batch in batches
    )
    assert len(set(keys)) == 30


def test_personal_external_replays_same_request_id(session) -> None:
    request = ExternalDiningRequest(
        audience="personal",
        party_size=1,
        request_id="external-idempotent-001",
    )

    first = recommend_external(session, 1, request)
    replay = recommend_external(session, 1, request)

    assert replay == first


def test_external_event_does_not_persist_city_or_search_keywords(session) -> None:
    response = recommend_external(
        session,
        1,
        ExternalDiningRequest(
            audience="personal",
            party_size=1,
            city="杭州",
            request_id="external-private-event-001",
        ),
    )

    event = session.exec(
        select(RecommendationEvent).where(
            RecommendationEvent.request_id == "external-private-event-001",
        )
    ).one()
    payload = event.primary_meal_json or {}
    assert payload == {
        "kind": "external_dining_v2",
        "suggestion_keys": [item.key for item in response.suggestions],
    }
    assert "杭州" not in str(payload)
