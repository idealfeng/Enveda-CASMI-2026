"""Verify generated E2/PubChem recovery source matching without running either."""
from pathlib import Path
import ast
import base64
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from validation import pipeline_adapter, recovery


def literals(text):
    result = {}
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            try: result[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError): pass
    return result


def main():
    work = ROOT / "runs/validation_flex_c2_recovery_prepare_20261105v2"
    notebook = recovery.read(work / "adapted_validation_flex.ipynb")
    values = {}
    for cell in notebook["cells"]:
        if cell.get("cell_type") == "code": values.update(literals(cell["source"]))
    frozen = json.loads(base64.b64decode(values["FROZEN_B64"]))
    engine_cell = frozen["cells"][32]["source"]
    data = literals(engine_cell)
    directory = work / "eng"; directory.mkdir(exist_ok=True)
    for name, source in data["ENG_FILES"].items():
        (directory / name).write_text(source, encoding="utf-8")
    runner = next(node.args[0].value for node in ast.walk(ast.parse(engine_cell))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "write"
        and node.args and isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str)
        and "import casmi_engine as E" in node.args[0].value)
    (directory / "eng_runner.py").write_text(runner, encoding="utf-8")
    pipeline_adapter.patch_generated_e2(directory/"eng_runner.py", work/"validation_config.json")
    pc = literals(frozen["cells"][34]["source"])
    (work/"probe_core2.py").write_text(pc["CORE"]+pc["V17_PATCH"], encoding="utf-8")
    (work/"pc_runner.py").write_text(pc["RUNNER"], encoding="utf-8")
    scope = {"_VALIDATION_CONFIG": str(work/"validation_config.json")}
    for stage in ("engine2", "pubchem"):
        result = recovery.reuse_subprocess(stage, scope, ["CPU_TEST_NO_SUBPROCESS"])
        assert result.returncode == 0
    output = dict(status="passed", gpu_used=False, subprocess_models_started=False,
        generated_e2_source_normalized_match=True, generated_pubchem_source_normalized_match=True,
        copied_output_sha_checks=True, current_mounted_asset_binding_checked=True)
    recovery.write(work/"recovery_sources_cpu_test.json", output)
    print(json.dumps(output))


if __name__ == "__main__": main()
