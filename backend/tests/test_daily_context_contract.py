import pytest
from pydantic import ValidationError as PydanticValidationError

from app.schemas.daily import RecommendRequest


def test_decision_context_defaults_preserve_old_clients() -> None:
    request = RecommendRequest()

    assert request.dining_mode == "cook"
    assert request.audience == "personal"
    assert request.party_size == 1
    assert request.exclude_food_ids == []


def test_recommend_request_normalizes_client_exclusions() -> None:
    request = RecommendRequest(exclude_food_ids=[3, 1, 3, 2])

    assert request.exclude_food_ids == [3, 1, 2]


def test_recommend_request_rejects_invalid_client_exclusions() -> None:
    with pytest.raises(PydanticValidationError):
        RecommendRequest(exclude_food_ids=[0])

    with pytest.raises(PydanticValidationError):
        RecommendRequest(exclude_food_ids=list(range(1, 14)))


def test_family_accepts_two_to_eight_people() -> None:
    assert RecommendRequest(audience="family", party_size=2).party_size == 2
    assert RecommendRequest(audience="family", party_size=8).party_size == 8


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"audience": "personal", "party_size": 2}, "个人模式人数必须为 1"),
        ({"audience": "family", "party_size": 1}, "家庭模式人数必须为 2-8"),
        ({"audience": "family", "party_size": 9}, "less than or equal to 8"),
    ],
)
def test_invalid_audience_and_party_size_is_rejected(
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(PydanticValidationError, match=message):
        RecommendRequest(**payload)
