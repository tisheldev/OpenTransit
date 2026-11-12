"""Stop mode and direction facets; synthetic data only."""

import pytest

from opentransit.stop_facets import dominant_mode, initial_bearing, mean_bearing


def test_dominant_mode_prefers_rail_then_light_rail_then_bus():
    assert dominant_mode(["bus", "rail", "bus"]) == "rail"
    assert dominant_mode(["bus", "light_rail"]) == "light_rail"
    assert dominant_mode(["bus"]) == "bus"
    assert dominant_mode(["ferry"]) == "other"
    assert dominant_mode([]) is None


def test_initial_bearing_points_the_way_of_travel():
    assert initial_bearing(32.081, 34.781, 32.0801, 34.7801) == pytest.approx(220.3, abs=0.2)
    assert initial_bearing(32.0, 34.0, 32.1, 34.0) == pytest.approx(0.0, abs=0.1)
    assert initial_bearing(32.0, 34.0, 32.0, 34.1) == pytest.approx(90.0, abs=0.1)
    assert initial_bearing(32.0, 34.0, 32.0, 34.0) is None


def test_mean_bearing_crosses_north_and_refuses_disagreement():
    assert mean_bearing([350.0, 10.0]) == 0.0
    assert mean_bearing([80.0, 100.0]) == pytest.approx(90.0, abs=0.1)
    assert mean_bearing([40.0, 40.0, 220.0]) is None
    assert mean_bearing([0.0, 90.0]) is None
    assert mean_bearing([]) is None
