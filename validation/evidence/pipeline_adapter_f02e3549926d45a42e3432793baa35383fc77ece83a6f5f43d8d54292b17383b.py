"""Reference-isolation hooks for generated validation copies of public pipelines.

Original notebooks/assets are read-only. Candidate structures and pretrained
models remain available: these runs diagnose reference isolation, not clean CV.
"""
from __future__ import annotations

import ast
import base64
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def load_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    return config


def _exclusions(config):
    import numpy as np
    import pandas as pd
    rows = pd.read_parquet(config["exclusion_rows_file"], columns=["source_row"])
    indices = np.unique(rows.source_row.to_numpy(dtype=np.int64))
    query = pd.read_parquet(config["queries_file"], columns=["source_row"])
    # Always remove the query itself, even in the class-1 reference split.
    indices = np.union1d(indices, query.source_row.to_numpy(dtype=np.int64))
    keys = set()
    if config["reference_mode"] == "class2":
        keys = set(json.loads(Path(config["exclusion_keys_file"]).read_text())["blocked_raw_keys"])
    return indices, keys


def _record(config, name, payload):
    write_json(Path(config["work_root"]) / name, payload)


def _library_mask(library, raw_keys, source_rows, base_rows):
    """Keep original CSR/metadata row coordinates; mask only reference indexes."""
    import numpy as np
    import pandas as pd
    st = pd.read_parquet(Path(library._validation_workdir) / "train_structs.parquet",
                         columns=["sid", "inchikey14"])
    blocked_sids = st.loc[st.inchikey14.astype(str).isin(raw_keys), "sid"].to_numpy(dtype=np.int64)
    mask = np.isin(library.sid, blocked_sids)
    if len(library.sid) < base_rows:
        raise ValueError("Reference cache has fewer rows than the full training cache")
    if len(source_rows) and (source_rows.min() < 0 or source_rows.max() >= base_rows):
        raise ValueError("Exclusion source_row is outside the original full training order")
    mask[source_rows] = True
    return mask, blocked_sids


def _clean_spectrum_hash(adduct, precursor, mode, mz, intensity):
    import numpy as np
    h = hashlib.sha256()
    h.update(json.dumps([str(adduct), float(precursor), int(mode)], separators=(",", ":")).encode())
    h.update(np.asarray(mz, dtype="<f4").tobytes())
    h.update(np.asarray(intensity, dtype="<f4").tobytes())
    return h.hexdigest()


def _query_clean_hashes(config):
    import numpy as np
    import pandas as pd
    from casmi.spectra import clean_peaks
    result = set()
    for row in pd.read_parquet(config["queries_file"]).itertuples(index=False):
        mz, it = clean_peaks(np.asarray(row.ms2_mzs, np.float64),
                            np.asarray(row.ms2_normalized_intensities, np.float64),
                            float(row.precursor_mz), 0.001, 512, 2.0)
        result.add(_clean_spectrum_hash(row.adduct, row.precursor_mz,
            1 if row.ionization_mode == "positive" else -1, mz, it))
    return result


def _engine_reps(engine, np, np_libs):
    """Original group selection over allowed rows, preserving original row IDs."""
    library = engine.L
    rows = np.flatnonzero(~library._validation_excluded)
    grp = (library.sid[rows].astype(np.int64) * 2 + (library.mode[rows] > 0)) * 16 + library.lib[rows].astype(np.int64)
    order = np.lexsort((-library.n_clean[rows], grp))
    groups = grp[order]
    first = np.ones(len(order), bool)
    first[1:] = groups[1:] != groups[:-1]
    rep = rows[order[first]]
    sort = np.argsort(library.smass[rep], kind="mergesort")
    rep = rep[sort]
    assert not library._validation_excluded[rep].any()
    return dict(idx=rep, sid=library.sid[rep], mass=library.smass[rep],
                mode=library.mode[rep], lib=library.lib[rep], is_np=np.isin(library.lib[rep], np_libs))


