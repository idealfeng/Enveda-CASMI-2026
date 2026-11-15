# ===== heliosli push489 generation, part B (after the FRIGID merge): insert the decoder's pick where the verifier is confident (reports/c3_design_v0.md 39) =====
# For each molecule in push_gen.json with p >= PGN_MIN_P and a pool of at least PGN_MIN_POOL structures: the pick goes to
# rank 2 when rank 2 is still the base list's (submission_pre_cvjoint.csv: no CV-JOINT / FRIGID insert there), else to
# rank 3; never rank 1; skipped when the list already holds it; the list stays at 25. Any failure leaves the list unchanged.
PGN_MIN_P = 0.47
PGN_MIN_POOL = 3


def _pushgen_b(work='/kaggle/working'):
    import json
    import os

    import pandas as pd
    from rdkit import Chem

    gp = os.path.join(work, "push_gen.json")
    if not os.path.exists(gp):
        print("[pushgen] part B: no push_gen.json; unchanged")
        return
    gen = json.load(open(gp))
    sub_path = os.path.join(work, "submission.csv")
    sub = pd.read_csv(sub_path, dtype=str, keep_default_na=False)
    pre_path = os.path.join(work, "submission_pre_cvjoint.csv")
    pre = pd.read_csv(pre_path, dtype=str, keep_default_na=False) if os.path.exists(pre_path) else sub
    pre2 = {m: (s.split(";")[1] if len(s.split(";")) > 1 else None) for m, s in zip(pre.molecule_id.astype(str), pre.smiles.astype(str))}
    kc = {}

    def key14(s):
        if s not in kc:
            m = Chem.MolFromSmiles(s)
            kc[s] = Chem.MolToInchiKey(m)[:14] if m is not None else None
        return kc[s]
    st = dict(candidates=len(gen), gated=0, at2=0, at3=0, already=0)
    new = []
    for mid, s in zip(sub.molecule_id.astype(str), sub.smiles.astype(str)):
        L = [x for x in s.split(";") if x]
        g = gen.get(mid)
        if g and g["p"] >= PGN_MIN_P and g["pool"] >= PGN_MIN_POOL and len(L) >= 1:
            st["gated"] += 1
            if g["key"] in {key14(x) for x in L}:
                st["already"] += 1
            else:
                pos = 1 if (len(L) > 1 and L[1] == pre2.get(mid)) or len(L) == 1 else 2
                L.insert(pos, g["smiles"])
                L = L[:25]
                st["at2" if pos == 1 else "at3"] += 1
        new.append(";".join(L))
    res = sub.copy()
    res["smiles"] = new
    assert len(res) == len(sub) and res["smiles"].str.split(";").map(len).max() <= 25
    res.to_csv(os.path.join(work, "submission.tmp.csv"), index=False)
    os.replace(os.path.join(work, "submission.tmp.csv"), sub_path)
    print("[pushgen] part B done:", json.dumps(st))


try:
    _pushgen_b(**{k: v for k, v in globals().get("PGN_DRYRUN_ARGS", {}).items() if k == "work"})
except Exception:
    import traceback

    traceback.print_exc()
    print("[pushgen] part B failed; the submission is unchanged")
