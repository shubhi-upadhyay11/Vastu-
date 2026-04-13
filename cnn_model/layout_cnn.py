"""
CNN Layout Scorer
-----------------
Takes a 2D grid representation of a room layout and outputs a
functional score (0–100) combining aesthetics and space efficiency.

Architecture: Lightweight CNN → GlobalAvgPool → Dense → Sigmoid
Input:  (GRID_H, GRID_W, N_CHANNELS) float32 grid
Output: scalar score in [0, 1]
"""

import os
import numpy as np
from typing import List, Tuple, Optional

# ── Optional heavy imports ──────────────────────────────────────────────────
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# ── Constants ───────────────────────────────────────────────────────────────
GRID_H = 32          # grid rows
GRID_W = 32          # grid cols
N_CHANNELS = 6       # bed, kitchen, study, living, other, empty
MODEL_PATH = os.path.join(os.path.dirname(__file__), "layout_cnn.pt")


# ════════════════════════════════════════════════════════════════════════════
#  PyTorch CNN Model
# ════════════════════════════════════════════════════════════════════════════

class LayoutCNN(nn.Module if TORCH_AVAILABLE else object):
    """
    Lightweight CNN for layout scoring.
    Input:  (B, N_CHANNELS, GRID_H, GRID_W)
    Output: (B, 1)  — sigmoid score
    """

    def __init__(self, n_channels: int = N_CHANNELS):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is not installed. Run: pip install torch")
        super().__init__()

        self.features = nn.Sequential(
            # Block 1
            nn.Conv2d(n_channels, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),                    # 32→16

            # Block 2
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),                    # 16→8

            # Block 3
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool2d((4, 4)),       # 8→4
        )

        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(128 * 4 * 4, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(256, 64),
            nn.ReLU(inplace=True),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        x = self.features(x)
        return self.classifier(x)


# ════════════════════════════════════════════════════════════════════════════
#  Grid Encoder — converts FurniturePlacement list → grid tensor
# ════════════════════════════════════════════════════════════════════════════

# Channel mapping: furniture category → channel index
CATEGORY_CHANNEL = {
    "bed":          0,
    "bedroom":      0,
    "kitchen":      1,
    "stove":        1,
    "refrigerator": 1,
    "desk":         2,
    "study_table":  2,
    "computer":     2,
    "sofa":         3,
    "dining_table": 3,
    "tv":           3,
    # channel 4 = other furniture
    # channel 5 = empty space (auto-filled)
}
OTHER_CH  = 4
EMPTY_CH  = 5


def encode_layout_to_grid(
    placements,
    room_width: float,
    room_height: float,
    grid_h: int = GRID_H,
    grid_w: int = GRID_W,
) -> np.ndarray:
    """
    Encode a list of FurniturePlacement objects into a (N_CHANNELS, H, W) grid.
    """
    grid = np.zeros((N_CHANNELS, grid_h, grid_w), dtype=np.float32)

    # Fill empty channel first
    grid[EMPTY_CH, :, :] = 1.0

    scale_x = grid_w / room_width
    scale_y = grid_h / room_height

    for p in placements:
        label = p.label.lower().replace(" ", "_")
        ch = CATEGORY_CHANNEL.get(label, OTHER_CH)

        # Convert real coords → grid coords
        gx1 = max(0, int(p.x * scale_x))
        gy1 = max(0, int(p.y * scale_y))
        gx2 = min(grid_w, int((p.x + p.w) * scale_x) + 1)
        gy2 = min(grid_h, int((p.y + p.h) * scale_y) + 1)

        grid[ch, gy1:gy2, gx1:gx2] = 1.0
        grid[EMPTY_CH, gy1:gy2, gx1:gx2] = 0.0   # mark as occupied

    return grid


# ════════════════════════════════════════════════════════════════════════════
#  Synthetic Training Data Generator
# ════════════════════════════════════════════════════════════════════════════

def _compute_heuristic_score(grid: np.ndarray) -> float:
    """
    Heuristic ground-truth score for synthetic training data.

    Combines:
      - Space efficiency: how well furniture fills room (not too sparse, not too dense)
      - Zone balance: furniture distributed across room zones
      - Symmetry bonus
    """
    occupied = 1.0 - grid[EMPTY_CH].mean()   # fraction occupied

    # Ideal occupancy: 30%–65%
    if occupied < 0.30:
        efficiency = occupied / 0.30
    elif occupied <= 0.65:
        efficiency = 1.0
    else:
        efficiency = max(0.0, 1.0 - (occupied - 0.65) / 0.35)

    # Zone balance: compare quadrant occupancy variances
    h, w = grid.shape[1], grid.shape[2]
    hh, hw = h // 2, w // 2
    quadrants = [
        grid[:, :hh, :hw].sum(),
        grid[:, :hh, hw:].sum(),
        grid[:, hh:, :hw].sum(),
        grid[:, hh:, hw:].sum(),
    ]
    q_arr = np.array(quadrants, dtype=float)
    if q_arr.sum() > 0:
        q_arr /= q_arr.sum()
        balance = 1.0 - np.std(q_arr) * 4   # std of uniform dist ≈ 0.25
        balance = max(0.0, balance)
    else:
        balance = 0.0

    # Channel diversity bonus (using more furniture types is better)
    channels_used = sum(1 for c in range(N_CHANNELS - 1) if grid[c].sum() > 0)
    diversity = channels_used / (N_CHANNELS - 1)

    score = 0.40 * efficiency + 0.35 * balance + 0.25 * diversity
    return float(np.clip(score, 0.0, 1.0))


def generate_synthetic_data(
    n_samples: int = 2000,
    room_w: float = 15.0,
    room_h: float = 12.0,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic (grid, score) pairs for CNN training.
    Returns arrays of shape (N, N_CHANNELS, GRID_H, GRID_W) and (N,).
    """
    rng = np.random.default_rng(seed)
    grids  = np.zeros((n_samples, N_CHANNELS, GRID_H, GRID_W), dtype=np.float32)
    scores = np.zeros(n_samples, dtype=np.float32)

    furniture_templates = [
        {"label": "bed",          "w": 3.0, "h": 2.0},
        {"label": "wardrobe",     "w": 2.0, "h": 1.0},
        {"label": "kitchen",      "w": 2.5, "h": 2.0},
        {"label": "desk",         "w": 1.5, "h": 1.0},
        {"label": "sofa",         "w": 3.0, "h": 1.2},
        {"label": "dining_table", "w": 2.0, "h": 1.5},
        {"label": "tv",           "w": 1.5, "h": 0.5},
        {"label": "refrigerator", "w": 1.0, "h": 0.8},
        {"label": "bookshelf",    "w": 2.0, "h": 0.5},
    ]

    # Lazy import to avoid circular
    from vastu_engine.vastu_rules import FurniturePlacement

    for i in range(n_samples):
        n_pieces = rng.integers(2, 7)
        chosen = rng.choice(furniture_templates, n_pieces, replace=False)

        placements = []
        for tmpl in chosen:
            rot = int(rng.choice([0, 90, 180, 270]))
            w = tmpl["w"] if rot in [0, 180] else tmpl["h"]
            h = tmpl["h"] if rot in [0, 180] else tmpl["w"]
            x = float(rng.uniform(0, max(0.1, room_w - w)))
            y = float(rng.uniform(0, max(0.1, room_h - h)))
            placements.append(FurniturePlacement(
                label=tmpl["label"], x=x, y=y, w=w, h=h, rotation=rot
            ))

        grid = encode_layout_to_grid(placements, room_w, room_h)
        grids[i]  = grid
        scores[i] = _compute_heuristic_score(grid)

    return grids, scores


# ════════════════════════════════════════════════════════════════════════════
#  Training Script
# ════════════════════════════════════════════════════════════════════════════

def train_cnn(
    n_samples: int = 2000,
    epochs: int = 30,
    batch_size: int = 64,
    lr: float = 1e-3,
    save_path: str = MODEL_PATH,
) -> LayoutCNN:
    """Train the CNN on synthetic data and save the model."""
    if not TORCH_AVAILABLE:
        raise ImportError("PyTorch required: pip install torch")

    print(f"[CNN] Generating {n_samples} synthetic training samples...")
    X, y = generate_synthetic_data(n_samples)

    # Train / val split
    split = int(0.85 * n_samples)
    X_tr, X_val = X[:split], X[split:]
    y_tr, y_val = y[:split], y[split:]

    tr_ds  = TensorDataset(torch.tensor(X_tr), torch.tensor(y_tr).unsqueeze(1))
    val_ds = TensorDataset(torch.tensor(X_val), torch.tensor(y_val).unsqueeze(1))
    tr_dl  = DataLoader(tr_ds,  batch_size=batch_size, shuffle=True)
    val_dl = DataLoader(val_ds, batch_size=batch_size)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model  = LayoutCNN().to(device)
    opt    = torch.optim.Adam(model.parameters(), lr=lr)
    sched  = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    loss_fn = nn.MSELoss()

    print(f"[CNN] Training on {device} for {epochs} epochs...")
    for epoch in range(1, epochs + 1):
        model.train()
        tr_loss = 0.0
        for xb, yb in tr_dl:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            pred = model(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            opt.step()
            tr_loss += loss.item() * len(xb)

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for xb, yb in val_dl:
                xb, yb = xb.to(device), yb.to(device)
                val_loss += loss_fn(model(xb), yb).item() * len(xb)

        sched.step()
        tr_loss  /= len(tr_ds)
        val_loss /= len(val_ds)

        if epoch % 5 == 0 or epoch == 1:
            print(f"  Epoch {epoch:3d}/{epochs}  "
                  f"train_loss={tr_loss:.4f}  val_loss={val_loss:.4f}")

    torch.save(model.state_dict(), save_path)
    print(f"[CNN] Model saved → {save_path}")
    return model


# ════════════════════════════════════════════════════════════════════════════
#  LayoutScorer — high-level wrapper used by optimization engine
# ════════════════════════════════════════════════════════════════════════════

class LayoutScorer:
    """
    Loads (or trains) the CNN and provides a score() method.
    Falls back to heuristic scoring when PyTorch is unavailable.
    """

    def __init__(self, model_path: str = MODEL_PATH, auto_train: bool = True):
        self.model = None
        self._device = None

        if not TORCH_AVAILABLE:
            print("[CNN] PyTorch not available — using heuristic scorer.")
            return

        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        if os.path.exists(model_path):
            self.model = LayoutCNN().to(self._device)
            self.model.load_state_dict(
                torch.load(model_path, map_location=self._device)
            )
            self.model.eval()
            print(f"[CNN] Loaded model from {model_path}")
        elif auto_train:
            print("[CNN] No saved model found — training from scratch...")
            self.model = train_cnn(save_path=model_path)
            self.model.eval()
        else:
            print("[CNN] No model found and auto_train=False — using heuristic.")

    def score(
        self,
        placements,
        room_width: float,
        room_height: float,
    ) -> float:
        """Return a functional score in [0, 100]."""
        grid = encode_layout_to_grid(placements, room_width, room_height)

        if self.model is not None and TORCH_AVAILABLE:
            tensor = torch.tensor(grid).unsqueeze(0).to(self._device)
            with torch.no_grad():
                raw = self.model(tensor).item()
            return round(raw * 100, 2)
        else:
            return round(_compute_heuristic_score(grid) * 100, 2)