"""Pinned public N-1c network overlay; all ranking mathematics remain upstream's.

The parent pipeline has already produced submission.csv. The adapter projects
only query observations, calls the original Rogers function at LAM=.35/TAU=.6,
and verifies the output. Visible fast-parent runs execute the network component
too; this never claims they executed the full parent inference.
"""
from __future__ import annotations

from collections import Counter
from contextlib import redirect_stdout
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import time

ROGERS_FUNCTION_SHA256 = "33153de76fccebe4ed2325bea7649573219e4cfb964483cd5c335ac7dc7e93b8"
ROGERS_FUNCTION_SOURCE = "def _n1c(work='/kaggle/working', inp='/kaggle/input', LAM=0.25, TAU=0.6):\n    import glob, os, shutil, time, numpy as np, pandas as pd\n    t0 = time.time(); sp = os.path.join(work, 'submission.csv')\n    if not os.path.exists(sp): print('[n1c] no submission.csv'); return\n    shutil.copy(sp, os.path.join(work, 'submission_pre_n1c.csv'))\n    tp = sorted(glob.glob(inp + '/**/test.parquet', recursive=True), key=lambda p: ('mass-spectra' not in p.lower(), len(p)))\n    te = pd.read_parquet(tp[0]); sub = pd.read_csv(sp, dtype=str, keep_default_na=False)\n    L = {m: [x for x in s.split(';') if x] for m, s in zip(sub.molecule_id.astype(str), sub.smiles)}\n    from rdkit import Chem, DataStructs\n    from rdkit.Chem import rdFingerprintGenerator\n    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048); fpc = {}\n    def fp(s):\n        if s not in fpc:\n            m = Chem.MolFromSmiles(s); fpc[s] = gen.GetFingerprint(m) if m is not None else None\n        return fpc[s]\n    SP = {}\n    for (m, ad), g in te.assign(_m=te.molecule_id.astype(str)).groupby(['_m', 'adduct']):\n        if str(ad) not in ('[M+H]+', '[M-H]-') or m not in L: continue\n        pr = float(np.median(pd.to_numeric(g.precursor_mz, errors='coerce')))\n        mz = np.concatenate([np.asarray(x, float) for x in g.ms2_mzs]); it = np.concatenate([np.asarray(x, float) / max(float(np.max(x)) if len(x) else 1.0, 1e-9) for x in g.ms2_normalized_intensities])\n        k = mz < pr - 1.5; mz, it = mz[k], it[k]\n        if not len(mz): continue\n        kb = np.round(mz, 2); u, inv = np.unique(kb, return_inverse=True); w = np.zeros(len(u)); np.maximum.at(w, inv, it)\n        o = np.argsort(-w)[:120]; u, w = u[o], np.sqrt(w[o]); oo = np.argsort(u)\n        SP.setdefault(m, {})[str(ad)] = (u[oo], (w / max(np.linalg.norm(w), 1e-12))[oo], pr)\n    def mcos(a, b):\n        (ma, ia_, pa), (mb, ib, pb) = a, b; sh = pa - pb; cand = []\n        for i in range(len(ma)):\n            for off in (0.0, sh):\n                lo, hi = np.searchsorted(mb, ma[i] - off - 0.0101), np.searchsorted(mb, ma[i] - off + 0.0101, 'right')\n                for j in range(lo, hi): cand.append((ia_[i] * ib[j], i, j))\n        cand.sort(reverse=True); ui, uj, s, n = set(), set(), 0.0, 0\n        for v, i, j in cand:\n            if i in ui or j in uj: continue\n            ui.add(i); uj.add(j); s += v; n += 1\n        return s, n\n    K = sorted(SP); E = {}\n    for x in range(len(K)):\n        for y in range(x + 1, len(K)):\n            best = None\n            for ad in set(SP[K[x]]) & set(SP[K[y]]):\n                s, n = mcos(SP[K[x]][ad], SP[K[y]][ad])\n                if n >= 6 and s >= TAU and (best is None or s > best): best = s\n            if best is not None: E.setdefault(K[x], []).append((K[y], best)); E.setdefault(K[y], []).append((K[x], best))\n    z = lambda v: (v - v.mean()) / (v.std() + 1e-9); nch = nt1 = 0; out = []\n    for m, s in zip(sub.molecule_id.astype(str), sub.smiles):\n        lst = L[m][:25]; nb_ = E.get(m, [])\n        if nb_ and len(lst) > 1:\n            base = -np.log(np.arange(1, len(lst) + 1)); N = np.zeros(len(lst))\n            for b, w in nb_:\n                lb = L.get(b, [])[:5]; p = 1 / np.arange(1, len(lb) + 1); p = p / p.sum() if len(lb) else p\n                jf = [(fp(j), pp) for j, pp in zip(lb, p)]\n                for i, c in enumerate(lst):\n                    fi = fp(c)\n                    if fi is None: continue\n                    N[i] += w ** 4 * sum(pp * DataStructs.TanimotoSimilarity(fi, fj) for fj, pp in jf if fj is not None)\n            o = np.argsort(-(z(base) + LAM * z(N)), kind='stable'); nl = [lst[i] for i in o]\n            if nl != lst: nch += 1; nt1 += nl[0] != lst[0]\n            out.append(';'.join(nl))\n        else: out.append(s)\n    sub['smiles'] = out; sub.to_csv(sp, index=False)\n    print(f'[n1c] LAM={LAM} TAU={TAU} molecules {len(L)}, with spectra {len(K)}, with neighbors {len(E)}, edges {sum(len(v) for v in E.values()) // 2}, changed lists {nch}, top1 changed {nt1}, {time.time() - t0:.0f}s', flush=True)\n"
QUERY_COLUMNS = ["molecule_id", "spectrum_id", "instrument_type", "adduct",
                 "collision_energy_ev", "precursor_mz", "ms2_mzs", "ms2_normalized_intensities"]
