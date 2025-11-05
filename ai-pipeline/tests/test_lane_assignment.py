from pipeline.beatmap_generator import assign_lanes


def _lane_for(component: str) -> int:
    hits = assign_lanes([
        {
            "component": component,
            "time": 0.0,
            "confidence": 1.0,
        }
    ])
    return hits[0]["lane"]


def test_primary_components_follow_liveinput_layout():
    expected = {
        "kick": 3,
        "snare": 1,
        "hihat_closed": 5,
        "hihat_open": 5,
        "hihat_pedal": 0,
        "tom_high": 2,
        "tom_mid": 4,
        "tom_low": 4,
        "crash": 6,
        "crash2": 0,
        "ride": 6,
    }

    for component, lane in expected.items():
        assert _lane_for(component) == lane, f"{component} should map to lane {lane}"


def test_aliases_and_case_insensitive_mapping():
    assert _lane_for("Bass_Drum") == 3
    assert _lane_for("HI-HAT") == 5
    assert _lane_for("Floor_Tom") == 4


def test_unknown_component_defaults_to_fallback_lane():
    assert _lane_for("triangle") == 4
    assert _lane_for("") == 4


def test_auxiliary_percussion_prefers_far_left_lane():
    assert _lane_for("cowbell") == 0
    assert _lane_for("shaker") == 0


def test_cymbal_clusters_alternate_between_edges():
    hits = assign_lanes([
        {"component": "crash", "time": 0.0},
        {"component": "ride", "time": 0.2},
        {"component": "crash", "time": 0.4},
    ])

    assert [hit["lane"] for hit in hits] == [6, 0, 6]
    stats = getattr(assign_lanes, "_lane_stats", {})
    assert stats.get("cymbal_switches") == 2


def test_cymbals_reset_after_spacing_gap():
    hits = assign_lanes([
        {"component": "crash", "time": 0.0},
        {"component": "ride", "time": 1.0},
    ])

    assert [hit["lane"] for hit in hits] == [6, 6]


def test_tom_rolls_alternate_between_inner_pairs():
    hits = assign_lanes([
        {"component": "tom_low", "time": 0.0},
        {"component": "tom_high", "time": 0.18},
        {"component": "tom_low", "time": 0.32},
    ])

    assert [hit["lane"] for hit in hits] == [4, 2, 4]
    stats = getattr(assign_lanes, "_lane_stats", {})
    assert stats.get("tom_switches") == 2


def test_tom_spacing_resets_to_default_lane():
    hits = assign_lanes([
        {"component": "tom_high", "time": 0.0},
        {"component": "tom_mid", "time": 1.0},
    ])

    assert [hit["lane"] for hit in hits] == [2, 4]
