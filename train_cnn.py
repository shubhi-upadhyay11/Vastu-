"""
train_cnn.py — Standalone CNN Training Script
----------------------------------------------
Run this once to train and save the CNN layout scorer model.

Usage:
    cd ml_optimization
    python train_cnn.py [--samples 2000] [--epochs 30]
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from cnn_model.layout_cnn import train_cnn, MODEL_PATH


def main():
    parser = argparse.ArgumentParser(description="Train CNN Layout Scorer")
    parser.add_argument("--samples",    type=int, default=2000,  help="Training samples")
    parser.add_argument("--epochs",     type=int, default=30,    help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=64,    help="Batch size")
    parser.add_argument("--lr",         type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--out",        type=str, default=MODEL_PATH, help="Model save path")
    args = parser.parse_args()

    print("=" * 55)
    print("  CNN Layout Scorer — Training")
    print("=" * 55)
    print(f"  Samples:    {args.samples}")
    print(f"  Epochs:     {args.epochs}")
    print(f"  Batch size: {args.batch_size}")
    print(f"  LR:         {args.lr}")
    print(f"  Save path:  {args.out}")
    print("=" * 55)

    model = train_cnn(
        n_samples=args.samples,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        save_path=args.out,
    )

    print("\n[✓] Training complete. Model ready for optimization.")


if __name__ == "__main__":
    main()