CONFIGURATION = dict(LAM=.35, TAU=.6, matched_peaks_min=6, neighbor_top_k=5,
                     edge_power=4, protected_prefix=0, extra_library_or_AB_protection=False)


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")


@lru_cache(maxsize=100000)
def official_identity(smiles):
    import rdkit
    from rdkit import Chem, rdBase
    from rdkit.Chem.MolStandardize import rdMolStandardize
    if rdkit.__version__ != "2026.03.3":
        raise RuntimeError("The official RDKit2026.03.3 identity is required")
    with rdBase.BlockLogs():
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                return None
            Chem.RemoveStereochemistry(mol)
            key = Chem.MolToInchiKey(rdMolStandardize.TautomerEnumerator().Canonicalize(mol))
            return key[:14] if key else None
        except (TypeError, ValueError, RuntimeError):
            return None


def _parse_summary(text):
    pattern = (r"\[n1c\] LAM=(?P<LAM>[0-9.]+) TAU=(?P<TAU>[0-9.]+) molecules (?P<molecules>\d+), "
               r"with spectra (?P<with_spectra>\d+), with neighbors (?P<with_neighbors>\d+), "
               r"edges (?P<edges>\d+), changed lists (?P<changed_lists>\d+), "
               r"top1 changed (?P<top1_changed>\d+), (?P<reported_seconds>\d+)s")
    matches = list(re.finditer(pattern, text))
    if len(matches) != 1:
        raise ValueError("Expected the one exact upstream N-1c summary")
    result = matches[0].groupdict()
    return {key: float(value) if key in ("LAM", "TAU") else int(value) for key, value in result.items()}