def install_e1(code_root, config_path):
    """Install reference masks before any base or extended Library is created."""
    import numpy as np
    config = load_config(config_path)
    source_rows, raw_keys = _exclusions(config)
    import sys
    sys.path.insert(0, str(code_root))
    module = importlib.import_module("casmi.library")
    eng = importlib.import_module("casmi.engine")
    if getattr(module.Library, "_validation_installed", False):
        raise RuntimeError("Validation Library hooks installed twice")
    original_init = module.Library.__init__
    original_reps = module.Library.representatives
    libraries = []
    query_hashes = _query_clean_hashes(config)

    def init(self, workdir="work", verbose=True):
        original_init(self, workdir, verbose)
        self._validation_workdir = str(Path(workdir).resolve())
        mask, sids = _library_mask(self, raw_keys, source_rows, config["base_train_rows"])
        extra_duplicates = 0
        for row in range(config["base_train_rows"], len(mask)):
            a, b = self.off[row:row + 2]
            meta = self.meta.iloc[row]
            signature = _clean_spectrum_hash(meta.adduct, meta.precursor_mz, meta["mode"],
                                              self.mz[a:b], self.it[a:b])
            if signature in query_hashes:
                extra_duplicates += 1
                mask[row] = True
        self._validation_excluded = mask
        # All numerical/metadata arrays keep original offsets and row IDs. Only
        # sorted search indexes change; no writes go through the shared links.
        self.order = self.order[~mask[self.order]]
        self.smass_sorted = self.smass[self.order]
        self._rep = {}
        assert len(self.meta) == len(self.sid) == len(self.off) - 1
        assert not mask[self.order].any()
        libraries.append(dict(workdir=self._validation_workdir, rows=len(mask),
            excluded_rows=int(mask.sum()), allowed_rows=int((~mask).sum()),
            excluded_base_rows=int(mask[:config["base_train_rows"]].sum()),
            excluded_extra_rows=int(mask[config["base_train_rows"]:].sum()),
            excluded_extra_query_clean_duplicates=extra_duplicates,
            blocked_sids=len(sids), csr_offsets_preserved=True,
            reference_mask_sha256=hashlib.sha256(mask.tobytes()).hexdigest()))
        _record(config, "validation_e1_reference_audit.json", dict(
            status="installed", cohort=config["cohort_policy"], libraries=libraries,
            source_library_sha256=sha(module.__file__), candidate_pool_filtered=False,
            extra_duplicate_policy="Same precursor/adduct/mode and identical clean float32 CSR; conservative superset of raw exact duplicates."))

    def representatives(self, exclude=None, key="default"):
        mask = self._validation_excluded if exclude is None else (self._validation_excluded | exclude)
        out = original_reps(self, exclude=mask, key=key + ":validation")
        assert not self._validation_excluded[out["idx"]].any()
        return out

    def engine_reps(self):
        return _engine_reps(self, np, eng.NP_LIBS)

    module.Library.__init__ = init
    module.Library.representatives = representatives
    module.Library._validation_installed = True
    eng.Engine._reps = engine_reps
    return dict(status="installed", source_rows=len(source_rows), blocked_raw_keys=len(raw_keys))


def install_e2(engine, config_path):
    """Exclude refs after complete candidate-pool construction and before indexes."""
    import numpy as np
    config = load_config(config_path)
    source_rows, raw_keys = _exclusions(config)
    original_load = engine.load_library
    original_index = engine.build_index
    original_main = engine.main

    def load_library(path):
        library = original_load(path)
        n = len(library["prec"])
        if n != config["base_train_rows"]:
            raise ValueError("E2 library order/count differs from full source training data")
        mask = np.isin(library["ik"], list(raw_keys))
        mask[source_rows] = True
        library["_validation_excluded"] = mask
        return library

    def build_index(library):
        mask = library["_validation_excluded"]
        # build_pool has already used ALL structures. This array only maps
        # spectral references into that unchanged pool. build_index's original
        # row_p>=0 gate is used by direct and all three representative indexes.
        library["row_p"][mask] = -1
        index = original_index(library)
        assert not mask[index["lib_rows"]].any()
        for channel in ("all", "pos", "neg"):
            assert not mask[index[channel]["rep"]].any()
            assert (index[channel]["rep_p"] >= 0).all()
        _record(config, "validation_e2_reference_audit.json", dict(status="passed",
            rows=len(mask), excluded_rows=int(mask.sum()), direct_index_rows=len(index["lib_rows"]),
            representatives={key: len(index[key]["rep"]) for key in ("all", "pos", "neg")},
            no_excluded_direct_or_representative_rows=True, candidate_pool_filtered=False,
            pool_structures=len(engine.POOL["keys"]),
            blocked_raw_keys_still_in_pool=int(np.isin(engine.POOL["keys"], list(raw_keys)).sum()),
            reference_mask_sha256=hashlib.sha256(mask.tobytes()).hexdigest(),
            cohort=config["cohort_policy"]))
        return index

    def main(*args, **kwargs):
        result = original_main(*args, **kwargs)
        _, records, scores = result
        blend = engine.blend_scores(scores["pv"], scores["ours"], kwargs.get("w_pv", 0.88))
        path = Path(config["work_root"]) / "validation_e2_candidates.jsonl"
        with path.open("w", encoding="utf-8") as stream:
            for record in records:
                mid = str(record["mid"])
                cand = record["cand"]
                for rank, pid in enumerate(cand, 1):
                    stream.write(json.dumps(dict(molecule_id=mid, stage="e2_mass_window", rank=rank,
                        smiles=str(engine.POOL["smiles"][pid]))) + "\n")
                if mid in blend:
                    order = np.argsort(-blend[mid], kind="stable")
                    for rank, j in enumerate(order, 1):
                        stream.write(json.dumps(dict(molecule_id=mid, stage="e2_ranked_all", rank=rank,
                            smiles=str(engine.POOL["smiles"][cand[j]]), score=float(blend[mid][j]))) + "\n")
        return result

    engine.load_library = load_library
    engine.build_index = build_index
    engine.main = main


