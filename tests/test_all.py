"""
Tests for the ML Layout Optimization module.
Run with:  pytest tests/test_all.py -v
"""

import sys
import os
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vastu_engine.vastu_rules import VastuEngine, FurniturePlacement
from cnn_model.layout_cnn import encode_layout_to_grid, _compute_heuristic_score, GRID_H, GRID_W, N_CHANNELS


# ─── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def small_room():
    return VastuEngine(room_width=15, room_height=12, north_direction="top")


@pytest.fixture
def bed_sw(small_room):
    """Bed placed in SW — ideal zone."""
    return FurniturePlacement(label="bed", x=11, y=9, w=3, h=2, rotation=0)


@pytest.fixture
def bed_ne(small_room):
    """Bed placed in NE — bad zone."""
    return FurniturePlacement(label="bed", x=10, y=0, w=3, h=2, rotation=0)


@pytest.fixture
def kitchen_se():
    return FurniturePlacement(label="kitchen", x=12, y=9, w=2.5, h=2, rotation=0)


@pytest.fixture
def desk_north():
    return FurniturePlacement(label="desk", x=5, y=0.5, w=1.5, h=1, rotation=0)


# ─── Vastu Engine Tests ──────────────────────────────────────────────────────

class TestVastuEngine:

    def test_entrance_north_scores_high(self, small_room):
        score = small_room.score_entrance_direction("top")  # top=North for north_direction=top
        assert score == 1.0

    def test_entrance_south_scores_low(self, small_room):
        score = small_room.score_entrance_direction("bottom")  # bottom=South
        assert score < 0.5

    def test_bed_in_sw_scores_high(self, small_room, bed_sw):
        score = small_room.score_furniture_zone(bed_sw)
        assert score >= 0.8

    def test_bed_in_ne_scores_low(self, small_room, bed_ne):
        score = small_room.score_furniture_zone(bed_ne)
        assert score <= 0.5

    def test_kitchen_in_se_scores_high(self):
        engine = VastuEngine(15, 12, "top")
        kitchen = FurniturePlacement(label="kitchen", x=12, y=9, w=2.5, h=2, rotation=0)
        score = engine.score_furniture_zone(kitchen)
        assert score >= 0.8

    def test_bed_head_south_is_best(self, small_room, bed_sw):
        # rotation=0 → head at top → visual top = North for north_direction=top
        # rotation=180 → head at bottom → South = best
        bed_good = FurniturePlacement(label="bed", x=11, y=9, w=3, h=2, rotation=180)
        score = small_room.score_bed_head_direction(bed_good)
        assert score == 1.0

    def test_bed_head_north_is_forbidden(self, small_room):
        bed_bad = FurniturePlacement(label="bed", x=11, y=9, w=3, h=2, rotation=0)
        score = small_room.score_bed_head_direction(bed_bad)
        assert score == 0.0

    def test_no_overlap_penalty_on_clean_layout(self, small_room, bed_sw, kitchen_se, desk_north):
        score = small_room.score_no_overlap([bed_sw, kitchen_se, desk_north])
        assert score == 1.0

    def test_overlap_detected(self, small_room):
        a = FurniturePlacement(label="bed",     x=5, y=5, w=3, h=2, rotation=0)
        b = FurniturePlacement(label="wardrobe", x=6, y=5, w=2, h=1, rotation=0)  # overlaps a
        score = small_room.score_no_overlap([a, b])
        assert score < 1.0

    def test_out_of_bounds_penalized(self, small_room):
        p = FurniturePlacement(label="bed", x=14, y=11, w=3, h=2, rotation=0)  # extends beyond 15x12
        score = small_room.score_within_bounds([p])
        assert score < 1.0

    def test_total_score_is_0_to_100(self, small_room, bed_sw, kitchen_se, desk_north):
        result = small_room.compute_vastu_score([bed_sw, kitchen_se, desk_north])
        assert 0 <= result["total_score"] <= 100

    def test_score_improves_with_good_layout(self, small_room):
        good = [
            FurniturePlacement("bed",          x=10, y=8,   w=3,   h=2,   rotation=180),  # SW, head South
            FurniturePlacement("kitchen",       x=11.5, y=9, w=2.5, h=2,   rotation=0),    # SE
            FurniturePlacement("desk",          x=5,  y=0.5, w=1.5, h=1,   rotation=0),    # N
        ]
        bad = [
            FurniturePlacement("bed",           x=0,  y=0,   w=3,   h=2,   rotation=0),    # NW, head N
            FurniturePlacement("kitchen",       x=0,  y=0.5, w=2.5, h=2,   rotation=0),    # NW (overlaps!)
            FurniturePlacement("desk",          x=10, y=9,   w=1.5, h=1,   rotation=0),    # SW
        ]
        good_score = small_room.compute_vastu_score(good)["total_score"]
        bad_score  = small_room.compute_vastu_score(bad)["total_score"]
        assert good_score > bad_score

    def test_violations_reported(self, small_room):
        bad_bed = FurniturePlacement("bed", x=0, y=0, w=3, h=2, rotation=0)  # NW + head North
        result = small_room.compute_vastu_score([bad_bed])
        assert len(result["violations"]) > 0

    def test_north_direction_variations(self):
        for nd in ["top", "bottom", "left", "right"]:
            engine = VastuEngine(15, 12, nd)
            p = FurniturePlacement("sofa", x=5, y=5, w=3, h=1.2, rotation=0)
            result = engine.compute_vastu_score([p])
            assert 0 <= result["total_score"] <= 100


