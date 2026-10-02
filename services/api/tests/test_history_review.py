"""OB-01 outlier review: is a slow segment a standstill, slow movement or a frozen distance?"""

from opentransit.history.review import TracePing, classify, segment_trace

LAT, LON = 31.78, 35.23
METRE_LAT = 1 / 111_320  # degrees of latitude per metre (good enough for tests)


def at(t, metres, north_m=None):
    north = metres if north_m is None else north_m
    return TracePing(t, metres, LAT + north * METRE_LAT, LON, 0)


def test_standstill_inside_the_segment_is_stationary():
    pings = [at(0, 900), at(60, 1100)]
    pings += [at(60 + 60 * i, 1100) for i in range(1, 21)]  # 20 minutes standing at 1100 m
    pings += [at(1320, 1400), at(1380, 1700), at(1440, 2100)]
    trace = segment_trace(pings, 1000, 2000)
    assert trace["frozenSeconds"] == 1200
    assert trace["longestFrozenSeconds"] == 1200
    assert trace["gpsNetMetresWhileFrozen"] < 1
    assert 1300 < trace["runSeconds"] < 1400
    assert classify(trace) == "stationary"


def test_frozen_distance_while_the_bus_moves_is_an_artefact():
    pings = [at(0, 900), at(60, 1100)]
    pings += [at(60 + 60 * i, 1100, north_m=1100 + 150 * i) for i in range(1, 11)]
    pings += [at(720, 2100, north_m=2700)]
    trace = segment_trace(pings, 1000, 2000)
    assert trace["gpsNetMetresWhileFrozen"] > 1000
    assert classify(trace) == "distanceFrozenWhileMoving"


def test_steady_slow_progress_is_moving_slowly():
    pings = [at(60 * i, 800 + 50 * i) for i in range(30)]  # 0.8 m/s, never standing
    trace = segment_trace(pings, 1000, 2000)
    assert trace["frozenSeconds"] == 0
    assert trace["runSeconds"] == 1200
    assert classify(trace) == "movingSlowly"


def test_trace_needs_pings_on_both_sides_of_the_segment():
    assert segment_trace([at(0, 1200), at(60, 1500)], 1000, 2000) is None