def patch_generated_e2(path, config_path):
    path = Path(path)
    code = path.read_text(encoding="utf-8")
    old = "    import casmi_engine as E"
    if code.count(old) != 1:
        raise ValueError("Unexpected generated E2 import count")
    hook = (old + f"\n    sys.path.insert(0, {str(ROOT)!r})"
            "\n    from validation.pipeline_adapter import install_e2"
            f"\n    install_e2(E, {str(config_path)!r})")
    adapted = code.replace(old, hook, 1)
    before_write = "    json.dump(res, open(out, 'w'))"
    if adapted.count(before_write) != 1:
        raise ValueError("Unexpected generated E2 output write count")
    adapted = adapted.replace(before_write,
        "    for _vr in recs:\n        res.setdefault(str(_vr['mid']), dict(smiles=[], keys=[]))\n" + before_write, 1)
    ast.parse(adapted)
    path.write_text(adapted, encoding="utf-8")
    config = load_config(config_path)
    _record(config, "validation_e2_runner_patch.json", dict(
        before_sha256=hashlib.sha256(code.encode()).hexdigest(), after_sha256=sha(path),
        change="Install local reference mask and candidate recorder; original E2 pool and rankers retained."))


def record_e1_candidates(mid, candidates, scores, config_path):
    import numpy as np
    config = load_config(config_path)
    path = Path(config["work_root"]) / "validation_e1_candidates.jsonl"
    with path.open("a", encoding="utf-8") as stream:
        for rank, j in enumerate(np.argsort(-scores, kind="stable"), 1):
            stream.write(json.dumps(dict(molecule_id=str(mid), stage="e1_ranked_all", rank=rank,
                smiles=str(candidates.smiles[j]), score=float(scores[j]), generated=bool(candidates.is_gen[j]))) + "\n")


def export_scope(scope, root):
    """Stage lists available in the actual execution namespace, without truth."""
    root = Path(root)
    active = set(scope["te"].molecule_id.astype(str))
    rows = []
    def add(stage, mid, smiles):
        if str(mid) in active:
            rows.extend(dict(molecule_id=str(mid), stage=stage, rank=i, smiles=str(s))
                        for i, s in enumerate(smiles, 1))
    for mid, value in scope.get("BASE", {}).items(): add("e1_base_top", mid, value[0])
    for mid, value in scope.get("ENG", {}).items(): add("e2_top40", mid, value.get("smiles", []))
    for mid, value in scope.get("PC", {}).items(): add("pubchem_top", mid, value.get("pc", []))
    for name in ("PREFUSION_LISTS", "BASE_TAIL_CANDIDATES", "FUSION_OVERFLOW"):
        for mid, value in scope.get(name, {}).items(): add(name.lower(), mid, value)
    import pandas as pd
    final = pd.read_csv(root / "submission.csv", dtype=str, keep_default_na=False)
    for mid, text in final.itertuples(index=False): add("frozen_final25", mid, text.split(";"))
    pd.DataFrame(rows).to_parquet(root / "validation_candidate_stages.parquet", index=False)
    audit = []
    by_mid = dict(zip(final.molecule_id.astype(str), final.smiles))
    for mid in sorted(active):
        base = scope.get("BASE", {}).get(mid, ([],))
        eng = scope.get("ENG", {}).get(mid, {})
        pc = scope.get("PC", {}).get(mid, {})
        no_candidates = not (base[0] or eng.get("smiles") or pc.get("pc"))
        audit.append(dict(molecule_id=mid, query_processed=True,
            empty_e1=not bool(base[0]), empty_e2=not bool(eng.get("smiles")),
            empty_pubchem=not bool(pc.get("pc")), all_materialized_sources_empty=no_candidates,
            output_is_cco_fallback=by_mid[mid] == "CCO", unprocessed_padding=False))
    write_json(root / "validation_empty_candidate_audit.json", dict(
        rows=audit, no_candidate_queries=sum(item["all_materialized_sources_empty"] for item in audit),
        scope="A CCO fallback for a processed query with empty sources is a retrieval miss, not unprocessed padding."))


