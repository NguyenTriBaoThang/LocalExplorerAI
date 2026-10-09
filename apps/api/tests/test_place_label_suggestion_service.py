from app.services.place_label_suggestion_service import suggest_place_labels


def test_food_place_gets_food_intent_from_kind_and_source_tags():
    labels = suggest_place_labels({
        "kind": "an-uong",
        "name": "Bánh Xèo Ngọc Sơn",
        "tags": ["banh-xeo", "dac-san", "nam-bo"],
        "description": "Quán bánh xèo lâu năm.",
        "outdoor": False,
    })

    assert labels["poi_type"] == "restaurant"
    assert labels["primary_intent"] == "food"
    assert "food" in labels["intent_tags"]
    assert labels["indoor_outdoor"] == "indoor"


def test_cultural_poi_is_classified_without_inventing_hands_on():
    labels = suggest_place_labels({
        "kind": "tham-quan",
        "name": "Bảo tàng Chứng tích Chiến tranh",
        "tags": ["lich-su", "bao-tang", "van-hoa"],
        "description": "Bảo tàng lưu giữ các hiện vật lịch sử.",
        "outdoor": False,
    })

    assert labels["poi_type"] == "sightseeing"
    assert labels["primary_intent"] == "culture"
    assert labels["hands_on"] is None
    assert labels["hands_on_status"] == "unknown_at_poi_level"


def test_explicit_participatory_description_gets_hands_on_suggestion():
    labels = suggest_place_labels({
        "kind": "tham-quan",
        "name": "Lớp học làm gốm",
        "tags": ["workshop", "thu-cong"],
        "description": "Du khách tự tay nặn gốm trong lớp học.",
        "outdoor": False,
    })

    assert labels["primary_intent"] == "handicraft"
    assert labels["hands_on"] is True
    assert labels["hands_on_status"] == "explicit_source_cue"


def test_entertainment_and_lodging_are_not_forced_into_core_intent():
    nightlife = suggest_place_labels({
        "kind": "giai-tri",
        "name": "Nightclub",
        "tags": ["dj", "live-music"],
        "description": "Live music and DJ.",
        "outdoor": False,
    })
    hotel = suggest_place_labels({"kind": "cho-o", "name": "Hotel", "tags": []})

    assert nightlife["poi_type"] == "entertainment"
    assert nightlife["primary_intent"] is None
    assert "entertainment" in nightlife["intent_tags"]
    assert hotel["poi_type"] == "accommodation"
    assert hotel["primary_intent"] is None
    assert "accommodation" in hotel["intent_tags"]
