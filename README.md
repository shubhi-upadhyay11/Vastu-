# 🏠 ML Layout Optimization Module
### AI-Based Interior Design Optimizer — Layout Engine

> Combines **Vastu Shastra rules**, a **CNN layout scorer**, and a **Genetic Algorithm**  
> to suggest optimized furniture arrangements for any room.

---

## 📁 Folder Structure

```
ml_optimization/
├── vastu_engine/
│   ├── __init__.py
│   └── vastu_rules.py          # Vastu Shastra rule engine (0–100 score)
├── cnn_model/
│   ├── __init__.py
│   └── layout_cnn.py           # CNN model + grid encoder + training code
├── genetic_algorithm/
│   ├── __init__.py
│   └── ga_optimizer.py         # DEAP-based GA optimization engine
├── sample_data/
│   └── sample_input.json       # Example input payload
├── tests/
│   └── test_all.py             # Unit + integration tests
├── app.py                      # Flask REST API
├── optimize.py                 # Main orchestrator (use standalone)
├── train_cnn.py                # Standalone CNN training script
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Train CNN model ahead of time
python train_cnn.py --samples 2000 --epochs 30

# 4. Run Flask API
python app.py
# → Listening on http://localhost:5000
```

---

## 🚀 API Reference

### `POST /optimize`

Accepts room + furniture JSON and returns top-3 optimized layouts.

**Request:**
```json
{
  "room_dimensions": { "width": 15, "height": 12 },
  "north_direction": "top",
  "entrance_wall": "top",
  "detected_furniture": [
    { "label": "bed",      "w": 3,   "h": 2   },
    { "label": "wardrobe", "w": 2,   "h": 1   },
    { "label": "desk",     "w": 1.5, "h": 1   },
    { "label": "sofa",     "w": 3,   "h": 1.2 }
  ]
}
```

**Response:**
```json
{
  "room_dimensions": { "width": 15.0, "height": 12.0 },
  "north_direction": "top",
  "optimized_layouts": [
    {
      "layout_id": 1,
      "vastu_score": 85,
      "functional_score": 78.4,
      "combined_score": 81.0,
      "vastu_violations": [],
      "vastu_rule_scores": {
        "entrance_direction": 100,
        "bedroom_position":   90,
        "kitchen_position":   75
      },
      "furniture_positions": [
        { "label": "bed",      "x": 10.5, "y": 8.2, "w": 3.0, "h": 2.0, "rotation": 180 },
        { "label": "wardrobe", "x": 12.0, "y": 9.5, "w": 2.0, "h": 1.0, "rotation": 0   },
        { "label": "desk",     "x": 4.5,  "y": 0.5, "w": 1.5, "h": 1.0, "rotation": 0   },
        { "label": "sofa",     "x": 1.0,  "y": 5.0, "w": 3.0, "h": 1.2, "rotation": 0   }
      ]
    }
  ]
}
```

---

### `POST /vastu/score`

Score a specific layout with explicit positions (no optimization).

```json
{
  "room_dimensions": { "width": 15, "height": 12 },
  "north_direction": "top",
  "entrance_wall": "top",
  "furniture_positions": [
    { "label": "bed", "x": 10, "y": 8, "w": 3, "h": 2, "rotation": 0 }
  ]
}
```

---

### `POST /train/cnn`

Re-train the CNN model on fresh synthetic data.

```json
{ "n_samples": 2000, "epochs": 30 }
```

---

### `GET /health`

```json
{ "status": "ok", "service": "ML Layout Optimizer" }
```

---

## 🧩 Module Details

### 1. Vastu Engine (`vastu_engine/vastu_rules.py`)

Encodes Vastu Shastra rules and returns a weighted compliance score.

| Rule                    | Weight | Details |
|-------------------------|--------|---------|
| Entrance direction      | 20%    | North or East = full score |
| Bedroom position        | 20%    | South-West zone |
| Kitchen position        | 15%    | South-East zone |
| Study/Office position   | 10%    | North or East zone |
| Bed head direction      | 15%    | South or East; North is forbidden |
| Doorway clearance       | 10%    | Furniture must not block passages |
| Bathroom position       | 5%     | North-West zone |
| Living room position    | 5%     | North-West zone |

Hard constraints (overlap, out-of-bounds) multiply the final score.

---

### 2. CNN Layout Scorer (`cnn_model/layout_cnn.py`)

- **Input:** `(N_CHANNELS=6, 32, 32)` grid tensor
- **Channels:** bed | kitchen | study | living | other | empty
- **Architecture:** 3× Conv+BN+ReLU → AdaptiveAvgPool → Dense → Sigmoid
- **Training:** Synthetic data with heuristic ground-truth scores
- **Output:** Functional score (0–100) = aesthetics + space efficiency

Training data is generated programmatically — no real images needed.

---

### 3. Genetic Algorithm (`genetic_algorithm/ga_optimizer.py`)

- **Library:** DEAP (falls back to random search if DEAP unavailable)
- **Chromosome:** `[x_norm, y_norm, rot_idx] × N_pieces`
- **Operators:** Blend crossover + Gaussian mutation + Tournament selection
- **Fitness:** `0.40 × vastu_score + 0.60 × cnn_score − overlap_penalty`
- **Output:** Top-3 unique layout configurations

---

## 🧪 Running Tests

```bash
cd ml_optimization
pytest tests/test_all.py -v
```

---

## 🔧 Environment Variables

| Variable        | Default | Description |
|----------------|---------|-------------|
| `GA_POP_SIZE`  | 120     | GA population size |
| `GA_GENERATIONS` | 60   | GA generation count |
| `PORT`         | 5000    | Flask port |
| `FLASK_DEBUG`  | false   | Enable Flask debug mode |

---

## 📐 Coordinate System

Room coordinates use a top-left origin `(0, 0)`.  
`north_direction` maps a compass direction to a visual room edge:

| Value    | Meaning |
|----------|---------|
| `"top"`    | Top wall faces North |
| `"bottom"` | Bottom wall faces North |
| `"left"`   | Left wall faces North |
| `"right"`  | Right wall faces North |

Furniture rotations: `0` = original orientation, `90/180/270` = clockwise degrees.

---

## 🏗️ Extending the Module

**Add a new Vastu rule:**  
Edit `VASTU_ZONES` and `RULE_WEIGHTS` in `vastu_engine/vastu_rules.py`.

**Swap CNN for a different architecture:**  
Extend `LayoutCNN` in `cnn_model/layout_cnn.py` and keep the `score()` interface.

**Use Reinforcement Learning instead of GA:**  
Replace `genetic_algorithm/ga_optimizer.py` with a Stable-Baselines3 agent  
that uses the same `FitnessEvaluator` as its reward function.