def _hook_import(config_path):
    return (f"\nimport sys as _validation_sys\n_validation_sys.path.insert(0, {str(ROOT)!r})\n"
            "from validation import pipeline_adapter as _validation_adapter\n"
            f"_VALIDATION_CONFIG = {str(config_path)!r}\n")


def patch_pipeline_cell(text, config_path, *, e1_shared_install=False):
    """Patch only generated source, guarded by exact source markers."""
    config = load_config(config_path)
    changes = []
    if "SMOKE_N = 12" in text:
        line = "IS_RERUN = bool(os.getenv('KAGGLE_IS_COMPETITION_RERUN')) or _sig != '654e030e4173780e945252b4a5adf70b'"
        assert text.count(line) == 1
        text = text.replace(line, "IS_RERUN = False  # validation: strict health policy, all explicitly supplied queries")
        text = text.replace("SMOKE_N = 12", f"SMOKE_N = {config['processed_molecules']}")
        text = text.replace("    ICE_BUDGET = 300", f"    ICE_BUDGET = {config['ice_budget_seconds']}")
        text += (f"\nassert len(_keep) == {config['processed_molecules']}, 'Validation query subset was truncated'\n"
                 f"assert set(_keep) == set({config['active_ids']!r}), 'Validation query IDs changed'\n")
        changes.append("all_query_strict_mode")
    # A diagnostic query can legitimately have no PubChem-only candidates.
    # Coverage is reported rather than imposing the visible 12-case fixture.
    old = "assert all(eng[mid]['smiles'] and pc.get(mid, {}).get('pc') for mid in processed)"
    if old in text:
        text = text.replace(old, "assert all(mid in eng for mid in processed), 'Engine2 skipped validation query IDs'")
        changes.append("allow_empty_pubchem_candidates_record_recall")
    old = "assert all(v[0] for v in base.values())"
    if old in text:
        text = text.replace(old, "assert set(map(str, base)) == processed  # empty retrieval is audited, not a model crash")
        changes.append("allow_empty_e1_candidates_record_recall")
    old = "assert eligible_active == len(active) and tags['no_eng'] == 0, (eligible_active, len(active), dict(tags))"
    if old in text:
        text = text.replace(old, "assert eligible_active == len(active), (eligible_active, len(active), dict(tags))")
        changes.append("allow_processed_empty_e2_rank2_noop")
    if "ENG_FILES = " in text:
        marker = "ENG = {}"
        assert text.count(marker) == 1
        hook = _hook_import(config_path) + "_validation_adapter.patch_generated_e2(os.path.join(ENG_DIR, 'eng_runner.py'), _VALIDATION_CONFIG)\n"
        text = text.replace(marker, hook + marker, 1)
        changes.append("e2_reference_and_candidate_hooks")
    if "from casmi.build import build_spec_cache" in text:
        marker = "from casmi.build import build_spec_cache"
        hook = _hook_import(config_path)
        if e1_shared_install:
            hook += (f"_validation_sys.path.insert(0, {str(ROOT / 'scripts')!r})\n"
                     "from reproduction_io import install_shared_cache as _validation_shared_cache\n"
                     f"_validation_shared_cache(V4CODE, {config['shared_spec_cache']!r}, mmap_pool=True)\n")
        hook += "_validation_adapter.install_e1(V4CODE, _VALIDATION_CONFIG)\n"
        text = text.replace(marker, hook + marker, 1)
        changes.append("e1_all_library_reference_hooks")
    marker = "score = rank_score(np.concatenate([X, F], 1), list(FEATURES) + list(names))"
    if marker in text:
        assert text.count(marker) == 1
        text = text.replace(marker, marker + "\n                _validation_adapter.record_e1_candidates(mid, C, score, _VALIDATION_CONFIG)", 1)
        changes.append("e1_full_candidate_record")
    if "GL_SCORES, gl_stats, GL_LAM, GL_BUDGET = " in text:
        old = "GL_SCORES, gl_stats, GL_LAM, GL_BUDGET = {}, dict(molecules=0, changed_vs_ice_top25=0, changed_vs_ice_top1=0), 1.0, 4000"
        assert text.count(old) == 1
        text = text.replace(old, old.rsplit("4000", 1)[0] + str(config["gl_budget_seconds"]))
        text = text.replace("N1_BUDGET = 1200.0 if IS_RERUN else 600.0", f"N1_BUDGET = {float(config['n1_budget_seconds'])}")
        changes.append("explicit_forward_model_budgets")
    ast.parse(text)
    return text, changes


