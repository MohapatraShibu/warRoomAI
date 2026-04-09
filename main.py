# entry point for the PurpleMerit War Room AI system
# usage: python main.py [--output output.json]

import json
import logging
import argparse
from pathlib import Path

from orchestrator import run_war_room

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)

def load_data():
    base = Path(__file__).parent / "data"
    with open(base / "metrics.json") as f:
        m = json.load(f)
    with open(base / "feedback.json") as f:
        feedback = json.load(f)
    with open(base / "release_notes.md") as f:
        notes = f.read()
    return m["metrics"], m["baselines"], feedback, notes

def main():
    parser = argparse.ArgumentParser(description="PurpleMerit War Room AI")
    parser.add_argument("--output", default="war_room_output.json",
                        help="Path to write the final JSON output (default: war_room_output.json)")
    args = parser.parse_args()

    metrics, baselines, feedback, release_notes = load_data()
    result = run_war_room(metrics, baselines, feedback, release_notes)

    out_path = Path(args.output)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print("\n" + "=" * 60)
    print(f"  DECISION : {result['decision']}")
    print(f"  CONFIDENCE: {result['confidence']['score']}/100")
    print(f"  RISKS     : {len(result['risk_register'])} identified")
    print(f"  ACTIONS   : {len(result['action_plan_24_48h'])} items")
    print(f"  OUTPUT    : {out_path.resolve()}")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
