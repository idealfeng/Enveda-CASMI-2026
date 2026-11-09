"""No-GPU regression checks for the bound ICE recovery merge.

Uses explicitly synthetic pending scores in a separate test-only directory;
these artifacts must never be evaluated as model predictions.
"""
from pathlib import Path
import copy
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from validation import recovery


def main():
    prepared = ROOT / "runs/validation_flex_c2_recovery_prepare_20261105v2"
    root = ROOT / "runs/recovery_cpu_logic_test_20261105"
    root.mkdir(exist_ok=True)
    view = root / "input_view"
    if not view.exists(): view.symlink_to(prepared / "input_view", target_is_directory=True)
    config = recovery.read(prepared / "validation_config.json")
    config["work_root"] = str(root)
    binding = recovery.read(prepared / "recovery_binding.json")
    binding["new_root"] = str(root)
    recovery.write(root / "validation_config.json", config)
    recovery.write(root / "recovery_binding.json", binding)
    old = Path(binding["prior_root"])
    # Asset mounting and byte-copy checks have their separate source test.
    # These tiny merge regressions intentionally avoid another 447-file walk.
    recovery.binding = lambda path: (config, binding, old)
    items = recovery.read(old / "ice_work/ice_in.json")
    old_output_sha = recovery.digest(old / "ice_work/ice_out.json")
    calls = []

    def synthetic_runner(pkg, pending, **kwargs):
        calls.append([x["mid"] for x in pending])
        out = {x["mid"]: {s: (0.125 if x["spectra"] else None) for s in x["cands"]} for x in pending}
        covered = sum(bool(x["spectra"]) for x in pending)
        path = Path(kwargs["workdir"])
        recovery.write(path / "ice_out.json.meta.json", dict(status="ok", errors=[], n_pred_fail=0,
            n_bad_smiles=0, n_mols_scored=covered, n_mols_covered=covered, seconds=1.0,
            rdkit="2025.03.6", device="cpu_test_only", synthetic_test_scores=True))
        return out

    result = recovery.run_ice(synthetic_runner, "TEST_ONLY", items,
        workdir=str(root / "ice_work"), budget_s=2400)
    meta = recovery.read(root / "ice_work/ice_out.json.meta.json")
    assert meta["recovery"]["reused_molecules"] == 32
    assert len(calls[-1]) == 16 and meta["n_mols_covered"] == meta["n_mols_scored"] == 46
    assert len(result) == 48
    unsupported = [x["mid"] for x in items if not x["spectra"]]
    assert len(unsupported) == 2 and all(v is None for m in unsupported for v in result[m].values())
    changed = copy.deepcopy(items)
    completed_mid = next(x["mid"] for x in items if x["mid"] not in calls[-1])
    changed[next(i for i,x in enumerate(changed) if x["mid"]==completed_mid)]["cands"].append("CCO")
    recovery.run_ice(synthetic_runner, "TEST_ONLY", changed, workdir=str(root / "ice_work"), budget_s=2400)
    changed_meta = recovery.read(root / "ice_work/ice_out.json.meta.json")
    assert changed_meta["recovery"]["reused_molecules"] == 31 and completed_mid in calls[-1]

    def unfinished(pkg, pending, **kwargs):
        path = Path(kwargs["workdir"])
        recovery.write(path / "ice_out.json.meta.json", dict(status="budget", errors=[], n_pred_fail=0,
            n_mols_scored=0, n_mols_covered=14, seconds=1.0))
        return {}
    rejected = False
    try:
        recovery.run_ice(unfinished, "TEST_ONLY", items, workdir=str(root / "ice_work"), budget_s=2400)
    except RuntimeError:
        rejected = True
    assert rejected
    assert recovery.digest(old / "ice_work/ice_out.json") == old_output_sha
    report = dict(status="passed", gpu_used=False, model_loaded=False, synthetic_test_only=True,
        original_outputs_unchanged=True, completed_groups_reused=32, pending_groups=16,
        unsupported_all_none_preserved=2, rebuilt_input_change_recomputed=True, budget_stop_rejected=True)
    recovery.write(root / "TEST_REPORT.json", report)
    print(json.dumps(report))


if __name__ == "__main__": main()