def prepare_flex(input_root, work_root, competition_root, config_path):
    spec = importlib.util.spec_from_file_location("flex_local_runner", ROOT / "third_party/flexonafft_evidence_gap/run_local.py")
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.path.insert(0, str(Path(spec.origin).parent))
    spec.loader.exec_module(module)
    view = module.make_input_view(Path(input_root), Path(work_root), Path(competition_root), False)
    config = load_config(config_path)
    notebook, receipt = module.build_adapted("v56", view, Path(work_root), 12, Path(config["shared_spec_cache"]))
    values = {}
    source_index = None
    for i, cell in enumerate(notebook["cells"]):
        if cell.get("cell_type") == "code":
            found = module.literals(module.get_source(cell)); values.update(found)
            if "FROZEN_B64" in found: source_index = i
    frozen = json.loads(base64.b64decode(values["FROZEN_B64"]))
    patches = []
    for i, cell in enumerate(frozen["cells"]):
        if cell.get("cell_type") == "code":
            text, changes = patch_pipeline_cell(module.get_source(cell), config_path)
            cell["source"] = text
            if changes: patches.append(dict(cell=i, changes=changes))
    frozen_raw = json.dumps(frozen, ensure_ascii=False, separators=(",", ":")).encode()
    modules = values["MODULES"]
    # The frozen runner retains its execution namespace, which is where raw
    # candidate lists exist. Export them after its original full baseline.
    modules["export_evidence.py"] += (_hook_import(config_path) + "\n_validation_original_export = export\n"
        "def export(scope, root):\n    _validation_original_export(scope, root)\n    _validation_adapter.export_scope(scope, root)\n")
    source_cell = "\n".join([
        "MODULES = " + repr(modules),
        "MODULE_SHA256 = " + repr({name: hashlib.sha256(code.encode()).hexdigest() for name, code in modules.items()}),
        "MODEL_PINS = " + repr(values["MODEL_PINS"]),
        "FROZEN_SHA256 = " + repr(hashlib.sha256(frozen_raw).hexdigest()),
        "FROZEN_B64 = " + repr(base64.b64encode(frozen_raw).decode()),
    ])
    notebook["cells"][source_index]["source"] = source_cell
    for cell in notebook["cells"]:
        if cell.get("cell_type") == "code":
            text = module.get_source(cell)
            outer_line = "IS_RERUN = bool(os.getenv('KAGGLE_IS_COMPETITION_RERUN')) or TEST_SIGNATURE != '654e030e4173780e945252b4a5adf70b'"
            text = text.replace(outer_line, "IS_RERUN = False  # validation strict mode; all supplied queries")
            # No display work is needed for an experiment; inference modes and
            # the inner strict health assertions remain explicit above.
            text = text.replace("SHOW = not IS_RERUN", "SHOW = False")
            cell["source"] = text
            compile(text, "validation_flex_cell", "exec")
    receipt["validation_patches"] = patches
    receipt["validation_config_sha256"] = sha(config_path)
    return notebook, receipt


