# ===== heliosli: p1 for the CV-JOINT gate (reports/c3_design_v0.md 48) =====
# The gp1 probe's p1 (L2 logistic over the notebook's own views of each list; on the board its lowest-30% lists hold a
# correct rank 1 22% of the time, the rest about 56%), computed at the same place as in gp1 and left in P1_LOW / P1_OF.
# Nothing in the submission changes here. Any failure leaves P1_LOW empty, so CV-JOINT changes no rank 1.
GP1_CFG = '{"views":["rr3","v2","main","engine2","prefusion","pubchem","ice","gl","rra"],"feats":["rr3_top","rr3_gap","rr3_na","v2_top","v2_gap","v2_na","main_top","main_gap","main_na","engine2_top","engine2_gap","engine2_na","prefusion_top","prefusion_gap","prefusion_na","pubchem_top","pubchem_gap","pubchem_na","ice_top","ice_gap","ice_na","gl_top","gl_gap","gl_na","rra_top","rra_gap","rra_na","n_agree","train1","n_list","lib"],"mu":[1.0,0.8480066699521719,0.0,0.8788927335640139,0.5746775533487803,0.0,0.6366782006920415,0.277113802203781,0.14359861591695502,0.43252595155709345,-0.32849766263093055,0.1245674740484429,0.5501730103806228,-0.054198606951532724,0.015570934256055362,0.12975778546712802,0.11757229424935543,0.8598615916955017,0.12629757785467127,-0.23632833028005323,0.5207612456747405,0.14878892733564014,-0.21182835597307645,0.5103806228373703,0.3546712802768166,-0.219846870187822,0.0,4.257785467128028,0.24048442906574394,24.993079584775085,0.3303432552237386],"sd":[1e-09,0.00048123884048992954,1e-09,0.32625189210928995,0.7707669964402255,1e-09,0.4809564121804582,0.963792246799692,0.35068226947630726,0.4954263353694228,1.3035312017334364,0.33022782910907234,0.4974763009674929,1.0787163356137124,0.12380824088107223,0.3360367587777676,0.4391756430940448,0.34713057415998605,0.3321844372439569,0.8971609622525232,0.4995687857314252,0.35588029328653514,0.9342137564163693,0.4998922320553613,0.4784135911326583,1.288707902239039,1e-09,1.4194581834873585,0.4273776658851309,0.10165004128767051,0.28416770249470197],"coef":[0.0,0.08259185751873321,0.0,-0.061508611022357516,0.09194569895459381,0.0,0.09954357305785327,0.4880399580036489,-0.8386331143059047,0.22226498028965153,0.17322419890604218,-0.27969412786379416,-0.5840515238074004,0.6143332042606896,-0.32836035414324205,0.7072361919730977,0.252608754484329,-0.40338042042468913,0.19287919938603162,0.03825095018150316,0.19118399083638513,0.03581097640196805,-0.0899463961634914,0.03069241740939939,0.027277862782212038,1.2507297971449116,0.0,0.12321342122700764,0.06017755793862125,-0.05036998199998021,-0.040000654579290654],"intercept":-0.7587194416952733,"frac":0.3,"decoy":"C","selftest":[{"molecule_id":"xb_ABAIOHPURNHXKB","n_list":25,"train1":false,"lib":0.011252092197537422,"views":{"rr3":[-0.0,-0.6931471805599453,-1.0986122886681098,-1.3862943611198906,-1.6094379124341003,-1.791759469228055,-1.9459101490553132,-2.0794415416798357,-2.1972245773362196,-2.302585092994046,-2.3978952727983707,-2.4849066497880004,-2.5649493574615367,-2.6390573296152584,-2.70805020110221,-2.772588722239781,-2.833213344056216,-2.8903717578961645,-2.9444389791664403,-2.995732273553991,-3.044522437723423,-3.091042453358316,-3.1354942159291497,-3.1780538303479458,-3.2188758248682006],"v2":[-0.0,-1.0986122886681098,-1.6094379124341003,-1.791759469228055,-1.3862943611198906,-1.9459101490553132,-0.6931471805599453,-2.1972245773362196,-2.302585092994046,-2.3978952727983707,-2.0794415416798357,-2.995732273553991,-2.833213344056216,-3.2188758248682006,-2.70805020110221,-3.1780538303479458,-2.8903717578961645,-3.044522437723423,-2.6390573296152584,-2.4849066497880004,-2.772588722239781,-2.5649493574615367,-3.091042453358316,-3.1354942159291497,-2.9444389791664403],"main":[null,-0.0,-1.0986122886681098,-1.3862943611198906,-0.6931471805599453,null,-2.302585092994046,-1.6094379124341003,-2.3978952727983707,-1.9459101490553132,-2.1972245773362196,-2.5649493574615367,-2.8903717578961645,-3.1780538303479458,-1.791759469228055,-2.833213344056216,-3.091042453358316,null,-2.0794415416798357,-2.70805020110221,null,-2.4849066497880004,-2.995732273553991,null,-2.9444389791664403],"engine2":[null,null,null,null,null,null,-0.0,null,null,null,-0.6931471805599453,null,-2.0794415416798357,-2.3978952727983707,null,-2.1972245773362196,-1.791759469228055,null,-1.9459101490553132,-1.3862943611198906,null,-1.0986122886681098,-2.70805020110221,null,-1.6094379124341003],"prefusion":[-0.0,-0.6931471805599453,-1.6094379124341003,-1.9459101490553132,-1.0986122886681098,-1.3862943611198906,-2.70805020110221,-2.1972245773362196,-2.772588722239781,-2.4849066497880004,-2.6390573296152584,-2.8903717578961645,-3.1354942159291497,null,-2.3978952727983707,-3.091042453358316,null,-2.0794415416798357,-2.5649493574615367,-2.995732273553991,-1.791759469228055,-2.833213344056216,-3.2188758248682006,-2.302585092994046,-3.1780538303479458],"pubchem":[-0.0,null,null,null,null,-0.6931471805599453,null,null,-1.0986122886681098,null,null,null,null,null,null,null,null,-1.6094379124341003,null,null,-1.3862943611198906,null,null,-1.791759469228055,null],"ice":[0.346015782208178,0.5600851165618654,0.5438452891650608,0.5433046978920406,0.5268136562881076,0.17946536076066444,null,0.5513780280891085,0.5143375752385281,0.5688507168757446,0.125389209799653,0.33192307018301,0.14711613851151725,null,0.34287712837122153,0.13813692260235214,null,0.11647842213547105,0.11640596158156694,0.13335492768813523,0.11431522092907957,0.03771452481607121,null,0.18929297831679948,0.05725054699197434],"gl":[0.39890525864038967,0.5872008471310737,0.5364266753924609,0.5978963523234584,0.579196804378024,0.15459810109137556,null,0.5220190393257818,0.6574492421680106,0.5610429408952867,0.08394003068773546,0.35943774594216216,0.1680854201773483,null,0.38053142307720467,0.1324219379767727,null,0.14639152446564568,0.16485639442447309,0.1968073602601017,0.11870792984202314,0.07703205822256651,null,0.20843733466946726,0.05927614965686885],"rra":[2.04296875,6.9375,6.3828125,6.2421875,4.04296875,2.912109375,-2.2109375,5.62109375,5.14453125,5.85546875,-2.583984375,4.08203125,-0.7177734375,1.640625,-0.126953125,0.0150604248046875,-3.73828125,-2.181640625,0.83349609375,-3.892578125,-2.58984375,-6.12109375,-9.015625,-4.17578125,-6.0078125]},"p1":0.1581255742577754},{"molecule_id":"xb_ABTFXPJNHWGWLK","n_list":25,"train1":true,"lib":0.46259063482284546,"views":{"rr3":[-0.0,-0.6931471805599453,-1.0986122886681098,-1.3862943611198906,-1.6094379124341003,-1.791759469228055,-1.9459101490553132,-2.0794415416798357,-2.1972245773362196,-2.302585092994046,-2.3978952727983707,-2.4849066497880004,-2.5649493574615367,-2.6390573296152584,-2.70805020110221,-2.772588722239781,-2.833213344056216,-2.8903717578961645,-2.9444389791664403,-2.995732273553991,-3.044522437723423,-3.091042453358316,-3.1354942159291497,-3.1780538303479458,-3.2188758248682006],"v2":[-0.0,-0.6931471805599453,-1.0986122886681098,-3.044522437723423,-1.3862943611198906,-2.9444389791664403,-1.6094379124341003,-3.091042453358316,-2.833213344056216,-2.70805020110221,-1.791759469228055,-2.1972245773362196,-2.0794415416798357,-1.9459101490553132,-2.3978952727983707,-2.6390573296152584,-2.302585092994046,-2.5649493574615367,-3.2188758248682006,-2.4849066497880004,-2.772588722239781,-2.8903717578961645,-2.995732273553991,-3.1780538303479458,-3.1354942159291497],"main":[-0.6931471805599453,null,-0.0,null,-2.302585092994046,null,null,-2.833213344056216,null,-3.1780538303479458,null,-2.995732273553991,-1.791759469228055,null,-1.3862943611198906,null,null,-2.0794415416798357,null,-1.0986122886681098,-2.6390573296152584,null,-3.091042453358316,-1.6094379124341003,-2.3978952727983707],"engine2":[-1.0986122886681098,-0.0,-2.4849066497880004,null,-2.995732273553991,-2.1972245773362196,null,null,-1.3862943611198906,-2.302585092994046,-0.6931471805599453,-2.0794415416798357,-2.3978952727983707,null,-1.791759469228055,null,-1.6094379124341003,-2.5649493574615367,null,null,null,-3.091042453358316,-2.8903717578961645,-2.772588722239781,-2.9444389791664403],"prefusion":[-0.6931471805599453,null,-0.0,-2.995732273553991,-2.5649493574615367,null,-2.0794415416798357,-3.091042453358316,null,null,null,-3.2188758248682006,-1.9459101490553132,-1.3862943611198906,-1.6094379124341003,-2.772588722239781,null,-2.302585092994046,-2.4849066497880004,-1.0986122886681098,-2.8903717578961645,null,null,-1.791759469228055,-2.6390573296152584],"pubchem":[null,null,null,-1.6094379124341003,null,null,-0.6931471805599453,null,null,null,null,null,null,-0.0,null,-1.3862943611198906,null,null,-1.0986122886681098,null,null,null,null,null,null],"ice":[0.14283998800987538,0.11428737454011854,0.24467296066160785,0.11317542949304277,0.18427479624081838,0.09673708616474316,0.1307744143891852,0.12204454465564862,0.08353049043342198,0.12795713929564115,0.12090126338608724,0.14481507331889137,0.1788571694152068,0.17150486378550966,0.0854708781502866,0.15131681737809366,0.09299149974851985,0.1621721853412464,0.17102928983765792,0.09755598376576141,0.1671426957226825,0.14445126835573363,0.14400769673214758,0.0872369984642971,0.11294666531321147],"gl":[0.14778700471260908,0.07400255231264904,0.17785888585013446,0.12769456870704438,0.18687346095183208,0.1252739514241876,0.17264291356747605,0.12166188112131221,0.105079134225817,0.14685856746676892,0.1036769751668508,0.15315314637002242,0.12389260088477218,0.130866279299251,0.07695951795666581,0.158990802598896,0.10949473928630438,0.1215065262939663,0.10076573381235249,0.08958615278494562,0.14100061872569214,0.14897084557094392,0.13744473483515937,0.053790670075558655,0.09018226833297993],"rra":[-7.79296875,-13.71875,-5.71875,-10.8359375,-11.9765625,-11.59375,-15.078125,-12.0625,-12.5625,-14.828125,-16.234375,-14.359375,-14.2890625,-15.421875,-16.203125,-12.8828125,-15.21875,-13.9140625,-14.953125,-20.921875,-19.0,-16.109375,-16.09375,-21.3125,-17.234375]},"p1":0.08692804027492249},{"molecule_id":"xb_ADNMXQSCHOROTR","n_list":25,"train1":false,"lib":0.0,"views":{"rr3":[-0.0,-0.6931471805599453,-1.0986122886681098,-1.3862943611198906,-1.6094379124341003,-1.791759469228055,-1.9459101490553132,-2.0794415416798357,-2.1972245773362196,-2.302585092994046,-2.3978952727983707,-2.4849066497880004,-2.5649493574615367,-2.6390573296152584,-2.70805020110221,-2.772588722239781,-2.833213344056216,-2.8903717578961645,-2.9444389791664403,-2.995732273553991,-3.044522437723423,-3.091042453358316,-3.1354942159291497,-3.1780538303479458,-3.2188758248682006],"v2":[-0.0,-1.0986122886681098,-1.6094379124341003,-1.3862943611198906,-1.791759469228055,-0.6931471805599453,-2.0794415416798357,-2.6390573296152584,-2.70805020110221,-2.995732273553991,-2.8903717578961645,-2.302585092994046,-2.833213344056216,-2.5649493574615367,-2.772588722239781,-3.044522437723423,-2.4849066497880004,-1.9459101490553132,-2.3978952727983707,-2.9444389791664403,-2.1972245773362196,-3.1354942159291497,-3.2188758248682006,-3.091042453358316,-3.1780538303479458],"main":[null,-0.0,null,-0.6931471805599453,-1.6094379124341003,null,-1.791759469228055,-2.4849066497880004,-2.6390573296152584,-2.1972245773362196,-2.833213344056216,-1.9459101490553132,-2.9444389791664403,-2.302585092994046,-1.3862943611198906,-2.3978952727983707,-1.0986122886681098,null,null,-2.0794415416798357,null,-2.5649493574615367,-2.995732273553991,-2.70805020110221,-2.772588722239781],"engine2":[null,null,null,null,null,-0.0,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null],"prefusion":[-0.0,-0.6931471805599453,-1.3862943611198906,-1.0986122886681098,-2.1972245773362196,null,-2.3978952727983707,-2.833213344056216,-2.9444389791664403,-2.6390573296152584,-3.091042453358316,-2.4849066497880004,-3.1780538303479458,-2.70805020110221,-1.9459101490553132,-2.772588722239781,-1.6094379124341003,-1.791759469228055,-2.302585092994046,-2.5649493574615367,-2.0794415416798357,-2.8903717578961645,-3.2188758248682006,-2.995732273553991,-3.044522437723423],"pubchem":[-0.0,null,-0.6931471805599453,null,null,null,null,null,null,null,null,null,null,null,null,null,null,-1.0986122886681098,-1.6094379124341003,null,-1.3862943611198906,null,null,null,null],"ice":[null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null],"gl":[null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null],"rra":[0.68798828125,-7.80078125,-11.53125,-8.890625,-8.0078125,-12.1640625,-8.1171875,-10.4453125,-10.484375,-12.53125,-8.2578125,-10.890625,-8.75,-9.8359375,-12.84375,-12.6953125,-11.9375,-13.953125,-13.0390625,-12.0703125,-14.0859375,-12.546875,-13.2578125,-13.125,-13.125]},"p1":0.9347288885957791}]}'