def run(root, input_root, is_rerun, sample_ids, parent_audit, branch, recipe_sha256):
    import pandas as pd
    root, input_root = Path(root).resolve(), Path(input_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    final = root / "submission.csv"
    control = root / "network_control.csv"
    runtime_path, audit_path = root / "network_runtime.json", root / "network_audit.json"
    if any(path.exists() for path in (control, runtime_path, audit_path)):
        raise FileExistsError("Preserve an earlier network overlay attempt")
    start = time.monotonic()
    checks = {}
    report = dict(status="prepared", mode="hidden_full" if is_rerun else "fast_static",
                  branch=branch, recipe_sha256=recipe_sha256, module_sha256=sha(__file__),
                  function_sha256=ROGERS_FUNCTION_SHA256, configuration=CONFIGURATION,
                  started_at_utc=datetime.now(timezone.utc).isoformat(),
                  network_executed=False, labels_read=False, query_columns_read=QUERY_COLUMNS,
                  gain_claim=False, parent_pipeline_complete_inference_claim=False,
                  scope="actual_network_after_parent_output; parent execution scope remains separate")

    def check(name, value):
        checks[name] = bool(value)
        if not value:
            raise ValueError(name)

    try:
        check("parent_audit_passed", parent_audit.get("status") == "passed")
        if is_rerun:
            check("parent_hidden_scope", parent_audit.get("mode") == "hidden_full")
        check("function_pin", hashlib.sha256(ROGERS_FUNCTION_SOURCE.encode("utf-8")).hexdigest() == ROGERS_FUNCTION_SHA256)
        check("network_parameters", CONFIGURATION == dict(LAM=.35, TAU=.6, matched_peaks_min=6, neighbor_top_k=5,
                                                           edge_power=4, protected_prefix=0, extra_library_or_AB_protection=False))
        shutil.copy2(final, control)
        report["control_sha256"] = sha(control)
        check("control_bound", report["control_sha256"] == parent_audit.get("csv_sha256"))
        before = pd.read_csv(control, dtype=str, keep_default_na=False)
        check("original_ids_schema", before.columns.tolist() == ["molecule_id", "smiles"]
              and before.molecule_id.tolist() == list(sample_ids) and before.molecule_id.is_unique and len(before) > 0)
        for raw in before.smiles:
            guesses = raw.split(";")
            if not 1 <= len(guesses) <= 25 or any(not s for s in guesses):
                raise ValueError("Original candidate count/content is invalid")

        # Match the original selector, but pass a new input directory containing
        # only the query observations. No target field enters the original code.
        import glob
        candidates = sorted(glob.glob(str(input_root) + "/**/test.parquet", recursive=True),
                            key=lambda p: ("mass-spectra" not in p.lower(), len(p)))
        if not candidates:
            raise FileNotFoundError("No competition test.parquet was attached")
        original_query = Path(candidates[0])
        query_sha = sha(original_query)
        frame = pd.read_parquet(original_query, columns=QUERY_COLUMNS)
        projected_root = root / "network_query_input"
        projected_root.mkdir(exist_ok=False)
        projected = projected_root / "test.parquet"
        frame.to_parquet(projected, index=False)
        projected_sha = sha(projected)
        check("labels_not_read", frame.columns.tolist() == QUERY_COLUMNS)
        report.update(original_query_path=str(original_query), original_query_sha256=query_sha,
                      projected_query_sha256=projected_sha, projected_query_rows=len(frame))
        scope = {}
        exec(compile(ROGERS_FUNCTION_SOURCE, "pinned_rogers_n1c_function", "exec"), scope)
        log = io.StringIO()
        with redirect_stdout(log):
            scope["_n1c"](work=str(root), inp=str(projected_root), LAM=.35, TAU=.6)
        text = log.getvalue()
        (root / "network_stdout.log").write_text(text, encoding="utf-8")
        summary = _parse_summary(text)
        report.update(network_executed=True, actual_network_summary=summary)
        check("actual_network_execution", summary["molecules"] == len(before) and summary["LAM"] == .35 and summary["TAU"] == .6)

        after = pd.read_csv(final, dtype=str, keep_default_na=False)
        check("exact_ids_order", after.columns.tolist() == ["molecule_id", "smiles"]
              and after.molecule_id.tolist() == before.molecule_id.tolist() == list(sample_ids)
              and after.molecule_id.is_unique)
        check("candidate_multisets", all(Counter(a.split(";")) == Counter(b.split(";"))
              for a, b in zip(before.smiles, after.smiles)))
        details = []
        identities_exact = True
        invalid_count = duplicate_rows = 0
        for mid, old, new in zip(before.molecule_id, before.smiles, after.smiles):
            a, b = old.split(";"), new.split(";")
            ia, ib = [official_identity(s) for s in a], [official_identity(s) for s in b]
            identities_exact &= Counter(ia) == Counter(ib)
            invalid_count += sum(key is None for key in ia)
            duplicate_rows += len(set(ia)) < len(ia)
            details.append(dict(molecule_id=mid, changed=a != b, top1_changed=a[0] != b[0],
                                changed_positions=[i + 1 for i, (x, y) in enumerate(zip(a, b)) if x != y]))
        check("official_identity_multisets", identities_exact)
        changed = sum(item["changed"] for item in details)
        top1 = sum(item["top1_changed"] for item in details)
        check("summary_counts", summary["changed_lists"] == changed and summary["top1_changed"] == top1)
        check("no_edges_no_changes", summary["edges"] > 0 or changed == 0)
        check("source_query_unchanged", sha(original_query) == query_sha and sha(projected) == projected_sha)
        check("original_function_control_exact", sha(root / "submission_pre_n1c.csv") == report["control_sha256"])
        temporary = root / "network_roundtrip.tmp.csv"
        after.to_csv(temporary, index=False)
        check("csv_roundtrip", pd.read_csv(temporary, dtype=str, keep_default_na=False).equals(after))
        temporary.unlink()
        check("final_bound", final.is_file())
        report.update(status="passed", checks=checks, rows=len(before), csv_sha256=sha(final),
                      changed_queries=changed, changed_top1=top1, details=details,
                      invalid_identity_guesses_preserved=invalid_count, duplicate_identity_rows_preserved=duplicate_rows,
                      elapsed_seconds=time.monotonic() - start)
        save(runtime_path, report)
        audit = dict(report)
        audit["runtime_sha256"] = sha(runtime_path)
        save(audit_path, audit)
        print(text.strip(), flush=True)
        return audit
    except BaseException as error:
        report.update(status="failed_closed", checks=checks, error_type=type(error).__name__,
                      error=str(error)[:1000], elapsed_seconds=time.monotonic() - start)
        save(runtime_path, report)
        final.unlink(missing_ok=True)
        raise