def prepare_v43(input_root, work_root, competition_root, config_path):
    path = ROOT / "third_party/prvsiyan_analog/run_local_linux.py"
    spec = importlib.util.spec_from_file_location("v43_local_runner", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    original = path.with_name("prvsiyan_v43.ipynb")
    assert sha(original) == module.SOURCE_SHA256
    notebook = json.loads(original.read_text(encoding="utf-8"))
    cells, patches = module.adapt_cells(notebook, Path(input_root), Path(work_root), mmap_train_fp=True)
    out = []
    for i, text in cells:
        text, changes = patch_pipeline_cell(text, config_path, e1_shared_install=True)
        if changes: patches.append(dict(cell=i, validation_changes=changes))
        out.append((i, text))
    return out, dict(source_sha256=module.SOURCE_SHA256, validation_patches=patches,
                     validation_config_sha256=sha(config_path))


def final_audit(config_path):
    import pandas as pd
    config = load_config(config_path); root = Path(config["work_root"])
    expected = set(config["active_ids"])
    frame = pd.read_csv(root / "submission.csv", dtype=str, keep_default_na=False)
    if set(frame.molecule_id) != expected or frame.molecule_id.duplicated().any():
        raise ValueError("Final validation output is not the complete query cohort")
    checks = {}
    for stage in ("ice", "gl", "n1"):
        path = root / f"{stage}_work/{stage}_out.json.meta.json"
        if not path.exists():
            raise ValueError(f"Required forward-model metadata missing: {path}")
        meta = json.loads(path.read_text())
        if meta.get("status") != "ok" or meta.get("errors") or meta.get("n_pred_fail", 0) or meta.get("n_feat_fail", 0):
            raise ValueError(f"Validation {stage} did not complete cleanly: {meta}")
        if stage == "n1":
            if meta.get("n_mols_done") != meta.get("n_mols"):
                raise ValueError("N1 budget did not finish all selected molecules")
        elif meta.get("n_mols_scored") != meta.get("n_mols_covered"):
            raise ValueError(f"{stage} budget did not finish every covered molecule")
        checks[stage] = {k: meta.get(k) for k in ("status", "n_mols", "n_mols_done", "n_mols_covered", "n_mols_scored", "seconds")}
    for name in ("validation_e1_reference_audit.json", "validation_e2_reference_audit.json"):
        if not (root / name).is_file(): raise ValueError("Missing reference-isolation audit: " + name)
    e1 = json.loads((root / "validation_e1_reference_audit.json").read_text())
    if not any(Path(item["workdir"]).name != "mask_preflight" for item in e1.get("libraries", [])):
        raise ValueError("E1 reference audit contains only a CPU preflight fixture")
    if config["pipeline"] == "flex":
        for name in ("merge_report.json", "final_layer_report.json"):
            report = json.loads((root / name).read_text())
            if report.get("status") != "applied":
                raise ValueError("Validation output restored/skipped a final stage: " + name)
        for name in ("neural_candidate_features.parquet", "outsider_neural_features.parquet"):
            features = pd.read_parquet(root / name)
            if not features.neural_ok.astype(bool).all():
                raise ValueError("Saner scoring did not cover every materialized candidate: " + name)
            errors = json.loads(Path(str(root / name) + ".errors.json").read_text())
            if errors: raise ValueError("Saner scorer recorded errors: " + name)
    ablations = {}
    base_path = root / "submission_baseline0465.csv"
    if base_path.is_file():
        base = pd.read_csv(base_path, dtype=str).set_index("molecule_id").smiles
        for name in ("V0", "V1", "V2", "V4", "CUSTOM"):
            path = root / "variants" / f"submission_{name}.csv"
            if not path.is_file(): continue
            other = pd.read_csv(path, dtype=str).set_index("molecule_id").smiles
            same = all(set(base[mid].split(";")) == set(other[mid].split(";")) for mid in expected)
            if not same: raise ValueError("Fixed-candidate ablation changed a candidate set: " + name)
            ablations[name] = dict(path=str(path), sha256=sha(path), same_candidate_set=True)
        write_json(root / "fixed_candidate_ablations.json", dict(baseline=str(base_path), variants=ablations,
            note="Fixed candidate sets only; V3 rescue intentionally excluded. Known pretrained exposure applies."))
    result = dict(status="passed", processed_molecules=len(expected), placeholder_rows=0,
        forward_models=checks, cohort_policy=config["cohort_policy"],
        evaluation_label=config["evaluation_label"], pretrained_exposure=config["pretrained_exposure"],
        final_sha256=sha(root / "submission.csv"), fixed_candidate_ablations=list(ablations))
    write_json(root / "validation_runtime_audit.json", result)
    return result
