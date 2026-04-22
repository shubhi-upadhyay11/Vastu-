"""
optimize.py — Main Orchestrator
--------------------------------
Ties together the Vastu engine, CNN scorer, and GA optimizer.
Can be used standalone or imported by the Flask app.
"""

import sys
import os
import json
from typing import Dict, Any, List

# ── Path setup ───────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from vastu_engine.vastu_rules import VastuEngine, FurniturePlacement
from cnn_model.layout_cnn import LayoutScorer
from genetic_algorithm.ga_optimizer import GeneticLayoutOptimizer


# ════════════════════════════════════════════════════════════════════════════
#  LayoutOptimizer — main facade
# ════════════════════════════════════════════════════════════════════════════

class LayoutOptimizer:
    """
    High-level facade that wires together all sub-modules.

    Usage:
        optimizer = LayoutOptimizer()
        result = optimizer.optimize(room_data)
    """

    def __init__(
        self,
        pop_size: int = 120,
        n_generations: int = 60,
        vastu_weight: float = 0.40,
        cnn_weight: float = 0.60,
        auto_train_cnn: bool = True,
        verbose: bool = True,
    ):
        self.verbose      = verbose
        self.vastu_weight = vastu_weight
        self.cnn_weight   = cnn_weight

        if verbose:
            print("[Optimizer] Initializing CNN Layout Scorer...")
        self.scorer = LayoutScorer(auto_train=auto_train_cnn)

        self.ga_config = dict(
            pop_size=pop_size,
            n_generations=n_generations,
            vastu_weight=vastu_weight,
            cnn_weight=cnn_weight,
        )

    def optimize(self, room_data: Dict[str, Any], top_k: int = 3) -> Dict[str, Any]:
        """
        Accept room_data JSON, return optimized_layouts JSON.

        Input schema:
        {
            "room_dimensions": {"width": 15, "height": 12},
            "north_direction": "top",
            "entrance_wall": "top",          # optional
            "detected_furniture": [
                {"label": "bed",      "w": 3, "h": 2},
                {"label": "wardrobe", "w": 2, "h": 1}
            ]
        }
        """
        # ── Parse input ─────────────────────────────────────────────────────
        dims    = room_data["room_dimensions"]
        room_w  = float(dims["width"])
        room_h  = float(dims["height"])
        north   = room_data.get("north_direction", "top").lower()
        entrance_wall = room_data.get("entrance_wall", north)

        furniture_specs = []
        for item in room_data["detected_furniture"]:
            furniture_specs.append({
                "label": item["label"],
                "w":     float(item["w"]),
                "h":     float(item["h"]),
            })

        if self.verbose:
            print(f"[Optimizer] Room: {room_w}×{room_h}, "
                  f"North={north}, Furniture={[f['label'] for f in furniture_specs]}")

        # ── Build engines ────────────────────────────────────────────────────
        vastu_engine = VastuEngine(room_w, room_h, north_direction=north)

        ga = GeneticLayoutOptimizer(
            vastu_engine=vastu_engine,
            layout_scorer=self.scorer,
            **self.ga_config,
        )

        # ── Run optimization ─────────────────────────────────────────────────
        if self.verbose:
            print("[Optimizer] Running Genetic Algorithm...")

        top_layouts = ga.optimize(
            furniture_specs=furniture_specs,
            room_width=room_w,
            room_height=room_h,
            entrance_wall=entrance_wall,
            top_k=top_k,
            verbose=self.verbose,
        )

        # ── Format output ────────────────────────────────────────────────────
        optimized_layouts = []
        for rank, layout in enumerate(top_layouts, start=1):
            furniture_positions = [
                {
                    "label":    p.label,
                    "x":        round(p.x, 2),
                    "y":        round(p.y, 2),
                    "w":        round(p.w, 2),
                    "h":        round(p.h, 2),
                    "rotation": p.rotation,
                }
                for p in layout["placements"]
            ]

            optimized_layouts.append({
                "layout_id":          rank,
                "vastu_score":        layout["vastu_score"],
                "functional_score":   layout["functional_score"],
                "combined_score":     layout["combined_score"],
                "vastu_violations":   layout["vastu_details"]["violations"],
                "vastu_rule_scores":  layout["vastu_details"]["rule_scores"],
                "furniture_positions": furniture_positions,
            })

        return {
            "room_dimensions":  {"width": room_w, "height": room_h},
            "north_direction":  north,
            "entrance_wall":    entrance_wall,
            "optimized_layouts": optimized_layouts,
        }


# ════════════════════════════════════════════════════════════════════════════
#  CLI entry point
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    sample_input = {
        "room_dimensions": {"width": 15, "height": 12},
        "north_direction": "top",
        "entrance_wall": "top",
        "detected_furniture": [
            {"label": "bed",          "w": 3,   "h": 2  },
            {"label": "wardrobe",     "w": 2,   "h": 1  },
            {"label": "desk",         "w": 1.5, "h": 1  },
            {"label": "sofa",         "w": 3,   "h": 1.2},
            {"label": "dining_table", "w": 2,   "h": 1.5},
        ],
    }

    print("=" * 60)
    print("  AI Interior Design — Layout Optimization Module")
    print("=" * 60)

    optimizer = LayoutOptimizer(
        pop_size=80,
        n_generations=40,
        auto_train_cnn=True,
        verbose=True,
    )

    result = optimizer.optimize(sample_input, top_k=3)

    print("\n" + "=" * 60)
    print("  OPTIMIZED LAYOUTS")
    print("=" * 60)
    print(json.dumps(result, indent=2))

    # Save sample output
    out_path = os.path.join(os.path.dirname(__file__), "sample_data", "sample_output.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n[✓] Output saved → {out_path}")