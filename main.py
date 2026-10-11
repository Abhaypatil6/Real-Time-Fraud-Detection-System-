"""
Main entry point — choose mode with CLI arguments.

Usage:
  python main.py train       # Train & save ML model
  python main.py serve       # Start API + dashboard
  python main.py demo        # Train then serve
"""
import sys
import os

def _train():
    from src.models.trainer import train
    train(n_samples=50_000)

def _serve():
    import uvicorn
    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info",
    )

def _demo():
    _train()
    _serve()

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "demo"
    modes = {"train": _train, "serve": _serve, "demo": _demo}

    if mode not in modes:
        print(f"Unknown mode: {mode}")
        print(f"Available: {list(modes.keys())}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  FraudShield - Mode: {mode.upper()}")
    print(f"{'='*60}\n")
    modes[mode]()


if __name__ == "__main__":
    main()