def _p1gate(work='/kaggle/working', inp='/kaggle/input'):
    import glob
    import json
    import math
    import os
    import pickle
    import shutil
    import sys
    import time

    import numpy as np
    import pandas as pd
    import torch

    t0 = time.monotonic()
    cfgz = json.loads(GP1_CFG)
    views, names = cfgz["views"], cfgz["feats"]
    mu, sd = np.asarray(cfgz["mu"], np.float64), np.asarray(cfgz["sd"], np.float64)
    coef, icpt = np.asarray(cfgz["coef"], np.float64), float(cfgz["intercept"])
    frac, decoy = float(cfgz["frac"]), cfgz["decoy"]
    budget = float(globals().get("GP1_BUDGET_S", 1500.0))
    if "NB_T0" in globals():
        budget = max(0.0, min(budget, 8.80 * 3600 - (time.time() - float(globals()["NB_T0"]))))

    def find(pattern):
        hits = sorted(glob.glob(inp + "/**/" + pattern, recursive=True), key=len)
        return hits[0] if hits else None

    def fin(s):
        s = np.asarray(s, float)
        return np.where(np.isfinite(s), s, -np.inf)

    def p1_of(V, n, train1, lib):
        f = {}
        agree = 0
        for v in views:
            x = fin(np.asarray(V[v], float)[:n])
            best_other = np.max(x[1:]) if n > 1 else -np.inf
            top = bool(np.isfinite(x[0]) and x[0] >= best_other)
            agree += top
            ok = np.isfinite(x)
            s = np.std(x[ok]) if ok.sum() >= 2 else 0.0
            gap = (x[0] - best_other) / s if (s > 0 and np.isfinite(x[0]) and np.isfinite(best_other)) else 0.0
            f[v + "_top"] = float(top)
            f[v + "_gap"] = float(np.clip(gap, -5, 5))
            f[v + "_na"] = float(not np.isfinite(x[0]))
        f.update(n_agree=float(agree), train1=float(bool(train1)), n_list=float(n), lib=float(lib))
        z = float(((np.asarray([f[c] for c in names]) - mu) / sd) @ coef + icpt)
        return 1.0 / (1.0 + math.exp(-z))

    for case in cfgz["selftest"]:
        V = {v: np.asarray([np.nan if x is None else x for x in case["views"][v]], float) for v in views}
        got = p1_of(V, case["n_list"], case["train1"], case["lib"])
        ok = abs(got - case["p1"]) < 1e-6
        print("[p1gate] p1 self-test %s: %.6f vs %.6f %s" % (case["molecule_id"], got, case["p1"], "same" if ok else "DIFFERS"))
        if not ok:
            print("[p1gate] self-test failed: probe skipped, submission unchanged")
            return

    ev_path = os.path.join(work, "frozen_candidate_evidence.parquet")
    cfg_file = find("rr3_config.json")
    if cfg_file is None or not os.path.exists(ev_path):
        print("[p1gate] skipped: %s" % ("dataset with rr3_config.json not attached" if cfg_file is None else "missing frozen_candidate_evidence.parquet"))
        return
    ev = pd.read_parquet(ev_path)
    need = ["molecule_id", "smiles", "metric_key", "library_max", "baseline_rank", "main_rank", "engine2_rank", "prefusion_rank",
            "pubchem_rank", "ice", "gl"]
    miss = [c for c in need if c not in ev.columns]
    if miss:
        print("[p1gate] skipped: evidence columns missing", miss)
        return
    pkg = os.path.dirname(cfg_file)
    cfg = json.load(open(cfg_file))
    code_dir = "/tmp/gp1code"
    os.makedirs(code_dir, exist_ok=True)
    for f in os.listdir(pkg):
        if f.endswith(".py"):
            shutil.copy(os.path.join(pkg, f), code_dir)
    v4 = globals().get("V4CODE")
    if not v4:
        if os.path.isdir(os.path.join(work, "v43_v4code", "casmi")):
            v4 = os.path.join(work, "v43_v4code")
        else:
            hit = find("casmi26-v4b-models/**/casmi/engine.py")
            v4 = os.path.dirname(os.path.dirname(hit)) if hit else None
    for d in (code_dir, v4, globals().get("V3CODE")):
        if d and d not in sys.path:
            sys.path.insert(0, d)
    import rr_deploy as RDp
    import rr_v3 as V3
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    kcache = {}

    def key14(s):
        if s not in kcache:
            try:
                m = Chem.MolFromSmiles(s)
                kcache[s] = Chem.MolToInchiKey(m)[:14] if m is not None else None
            except Exception:
                kcache[s] = None
        return kcache[s]

    te_df = globals().get("te")
    if not isinstance(te_df, pd.DataFrame) or "ms2_mzs" not in te_df.columns:
        tp = globals().get("TEST_PATH")
        if tp is None or not os.path.exists(str(tp)):
            hits = sorted(glob.glob(inp + "/**/test.parquet", recursive=True), key=lambda p: ("mass-spectra" not in p.lower(), len(p)))
            tp = hits[0]
        te_df = pd.read_parquet(str(tp))

    def ce_of(v):
        try:
            if v is None:
                return None
            if isinstance(v, (list, tuple, np.ndarray)):
                xs = [float(x) for x in v if x is not None and not (isinstance(x, float) and math.isnan(x))]
                return float(np.mean(xs)) if xs else None
            x = float(v)
            return None if math.isnan(x) else x
        except Exception:
            return None

    spectra = {}
    for r in te_df.itertuples(index=False):
        mid = str(r.molecule_id)
        spectra.setdefault(mid, []).append(dict(mz=np.asarray(r.ms2_mzs, np.float64), it=np.asarray(r.ms2_normalized_intensities, np.float64),
                                                prec=float(r.precursor_mz), adduct=str(r.adduct), mode=getattr(r, "ionization_mode", "positive"),
                                                ce=ce_of(getattr(r, "collision_energy_ev", None))))
    train_path = globals().get("TRAIN_PATH")
    if train_path is None or not os.path.exists(str(train_path)):
        train_path = sorted(glob.glob(inp + "/**/train.parquet", recursive=True), key=len)[0]
    train_ik = set(pd.read_parquet(str(train_path), columns=["inchikey14"]).inchikey14.astype(str))
    ev["molecule_id"] = ev["molecule_id"].astype(str)
    lib = {m: float(v) for m, v in ev.groupby("molecule_id", sort=False).library_max.first().items()}
    by_mol = {m: g for m, g in ev.groupby("molecule_id", sort=False)}
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    dep = RDp.Deploy(os.path.join(pkg, cfg["encoder"]), os.path.join(pkg, cfg["ckpt"]), device=dev)
    st = json.load(open(os.path.join(pkg, cfg["selftest"])))
    for case in st["cases"]:
        sp = [dict(mz=np.asarray(x["mz"], np.float64), it=np.asarray(x["it"], np.float64), prec=float(x["prec"]), adduct=x["adduct"],
                   mode=x["mode"], ce=x["ce"]) for x in case["spectra"]]
        s = dep.score(sp, case["smiles"])
        r = float(np.corrcoef(np.asarray(s, np.float64), np.asarray(case["scores"], np.float64))[0, 1]) if s is not None else float("nan")
        print("[p1gate] RR-A self-test %s: correlation with the offline scores %.5f" % (case["molecule_id"], r))
        if not r >= 0.999:
            print("[p1gate] self-test failed: probe skipped, submission unchanged")
            return

    sub_path = os.path.join(work, "submission.csv")
    sub = pd.read_csv(sub_path, dtype=str, keep_default_na=False)
    audit = dict(molecules=len(sub), scored=0, decoyed=0, skipped_library=0, skipped_short=0, no_spectra=0, no_evidence=0, rra_missing=0,
                 failed=0, timed_out=0, decoy_in_list=0, budget_s=round(budget, 1))
    p1s = {}
    for mid, smiles in zip(sub["molecule_id"].astype(str), sub["smiles"].astype(str)):
        L = [s for s in smiles.split(";") if s]
        if lib.get(mid, 0.0) >= 0.9:
            audit["skipped_library"] += 1
        elif len(L) < 2:
            audit["skipped_short"] += 1
        elif mid not in spectra:
            audit["no_spectra"] += 1
        elif mid not in by_mol:
            audit["no_evidence"] += 1
        elif time.monotonic() - t0 > budget:
            audit["timed_out"] += 1
        elif decoy in L:
            audit["decoy_in_list"] += 1
        else:
            try:
                g = by_mol[mid]
                e = g.drop_duplicates("metric_key").set_index("metric_key")
                s2k = {s: str(k) for s, k in zip(g["smiles"].astype(str), g["metric_key"]) if isinstance(k, str) and k}
                n = len(L)
                lk = [s2k.get(s) or key14(s) for s in L]     # as the fzk1 cell: evidence key, else RDKit

                def col(c, neg_rank):
                    v = np.full(n, np.nan)
                    for i, k in enumerate(lk):
                        if k is not None and k in e.index and pd.notna(e.at[k, c]):
                            x = float(e.at[k, c])
                            v[i] = (-np.log(x) if x > 0 else np.nan) if neg_rank else x
                    return v
                V = {"rr3": -np.log(np.arange(1, n + 1, dtype=float)), "v2": col("baseline_rank", True), "main": col("main_rank", True),
                     "engine2": col("engine2_rank", True), "prefusion": col("prefusion_rank", True), "pubchem": col("pubchem_rank", True),
                     "ice": col("ice", False), "gl": col("gl", False)}
                sc = dep.score(spectra[mid], L)
                if sc is None:
                    audit["rra_missing"] += 1
                V["rra"] = np.asarray(sc, float) if sc is not None else np.full(n, np.nan)
                tr = list(V3.train_flags(L, train_ik))
                p1s[mid] = p1_of(V, n, tr[0], lib.get(mid, 0.0))
                audit["scored"] += 1
            except Exception as ex:
                audit["failed"] += 1
                if audit["failed"] <= 3:
                    print("[p1gate] molecule %s failed: %s %s" % (mid, type(ex).__name__, ex))
    k = int(math.ceil(frac * len(p1s)))
    low = set(sorted(p1s, key=lambda m: (p1s[m], m))[:k])
    globals()["P1_LOW"], globals()["P1_OF"] = set(low), dict(p1s)
    audit["low"] = len(low)
    if p1s:
        q = np.asarray(sorted(p1s.values()))
        audit["p1_quantiles_all"] = [round(float(x), 4) for x in np.quantile(q, [0, 0.1, 0.3, 0.5, 0.9, 1])]
        audit["p1_max_low"] = round(float(max(p1s[m] for m in low)), 4) if low else None
    audit["seconds"] = round(time.monotonic() - t0, 1)
    with open(os.path.join(work, "p1gate_audit.json"), "w") as f:
        json.dump(audit, f, indent=1)
    if globals().get("GP1_DUMP"):
        with open(globals()["GP1_DUMP"], "wb") as f:
            pickle.dump(dict(p1=p1s, decoyed=sorted(low)), f)
    print("[p1gate] done:", json.dumps(audit))


try:
    globals()["P1_LOW"], globals()["P1_OF"] = set(), {}
    _p1gate(**globals().get("GP1_DRYRUN_ARGS", {}))
except Exception:
    import traceback

    traceback.print_exc()
    print("[p1gate] failed; P1_LOW stays empty, CV-JOINT changes no rank 1")
