"""Guard recovery paths before the frozen runner performs any writes."""
import argparse
import os
from pathlib import Path
import sys

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--work-root", type=Path, required=True)
parser.add_argument("--resume-from", type=Path, required=True)
args, _ = parser.parse_known_args()
root = Path(__file__).resolve().parents[1]
new, old = args.work_root.resolve(), args.resume_from.resolve()
if not new.is_relative_to(root) or not old.is_relative_to(root):
    parser.error("Recovery directories must stay inside the D: workspace")
if new == old or new.is_relative_to(old) or old.is_relative_to(new):
    parser.error("Recovery work-root must be separate from, and never contain, the failed directory")
if new.exists() and any(new.iterdir()):
    parser.error("Use a fresh empty work-root for guarded recovery")
if not (old / "validation_run_receipt.json").is_file():
    parser.error("Failed-run receipt missing")
os.execv(sys.executable, [sys.executable, str(root / "scripts/run_validation_pipeline.py"), *sys.argv[1:]])
