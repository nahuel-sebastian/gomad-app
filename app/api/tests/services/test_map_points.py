import pytest

import settings
from services.map_points import InvalidBbox, clip_bbox, parse_bbox, validate_map_config


def test_parse_bbox_reads_four_numbers():
    assert parse_bbox("-3.75,40.29,-3.70,40.32") == (-3.75, 40.29, -3.70, 40.32)


@pytest.mark.parametrize("text", ["a,b,c,d", "1,2,3", "1,2,3,4,5", "nan,0,1,1", "0,0,inf,1", "1,0,0,1",
                                  "0,1,1,0", "0,0,1,91", "-181,0,1,1", ""])
def test_parse_bbox_rejects_bad_text(text):
    with pytest.raises(InvalidBbox):
        parse_bbox(text)


def test_clip_bbox_keeps_small_box():
    assert clip_bbox((-3.75, 40.29, -3.70, 40.32), 0.3) == ((-3.75, 40.29, -3.70, 40.32), False)


def test_clip_bbox_centres_big_box():
    box, clipped = clip_bbox((0.0, 0.0, 1.0, 1.0), 0.3)
    assert clipped
    assert box == pytest.approx((0.35, 0.35, 0.65, 0.65))


def test_clip_bbox_clips_one_side_only():
    box, clipped = clip_bbox((0.0, 0.0, 1.0, 0.1), 0.3)
    assert clipped
    assert box == pytest.approx((0.35, 0.0, 0.65, 0.1))


@pytest.mark.parametrize("cfg", [None, {}, {"max_span_deg": 0, "max_points": 10, "pool_activity": "swim"},
                                 {"max_span_deg": 0.3, "max_points": -1, "pool_activity": "swim"},
                                 {"max_span_deg": 0.3, "max_points": 10, "pool_activity": ""}])
def test_validate_map_config_needs_positive_values(cfg):
    with pytest.raises(ValueError):
        validate_map_config(cfg)


def test_shipped_map_config_is_valid():
    validate_map_config(settings.load("map"))
