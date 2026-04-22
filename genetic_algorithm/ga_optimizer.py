"""
Genetic Algorithm Layout Optimizer
-----------------------------------
Uses DEAP to explore furniture arrangement possibilities.

Chromosome encoding:
  For N furniture pieces, genome = [x0, y0, rot0, x1, y1, rot1, ...]
  where xi, yi are real positions and roti ∈ {0, 90, 180, 270}

Fitness = 0.40 * vastu_score + 0.60 * cnn_score  (both in [0, 100])
"""

import random
import math
from copy import deepcopy
from typing import List, Dict, Any, Tuple, Optional

try:
    from deap import base, creator, tools, algorithms
    DEAP_AVAILABLE = True
except ImportError:
    DEAP_AVAILABLE = False
    print("[GA] DEAP not installed — falling back to simple random search.")

from vastu_engine.vastu_rules import VastuEngine, FurniturePlacement
from cnn_model.layout_cnn import LayoutScorer


# ─────────────────────────────────────────────────────────────────────────────
#  Helper: decode genome → list of FurniturePlacement
# ─────────────────────────────────────────────────────────────────────────────

ROTATIONS = [0, 90, 180, 270]
GENES_PER_PIECE = 3   # x, y, rot_idx


def genome_to_placements(
    genome: List[float],
    furniture_specs: List[Dict],
    room_width: float,
    room_height: float,
) -> List[FurniturePlacement]:
    placements = []
    for i, spec in enumerate(furniture_specs):
        base_idx = i * GENES_PER_PIECE
        x_norm   = genome[base_idx]        # [0, 1]
        y_norm   = genome[base_idx + 1]    # [0, 1]
        rot_idx  = int(genome[base_idx + 2]) % 4
        rotation = ROTATIONS[rot_idx]

        # Swap w/h for 90/270 rotation
        if rotation in [90, 270]:
            w, h = spec["h"], spec["w"]
        else:
            w, h = spec["w"], spec["h"]

        # Clamp so furniture stays inside room
        x = max(0.0, min(room_width  - w, x_norm * room_width))
        y = max(0.0, min(room_height - h, y_norm * room_height))

        placements.append(FurniturePlacement(
            label=spec["label"],
            x=round(x, 2),
            y=round(y, 2),
            w=w,
            h=h,
            rotation=rotation,
        ))
    return placements


# ─────────────────────────────────────────────────────────────────────────────
#  Fitness Function
# ─────────────────────────────────────────────────────────────────────────────

class FitnessEvaluator:
    def __init__(
        self,
        vastu_engine: VastuEngine,
        layout_scorer: LayoutScorer,
        furniture_specs: List[Dict],
        room_width: float,
        room_height: float,
        entrance_wall: str = "top",
        vastu_weight: float = 0.40,
        cnn_weight: float = 0.60,
    ):
        self.vastu     = vastu_engine
        self.scorer    = layout_scorer
        self.specs     = furniture_specs
        self.rw        = room_width
        self.rh        = room_height
        self.entrance  = entrance_wall
        self.wv        = vastu_weight
        self.wc        = cnn_weight

    def __call__(self, genome: List[float]) -> Tuple[float]:
        placements = genome_to_placements(genome, self.specs, self.rw, self.rh)

        vastu_result = self.vastu.compute_vastu_score(
            placements, entrance_wall=self.entrance
        )
        vastu_score = vastu_result["total_score"]  # 0–100

        cnn_score = self.scorer.score(placements, self.rw, self.rh)  # 0–100

        # Overlap / bounds penalties (hard constraints)
        overlap_penalty = vastu_result["overlap_penalty"]       # 0–100
        bounds_penalty  = vastu_result["bounds_penalty"]        # 0–100

        combined = (
            self.wv * vastu_score
            + self.wc * cnn_score
            - 0.5 * overlap_penalty
            - 0.3 * bounds_penalty
        )
        return (max(0.0, combined),)   # DEAP expects a tuple


# ─────────────────────────────────────────────────────────────────────────────
#  Genetic Algorithm Optimizer
# ─────────────────────────────────────────────────────────────────────────────

