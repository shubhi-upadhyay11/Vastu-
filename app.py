"""
app.py — Flask REST API
------------------------
POST /optimize   → Run layout optimization
GET  /health     → Health check
GET  /vastu/score → Score a specific layout (no GA)
POST /train/cnn  → Re-train the CNN model
"""

import sys
import os
import json
import time
import logging

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify, Response
from flask_cors import CORS

from optimize import LayoutOptimizer
from vastu_engine.vastu_rules import VastuEngine, FurniturePlacement
from cnn_model.layout_cnn import LayoutScorer, train_cnn

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── Flask App ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

# ── Singleton optimizer (loads CNN once at startup) ───────────────────────────
logger.info("Initializing Layout Optimizer (loading/training CNN)...")
_optimizer = LayoutOptimizer(
    pop_size=int(os.environ.get("GA_POP_SIZE", 120)),
    n_generations=int(os.environ.get("GA_GENERATIONS", 60)),
    auto_train_cnn=True,
    verbose=True,
)
logger.info("Optimizer ready.")


# ═══════════════════════════════════════════════════════════════════════════
#  Routes
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "ML Layout Optimizer"})


# ─── POST /optimize ──────────────────────────────────────────────────────────

@app.route("/optimize", methods=["POST"])
def optimize():
    """
    Accept room + furniture JSON, return top-3 optimized layouts.

    Request body:
    {
        "room_dimensions": {"width": 15, "height": 12},
        "north_direction": "top",
        "detected_furniture": [
            {"label": "bed",      "w": 3, "h": 2},
            {"label": "wardrobe", "w": 2, "h": 1}
        ]
    }
    """
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400

    data = request.get_json()
    top_k = int(request.args.get("top_k", 3))

    # ── Validate required fields ─────────────────────────────────────────────
    missing = []
    if "room_dimensions" not in data:
        missing.append("room_dimensions")
    if "detected_furniture" not in data:
        missing.append("detected_furniture")
    if missing:
        return jsonify({"error": f"Missing required fields: {missing}"}), 422

    dims = data.get("room_dimensions", {})
    if "width" not in dims or "height" not in dims:
        return jsonify({"error": "room_dimensions must include 'width' and 'height'"}), 422

    if not data.get("detected_furniture"):
        return jsonify({"error": "detected_furniture cannot be empty"}), 422

    for i, item in enumerate(data["detected_furniture"]):
        for field in ["label", "w", "h"]:
            if field not in item:
                return jsonify({
                    "error": f"detected_furniture[{i}] missing '{field}'"
                }), 422

    # ── Run optimization ─────────────────────────────────────────────────────
    t0 = time.time()
    try:
        result = _optimizer.optimize(data, top_k=top_k)
    except Exception as e:
        logger.exception("Optimization failed")
        return jsonify({"error": str(e)}), 500

    elapsed = round(time.time() - t0, 2)
    result["optimization_time_seconds"] = elapsed
    logger.info(f"/optimize completed in {elapsed}s")

    return jsonify(result)


# ─── POST /vastu/score ───────────────────────────────────────────────────────

@app.route("/vastu/score", methods=["POST"])
def vastu_score():
    """
    Score a specific furniture layout using only the Vastu engine (no GA).

    Request body:
    {
        "room_dimensions": {"width": 15, "height": 12},
        "north_direction": "top",
        "entrance_wall": "top",
        "furniture_positions": [
            {"label": "bed", "x": 10, "y": 8, "w": 3, "h": 2, "rotation": 0}
        ]
    }
    """
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 400

    data = request.get_json()

    try:
        dims   = data["room_dimensions"]
        north  = data.get("north_direction", "top")
        entry  = data.get("entrance_wall", north)

        engine = VastuEngine(dims["width"], dims["height"], north)

        placements = [
            FurniturePlacement(
                label    = p["label"],
                x        = float(p["x"]),
                y        = float(p["y"]),
                w        = float(p["w"]),
                h        = float(p["h"]),
                rotation = int(p.get("rotation", 0)),
            )
            for p in data["furniture_positions"]
        ]

        result = engine.compute_vastu_score(placements, entrance_wall=entry)
        return jsonify(result)

    except KeyError as e:
        return jsonify({"error": f"Missing field: {e}"}), 422
    except Exception as e:
        logger.exception("Vastu scoring failed")
        return jsonify({"error": str(e)}), 500


# ─── POST /train/cnn ─────────────────────────────────────────────────────────

@app.route("/train/cnn", methods=["POST"])
def retrain_cnn():
    """
    Re-train the CNN model on new synthetic data.

    Optional JSON body:
    {
        "n_samples": 2000,
        "epochs": 30
    }
    """
    body = request.get_json(silent=True) or {}
    n_samples = int(body.get("n_samples", 2000))
    epochs    = int(body.get("epochs", 30))

    try:
        t0 = time.time()
        logger.info(f"Re-training CNN: n_samples={n_samples}, epochs={epochs}")
        train_cnn(n_samples=n_samples, epochs=epochs)
        elapsed = round(time.time() - t0, 2)
        return jsonify({
            "status":  "CNN retrained successfully",
            "elapsed": elapsed,
        })
    except Exception as e:
        logger.exception("CNN training failed")
        return jsonify({"error": str(e)}), 500


# ─── Error Handlers ───────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found", "available": [
        "GET /health",
        "POST /optimize",
        "POST /vastu/score",
        "POST /train/cnn",
    ]}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    logger.info(f"Starting Flask API on port {port} (debug={debug})")
    app.run(host="0.0.0.0", port=port, debug=debug)