# ─── Grid Encoder Tests ──────────────────────────────────────────────────────

class TestGridEncoder:

    def test_grid_shape(self):
        p = FurniturePlacement("bed", x=5, y=5, w=3, h=2, rotation=0)
        grid = encode_layout_to_grid([p], room_width=15, room_height=12)
        assert grid.shape == (N_CHANNELS, GRID_H, GRID_W)

    def test_grid_values_in_range(self):
        p = FurniturePlacement("kitchen", x=2, y=2, w=2, h=2, rotation=0)
        grid = encode_layout_to_grid([p], 15, 12)
        assert grid.min() >= 0.0
        assert grid.max() <= 1.0

    def test_empty_channel_decreases_with_furniture(self):
        import numpy as np
        p = FurniturePlacement("sofa", x=0, y=0, w=5, h=5, rotation=0)
        grid_with = encode_layout_to_grid([p], 15, 12)
        grid_empty_room = encode_layout_to_grid([], 15, 12)
        assert grid_with[5].sum() < grid_empty_room[5].sum()  # channel 5 = empty

    def test_heuristic_score_range(self):
        import numpy as np
        p = FurniturePlacement("bed", x=5, y=5, w=3, h=2, rotation=0)
        grid = encode_layout_to_grid([p], 15, 12)
        score = _compute_heuristic_score(grid)
        assert 0.0 <= score <= 1.0


# ─── Integration Test ────────────────────────────────────────────────────────

class TestIntegration:

    def test_full_optimize_pipeline(self):
        """End-to-end test using heuristic scorer (no CNN required)."""
        from cnn_model.layout_cnn import LayoutScorer
        from genetic_algorithm.ga_optimizer import GeneticLayoutOptimizer

        engine = VastuEngine(15, 12, "top")
        scorer = LayoutScorer(auto_train=False)   # heuristic mode

        ga = GeneticLayoutOptimizer(
            vastu_engine=engine,
            layout_scorer=scorer,
            pop_size=20,
            n_generations=5,
        )

        specs = [
            {"label": "bed",      "w": 3,   "h": 2  },
            {"label": "wardrobe", "w": 2,   "h": 1  },
        ]

        results = ga.optimize(specs, 15, 12, top_k=3, verbose=False)
        assert len(results) > 0
        for r in results:
            assert 0 <= r["vastu_score"] <= 100
            assert 0 <= r["functional_score"] <= 100
            assert len(r["placements"]) == 2