class GeneticLayoutOptimizer:
    """
    DEAP-based genetic algorithm for furniture layout optimization.
    Falls back to random search when DEAP is unavailable.
    """

    def __init__(
        self,
        vastu_engine: VastuEngine,
        layout_scorer: LayoutScorer,
        pop_size: int = 120,
        n_generations: int = 60,
        cx_prob: float = 0.7,
        mut_prob: float = 0.3,
        vastu_weight: float = 0.40,
        cnn_weight: float = 0.60,
    ):
        self.vastu      = vastu_engine
        self.scorer     = layout_scorer
        self.pop_size   = pop_size
        self.n_gens     = n_generations
        self.cx_prob    = cx_prob
        self.mut_prob   = mut_prob
        self.wv         = vastu_weight
        self.wc         = cnn_weight

    def _genome_length(self, n_pieces: int) -> int:
        return n_pieces * GENES_PER_PIECE

    def _random_genome(self, n_pieces: int) -> List[float]:
        genome = []
        for _ in range(n_pieces):
            genome.append(random.random())          # x_norm
            genome.append(random.random())          # y_norm
            genome.append(float(random.randint(0, 3)))  # rot_idx
        return genome

    def optimize(
        self,
        furniture_specs: List[Dict],
        room_width: float,
        room_height: float,
        entrance_wall: str = "top",
        top_k: int = 3,
        verbose: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Run GA optimization and return top_k layout configurations.

        Each config: {
            genome, placements, vastu_score, functional_score, combined_score
        }
        """
        n_pieces = len(furniture_specs)
        g_len    = self._genome_length(n_pieces)

        evaluator = FitnessEvaluator(
            self.vastu, self.scorer, furniture_specs,
            room_width, room_height, entrance_wall, self.wv, self.wc,
        )

        if DEAP_AVAILABLE:
            results = self._run_deap(g_len, n_pieces, evaluator, verbose)
        else:
            results = self._run_random_search(g_len, evaluator, verbose)

        # Re-score top results for detailed breakdown
        output = []
        seen_genomes = set()
        for genome, _ in results:
            key = tuple(round(g, 2) for g in genome)
            if key in seen_genomes:
                continue
            seen_genomes.add(key)

            placements = genome_to_placements(genome, furniture_specs, room_width, room_height)
            vastu_result = self.vastu.compute_vastu_score(placements, entrance_wall=entrance_wall)
            cnn_score    = self.scorer.score(placements, room_width, room_height)

            output.append({
                "placements":       placements,
                "vastu_score":      vastu_result["total_score"],
                "vastu_details":    vastu_result,
                "functional_score": round(cnn_score, 1),
                "combined_score":   round(
                    self.wv * vastu_result["total_score"] + self.wc * cnn_score, 1
                ),
            })

            if len(output) >= top_k:
                break

        output.sort(key=lambda x: x["combined_score"], reverse=True)
        return output[:top_k]

    # ── DEAP Implementation ─────────────────────────────────────────────────

    def _run_deap(self, g_len: int, n_pieces: int, evaluator, verbose: bool):
        # Re-create creator to avoid duplicate registration errors
        if "FitnessMax" not in dir(creator):
            creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        if "Individual" not in dir(creator):
            creator.create("Individual", list, fitness=creator.FitnessMax)

        toolbox = base.Toolbox()
        toolbox.register("attr_float", random.random)
        toolbox.register(
            "individual",
            tools.initIterate,
            creator.Individual,
            lambda: self._random_genome(n_pieces),
        )
        toolbox.register("population", tools.initRepeat, list, toolbox.individual)
        toolbox.register("evaluate", evaluator)
        toolbox.register("mate",   tools.cxBlend, alpha=0.3)
        toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=0.15, indpb=0.3)
        toolbox.register("select", tools.selTournament, tournsize=5)

        pop  = toolbox.population(n=self.pop_size)
        hof  = tools.HallOfFame(20)
        stats = tools.Statistics(lambda ind: ind.fitness.values)
        stats.register("max", max)
        stats.register("avg", lambda vals: sum(v[0] for v in vals) / len(vals))

        if verbose:
            print(f"[GA] Running DEAP: pop={self.pop_size}, gens={self.n_gens}")

        pop, log = algorithms.eaSimple(
            pop, toolbox,
            cxpb=self.cx_prob,
            mutpb=self.mut_prob,
            ngen=self.n_gens,
            stats=stats,
            halloffame=hof,
            verbose=verbose,
        )

        # Return (genome, fitness) tuples from hall of fame
        return [(list(ind), ind.fitness.values[0]) for ind in hof]

    # ── Fallback Random Search ──────────────────────────────────────────────

    def _run_random_search(self, g_len: int, evaluator, verbose: bool):
        """Simple random search fallback when DEAP is unavailable."""
        n_trials = self.pop_size * self.n_gens
        if verbose:
            print(f"[GA] DEAP unavailable — random search over {n_trials} samples")

        best = []
        for i in range(n_trials):
            genome = [random.random() if j % 3 != 2 else float(random.randint(0, 3))
                      for j in range(g_len)]
            score = evaluator(genome)[0]
            best.append((genome, score))

        best.sort(key=lambda x: x[1], reverse=True)
        return best[:20]