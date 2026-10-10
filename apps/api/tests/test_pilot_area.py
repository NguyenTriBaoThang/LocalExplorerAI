from app.services.pilot_area import is_pilot_location


def test_legacy_district_one_polygon_accepts_central_pois():
    assert is_pilot_location(10.7769, 106.7009)  # Central District 1
    assert is_pilot_location(10.7875, 106.7053)  # Saigon Zoo


def test_legacy_district_one_polygon_rejects_other_city_areas_even_if_labels_lie():
    assert not is_pilot_location(10.7950, 106.7219)  # Landmark 81 / Binh Thanh
    assert not is_pilot_location(11.1444, 106.4628)  # Cu Chi
    assert not is_pilot_location(10.8661, 106.8028)  # Suoi Tien / Thu Duc


def test_pilot_polygon_rejects_invalid_coordinates():
    assert not is_pilot_location(91, 106.7)
    assert not is_pilot_location(10.77, 181)
