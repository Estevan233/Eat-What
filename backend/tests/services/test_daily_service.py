from datetime import date, timedelta

from sqlmodel import select

from app.models.daily_log import DailyLog
from app.models.recommendation_event import RecommendationEvent
from app.models.user import User
from app.services import daily_service


def _create_user(session) -> User:
    user = User(openid="daily_service_user", nickname="测试用户", avatar_url=None)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_record_recommendation_keeps_events_and_latest_daily_log(session):
    user = _create_user(session)
    assert user.id is not None

    _, first = daily_service.record_recommendation(
        session,
        user.id,
        recommended_food_ids=[1, 2, 3],
        mood="neutral",
        activity_level="normal",
        weather_tag="mild",
        engine="rules_v2",
    )
    latest, second = daily_service.record_recommendation(
        session,
        user.id,
        recommended_food_ids=[4, 5, 6],
        mood="tired",
        activity_level="high",
        weather_tag="rainy",
        engine="rules_v2",
    )

    logs = list(session.exec(select(DailyLog)).all())
    events = list(
        session.exec(
            select(RecommendationEvent).order_by(RecommendationEvent.id)
        ).all()
    )
    assert len(logs) == 1
    assert logs[0].recommended_food_ids_json == [4, 5, 6]
    assert logs[0].chosen_food_ids_json == []
    assert latest.id == logs[0].id
    assert len(events) == 2
    assert {first.id, second.id} == {events[0].id, events[1].id}
    assert [event.recommended_food_ids_json for event in events] == [
        [1, 2, 3],
        [4, 5, 6],
    ]
    sensitive_fields = {"lat", "lng", "birthday", "height_cm", "weight_kg"}
    assert sensitive_fields.isdisjoint(RecommendationEvent.model_fields)


def test_get_recent_recommendation_events_respects_seven_day_window(session):
    user = _create_user(session)
    assert user.id is not None
    today = date(2026, 8, 11)
    session.add_all(
        [
            RecommendationEvent(
                user_id=user.id,
                event_date=today,
                recommended_food_ids_json=[1, 2, 3],
            ),
            RecommendationEvent(
                user_id=user.id,
                event_date=today - timedelta(days=6),
                recommended_food_ids_json=[4, 5, 6],
            ),
            RecommendationEvent(
                user_id=user.id,
                event_date=today - timedelta(days=7),
                recommended_food_ids_json=[7, 8, 9],
            ),
        ]
    )
    session.commit()

    events = daily_service.get_recent_recommendation_events(
        session,
        user.id,
        days=7,
        as_of=today,
    )
    assert {event.recommended_food_ids_json[0] for event in events} == {1, 4}
