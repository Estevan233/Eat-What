from __future__ import annotations


def _login(client, guest_id: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/guest-login",
        json={"guest_id": guest_id, "nickname": "外食测试"},
    )
    assert response.status_code == 200
    token = response.json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


def test_dining_memory_upsert_list_and_delete_is_private(client) -> None:
    owner = _login(client, "dining-owner-123456")
    stranger = _login(client, "dining-stranger-123456")

    created = client.put(
        "/api/v1/dining/memories",
        headers=owner,
        json={
            "shop_name": "  老王面馆 ",
            "dish_name": "牛肉面",
            "verdict": "liked",
            "note": "少盐，别加香菜",
        },
    )
    assert created.status_code == 200
    memory = created.json()["data"]
    assert memory["shop_name"] == "老王面馆"
    assert memory["dish_name"] == "牛肉面"
    assert memory["verdict"] == "liked"

    updated = client.put(
        "/api/v1/dining/memories",
        headers=owner,
        json={
            "shop_name": "老王面馆",
            "dish_name": "牛肉面",
            "verdict": "avoided",
            "note": "这家这道太咸",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["id"] == memory["id"]
    assert updated.json()["data"]["verdict"] == "avoided"

    owner_list = client.get("/api/v1/dining/memories", headers=owner)
    stranger_list = client.get("/api/v1/dining/memories", headers=stranger)
    assert owner_list.json()["data"]["total"] == 1
    assert stranger_list.json()["data"]["total"] == 0

    forbidden_delete = client.delete(
        f"/api/v1/dining/memories/{memory['id']}",
        headers=stranger,
    )
    assert forbidden_delete.status_code == 404

    deleted = client.delete(
        f"/api/v1/dining/memories/{memory['id']}",
        headers=owner,
    )
    assert deleted.status_code == 200
    assert deleted.json()["data"] == {"deleted": True}


def test_dining_memory_rejects_empty_identity_and_long_note(client) -> None:
    headers = _login(client, "dining-validation-123456")

    empty = client.put(
        "/api/v1/dining/memories",
        headers=headers,
        json={"shop_name": "   ", "dish_name": "面", "verdict": "neutral"},
    )
    long_note = client.put(
        "/api/v1/dining/memories",
        headers=headers,
        json={
            "shop_name": "店",
            "dish_name": "面",
            "verdict": "neutral",
            "note": "x" * 501,
        },
    )

    assert empty.status_code == 422
    assert long_note.status_code == 422


def test_external_recommendation_works_with_manual_city_and_family(client) -> None:
    headers = _login(client, "dining-recommend-family-123456")

    response = client.post(
        "/api/v1/dining/recommend",
        headers=headers,
        json={
            "mood": "tired",
            "activity_level": "normal",
            "audience": "family",
            "party_size": 4,
            "city": "杭州",
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["city_label"] == "杭州"
    assert data["audience"] == "family"
    assert data["party_size"] == 4
    assert len(data["suggestions"]) == 3
    for item in data["suggestions"]:
        assert item["dish_name"]
        assert item["category"]
        assert item["search_keywords"]
        assert item["order_tips"]
        assert item["energy_kcal_min_per_person"] < item["energy_kcal_max_per_person"]
        assert item["seasonal_note"]
        assert item["nutrition_note"]


def test_external_recommendation_rotates_away_from_previous_batch(client) -> None:
    headers = _login(client, "dining-rotation-123456")

    first = client.post("/api/v1/dining/recommend", headers=headers, json={})
    assert first.status_code == 200
    first_keys = [item["key"] for item in first.json()["data"]["suggestions"]]

    second = client.post(
        "/api/v1/dining/recommend",
        headers=headers,
        json={"exclude_keys": first_keys},
    )
    assert second.status_code == 200
    second_keys = [item["key"] for item in second.json()["data"]["suggestions"]]

    assert len(set(first_keys) & set(second_keys)) <= 1


def test_family_external_batches_use_shareable_distinct_meal_formats(client) -> None:
    """多人到店不应把不同名字的盖饭伪装成多样化。"""
    headers = _login(client, "dining-family-format-123456")
    request = {
        "audience": "family",
        "party_size": 4,
        "city": "杭州",
    }

    first = client.post(
        "/api/v1/dining/recommend",
        headers=headers,
        json=request,
    )
    assert first.status_code == 200
    first_items = first.json()["data"]["suggestions"]

    second = client.post(
        "/api/v1/dining/recommend",
        headers=headers,
        json={
            **request,
            "exclude_keys": [item["key"] for item in first_items],
        },
    )
    assert second.status_code == 200
    second_items = second.json()["data"]["suggestions"]

    third = client.post(
        "/api/v1/dining/recommend",
        headers=headers,
        json={
            **request,
            "exclude_keys": [
                item["key"]
                for item in (*first_items, *second_items)
            ],
        },
    )
    assert third.status_code == 200
    third_items = third.json()["data"]["suggestions"]

    batches = (first_items, second_items, third_items)
    for batch in batches:
        assert all(item["serving_style"] == "shared" for item in batch)
        assert len({item["meal_format"] for item in batch}) == 3
        assert not any("盖饭" in item["dish_name"] for item in batch)
    assert len({item["key"] for batch in batches for item in batch}) == 9


def test_external_recommendation_rejects_too_many_or_blank_exclusions(client) -> None:
    headers = _login(client, "dining-rotation-validation-123456")

    too_many = client.post(
        "/api/v1/dining/recommend",
        headers=headers,
        json={"exclude_keys": [f"rule-{index}" for index in range(31)]},
    )
    blank = client.post(
        "/api/v1/dining/recommend",
        headers=headers,
        json={"exclude_keys": ["   "]},
    )

    assert too_many.status_code == 422
    assert blank.status_code == 422


def test_external_recommendation_recalls_liked_but_excludes_avoided_pair(client) -> None:
    headers = _login(client, "dining-memory-recommend-123456")
    pair = {
        "shop_name": "小陈砂锅",
        "dish_name": "菌菇豆腐煲",
        "note": "少油很好吃",
    }
    liked = client.put(
        "/api/v1/dining/memories",
        headers=headers,
        json={**pair, "verdict": "liked"},
    )
    assert liked.status_code == 200

    first = client.post("/api/v1/dining/recommend", headers=headers, json={})
    first_pairs = {
        (item["shop_name"], item["dish_name"])
        for item in first.json()["data"]["suggestions"]
    }
    assert ("小陈砂锅", "菌菇豆腐煲") in first_pairs

    avoided = client.put(
        "/api/v1/dining/memories",
        headers=headers,
        json={**pair, "verdict": "avoided"},
    )
    assert avoided.status_code == 200

    second = client.post("/api/v1/dining/recommend", headers=headers, json={})
    second_pairs = {
        (item["shop_name"], item["dish_name"])
        for item in second.json()["data"]["suggestions"]
    }
    assert ("小陈砂锅", "菌菇豆腐煲") not in second_pairs


def test_dining_memory_filters_by_date(client) -> None:
    import datetime as _dt

    headers = _login(client, "dining-date-filter-123456")
    memory = client.put(
        "/api/v1/dining/memories",
        headers=headers,
        json={"shop_name": "今天吃的", "dish_name": "面", "verdict": "liked"},
    )
    assert memory.status_code == 200

    today = _dt.date.today().isoformat()
    matched = client.get(f"/api/v1/dining/memories?date={today}", headers=headers)
    assert matched.status_code == 200
    assert matched.json()["data"]["total"] == 1

    future = (_dt.date.today() + _dt.timedelta(days=10)).isoformat()
    empty = client.get(f"/api/v1/dining/memories?date={future}", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["data"]["total"] == 0

    bad = client.get("/api/v1/dining/memories?date=2026-13-01", headers=headers)
    assert bad.status_code == 422
