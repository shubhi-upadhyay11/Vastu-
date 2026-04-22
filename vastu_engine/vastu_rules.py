"""
Vastu Shastra Rule Engine
Encodes traditional Vastu principles and scores room layouts (0-100).
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import math


@dataclass
class FurniturePlacement:
    label: str
    x: float        # top-left x position
    y: float        # top-left y position
    w: float        # width
    h: float        # height
    rotation: int   # 0, 90, 180, 270


class VastuEngine:
    """
    Encodes Vastu Shastra rules for room layout optimization.

    North direction is defined by the 'north_direction' field in room config:
      - "top"    → y=0 is North
      - "bottom" → y=max is North
      - "left"   → x=0 is North
      - "right"  → x=max is North
    """

    # Vastu zone weights (what fraction of total score each rule contributes)
    RULE_WEIGHTS = {
        "entrance_direction":     0.20,
        "bedroom_position":       0.20,
        "kitchen_position":       0.15,
        "study_position":         0.10,
        "bed_head_direction":     0.15,
        "doorway_clearance":      0.10,
        "bathroom_position":      0.05,
        "living_room_position":   0.05,
    }

    # Ideal quadrant/zone mapping for each furniture type
    # Zones: NE, NW, SE, SW, N, S, E, W, CENTER
    VASTU_ZONES = {
        "bed":          ["SW"],                     # Bedroom → South-West
        "wardrobe":     ["SW", "S", "W"],
        "kitchen":      ["SE"],                     # Kitchen → South-East
        "stove":        ["SE"],
        "refrigerator": ["SE", "NW"],
        "desk":         ["N", "NE", "E"],           # Study/Office → North or East
        "study_table":  ["N", "NE", "E"],
        "computer":     ["N", "NE", "E"],
        "sofa":         ["NW", "W", "SW"],          # Living → North-West
        "tv":           ["SE", "E"],
        "dining_table": ["W", "NW"],
        "toilet":       ["NW", "W"],
        "bathroom":     ["NW", "W"],
        "plant":        ["NE", "N", "E"],           # Plants → North-East (prosperity)
        "bookshelf":    ["N", "NE", "E", "W"],
        "mirror":       ["N", "E"],                 # Mirrors → North or East walls
    }

    # Bed head direction rules (South or East preferred)
    BED_HEAD_PREFERRED = ["S", "E"]
    BED_HEAD_FORBIDDEN = ["N"]   # Never head towards North (bad for sleep)

    def __init__(self, room_width: float, room_height: float, north_direction: str = "top"):
        self.room_width = room_width
        self.room_height = room_height
        self.north_direction = north_direction.lower()
        self._validate_north()

    def _validate_north(self):
        valid = ["top", "bottom", "left", "right"]
        if self.north_direction not in valid:
            raise ValueError(f"north_direction must be one of {valid}")

    # ─────────────────────────────────────────────
    # Coordinate → Cardinal Direction utilities
    # ─────────────────────────────────────────────

    def _get_center(self, p: FurniturePlacement) -> Tuple[float, float]:
        """Return the center (cx, cy) of a furniture piece."""
        return p.x + p.w / 2, p.y + p.h / 2

    def _normalize_to_compass(self, cx: float, cy: float) -> str:
        """
        Given a center point, return which compass zone it belongs to
        based on room dimensions and north_direction.

        Returns one of: N, NE, E, SE, S, SW, W, NW, CENTER
        """
        rx = cx / self.room_width    # 0..1  (left → right in pixel space)
        ry = cy / self.room_height   # 0..1  (top → bottom in pixel space)

        # Remap rx, ry → compass (nx=East magnitude, ny=North magnitude)
        if self.north_direction == "top":
            north_mag = 1 - ry   # higher y → more South
            east_mag  = rx
        elif self.north_direction == "bottom":
            north_mag = ry
            east_mag  = rx
        elif self.north_direction == "left":
            north_mag = 1 - rx
            east_mag  = 1 - ry
        else:  # right
            north_mag = rx
            east_mag  = ry

        # Classify into 9 zones
        col = "E" if east_mag > 0.60 else ("W" if east_mag < 0.40 else "C")
        row = "N" if north_mag > 0.60 else ("S" if north_mag < 0.40 else "C")

        if row == "C" and col == "C":
            return "CENTER"
        if row == "C":
            return col
        if col == "C":
            return row
        return row + col   # e.g. "NE", "SW"

    def _get_compass_of_wall(self, side: str) -> str:
        """Map a visual wall ('top','bottom','left','right') to compass direction."""
        wall_map = {
            ("top",    "top"):    "N",
            ("top",    "bottom"): "S",
            ("top",    "left"):   "W",
            ("top",    "right"):  "E",
            ("bottom", "top"):    "S",
            ("bottom", "bottom"): "N",
            ("bottom", "left"):   "W",
            ("bottom", "right"):  "E",
            ("left",   "top"):    "E",
            ("left",   "bottom"): "W",
            ("left",   "left"):   "N",
            ("left",   "right"):  "S",
            ("right",  "top"):    "W",
            ("right",  "bottom"): "E",
            ("right",  "left"):   "S",
            ("right",  "right"):  "N",
        }
        return wall_map.get((self.north_direction, side), "N")

    def _entrance_compass(self, entrance_wall: str) -> str:
        """Return compass direction an entrance on a given visual wall faces."""
        return self._get_compass_of_wall(entrance_wall)

    # ─────────────────────────────────────────────
    # Individual Rule Scorers (each returns 0.0–1.0)
    # ─────────────────────────────────────────────

    def score_entrance_direction(self, entrance_wall: str = "top") -> float:
        """Main entrance should face North or East."""
        compass = self._entrance_compass(entrance_wall)
        if compass in ["N", "E", "NE"]:
            return 1.0
        if compass in ["NW", "SE"]:
            return 0.6
        return 0.2

    def score_furniture_zone(self, piece: FurniturePlacement) -> float:
        """Score how well a furniture piece sits in its ideal Vastu zone."""
        label = piece.label.lower().replace(" ", "_")
        ideal_zones = self.VASTU_ZONES.get(label)
        if ideal_zones is None:
            return 0.75   # Unknown furniture → neutral score

        cx, cy = self._get_center(piece)
        zone = self._normalize_to_compass(cx, cy)

        if zone in ideal_zones:
            return 1.0

        # Partial credit if adjacent zone
        partial_adjacency = {
            "N":  ["NE", "NW"],
            "S":  ["SE", "SW"],
            "E":  ["NE", "SE"],
            "W":  ["NW", "SW"],
            "NE": ["N", "E"],
            "NW": ["N", "W"],
            "SE": ["S", "E"],
            "SW": ["S", "W"],
            "CENTER": [],
        }
        adjacent = partial_adjacency.get(zone, [])
        for iz in ideal_zones:
            if iz in adjacent or zone in partial_adjacency.get(iz, []):
                return 0.5

        return 0.1

    def score_bed_head_direction(self, bed: FurniturePlacement) -> float:
        """
        Bed head direction score.
        Rotation=0   → head at top (visual top wall)
        Rotation=90  → head at right wall
        Rotation=180 → head at bottom wall
        Rotation=270 → head at left wall
        """
        visual_head_wall = {0: "top", 90: "right", 180: "bottom", 270: "left"}.get(
            bed.rotation % 360, "top"
        )
        head_compass = self._get_compass_of_wall(visual_head_wall)

        if head_compass in self.BED_HEAD_PREFERRED:
            return 1.0
        if head_compass in self.BED_HEAD_FORBIDDEN:
            return 0.0
        return 0.5

    def score_doorway_clearance(
        self,
        placements: List[FurniturePlacement],
        doorways: List[Dict[str, float]] = None,
        min_clearance: float = 1.5,
    ) -> float:
        """
        Penalize furniture that blocks doorways or is too close to room edges
        (simulating doorway clearance when no explicit doorway coords given).
        """
        if doorways:
            penalties = 0
            total_checks = 0
            for door in doorways:
                dx, dy = door["x"], door["y"]
                for p in placements:
                    dist = math.hypot(
                        max(p.x - dx, 0, dx - (p.x + p.w)),
                        max(p.y - dy, 0, dy - (p.y + p.h)),
                    )
                    total_checks += 1
                    if dist < min_clearance:
                        penalties += 1
            return 1.0 - (penalties / max(total_checks, 1))

        # Heuristic: penalize pieces within min_clearance of any wall
        # (doorways are usually near walls)
        penalties = 0
        for p in placements:
            near_wall = (
                p.x < min_clearance
                or p.y < min_clearance
                or (p.x + p.w) > (self.room_width - min_clearance)
                or (p.y + p.h) > (self.room_height - min_clearance)
            )
            if near_wall:
                penalties += 0.5   # soft penalty — being near wall is fine unless blocking
        score = 1.0 - (penalties / max(len(placements), 1))
        return max(0.0, min(1.0, score))

    def score_no_overlap(self, placements: List[FurniturePlacement]) -> float:
        """Penalize overlapping furniture (hard constraint)."""
        n = len(placements)
        if n <= 1:
            return 1.0

        overlaps = 0
        pairs = 0
        for i in range(n):
            for j in range(i + 1, n):
                a, b = placements[i], placements[j]
                pairs += 1
                if not (
                    a.x + a.w <= b.x
                    or b.x + b.w <= a.x
                    or a.y + a.h <= b.y
                    or b.y + b.h <= a.y
                ):
                    overlaps += 1
        return 1.0 - (overlaps / pairs)

    def score_within_bounds(self, placements: List[FurniturePlacement]) -> float:
        """All furniture must be within room bounds."""
        violations = sum(
            1 for p in placements
            if p.x < 0
            or p.y < 0
            or (p.x + p.w) > self.room_width
            or (p.y + p.h) > self.room_height
        )
        return 1.0 - (violations / max(len(placements), 1))

    # ─────────────────────────────────────────────
    # Main Scoring Function
    # ─────────────────────────────────────────────

    def compute_vastu_score(
        self,
        placements: List[FurniturePlacement],
        entrance_wall: str = "top",
        doorways: List[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Compute an overall Vastu compliance score (0–100) for a layout.

        Returns a dict with:
          - total_score: int (0–100)
          - rule_scores: individual sub-scores
          - violations: list of rule violation messages
        """
        rule_scores = {}
        violations = []

        # 1. Entrance direction
        rule_scores["entrance_direction"] = self.score_entrance_direction(entrance_wall)
        if rule_scores["entrance_direction"] < 0.5:
            violations.append(
                f"Entrance faces {self._entrance_compass(entrance_wall)} — "
                "should face North or East."
            )

        # 2. Furniture zone placement
        zone_scores = []
        for p in placements:
            s = self.score_furniture_zone(p)
            zone_scores.append(s)
            label = p.label.lower().replace(" ", "_")
            if label in self.VASTU_ZONES and s < 0.5:
                cx, cy = self._get_center(p)
                actual_zone = self._normalize_to_compass(cx, cy)
                ideal = self.VASTU_ZONES[label]
                violations.append(
                    f"{p.label} is in {actual_zone} zone — "
                    f"ideal zone(s): {', '.join(ideal)}."
                )

        # Bedroom score
        beds = [p for p in placements if "bed" in p.label.lower()]
        rule_scores["bedroom_position"] = (
            sum(self.score_furniture_zone(b) for b in beds) / len(beds) if beds else 0.75
        )

        # Kitchen score
        kitchens = [p for p in placements if any(k in p.label.lower() for k in ["kitchen", "stove", "refrigerator"])]
        rule_scores["kitchen_position"] = (
            sum(self.score_furniture_zone(k) for k in kitchens) / len(kitchens) if kitchens else 0.75
        )

        # Study score
        studies = [p for p in placements if any(s in p.label.lower() for s in ["desk", "study", "computer"])]
        rule_scores["study_position"] = (
            sum(self.score_furniture_zone(s) for s in studies) / len(studies) if studies else 0.75
        )

        # Living room
        sofas = [p for p in placements if "sofa" in p.label.lower()]
        rule_scores["living_room_position"] = (
            sum(self.score_furniture_zone(s) for s in sofas) / len(sofas) if sofas else 0.75
        )

        # 3. Bed head direction
        if beds:
            head_scores = [self.score_bed_head_direction(b) for b in beds]
            rule_scores["bed_head_direction"] = sum(head_scores) / len(head_scores)
            for b, s in zip(beds, head_scores):
                if s == 0.0:
                    violations.append(
                        f"Bed '{b.label}' head faces North — "
                        "this is forbidden in Vastu (causes sleep disorders)."
                    )
        else:
            rule_scores["bed_head_direction"] = 0.75

        # 4. Doorway clearance
        rule_scores["doorway_clearance"] = self.score_doorway_clearance(placements, doorways)
        if rule_scores["doorway_clearance"] < 0.5:
            violations.append("Furniture may be blocking doorway clearance zones.")

        # 5. Bathroom position
        bathrooms = [p for p in placements if any(b in p.label.lower() for b in ["bathroom", "toilet"])]
        rule_scores["bathroom_position"] = (
            sum(self.score_furniture_zone(b) for b in bathrooms) / len(bathrooms) if bathrooms else 0.75
        )

        # Hard constraint scores (not weighted but gated)
        overlap_score = self.score_no_overlap(placements)
        bounds_score = self.score_within_bounds(placements)

        if overlap_score < 1.0:
            violations.append("⚠ Furniture pieces are overlapping each other.")
        if bounds_score < 1.0:
            violations.append("⚠ Some furniture is placed outside room boundaries.")

        # Weighted combination
        weighted = sum(
            self.RULE_WEIGHTS.get(k, 0) * v
            for k, v in rule_scores.items()
        )

        # Hard constraints multiply the score
        final = weighted * overlap_score * bounds_score

        total_score = round(final * 100)

        return {
            "total_score": total_score,
            "rule_scores": {k: round(v * 100, 1) for k, v in rule_scores.items()},
            "overlap_penalty": round((1 - overlap_score) * 100, 1),
            "bounds_penalty": round((1 - bounds_score) * 100, 1),
            "violations": violations,
        }