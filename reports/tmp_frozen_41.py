'''--- CLAW FIX (b418/b419): stage health is now RECORDED, never silently swallowed ---'''
'''`glob('/kaggle/input/**/x')` WITHOUT recursive=True matches one directory level only, so it'''
'''misses /kaggle/input/datasets/<owner>/<slug>/. That silently disabled ICEBERG+GLACIER:'''
'''ICE FAILED -> ranker order kept: FileNotFoundError('cp313 rdkit wheel not found')  [b417 log]'''
'''rdkit-2025.3.6-cp312-...whl is not a supported wheel on this platform               [b417 log]'''
'''recursive=True finds the wheel under BOTH mount layouts (same 2025.3.6 cp313 file either way).'''
CLAW_ICE_HEALTH = 'ICE NOT RUN'
CLAW_GL_HEALTH = 'GL NOT RUN'
BASE_ICE = False         # b421: base-list ICEBERG fusion OFF (b420 showed it costs 0.009); see header
'''ICEBERG post-ranker isomer re-scoring (casmi26-iceberg). Optional: any failure keeps the ranker order.'''
import gc
ICE_SCORES, ice_stats = {}, dict(molecules=0, changed_top25=0, changed_top1=0)


'''--- CLAW FIX (b415c): make ICEBERG/GLACIER runnable on a cp313 Kaggle image ---'''
'''The ICEBERG package bundles rdkit-2025.3.6 built for **cp312**; this image is cp313,'''
'''so pip rejects that wheel and install_site() raises before anything is scored'''
'''(n_mols_scored == 0 for ICEBERG *and* GLACIER). The MANIFEST pins 2025.3.6 because'''
'''"FragmentEngine Kekulize differs in 2026.03", so swapping in the runtime's 2026.03'''
'''rdkit would change the scoring. Instead we install the SAME 2025.3.6 release built'''
'''for cp313, so the pinned version is honoured exactly and RDKIT_REQ passes natively.'''
''''''
'''install_site() is idempotent via <site>/.ice_site_ok, which it compares against the'''
'''name list of `pkg/wheels`. We pre-build the site and write that exact list, so both'''
'''runners short-circuit and never invoke the failing pip.'''
def _claw_preseed_site(pkg, site):
    import glob as _g, os as _o, shutil as _s, subprocess as _sp, sys as _sys
    srcs = sorted(_g.glob(_o.path.join(pkg, 'wheels', '*.whl.ice')) +
                  _g.glob(_o.path.join(pkg, 'wheels', '*.whl')))
    # install everything EXCEPT the cp-tag-mismatched rdkit
    keep = [w for w in srcs if not _o.path.basename(w).lower().startswith('rdkit')]
    dropped = [_o.path.basename(w) for w in srcs if w not in keep]
    new = [simulator_rdkit_wheel(pkg)]
    keep = keep + new[:1]
    _o.makedirs(site, exist_ok=True)
    wdir = _o.path.join(site, '.wheels')
    _o.makedirs(wdir, exist_ok=True)
    whl = []
    for w in keep:
        dst = _o.path.join(wdir, _o.path.basename(w)[:-4] if w.endswith('.ice') else _o.path.basename(w))
        _s.copyfile(w, dst)
        whl.append(dst)
    r = _sp.run([_sys.executable, '-m', 'pip', 'install', '-q', '--no-index', '--no-deps',
                 '--no-compile', '--disable-pip-version-check', '--upgrade', '--target', site] + whl,
                stdout=_sp.PIPE, stderr=_sp.STDOUT, text=True)
    print('[claw] site preseed rc', r.returncode, (r.stdout or '')[-400:], flush=True)
    if r.returncode != 0:
        raise RuntimeError('claw preseed pip failed: ' + (r.stdout or '')[-600:])
    _s.rmtree(wdir, ignore_errors=True)
    # the marker MUST equal exactly what install_site() derives from the PACKAGE list
    want = '\n'.join(_o.path.basename(w) for w in srcs)
    with open(_o.path.join(site, '.ice_site_ok'), 'w') as f:
        f.write(want)
    print('[claw] site ready; substituted', dropped, '->', [_o.path.basename(w) for w in new[:1]], flush=True)
    return want


try:
    ICE_PKG = os.path.dirname(find('casmi26-iceberg/**/ice_runner.py'))
    sys.path.append(ICE_PKG)
    import fuse as ice_fuse
    del V, E, bank; gc.collect(); torch.cuda.empty_cache()
    # priority: molecules without a library-level match first (class 1 rarely changes), then the rest
    mids = sorted(BASE, key=lambda m: BASE[m][2])
    cands = {m: (ice_fuse.ice_candidates(BASE[m][0], BASE[m][4], TOPN) if BASE_ICE else []) for m in mids}
    if ENG:                              # ADDED (ICE_UNION): also score our engine's candidates (same-formula groups
        from rdkit.Chem.rdMolDescriptors import CalcMolFormula as _CMF   # formed over the v4g top-N + engine top-40)
        from rdkit import Chem as _Ch
        def _f2(s):
            try:
                return _CMF(_Ch.MolFromSmiles(s))
            except Exception:
                return s
        n_add = 0
        for m in mids:
            e = ENG.get(str(m))
            if not e or not e.get('smiles'):
                continue
            bs, bk, bf = list(BASE[m][0][:TOPN]), set(BASE[m][1][:TOPN]), list(BASE[m][4][:TOPN])
            es = [s for s, k in zip(e['smiles'][:40], e['keys'][:40]) if k not in bk]
            ef = [_f2(s) for s in es]
            extra = ice_fuse.ice_candidates(bs + es, bf + ef, len(bs) + len(es))
            before = len(cands.get(m, []))
            cands[m] = list(dict.fromkeys(list(cands.get(m, [])) + extra))
            n_add += len(cands[m]) - before
        print('ICE_UNION: engine candidates added to ICE input:', n_add, flush=True)
    if ICE_PC:                          # also the PubChem-only list of molecules the v3.6 gate may use (lib_max < LIB_TAU)
        from rdkit.Chem.rdMolDescriptors import CalcMolFormula
        from rdkit import Chem as _Chem
        def _form(s):
            try:
                return CalcMolFormula(_Chem.MolFromSmiles(s))
            except Exception:
                return s
        for m in mids:
            p = PC.get(m) if isinstance(PC, dict) else None
            if p and p.get('pc') and BASE[m][2] < LIB_TAU:
                p['pc_form'] = [_form(x) for x in p['pc']]
                extra = ice_fuse.ice_candidates(p['pc'], p['pc_form'], 25)
                cands[m] = list(dict.fromkeys(list(cands.get(m, [])) + extra))
    cands = {m: c for m, c in cands.items() if c}
    items = ice_fuse.build_ice_input(te, cands)
    print('ICE input molecules', len(items), 'candidates', sum(len(it['cands']) for it in items), f'{time.time()-T0:.0f}s', flush=True)
    _claw_preseed_site(ICE_PKG, '/kaggle/working/ice_site')
    ICE_SCORES = ice_fuse.run_ice(ICE_PKG, items, workdir='/kaggle/working/ice_work', device='cuda', budget_s=ICE_BUDGET,
                                  site='/kaggle/working/ice_site', extra_args=['--any-rdkit'])
    meta_f = '/kaggle/working/ice_work/ice_out.json.meta.json'
    if os.path.exists(meta_f):
        print('ICE meta', open(meta_f).read()[:1500])
except Exception as e:
    CLAW_ICE_HEALTH = f'ICE FAILED: {e!r}'
    print('ICE FAILED -> ranker order kept:', repr(e), flush=True)
'''v4h: GLACIER third re-scoring term (casmi26-glacier) on the SAME runner input; any GLACIER failure -> v4g (ICE only)'''
GL_SCORES, gl_stats, GL_LAM, GL_BUDGET = {}, dict(molecules=0, changed_vs_ice_top25=0, changed_vs_ice_top1=0), 1.0, 4000
try:
    GL_PKG = os.path.dirname(find('casmi26-glacier/**/gl_runner.py'))
    sys.path.append(GL_PKG)
    import gl_fuse
    gc.collect(); torch.cuda.empty_cache()   # ICE ran in its own (finished) process; free the notebook's cached GPU memory
    gl_items = [dict(it, spectra=[s for s in it['spectra'] if s.get('adduct') == '[M+H]+']) for it in items]   # v29: GLACIER on [M+H]+ only (v27: +0.006)
    gl_items = [it for it in gl_items if it['spectra']]
    print('v29 GLACIER [M+H]+ only: molecules', len(gl_items), 'of', len(items))
    GL_SCORES = gl_fuse.run_gl(GL_PKG, gl_items, workdir='/kaggle/working/gl_work', device='cuda', budget_s=GL_BUDGET,
                               site='/kaggle/working/ice_site', wheels=os.path.join(ICE_PKG, 'wheels'), extra_args=['--any-rdkit'])
    meta_f = '/kaggle/working/gl_work/gl_out.json.meta.json'
    print('GL meta', open(meta_f).read()[:1500] if os.path.exists(meta_f) else 'missing')
except Exception as e:
    GL_SCORES = {}
    CLAW_GL_HEALTH = f'GL FAILED: {e!r}'
    print('GL FAILED -> v4g behaviour (ICE only):', repr(e), flush=True)
# N1A complement: Seyit Kaan Gunes; integration as in Ahmed Berat Ozer v15 / guhongbin v465.
# ---- N1A_MCE (gold roadmap 2026-10-09 section 3.2: N1 arm A + I14b merged CE on the proxies only) ---------------
# Molecules WITHOUT a real [M+H]+ spectrum are GLACIER-blind in H1. N1 arm A scores their [M+NH4]+ / [M-H2O+H]+
# spectra as [M+H]+ proxies (NH4: M = prec - 18.033823, peaks >= M + 1.007276 - 1.5 dropped; water loss:
# M = prec + 18.010565 - 1.007276, peaks < prec - 1.5 kept; precursor -> M + 1.007276, relabelled [M+H]+;
# [M-2H2O+H]+ / Na / K never), and a merged-CE proxy (>= 2 distinct CE buckets) is predicted at EVERY bucket and the
# predictions merge()d like the SUM_CE path (I14b). = bench kdev_glbench_n1 arm N1A_D on the blind molecules (521
# bench molecules: 21 blind molecules with a proxy, lift over random +0.270 [0.117, 0.443]; vs H1 on all np molecules
# +0.027 [0.010, 0.047]; merged vs mean CE on those 21 +0.0026). Arm B (proxies also where [M+H]+ exists, -0.047) and
# merged CE for real [M+H]+ spectra (no gain) are NOT done: molecules WITH a real [M+H]+ keep the H1 run above
# untouched (stock gl_runner, mean CE, byte-identical input). The bench's own code runs here, embedded verbatim
# (sha256-checked): glb_core.py (n1_proxy / build_variants / mol_flags / arm_tags / arm_scores) in this process,
# glb_driver.py (driver around the attached gl_runner.py: same env, model, Predictor, canonicalisation, CE bucketing,
# merge, entropy similarity) in its own process like gl_runner. N1 scores are added to GL_SCORES (-> the PubChem-list
# re-rank below and the fused re-rank of cell 19, whose `if ice:` gate is opened ONLY for N1 molecules with scores).
# Any failure -> no N1 scores = H1 behaviour (the commit raises instead). The 12 dummy commit molecules never
# trigger N1, so the commit adds a forced exercise: synthetic [M+H]+-less copies 'n1x:<mid>' ([M+H]+ -> [M+NH4]+ with
# an injected NH4 precursor peak, the first one also -> [M-H2O+H]+) run through the same code + asserts.
N1_ARM = 'N1A_D'                 # bench arm: blind molecule -> spectrum tags (NH4p, WLp), CE mode 'merged'
N1_BUDGET = 1200.0 if IS_RERUN else 600.0
N1_WORK, N1_SITE, N1_DEVICE, N1_DRIVER_EXTRA = '/kaggle/working/n1_work', '/kaggle/working/ice_site', 'cuda', []
N1_MIDS, N1_GL_MIDS, N1_STATS, N1_DRV, N1_HEALTH = set(), set(), {}, {}, 'N1 NOT RUN'
N1X_MIDS, N1X_GL, N1X_STATS = set(), {}, {}
# k2 (E006 port), variant A = N1-complement. E006 (cell 31) re-ranks a GLACIER-blind molecule with ICEBERG when its ICE
# dict has finite scores (in practice [M+Na]+ without [M+H]+: `elif ice_fallback and ice and not gl`). N1 GL scores
# would move such a molecule to the GLACIER branch, so they are kept ONLY for N1 molecules WITHOUT any finite ICE
# score (E006 has no forward-model evidence there: its ICE fallback on an all-None dict is a no-op). False = the plain
# port (N1 GL scores for every N1 molecule, E2 behaviour). Molecules with a real [M+H]+ are never touched either way.
# Challenger route: flexonafft, casmi26-closing-the-evidence-gap v47.
N1_COMPLEMENT = False
print('[N1 challenger] configuration: N1_COMPLEMENT=False; real [M+H]+ stays on H1', flush=True)
N1_ICE_DROPPED = set()           # N1 molecules left to E006's ICE fallback by the complement filter
N1_CORE_SHA256 = 'f7a3b8cd8802a7ba3b69a297603241784a63c069044cf7bd6efda7d68cc8fdfa'      # = subs/out/kdev_glbench_n1_full/glb_core.py
N1_DRIVER_SHA256 = 'e919a154b57bda5a52573481348e38d8b4e7c97883532ea5b385bc3cb6f98502'    # = subs/out/kdev_glbench_n1_full/glb_driver.py
N1_GL_RUNNER_SHA256 = '5c4f74313ac54263d05d987c39d012d81ec57c5f35e1095ecd49a5bcb6440fca'   # casmi26-glacier gl_runner.py (B1 MANIFEST, bench)
# kdev_glbench_n1 glb_core.py, verbatim (proxy construction, variants, arm resolution, aggregation)
N1_CORE_SRC = ''.join([
    '"""casmi26 kdev_glbench_n1 -- pure-python core of the roadmap 3.2 GLACIER bench (no torch / rdkit import).\n',
    '\n',
    'Query handling (N1, roadmap 3.2), on fuse.build_ice_input(..., covered_only=False) spectrum dicts:\n',
    '  [M+NH4]+    M = prec - 18.033823; prec -> M + 1.007276; drop peaks mz >= M + 1.007276 - 1.5; relabel [M+H]+\n',
    '  [M-H2O+H]+  M = prec + 18.010565 - 1.007276; prec -> M + 1.007276; keep peaks mz < original prec - 1.5; relabel\n',
    '  (a proxy left without peaks is dropped; [M-2H2O+H]+, [M+Na]+, [M+K]+ are never proxied)\n',
    '  Hcut (diagnostic): a real [M+H]+ spectrum with the same precursor-region cut (peaks mz >= prec - 1.5 dropped), the\n',
    '  like-for-like reference for the proxies (separates "different adduct" from "precursor region removed").\n',
    '\n',
    'Scoring: the driver returns per-spectrum GLACIER similarities for the frozen bench candidates in two CE modes\n',
    "('mean' = production gl_runner: one prediction at the bucket of mean(ce_ev); 'merged' = I14b: one prediction per\n",
    "distinct CE bucket of a merged-CE spectrum, merged like the SUM_CE path). A molecule's arm score per candidate =\n",
    "mean over the arm's spectra with a similarity = gl_ex_mean restricted to those spectra.\n",
    '\n',
    'Ranking metric: expected reciprocal rank of the truth (cands[mid][0]) under a UNIFORM RANDOM tie-break (no truth-first\n',
    'bias: a truth tied with k decoys gets mean(1/(r..r+k))); unscored candidates rank below every scored one (tied among\n',
    'themselves). Baseline = a random order of all frozen candidates, mean(1/1..1/n). An arm "covers" a molecule when the\n',
    'truth and >= 2 candidates are scored; elsewhere the arm has no evidence (= the random baseline in fill-in totals).\n',
    '"""\n',
    'import math\n',
    'from collections import Counter, OrderedDict\n',
    '\n',
    'import numpy as np\n',
    '\n',
    'PROTON = 1.007276\n',
    'NH4_ADD = 18.033823           # [M+NH4]+ precursor m/z - M\n',
    'H2O = 18.010565\n',
    'CUT_DA = 1.5\n',
    'MIN_PEAKS = 1\n',
    "PROXY_TAG = OrderedDict([('[M+NH4]+', 'NH4p'), ('[M-H2O+H]+', 'WLp')])\n",
    'EPS_TIE = 1e-12\n',
    'N_BOOT = 2000\n',
    'BOOT_SEED = 12345\n',
    '\n',
    "# arm -> (spectrum tags, CE mode, description); 'N1A' is resolved per molecule (see arm_tags)\n",
    'ARMS = OrderedDict([\n',
    "    ('A_H', (('H',), 'mean', '(a) [M+H]+ only, mean CE = B1 production GL')),\n",
    "    ('B_NH4', (('NH4p',), 'mean', '(b) [M+NH4]+ proxies relabelled [M+H]+')),\n",
    "    ('C_WL', (('WLp',), 'mean', '(c) [M-H2O+H]+ proxies relabelled [M+H]+')),\n",
    "    ('D_Hmerged', (('H',), 'merged', '(d) [M+H]+ only, merged-CE per-bucket prediction (I14b)')),\n",
    "    ('A_Hcut', (('Hcut',), 'mean', 'diag: [M+H]+ with the proxy-style precursor cut')),\n",
    "    ('B_NH4m', (('NH4p',), 'merged', 'diag: NH4 proxies, merged CE')),\n",
    "    ('C_WLm', (('WLp',), 'merged', 'diag: water-loss proxies, merged CE')),\n",
    "    ('HNa', (('H', 'Na'), 'mean', 'diag: [M+H]+ and [M+Na]+ (old fwdbench COV; P4 analogue)')),\n",
    "    ('AB', (('H', 'NH4p', 'WLp'), 'mean', 'diag: N1 arm B = [M+H]+ plus all proxies')),\n",
    "    ('N1A', (None, 'mean', 'N1 arm A: [M+H]+ if the molecule has one, else its proxies')),\n",
    "    ('N1A_D', (None, 'merged', 'diag: N1 arm A with merged CE (N1A + I14b)')),\n",
    '])\n',
    '\n',
    '\n',
    '# ------------------------------------------------------------------------------------------------ query handling --\n',
    'def _keep_below(sp, cut, min_peaks):\n',
    "    mz, it = sp.get('mz') or [], sp.get('it') or []\n",
    '    keep = [(float(m), float(i)) for m, i in zip(mz, it) if float(m) < cut]\n',
    '    if len(keep) < min_peaks or not any(i > 0 for _, i in keep):\n',
    '        return None\n',
    '    return [m for m, _ in keep], [i for _, i in keep]\n',
    '\n',
    '\n',
    'def n1_proxy(sp, min_peaks=MIN_PEAKS):\n',
    '    """[M+NH4]+ / [M-H2O+H]+ positive spectrum dict -> relabelled [M+H]+ proxy dict, or None."""\n',
    "    if not isinstance(sp, dict) or sp.get('mode') != 'positive':\n",
    '        return None\n',
    "    ad = sp.get('adduct')\n",
    '    try:\n',
    "        prec = float(sp['prec'])\n",
    '    except Exception:\n',
    '        return None\n',
    '    if not math.isfinite(prec):\n',
    '        return None\n',
    "    if ad == '[M+NH4]+':\n",
    '        M = prec - NH4_ADD\n',
    '        cut = M + PROTON - CUT_DA\n',
    "    elif ad == '[M-H2O+H]+':\n",
    '        M = prec + H2O - PROTON\n',
    '        cut = prec - CUT_DA\n',
    '    else:\n',
    '        return None\n',
    '    k = _keep_below(sp, cut, min_peaks)\n',
    '    if k is None:\n',
    '        return None\n',
    '    out = dict(sp)\n',
    "    out.update(mz=k[0], it=k[1], prec=M + PROTON, adduct='[M+H]+', mode='positive', n1_src=ad)\n",
    '    return out\n',
    '\n',
    '\n',
    'def h_cut(sp, min_peaks=MIN_PEAKS):\n',
    '    """Real [M+H]+ spectrum with the proxy-style cut (peaks mz >= prec - 1.5 dropped); None if nothing is left."""\n',
    "    if not isinstance(sp, dict) or sp.get('mode') != 'positive' or sp.get('adduct') != '[M+H]+':\n",
    '        return None\n',
    "    k = _keep_below(sp, float(sp['prec']) - CUT_DA, min_peaks)\n",
    '    if k is None:\n',
    '        return None\n',
    '    return dict(sp, mz=k[0], it=k[1])\n',
    '\n',
    '\n',
    'def build_variants(items_all):\n',
    '    """fuse.build_ice_input(Q, cands, covered_only=False) items -> driver items whose spectra carry sid / tag\n',
    '    (tags H, Hcut, Na, NH4p, WLp), plus counts. sid = \'<index of the spectrum in the molecule>:<tag>\'."""\n',
    '    out, st = [], Counter()\n',
    '    for it in items_all:\n',
    '        sps = []\n',
    "        for j, sp in enumerate(it.get('spectra') or []):\n",
    "            if sp.get('mode') != 'positive':\n",
    '                continue\n',
    "            ad = sp.get('adduct')\n",
    "            if ad == '[M+H]+':\n",
    "                sps.append(dict(sp, sid=f'{j}:H', tag='H')); st['H'] += 1\n",
    '                c = h_cut(sp)\n',
    '                if c is None:\n',
    "                    st['Hcut_empty'] += 1\n",
    '                else:\n',
    "                    sps.append(dict(c, sid=f'{j}:Hcut', tag='Hcut')); st['Hcut'] += 1\n",
    "            elif ad == '[M+Na]+':\n",
    "                sps.append(dict(sp, sid=f'{j}:Na', tag='Na')); st['Na'] += 1\n",
    '            elif ad in PROXY_TAG:\n',
    '                tag = PROXY_TAG[ad]\n',
    '                p = n1_proxy(sp)\n',
    '                if p is None:\n',
    "                    st[tag + '_empty'] += 1\n",
    '                else:\n',
    "                    sps.append(dict(p, sid=f'{j}:{tag}', tag=tag)); st[tag] += 1\n",
    "        out.append(dict(mid=str(it['mid']), cands=list(it['cands']), spectra=sps))\n",
    '    return out, dict(st)\n',
    '\n',
    '\n',
    'def proxy_prec_check(items):\n',
    '    """Real-data check of the adduct arithmetic: proxy precursor (M + 1.007276) vs the molecule\'s real [M+H]+\n',
    '    precursor m/z (median over its [M+H]+ spectra), in mDa, per proxy tag."""\n',
    '    out = {}\n',
    '    for tag in PROXY_TAG.values():\n',
    '        d = []\n',
    '        for it in items:\n',
    "            H = [float(sp['prec']) for sp in it['spectra'] if sp.get('tag') == 'H']\n",
    '            if H:\n',
    "                d += [1000.0 * (float(sp['prec']) - float(np.median(H))) for sp in it['spectra'] if sp.get('tag') == tag]\n",
    '        out[tag] = dict(n=len(d), median_mda=float(np.median(d)) if d else None,\n',
    '                        max_abs_mda=float(np.max(np.abs(d))) if d else None)\n',
    '    return out\n',
    '\n',
    '\n',
    '# ---------------------------------------------------------------------------------------------------- ranking ----\n',
    'def rr_random_tb(vals, ti=0, eps=EPS_TIE):\n',
    '    """Expected reciprocal rank of vals[ti] under a uniform random tie-break; None entries rank below all scored\n',
    '    ones. None if vals[ti] is None."""\n',
    '    t = vals[ti]\n',
    '    if t is None:\n',
    '        return None\n',
    '    gt = eq = 0\n',
    '    for j, v in enumerate(vals):\n',
    '        if j == ti or v is None:\n',
    '            continue\n',
    '        if v > t + eps:\n',
    '            gt += 1\n',
    '        elif abs(v - t) <= eps:\n',
    '            eq += 1\n',
    '    return sum(1.0 / (gt + 1 + k) for k in range(eq + 1)) / (eq + 1)\n',
    '\n',
    '\n',
    'def rr_truth_first(vals, ti=0, eps=EPS_TIE):\n',
    '    """Old-bench convention with the truth winning every tie (the bias this bench removes)."""\n',
    '    t = vals[ti]\n',
    '    if t is None:\n',
    '        return None\n',
    '    return 1.0 / (1 + sum(1 for j, v in enumerate(vals) if j != ti and v is not None and v > t + eps))\n',
    '\n',
    '\n',
    'def rr_split(vals, ti=0, eps=EPS_TIE):\n',
    '    """fwdbench bench_core.mrr_table convention (ties count half)."""\n',
    '    t = vals[ti]\n',
    '    if t is None:\n',
    '        return None\n',
    '    gt = sum(1 for j, v in enumerate(vals) if j != ti and v is not None and v > t + eps)\n',
    '    eq = sum(1 for j, v in enumerate(vals) if j != ti and v is not None and abs(v - t) <= eps)\n',
    '    return 1.0 / (1 + gt + 0.5 * eq)\n',
    '\n',
    '\n',
    'def rr_rand(n):\n',
    "    return sum(1.0 / k for k in range(1, n + 1)) / n if n > 0 else float('nan')\n",
    '\n',
    '\n',
    'def covered(vals, ti=0):\n',
    '    return vals[ti] is not None and sum(v is not None for v in vals) >= 2\n',
    '\n',
    '\n',
    '# ------------------------------------------------------------------------------------------------ aggregation ----\n',
    'def mol_flags(item):\n',
    "    tags = Counter(sp['tag'] for sp in item['spectra'])\n",
    "    return dict(has_H=tags['H'] > 0, has_NH4p=tags['NH4p'] > 0, has_WLp=tags['WLp'] > 0, has_Na=tags['Na'] > 0)\n",
    '\n',
    '\n',
    'def arm_tags(arm, flags):\n',
    '    tags, mode, _ = ARMS[arm]\n',
    '    if tags is None:                                        # N1 arm A: proxies only where no real [M+H]+ exists\n',
    "        tags = ('H',) if flags['has_H'] else ('NH4p', 'WLp')\n",
    '    return tags, mode\n',
    '\n',
    '\n',
    'def arm_scores(mol_out, tags, mode):\n',
    '    """mol_out = driver output of one molecule {\'cands\': [...], \'spec\': {sid: {\'tag\',\'nb\',\'mean\',\'merged\'}}} ->\n',
    '    per-candidate list (aligned with mol_out[\'cands\']) of the mean similarity over the arm\'s spectra (None if none)."""\n',
    "    cands = mol_out.get('cands') or []\n",
    "    cols = [s[mode] for sid, s in sorted((mol_out.get('spec') or {}).items(), key=lambda kv: _sid_key(kv[0]))\n",
    "            if s.get('tag') in tags and s.get(mode) is not None]\n",
    '    out = []\n',
    '    for i in range(len(cands)):\n',
    '        xs = [c[i] for c in cols if i < len(c) and c[i] is not None]\n',
    '        out.append(float(np.mean(xs)) if xs else None)\n',
    '    return out\n',
    '\n',
    '\n',
    'def _sid_key(sid):\n',
    "    a, _, b = str(sid).partition(':')\n",
    '    try:\n',
    '        return (int(a), b)\n',
    '    except ValueError:\n',
    '        return (10 ** 9, str(sid))\n',
    '\n',
    '\n',
    'def molecule_table(items, out, done):\n',
    '    """-> list of row dicts, one per molecule the driver finished: rr per arm (None = arm does not cover it)."""\n',
    '    rows = []\n',
    '    for it in items:\n',
    "        mid = it['mid']\n",
    '        if mid not in done:\n',
    '            continue\n',
    "        mo = out.get(mid) or {'cands': it['cands'], 'spec': {}}\n",
    "        assert list(mo.get('cands') or it['cands']) == list(it['cands']), ('candidate order changed', mid)\n",
    '        fl = mol_flags(it)\n',
    "        n = len(it['cands'])\n",
    "        nb_h = [s.get('nb', 1) for s in (mo.get('spec') or {}).values() if s.get('tag') == 'H']\n",
    "        r = dict(mid=mid, set=mid.split(':')[0], n=n, rand=rr_rand(n), has_merged_H=any(b >= 2 for b in nb_h), **fl)\n",
    '        for arm in ARMS:\n',
    '            tags, mode = arm_tags(arm, fl)\n',
    '            v = arm_scores(mo, tags, mode)\n',
    "            r['rr_' + arm] = rr_random_tb(v) if covered(v) else None\n",
    "            if arm == 'A_H':\n",
    "                r['rrtf_A_H'] = rr_truth_first(v) if covered(v) else None\n",
    "                r['rrsp_A_H'] = rr_split(v) if covered(v) else None\n",
    "                r['top1_A_H'] = (None if not covered(v) else float(rr_random_tb(v) == 1.0))\n",
    '        rows.append(r)\n',
    '    return rows\n',
    '\n',
    '\n',
    '# ----------------------------------------------------------------------------------------------------- stats -----\n',
    'def _boot_idx(n, seed=BOOT_SEED, nb=N_BOOT):\n',
    '    return np.random.default_rng(seed).integers(0, n, (nb, n))\n',
    '\n',
    '\n',
    "def paired(rows, a, b, sel=None, label=''):\n",
    '    """Paired comparison of arms a and b over the rows both cover (and sel(row) if given)."""\n',
    "    R = [r for r in rows if r['rr_' + a] is not None and r['rr_' + b] is not None and (sel is None or sel(r))]\n",
    '    n = len(R)\n',
    '    res = dict(label=label, a=a, b=b, n=n)\n',
    '    if n == 0:\n',
    '        return res\n',
    "    ra = np.array([r['rr_' + a] for r in R]); rb = np.array([r['rr_' + b] for r in R])\n",
    "    rn = np.array([r['rand'] for r in R])\n",
    '    d = rb - ra\n',
    '    idx = _boot_idx(n)\n',
    '    la, lb = ra - rn, rb - rn\n',
    "    with np.errstate(divide='ignore', invalid='ignore'):\n",
    '        bo_ratio = lb[idx].mean(1) / la[idx].mean(1)\n',
    "    ratio = float(lb.mean() / la.mean()) if la.mean() > 0 else float('nan')\n",
    '    res.update(mrr_a=float(ra.mean()), mrr_b=float(rb.mean()), rand=float(rn.mean()), lift_a=float(la.mean()),\n',
    '               lift_b=float(lb.mean()), delta=float(d.mean()),\n',
    '               delta_ci=[float(x) for x in np.percentile(d[idx].mean(1), [2.5, 97.5])],\n',
    '               ratio=ratio, ratio_ci=[float(x) for x in np.nanpercentile(bo_ratio, [2.5, 97.5])] if n > 1 else [ratio, ratio],\n',
    '               wins=int((d > 1e-9).sum()), ties=int((np.abs(d) <= 1e-9).sum()), losses=int((d < -1e-9).sum()),\n',
    "               by_set={s: int(sum(r['set'] == s for r in R)) for s in sorted({r['set'] for r in R})})\n",
    '    return res\n',
    '\n',
    '\n',
    "def arm_table(rows, arm, sets=('np', 'e180', 'all')):\n",
    '    out = {}\n',
    '    for s in sets:\n',
    "        R = [r for r in rows if r['rr_' + arm] is not None and (s == 'all' or r['set'] == s)]\n",
    '        if not R:\n',
    '            out[s] = dict(n=0)\n',
    '            continue\n',
    "        rr = np.array([r['rr_' + arm] for r in R]); rn = np.array([r['rand'] for r in R])\n",
    '        out[s] = dict(n=len(R), mrr=float(rr.mean()), rand=float(rn.mean()), lift=float((rr - rn).mean()),\n',
    '                      top1=float(np.mean(rr >= 1.0 - 1e-12)))\n',
    '    return out\n',
    '\n',
    '\n',
    "def filled_delta(rows, a, b, sel=None, label=''):\n",
    '    """Mean over ALL selected molecules with a missing arm filled by the random baseline (no evidence)."""\n',
    '    R = [r for r in rows if sel is None or sel(r)]\n',
    '    n = len(R)\n',
    '    res = dict(label=label, a=a, b=b, n=n)\n',
    '    if n == 0:\n',
    '        return res\n',
    "    fa = np.array([r['rr_' + a] if r['rr_' + a] is not None else r['rand'] for r in R])\n",
    "    fb = np.array([r['rr_' + b] if r['rr_' + b] is not None else r['rand'] for r in R])\n",
    '    d = fb - fa\n',
    '    idx = _boot_idx(n)\n',
    '    res.update(mrr_a=float(fa.mean()), mrr_b=float(fb.mean()), delta=float(d.mean()),\n',
    '               delta_ci=[float(x) for x in np.percentile(d[idx].mean(1), [2.5, 97.5])],\n',
    '               n_changed=int((np.abs(d) > 1e-9).sum()))\n',
    '    return res\n',
    '\n',
    '\n',
    'def fmt_p(p):\n',
    "    if not p.get('n'):\n",
    '        return f"{p.get(\'label\', \'\')}: {p[\'a\']} vs {p[\'b\']} n=0"\n',
    '    s = (f"{p.get(\'label\', \'\')}: n={p[\'n\']} {p[\'a\']} {p[\'mrr_a\']:.4f} vs {p[\'b\']} {p[\'mrr_b\']:.4f} (rand {p[\'rand\']:.4f}) "\n',
    '         f"delta {p[\'delta\']:+.4f} CI [{p[\'delta_ci\'][0]:+.4f}, {p[\'delta_ci\'][1]:+.4f}] "\n',
    '         f"lift {p[\'lift_a\']:.4f} -> {p[\'lift_b\']:.4f} ratio {p[\'ratio\']:.3f} CI [{p[\'ratio_ci\'][0]:.3f}, {p[\'ratio_ci\'][1]:.3f}] "\n',
    '         f"W/T/L {p[\'wins\']}/{p[\'ties\']}/{p[\'losses\']} sets {p[\'by_set\']}")\n',
    '    return s\n',
    '\n',
    '\n',
    'def gates(rows):\n',
    '    """Roadmap 3.2 gates. N1-NH4 / N1-WL: kill if the proxy lift < 50% of the paired [M+H]+ lift (same molecules).\n',
    '    I14b: adopt only if delta >= +0.01 on merged-CE e180 molecules and >= 0 on np merged-CE molecules."""\n',
    '    g = OrderedDict()\n',
    "    for key, arm in (('N1_NH4', 'B_NH4'), ('N1_WL', 'C_WL')):\n",
    "        p = paired(rows, 'A_H', arm, label=f'{key} paired [M+H]+ vs proxy')\n",
    "        pc = paired(rows, 'A_Hcut', arm, label=f'{key} paired [M+H]+cut vs proxy (diag)')\n",
    "        if not p.get('n'):\n",
    "            v = 'NO DATA'\n",
    "        elif not math.isfinite(p['ratio']):\n",
    "            v = 'UNDEFINED ([M+H]+ lift <= 0)'\n",
    '        else:\n',
    "            v = 'PASS' if p['ratio'] >= 0.5 else 'KILL'\n",
    "        g[key] = dict(verdict=v, rule='proxy lift >= 0.5 x paired [M+H]+ lift', paired=p, paired_cut=pc)\n",
    "    pe = paired(rows, 'A_H', 'D_Hmerged', sel=lambda r: r['set'] == 'e180' and r['has_merged_H'], label='I14b e180 merged-CE')\n",
    "    pn = paired(rows, 'A_H', 'D_Hmerged', sel=lambda r: r['set'] == 'np' and r['has_merged_H'], label='I14b np merged-CE')\n",
    "    if not pe.get('n') or not pn.get('n'):\n",
    "        v = 'NO DATA'\n",
    '    else:\n',
    "        v = 'ADOPT' if (pe['delta'] >= 0.01 and pn['delta'] >= 0.0) else 'REJECT'\n",
    "    g['I14b'] = dict(verdict=v, rule='delta >= +0.01 on e180 merged-CE and >= 0 on np merged-CE', e180=pe, np=pn,\n",
    "                     np_all=paired(rows, 'A_H', 'D_Hmerged', sel=lambda r: r['set'] == 'np', label='I14b np all'),\n",
    "                     e180_all=paired(rows, 'A_H', 'D_Hmerged', sel=lambda r: r['set'] == 'e180', label='I14b e180 all'))\n",
    '    return g\n',
    '\n',
    '\n',
    'def blind_report(rows):\n',
    '    """Molecules with NO real [M+H]+ spectrum (GLACIER-blind in B1): what N1 arm A recovers there."""\n',
    "    B = [r for r in rows if not r['has_H']]\n",
    "    res = OrderedDict(n_blind=len(B), n_blind_np=sum(r['set'] == 'np' for r in B),\n",
    "                      n_blind_with_proxy=sum(r['has_NH4p'] or r['has_WLp'] for r in B),\n",
    "                      n_blind_proxy_covered=sum(r['rr_N1A'] is not None for r in B))\n",
    "    C = [r for r in B if r['rr_N1A'] is not None]\n",
    '    if C:\n',
    "        rr = np.array([r['rr_N1A'] for r in C]); rn = np.array([r['rand'] for r in C])\n",
    '        idx = _boot_idx(len(C))\n',
    '        res.update(mrr_proxy=float(rr.mean()), rand=float(rn.mean()), lift=float((rr - rn).mean()),\n',
    '                   lift_ci=[float(x) for x in np.percentile((rr - rn)[idx].mean(1), [2.5, 97.5])],\n',
    '                   top1=float(np.mean(rr >= 1.0 - 1e-12)),\n',
    "                   by_src={k: int(sum(1 for r in C if r[k])) for k in ('has_NH4p', 'has_WLp')},\n",
    "                   mids=[r['mid'] for r in C])\n",
    "    res['overall_np'] = filled_delta(rows, 'A_H', 'N1A', sel=lambda r: r['set'] == 'np', label='N1A vs A, all np (blind filled with rand)')\n",
    "    res['overall_all'] = filled_delta(rows, 'A_H', 'N1A', label='N1A vs A, all molecules')\n",
    "    res['overall_np_D'] = filled_delta(rows, 'A_H', 'N1A_D', sel=lambda r: r['set'] == 'np', label='N1A+I14b vs A, all np')\n",
    '    return res\n',
    '\n',
    '\n',
    'def score_corr(new, old):\n',
    '    """new / old: {mid: {smiles: score|None}} -> pooled Pearson + mean per-molecule Spearman over common scored."""\n',
    '    xs, ys, sp = [], [], []\n',
    '    for mid, d in new.items():\n',
    '        o = old.get(mid) or {}\n',
    '        pairs = [(v, o.get(s)) for s, v in d.items() if v is not None and o.get(s) is not None]\n',
    '        if len(pairs) < 3:\n',
    '            continue\n',
    '        a = np.array([p[0] for p in pairs]); b = np.array([p[1] for p in pairs])\n',
    '        xs.extend(a); ys.extend(b)\n',
    '        ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))\n',
    '        if ra.std() > 0 and rb.std() > 0:\n',
    '            sp.append(float(np.corrcoef(ra, rb)[0, 1]))\n',
    '    if len(xs) < 3:\n',
    '        return dict(n_mols=0)\n',
    '    return dict(n_mols=len(sp), n_pairs=len(xs), pearson=float(np.corrcoef(xs, ys)[0, 1]),\n',
    "                spearman_mean=float(np.mean(sp)) if sp else float('nan'))\n",
    '\n',
    '\n',
    '# -------------------------------------------------------------------------------------------------- self-test ----\n',
    'def selftest():\n',
    '    """Forced unit tests of the pure functions (run on Kaggle before any GPU work and locally by the build)."""\n',
    '    M = 300.0\n',
    '    nh4 = dict(mz=[100.0, 250.0, 299.5, 300.0, 301.0, 318.03], it=[0.1, 1.0, 0.2, 0.3, 0.4, 0.5], prec=M + NH4_ADD,\n',
    "               adduct='[M+NH4]+', mode='positive', instrument='timsTOF', ce_ev=[20.0], ce_orig='20', ce_units='eV')\n",
    '    p = n1_proxy(nh4)\n',
    "    assert p is not None and p['mz'] == [100.0, 250.0, 299.5] and p['it'] == [0.1, 1.0, 0.2], p\n",
    "    assert abs(p['prec'] - (M + PROTON)) < 1e-9 and p['adduct'] == '[M+H]+' and p['n1_src'] == '[M+NH4]+'\n",
    "    assert p['ce_ev'] == [20.0] and p['instrument'] == 'timsTOF' and nh4['adduct'] == '[M+NH4]+'   # input untouched\n",
    "    wl = dict(nh4, mz=[100.0, 281.4, 281.5, 283.0], it=[1.0, 0.5, 0.5, 0.9], prec=M + PROTON - H2O, adduct='[M-H2O+H]+')\n",
    '    p = n1_proxy(wl)\n',
    "    assert p is not None and p['mz'] == [100.0, 281.4] and abs(p['prec'] - (M + PROTON)) < 1e-9, p\n",
    "    for ad in ('[M+Na]+', '[M+K]+', '[M-2H2O+H]+', '[M+H]+', '[M-H]-'):\n",
    '        assert n1_proxy(dict(nh4, adduct=ad)) is None, ad\n',
    "    assert n1_proxy(dict(nh4, mode='negative')) is None\n",
    '    assert n1_proxy(dict(nh4, mz=[310.0, 315.0], it=[1.0, 1.0])) is None             # nothing below the cut\n',
    '    assert n1_proxy(dict(nh4, mz=[100.0], it=[0.0])) is None                           # no positive intensity\n',
    "    h = dict(nh4, adduct='[M+H]+', prec=M + PROTON, mz=[100.0, 299.5, 299.6, 301.0], it=[1.0, 1.0, 1.0, 1.0])\n",
    '    c = h_cut(h)\n',
    "    assert c is not None and c['mz'] == [100.0, 299.5] and c['prec'] == h['prec'] and c['adduct'] == '[M+H]+', c\n",
    '    assert h_cut(nh4) is None\n',
    "    items = [dict(mid='np:X', cands=['A', 'B'], spectra=[h, nh4, wl, dict(h, mode='negative', adduct='[M-H]-'),\n",
    "                                                        dict(h, adduct='[M+Na]+'), dict(h, adduct='[M+K]+')])]\n",
    '    v, st = build_variants(items)\n',
    "    assert [s['sid'] for s in v[0]['spectra']] == ['0:H', '0:Hcut', '1:NH4p', '2:WLp', '4:Na'], v\n",
    '    assert st == dict(H=1, Hcut=1, NH4p=1, WLp=1, Na=1), st\n',
    '    # random tie-break expected RR\n',
    '    assert abs(rr_random_tb([0.5, 0.9, 0.5, 0.1]) - (1 / 2 + 1 / 3) / 2) < 1e-12\n',
    '    assert rr_random_tb([None, 0.2, 0.1]) is None and rr_random_tb([0.2, None, 0.1]) == 1.0\n',
    '    assert abs(rr_random_tb([0.0, 0.0, 0.0, 0.0]) - rr_rand(4)) < 1e-12\n',
    '    assert rr_truth_first([0.0, 0.0, 0.0, 0.0]) == 1.0 and abs(rr_split([0.0, 0.0, 0.0]) - 0.5) < 1e-12\n',
    '    assert abs(rr_rand(3) - (1 + 0.5 + 1 / 3) / 3) < 1e-12\n',
    '    assert covered([0.1, None, 0.2]) and not covered([0.1, None]) and not covered([None, 0.1, 0.2])\n',
    "    # aggregation: mean over the arm's spectra, None-aware; N1A tag resolution\n",
    "    mo = {'cands': ['A', 'B', 'C'], 'spec': {\n",
    "        '0:H': dict(tag='H', nb=3, mean=[0.2, 0.4, None], merged=[0.3, 0.1, None]),\n",
    "        '1:H': dict(tag='H', nb=1, mean=[0.4, None, None], merged=[0.4, None, None]),\n",
    "        '2:NH4p': dict(tag='NH4p', nb=1, mean=[0.9, 0.1, 0.5], merged=[0.9, 0.1, 0.5])}}\n",
    "    am = arm_scores(mo, ('H',), 'mean')\n",
    '    assert len(am) == 3 and np.allclose(am[:2], [0.3, 0.4]) and am[2] is None, am\n',
    "    assert np.allclose(arm_scores(mo, ('H',), 'merged')[:2], [0.35, 0.1])\n",
    "    assert arm_tags('N1A', dict(has_H=True)) == (('H',), 'mean')\n",
    "    assert arm_tags('N1A', dict(has_H=False)) == (('NH4p', 'WLp'), 'mean')\n",
    "    assert arm_tags('N1A_D', dict(has_H=False)) == (('NH4p', 'WLp'), 'merged')\n",
    '    # end-to-end on two synthetic molecules\n',
    "    its = [dict(mid='np:X', cands=['A', 'B', 'C'], spectra=[dict(tag='H'), dict(tag='NH4p')]),\n",
    "           dict(mid='np:Y', cands=['A', 'B', 'C'], spectra=[dict(tag='NH4p')]),\n",
    "           dict(mid='e180:Z', cands=['A', 'B'], spectra=[dict(tag='H')])]\n",
    "    out = {'np:X': mo, 'np:Y': {'cands': ['A', 'B', 'C'], 'spec': {'0:NH4p': dict(tag='NH4p', nb=1, mean=[0.1, 0.5, 0.0], merged=[0.1, 0.5, 0.0])}}}\n",
    "    rows = molecule_table(its, out, done={'np:X', 'np:Y'})\n",
    "    assert [r['mid'] for r in rows] == ['np:X', 'np:Y']\n",
    '    x, y = rows\n',
    "    assert abs(x['rr_A_H'] - 0.5) < 1e-12 and x['rr_B_NH4'] == 1.0 and x['rr_N1A'] == x['rr_A_H'] and x['has_merged_H']\n",
    "    assert y['rr_A_H'] is None and abs(y['rr_N1A'] - 0.5) < 1e-12 and not y['has_H']\n",
    "    p = paired(rows, 'A_H', 'B_NH4')\n",
    "    assert p['n'] == 1 and abs(p['delta'] - 0.5) < 1e-12\n",
    "    f = filled_delta(rows, 'A_H', 'N1A')\n",
    "    assert f['n'] == 2 and abs(f['delta'] - (0.5 - rr_rand(3)) / 2) < 1e-12\n",
    '    g = gates(rows)                                          # A lift < 0 here (0.5 vs rand 0.611)\n',
    "    assert g['N1_NH4']['verdict'].startswith('UNDEFINED') and g['N1_WL']['verdict'] == 'NO DATA', g['N1_NH4']['verdict']\n",
    "    assert g['I14b']['verdict'] == 'NO DATA'\n",
    '\n',
    '    def row(s, a, b, d, mh=True):\n',
    "        return dict(mid=f'{s}:{a}{b}{d}', set=s, rand=0.2, rr_A_H=a, rr_B_NH4=b, rr_A_Hcut=None, rr_C_WL=None,\n",
    '                    rr_D_Hmerged=d, has_merged_H=mh)\n',
    "    gk = gates([row('np', 1.0, 0.5, 1.0), row('np', 0.6, 0.4, 0.6), row('e180', 1.0, None, 1.0)])   # ratio 0.25/0.6\n",
    "    assert gk['N1_NH4']['verdict'] == 'KILL' and abs(gk['N1_NH4']['paired']['ratio'] - 0.25 / 0.6) < 1e-12\n",
    "    assert gk['I14b']['verdict'] == 'REJECT' and gk['I14b']['e180']['delta'] == 0.0      # +0.01 needed on e180\n",
    "    gp = gates([row('np', 1.0, 0.9, 1.0), row('np', 0.6, 0.6, 0.5), row('e180', 0.5, None, 1.0)])   # ratio 1.1/1.2\n",
    "    assert gp['N1_NH4']['verdict'] == 'PASS' and gp['I14b']['verdict'] == 'REJECT'          # np merged delta < 0\n",
    "    ga = gates([row('np', 0.5, 0.5, 0.5), row('e180', 0.5, None, 0.52)])\n",
    "    assert ga['I14b']['verdict'] == 'ADOPT' and abs(ga['I14b']['e180']['delta'] - 0.02) < 1e-12\n",
    '    b = blind_report(rows)\n',
    "    assert b['n_blind'] == 1 and b['n_blind_proxy_covered'] == 1\n",
    "    sc = score_corr({'m': {'a': 1.0, 'b': 2.0, 'c': 3.0}}, {'m': {'a': 2.0, 'b': 4.0, 'c': 6.5}})\n",
    "    assert sc['n_mols'] == 1 and sc['pearson'] > 0.99 and abs(sc['spearman_mean'] - 1.0) < 1e-12\n",
    "    return 'glb_core selftest ok (proxy NH4/WL/Hcut, variants, random tie-break RR, aggregation, paired, gates, blind)'\n",
])
# kdev_glbench_n1 glb_driver.py, verbatim (GLACIER driver: mean + merged-CE per spectrum, own process)
N1_DRIVER_SRC = ''.join([
    '#!/usr/bin/env python\n',
    '"""casmi26 kdev_glbench_n1 -- GLACIER bench driver (runs in its OWN process, like gl_runner.py).\n',
    '\n',
    'Imports the attached casmi26-glacier gl_runner.py as a module and reuses ITS environment setup (offline wheel site,\n',
    'shims, RDKit 2025.03 check), model loading, batched Predictor (canonical-SMILES dedupe, OOM split, fail-fast), query\n',
    "cleaning, CE bucketing, summed-CE merge() and entropy similarity. The 'mean' mode calls gl_runner.score_molecule on\n",
    "one spectrum at a time, so a molecule's mean over its [M+H]+ spectra is exactly the production gl_ex_mean.\n",
    "Added: per-spectrum output, and the I14b 'merged' mode (a merged-CE eV spectrum = >= 2 distinct CE buckets is\n",
    'predicted at each bucket and the predictions are merge()d like the SUM_CE path; single-CE / NCE / no-CE spectra:\n',
    'merged = mean).\n',
    '\n',
    'usage: python glb_driver.py <gl_pkg> <in.json> <out.json> [--device cuda] [--budget S] [--site DIR] [--wheels DIR]\n',
    '                            [--bs 32] [--chunk-jobs 3000] [--fake]\n',
    'in.json : [{"mid", "cands": [smiles], "spectra": [{"sid", "tag", "mz", "it", "prec", "adduct", "mode", "instrument",\n',
    '            "ce_ev", "ce_orig", "ce_units"}]}]\n',
    'out.json: {mid: {"cands": [smiles], "spec": {sid: {"tag", "nb", "mean": [sim|null], "merged": [sim|null]}}}}\n',
    '          (lists aligned with "cands"; null = rejected SMILES / failed prediction)\n',
    'out.json.meta.json: status, counts, timings, versions, errors, "done" = molecules fully scored (input order).\n',
    '--fake: no torch / model / wheel site (local dry run): deterministic pseudo-random predictions, SMILES accepted as is.\n',
    '"""\n',
    'import os, sys, json, time, math, argparse, traceback, hashlib, importlib.util\n',
    '\n',
    'sys.dont_write_bytecode = True\n',
    "NEED = ('setup_env', 'load_model', 'Predictor', 'smiles_ok', '_CANON', 'molecule_jobs', 'score_molecule',\n",
    "        'prep_spectrum', 'prep_query', 'entropy_sim', 'merge', 'post', 'ce_bucket', 'spectrum_ce', 'is_covered',\n",
    "        'instr_token', 'SUM_CE', 'FLOOR', 'TOPK', 'POWER', 'ENTW', 'TOL', 'PPM', 'write_json', 'Log')\n",
    '\n',
    '\n',
    'def sha256(path):\n',
    '    h = hashlib.sha256()\n',
    "    with open(path, 'rb') as f:\n",
    "        for b in iter(lambda: f.read(1 << 20), b''):\n",
    '            h.update(b)\n',
    '    return h.hexdigest()\n',
    '\n',
    '\n',
    'def load_gl(pkg):\n',
    '    """gl_runner.py of the package as a module (no side effects beyond its imports: numpy, numba)."""\n',
    "    spec = importlib.util.spec_from_file_location('gl_runner', os.path.join(pkg, 'gl_runner.py'))\n",
    '    G = importlib.util.module_from_spec(spec)\n',
    "    sys.modules['gl_runner'] = G\n",
    '    spec.loader.exec_module(G)\n',
    '    miss = [n for n in NEED if not hasattr(G, n)]\n',
    '    if miss:\n',
    "        raise RuntimeError(f'gl_runner API differs from the one this driver was written for: missing {miss}')\n",
    '    return G\n',
    '\n',
    '\n',
    '# ------------------------------------------------------------------------------------------- per-spectrum plan ----\n',
    'def merged_buckets(G, sp):\n',
    '    """I14b: sorted distinct CE buckets of a merged-CE eV spectrum when there are >= 2, else None."""\n',
    "    if sp.get('ce_units') == 'NCE':\n",
    '        return None\n',
    '    b = set()\n',
    "    for x in sp.get('ce_ev') or []:\n",
    '        try:\n',
    '            x = float(x)\n',
    '        except (TypeError, ValueError):\n',
    '            continue\n',
    '        if math.isfinite(x):\n',
    '            cb = G.ce_bucket(x)\n',
    '            if math.isfinite(cb):\n',
    '                b.add(float(cb))\n',
    '    return sorted(b) if len(b) >= 2 else None\n',
    '\n',
    '\n',
    'def spec_plan(G, sp):\n',
    '    """None if gl_runner would not score this spectrum, else {\'entry\': molecule_plan entry, \'mb\': buckets|None}."""\n',
    '    if not G.is_covered(sp):\n',
    '        return None\n',
    '    qm, qp = G.prep_spectrum(sp)\n',
    "    return dict(entry=(qm, qp, sp['adduct'], G.instr_token(sp), G.ce_bucket(G.spectrum_ce(sp))), mb=merged_buckets(G, sp))\n",
    '\n',
    '\n',
    'def spec_jobs(G, plan, cands):\n',
    "    J = set(G.molecule_jobs([plan['entry']], cands))\n",
    "    if plan['mb']:\n",
    "        _, _, ad, ins, _ = plan['entry']\n",
    '        for c in cands:\n',
    "            for b in plan['mb']:\n",
    '                J.add((c, ad, ins, b))\n',
    '    return J\n',
    '\n',
    '\n',
    'def spec_scores(G, plan, cands, cache):\n',
    '    """-> (mean {c: sim|None}, merged {c: sim|None}, n_buckets)."""\n',
    "    mean = G.score_molecule([plan['entry']], cands, cache)\n",
    "    if not plan['mb']:\n",
    '        return mean, dict(mean), 1\n',
    "    qm, qp, ad, ins, _ = plan['entry']\n",
    '    merged = {}\n',
    '    for c in cands:\n',
    "        parts = [cache.get((c, ad, ins, b)) for b in plan['mb']]\n",
    '        if any(p is None for p in parts):            # = the SUM_CE path: every component must be predicted\n',
    '            merged[c] = None\n',
    '            continue\n',
    '        pr = G.merge(parts)\n',
    '        pm, pp = G.prep_query(pr[0], pr[1], G.FLOOR, G.TOPK, G.POWER, G.ENTW)\n',
    '        s = float(G.entropy_sim(qm, qp, pm, pp, G.TOL, G.PPM))\n',
    '        merged[c] = s if math.isfinite(s) else None\n',
    "    return mean, merged, len(plan['mb'])\n",
    '\n',
    '\n',
    '# ------------------------------------------------------------------------------------------------ fake mode ------\n',
    'class FakePredictor:\n',
    '    """Same interface as gl_runner.Predictor (predict(jobs, deadline) -> bool, .cache); deterministic random peaks."""\n',
    '\n',
    '    def __init__(self, G):\n',
    '        self.G, self.cache = G, {}\n',
    '        self.n_pred = self.n_fail = self.n_feat_fail = 0\n',
    '        self.t_pred, self.bs = 0.0, 0\n',
    '\n',
    '    def predict(self, jobs, deadline):\n',
    '        import numpy as np\n',
    '        t0 = time.time()\n',
    '        for j in sorted(jobs):\n',
    '            if j in self.cache:\n',
    '                continue\n',
    '            if time.time() > deadline:\n',
    '                self.t_pred += time.time() - t0\n',
    '                return False\n',
    '            c = self.G._CANON.get(j[0], (None,))[0]\n',
    '            if c is None:\n',
    '                self.cache[j] = None\n',
    '                continue\n',
    '            r = np.random.default_rng(int(hashlib.md5(repr((c, j[1], j[2], float(j[3]))).encode()).hexdigest()[:8], 16))\n',
    '            mz = np.round(r.uniform(40.0, 400.0, 25), 2)\n',
    '            o = self.G.post(np.stack([mz, r.uniform(0.05, 1.0, 25)], 1).astype(np.float32))\n',
    '            self.cache[j] = (o[0].astype(np.float64), o[1].astype(np.float64))\n',
    '            self.n_pred += 1\n',
    '        self.t_pred += time.time() - t0\n',
    '        return True\n',
    '\n',
    '\n',
    'def fake_smiles_ok(G):\n',
    '    def ok(smi):\n',
    '        good = isinstance(smi, str) and bool(smi)\n',
    "        G._CANON[smi] = (smi if good else None, max(1, len(smi) // 2) if good else 0, '' if good else 'empty')\n",
    "        return good, ('' if good else 'empty')\n",
    '    return ok\n',
    '\n',
    '\n',
    '# ------------------------------------------------------------------------------------------------- self-test -----\n',
    'def selftest(G):\n',
    '    """Forced unit test of the merged-CE logic on a synthetic cache (no model); run by the notebook before the GPU\n',
    '    job and by the local build."""\n',
    '    import numpy as np\n',
    "    sp = dict(mz=[50.0, 80.0, 120.0, 150.5], it=[0.2, 1.0, 0.5, 0.3], prec=151.0, adduct='[M+H]+', mode='positive',\n",
    "              instrument='timsTOF', ce_ev=[20.0, 40.0, 60.0], ce_orig='20,40,60', ce_units='eV')\n",
    '    p = spec_plan(G, sp)\n',
    "    assert p is not None and p['mb'] == [20.0, 40.0, 60.0], p\n",
    "    assert p['entry'][2:] == ('[M+H]+', 'QTOF', 40.0), p['entry'][2:]\n",
    "    cands = ['CCO', 'CCC']\n",
    '    J = spec_jobs(G, p, cands)\n',
    "    assert J == {(c, '[M+H]+', 'QTOF', b) for c in cands for b in (20.0, 40.0, 60.0)}, J\n",
    '    rng = np.random.default_rng(0)\n',
    '    cache = {}\n',
    '    for j in sorted(J):\n',
    '        mz = np.sort(rng.choice([50.0, 80.0, 120.0, 150.5, 60.0, 99.0], 4, replace=False))\n',
    '        cache[j] = (mz.astype(np.float64), rng.uniform(0.1, 1.0, 4).astype(np.float64))\n',
    "    cache[('CCC', '[M+H]+', 'QTOF', 60.0)] = None\n",
    '    mean, merged, nb = spec_scores(G, p, cands, cache)\n',
    "    assert nb == 3 and merged['CCC'] is None and mean['CCC'] is not None and mean['CCO'] is not None, (mean, merged)\n",
    "    pr = G.merge([cache[('CCO', '[M+H]+', 'QTOF', b)] for b in (20.0, 40.0, 60.0)])\n",
    '    qm, qp = G.prep_spectrum(sp)\n',
    '    pm, pp = G.prep_query(pr[0], pr[1], G.FLOOR, G.TOPK, G.POWER, G.ENTW)\n',
    "    assert abs(merged['CCO'] - float(G.entropy_sim(qm, qp, pm, pp, G.TOL, G.PPM))) < 1e-12\n",
    "    pm, pp = G.prep_query(*cache[('CCO', '[M+H]+', 'QTOF', 40.0)], G.FLOOR, G.TOPK, G.POWER, G.ENTW)\n",
    "    assert abs(mean['CCO'] - float(G.entropy_sim(qm, qp, pm, pp, G.TOL, G.PPM))) < 1e-12\n",
    '    p1 = spec_plan(G, dict(sp, ce_ev=[40.0]))                         # single CE: merged == mean\n',
    '    m1, g1, n1 = spec_scores(G, p1, cands, cache)\n',
    "    assert p1['mb'] is None and n1 == 1 and m1 == g1 and abs(m1['CCO'] - mean['CCO']) < 1e-12\n",
    '    assert merged_buckets(G, dict(sp, ce_ev=[20.0, 21.0])) is None    # same bucket twice\n',
    '    assert merged_buckets(G, dict(sp, ce_ev=[0.0, 20.0])) == [5.0, 20.0]\n',
    "    assert merged_buckets(G, dict(sp, ce_units='NCE', ce_orig='20,40')) is None\n",
    '    assert merged_buckets(G, dict(sp, ce_ev=[])) is None\n',
    "    assert spec_plan(G, dict(sp, adduct='[M+NH4]+')) is None and spec_plan(G, dict(sp, mode='negative')) is None\n",
    '    pn = spec_plan(G, dict(sp, ce_ev=[]))                              # no CE: SUM_CE jobs, merged == mean\n',
    "    assert pn['mb'] is None and spec_jobs(G, pn, ['CCO']) == {('CCO', '[M+H]+', 'QTOF', c) for c in G.SUM_CE}\n",
    "    return 'glb_driver selftest ok (merged-CE buckets, jobs, merge == SUM_CE path, single-CE identity, coverage)'\n",
    '\n',
    '\n',
    '# ------------------------------------------------------------------------------------------------------ main -----\n',
    'def parse(argv=None):\n',
    '    ap = argparse.ArgumentParser()\n',
    "    ap.add_argument('pkg'); ap.add_argument('inp'); ap.add_argument('out')\n",
    "    ap.add_argument('--device', default='cuda')\n",
    "    ap.add_argument('--budget', type=float, default=0.0)\n",
    "    ap.add_argument('--site', default='/tmp/glb_site')\n",
    "    ap.add_argument('--wheels', default=None)\n",
    "    ap.add_argument('--bs', type=int, default=32)\n",
    "    ap.add_argument('--chunk-jobs', type=int, default=3000)\n",
    "    ap.add_argument('--fake', action='store_true')\n",
    '    return ap.parse_args(argv)\n',
    '\n',
    '\n',
    'def main(argv=None):\n',
    '    a = parse(argv)\n',
    '    if not a.fake:\n',
    "        os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')   # = gl_runner.main (deterministic torch)\n",
    '    t_start = time.time()\n',
    "    deadline = t_start + a.budget if a.budget > 0 else float('inf')\n",
    "    meta = dict(model='glacier-bench', status='init', fake=a.fake, n_mols=0, n_mols_done=0, n_spec=0, n_spec_covered=0,\n",
    '                n_spec_merged=0, n_jobs=0, errors=[], done=[])\n',
    '    G = None\n',
    '    result = {}\n',
    '\n',
    '    def write(status=None):\n',
    '        if status:\n',
    "            meta['status'] = status\n",
    "        meta['seconds'] = round(time.time() - t_start, 2)\n",
    "        tmp = a.out + '.tmp'\n",
    "        with open(tmp, 'w') as f:\n",
    '            json.dump(result, f, allow_nan=False)\n',
    '        os.replace(tmp, a.out)\n',
    "        with open(a.out + '.meta.json.tmp', 'w') as f:          # atomic too: a kill mid-write never leaves bad JSON\n",
    '            json.dump(meta, f, allow_nan=False)\n',
    "        os.replace(a.out + '.meta.json.tmp', a.out + '.meta.json')\n",
    '\n',
    '    def log(*x):\n',
    "        print(f'[glb {time.time() - t_start:7.1f}s]', *x, file=sys.stderr, flush=True)\n",
    '\n',
    '    try:\n',
    '        mols = json.load(open(a.inp))\n',
    "        meta['n_mols'] = len(mols)\n",
    '        write()\n',
    '        G = load_gl(a.pkg)\n',
    "        meta['gl_runner_sha256'] = sha256(os.path.join(a.pkg, 'gl_runner.py'))\n",
    '        if a.fake:\n',
    "            meta['rdkit'] = 'fake'\n",
    '            G.smiles_ok = fake_smiles_ok(G)\n',
    '            pred = FakePredictor(G)\n',
    "            log('FAKE mode: pseudo-random predictions, no model')\n",
    '        else:\n',
    '            ns = argparse.Namespace(pkg=a.pkg, site=a.site, wheels=a.wheels, any_rdkit=False)\n',
    "            meta['rdkit'] = G.setup_env(ns, log)\n",
    '            import torch\n',
    "            meta['torch'] = torch.__version__\n",
    '            dev = a.device\n',
    "            if dev.startswith('cuda') and not torch.cuda.is_available():\n",
    "                log('cuda unavailable -> cpu'); dev = 'cpu'\n",
    "            meta['device'] = dev\n",
    '            torch.use_deterministic_algorithms(True, warn_only=True)\n',
    '            torch.backends.cudnn.benchmark = False\n',
    '            model = G.load_model(os.path.abspath(a.pkg), dev, log)\n',
    '            pred = G.Predictor(model, dev, a.bs, log)\n',
    '            log(f\'model loaded on {dev} (rdkit {meta["rdkit"]}, torch {torch.__version__}, numba {G.HAVE_NUMBA})\')\n',
    "        meta['t_load'] = round(time.time() - t_start, 2)\n",
    '        okc = {}\n',
    '        chunk, chunk_jobs = [], set()\n',
    '\n',
    '        def flush():\n',
    '            nonlocal chunk, chunk_jobs\n',
    '            if not chunk:\n',
    '                return True\n',
    '            t0 = time.time()\n',
    '            if not pred.predict(chunk_jobs, deadline):\n',
    '                return False\n',
    '            for mid, cands, plans in chunk:\n',
    '                spec = {}\n',
    '                for sid, tag, pl in plans:\n',
    '                    try:\n',
    '                        mean, merged, nb = spec_scores(G, pl, cands, pred.cache)\n',
    '                    except Exception as e:\n',
    "                        meta['errors'].append(f'{mid} {sid}: score {repr(e)[:200]}')\n",
    '                        continue\n',
    "                    spec[sid] = dict(tag=tag, nb=nb, mean=[mean.get(c) for c in result[mid]['cands']],\n",
    "                                     merged=[merged.get(c) for c in result[mid]['cands']])\n",
    "                result[mid]['spec'] = spec\n",
    "                meta['done'].append(mid)\n",
    "            meta['n_mols_done'] = len(meta['done'])\n",
    '            write()\n',
    "            log(f'chunk: {len(chunk)} mols {len(chunk_jobs)} jobs {time.time() - t0:.1f}s '\n",
    '                f\'({meta["n_mols_done"]}/{meta["n_mols"]} mols done, {pred.n_pred} predictions)\')\n',
    '            chunk, chunk_jobs = [], set()\n',
    '            return True\n',
    '\n',
    '        stopped = False\n',
    '        for mol in mols:\n',
    "            mid = str(mol['mid'])\n",
    "            allc = list(dict.fromkeys(mol.get('cands') or []))\n",
    '            result[mid] = dict(cands=allc, spec={})\n',
    '            for c in allc:\n',
    '                if c not in okc:\n',
    '                    okc[c], why = G.smiles_ok(c)\n',
    '                    if not okc[c] and sum(1 for v in okc.values() if not v) <= 5:\n',
    "                        meta['errors'].append(f'smiles rejected ({why}): {str(c)[:100]}')\n",
    '            cands = [c for c in allc if okc[c]]\n',
    '            plans = []\n',
    "            for sp in mol.get('spectra') or []:\n",
    "                meta['n_spec'] += 1\n",
    '                try:\n',
    '                    pl = spec_plan(G, sp)\n',
    '                except Exception as e:\n',
    '                    meta[\'errors\'].append(f\'{mid} {sp.get("sid")}: plan {repr(e)[:200]}\')\n',
    '                    continue\n',
    '                if pl is None:\n',
    '                    continue\n',
    "                meta['n_spec_covered'] += 1\n",
    "                meta['n_spec_merged'] += int(bool(pl['mb']))\n",
    "                plans.append((sp['sid'], sp.get('tag'), pl))\n",
    '            if not cands or not plans:\n',
    "                meta['done'].append(mid)                         # nothing GLACIER could score: done, empty\n",
    '                continue\n',
    '            J = set()\n',
    '            for _, _, pl in plans:\n',
    '                J |= spec_jobs(G, pl, cands)\n',
    "            meta['n_jobs'] += len(J)\n",
    '            chunk.append((mid, cands, plans))\n',
    '            chunk_jobs |= J\n',
    '            if len(chunk_jobs) >= a.chunk_jobs and not flush():\n',
    '                stopped = True\n',
    '                break\n',
    '        if not stopped and not flush():\n',
    '            stopped = True\n',
    '        meta.update(n_pred=pred.n_pred, n_pred_fail=pred.n_fail, n_feat_fail=pred.n_feat_fail, t_pred=round(pred.t_pred, 2),\n',
    '                    pred_per_s=round(pred.n_pred / max(pred.t_pred, 1e-9), 2), bs_final=pred.bs,\n',
    "                    n_bad_smiles=sum(1 for v in okc.values() if not v), n_mols_done=len(meta['done']))\n",
    "        if not a.fake and meta.get('device', '').startswith('cuda'):\n",
    '            import torch\n',
    "            meta['max_mem_gb'] = round(torch.cuda.max_memory_allocated() / 2 ** 30, 2)\n",
    "        write('budget' if stopped else 'ok')\n",
    "        log('status', meta['status'], {k: meta[k] for k in ('n_mols', 'n_mols_done', 'n_spec_covered', 'n_spec_merged',\n",
    "                                                            'n_pred', 'n_pred_fail', 'pred_per_s')})\n",
    '        return 0\n',
    '    except BaseException as e:                                   # never crash the notebook: status error + partial out\n',
    "        meta['errors'].append(traceback.format_exc()[-3000:])\n",
    "        log('ERROR', repr(e)[:300])\n",
    '        try:\n',
    "            write('error')\n",
    '        except Exception:\n',
    '            return 2\n',
    '        return 0\n',
    '\n',
    '\n',
    "if __name__ == '__main__':\n",
    '    sys.exit(main())\n',
])


def _n1_mod(name, path):
    import importlib.util as _iu
    spec = _iu.spec_from_file_location(name, path)
    mod = _iu.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def n1_select(items_all, K):
    """N1 arm A (bench glb_core) on fuse.build_ice_input(..., covered_only=False) items -> (driver items, counts):
    the molecules WITHOUT a real positive [M+H]+ spectrum that have >= 1 [M+NH4]+ / [M-H2O+H]+ proxy, carrying only
    those proxies (bench tags NH4p / WLp, sid '<spectrum index>:<tag>'), in input (= GLACIER priority) order."""
    var, _ = K.build_variants(items_all)
    raw = {str(it['mid']): sum(1 for s in it.get('spectra') or [] if s.get('mode') == 'positive'
                               and s.get('adduct') in K.PROXY_TAG) for it in items_all}
    out = []
    st = dict(molecules=0, with_H=0, blind=0, blind_nh4_wl=0, n1=0, proxies=0, NH4p=0, WLp=0, proxy_empty=0)
    for it in var:
        fl = K.mol_flags(it)
        st['molecules'] += 1
        if fl['has_H']:                  # arm A: a real [M+H]+ exists -> the H1 run above scores this molecule
            st['with_H'] += 1
            continue
        st['blind'] += 1
        tags, _mode = K.arm_tags(N1_ARM, fl)
        sps = [s for s in it['spectra'] if s.get('tag') in tags]
        st['blind_nh4_wl'] += int(raw.get(it['mid'], 0) > 0)
        st['proxy_empty'] += raw.get(it['mid'], 0) - len(sps)
        if not sps or not it['cands']:
            continue
        st['n1'] += 1
        st['proxies'] += len(sps)
        for s in sps:
            st[s['tag']] += 1
        out.append(dict(mid=it['mid'], cands=list(it['cands']), spectra=sps))
    return out, st


def n1_run(items, budget):
    """The bench glb_driver.py in its own process (= gl_fuse.run_gl pattern) -> (out, meta, done). Never raises for a
    driver failure: the driver checkpoints after every chunk, so a budget stop / crash / kill keeps the molecules it
    finished; unreadable output -> nothing done."""
    fin, fout = os.path.join(N1_WORK, 'n1_in.json'), os.path.join(N1_WORK, 'n1_out.json')
    for f in (fout, fout + '.meta.json'):
        if os.path.exists(f):
            os.remove(f)
    with open(fin, 'w') as f:
        json.dump(items, f)
    cmd = [sys.executable, os.path.join(N1_WORK, 'glb_driver.py'), GL_PKG, fin, fout, '--device', N1_DEVICE,
           '--budget', str(float(budget)), '--site', N1_SITE, '--wheels', os.path.join(ICE_PKG, 'wheels')] + list(N1_DRIVER_EXTRA)
    t0 = time.time()
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace',
                           timeout=float(budget) + 600)
        tail = (r.stdout or '')[-3000:]
    except subprocess.TimeoutExpired as e:
        tail = f'TIMEOUT after {time.time() - t0:.0f}s ' + (e.stdout.decode(errors='replace') if isinstance(e.stdout, bytes)
                                                            else str(e.stdout or ''))[-2000:]
    print(tail, flush=True)
    meta, out = {}, {}
    try:
        with open(fout + '.meta.json') as f:
            meta = json.load(f)
    except Exception as e:
        print('[N1] driver meta unreadable:', repr(e), flush=True)
    try:
        with open(fout) as f:
            out = json.load(f)
    except Exception as e:
        print('[N1] driver output unreadable:', repr(e), flush=True)
    done = set(meta.get('done') or []) if meta else {m for m, v in out.items() if isinstance(v, dict) and v.get('spec')}
    return out, meta, done


def n1_scores(out, done, items, K, mode=None):
    """Driver output -> {mid: {smiles: score | None}} = bench arm_scores of N1_ARM (mean over the molecule's proxy
    spectra of the per-spectrum similarity in the arm's CE mode, or `mode`); finished molecules only, candidate order
    as sent; non-finite / outside [0, 1] -> None; molecules without any score are left out."""
    tags, amode = K.arm_tags(N1_ARM, dict(has_H=False))
    res = {}
    for it in items:
        mid = str(it['mid'])
        mo = out.get(mid)
        if mid not in done or not isinstance(mo, dict):
            continue
        cands = [str(c) for c in mo.get('cands') or []]
        if cands != [str(c) for c in dict.fromkeys(it['cands'])]:
            print('[N1] candidate order changed -> molecule dropped', mid, flush=True)
            continue
        d = {}
        for c, x in zip(cands, K.arm_scores(mo, tags, mode or amode)):
            d[c] = float(x) if x is not None and math.isfinite(x) and -1e-9 <= x <= 1.0 + 1e-9 else None
        if any(x is not None for x in d.values()):
            res[mid] = d
    return res


def n1_synthetic_te(te_df, mids, K):
    """Commit-only forced exercise input: for every molecule in `mids` with a positive [M+H]+ spectrum a copy
    'n1x:<mid>' WITHOUT any [M+H]+: each positive [M+H]+ row -> an [M+NH4]+ row (precursor + 18.033823 - 1.007276,
    plus an injected peak AT the NH4 precursor that the proxy cut must drop); the first one also -> an [M-H2O+H]+ row
    (precursor - 18.010565, peaks unchanged); original NH4 / water-loss rows are left out; every other row (negative,
    Na, K, 2M, ...) is copied unchanged and must never be proxied.
    -> (DataFrame, {xmid: [(kind, original [M+H]+ precursor, mz list, intensity list) per row]})"""
    rows, ref = [], {}
    want = {str(m) for m in mids}
    for mid, sub in te_df.groupby(te_df.molecule_id.astype(str), sort=False):
        if mid not in want:
            continue
        recs = sub.to_dict('records')
        if not any(r.get('ionization_mode') == 'positive' and r.get('adduct') == '[M+H]+' for r in recs):
            continue
        xm, first, rf = f'n1x:{mid}', True, []
        for r in recs:
            r = dict(r, molecule_id=xm)
            if r.get('ionization_mode') == 'positive' and r.get('adduct') == '[M+H]+':
                prec = float(r['precursor_mz'])
                mz = [float(x) for x in r['ms2_mzs']]
                it = [float(x) for x in r['ms2_normalized_intensities']]
                if first:
                    rows.append(dict(r, adduct='[M-H2O+H]+', precursor_mz=prec - K.H2O, ms2_mzs=np.asarray(mz),
                                     ms2_normalized_intensities=np.asarray(it)))
                    rf.append(('WL', prec, mz, it))
                    first = False
                p2 = prec - K.PROTON + K.NH4_ADD
                rows.append(dict(r, adduct='[M+NH4]+', precursor_mz=p2, ms2_mzs=np.asarray(mz + [p2]),
                                 ms2_normalized_intensities=np.asarray(it + [1.0])))
                rf.append(('NH4', prec, mz, it))
            elif r.get('ionization_mode') == 'positive' and r.get('adduct') in K.PROXY_TAG:
                continue                 # an original NH4 / water-loss row: left out, so every proxy traces to a converted row
            else:
                rows.append(r)
                rf.append(('keep', None, None, None))
        ref[xm] = rf
    return pd.DataFrame(rows), ref


def n1_check_proxies(x_items, ref, K):
    """Commit asserts on the synthetic proxies: relabel, precursor back at the original [M+H]+ m/z (< 1e-6 Da), cut =
    exactly the original peaks below the bench cut (injected NH4 precursor peak gone), one proxy per converted row."""
    n = 0
    for it in x_items:
        rf = ref[it['mid']]
        for s in it['spectra']:
            j, tag = s['sid'].split(':')
            kind, prec0, mz0, it0 = rf[int(j)]
            assert (tag, kind) in (('NH4p', 'NH4'), ('WLp', 'WL')), (it['mid'], s['sid'], kind)
            assert s['adduct'] == '[M+H]+' and s['mode'] == 'positive' and s['n1_src'] == (
                '[M+NH4]+' if kind == 'NH4' else '[M-H2O+H]+'), (it['mid'], s['sid'])
            assert abs(float(s['prec']) - prec0) < 1e-6, (it['mid'], s['sid'], s['prec'], prec0)
            if kind == 'NH4':
                p2 = prec0 - K.PROTON + K.NH4_ADD
                cut = (p2 - K.NH4_ADD) + K.PROTON - K.CUT_DA
            else:
                cut = (prec0 - K.H2O) - K.CUT_DA
            keep = [(m, i) for m, i in zip(mz0, it0) if m < cut]
            assert s['mz'] == [m for m, _ in keep] and s['it'] == [i for _, i in keep], (it['mid'], s['sid'])
            assert max(s['mz']) < float(s['prec']) - K.CUT_DA + 1e-6, (it['mid'], s['sid'])
            n += 1
        assert {s['tag'] for s in it['spectra']} <= {'NH4p', 'WLp'}, it['mid']
    return n


def _n1_spearman(a, b):
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    ra, rb = np.argsort(np.argsort(a)), np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1]) if ra.std() > 0 and rb.std() > 0 else float('nan')


def n1_ice_finite(ice):
    """Number of finite ICEBERG scores in one molecule's ICE dict (None / NaN / inf / non-numeric = no evidence; the
    per-value test of fuse.rerank and of E006's _finite_coverage)."""
    import math as _m
    n = 0
    for v in (ice.values() if isinstance(ice, dict) else ()):
        try:
            n += v is not None and _m.isfinite(float(v))
        except (TypeError, ValueError):
            pass
    return n


def n1_complement(scores, ice_scores):
    """k2 variant A: drop the N1 GL scores of the molecules whose ICE dict (ice_scores[str(mid)]) holds a finite
    score -> (kept {mid: same score dict}, dropped {mid}). Kept dicts are passed through unchanged."""
    ice_scores = ice_scores if isinstance(ice_scores, dict) else {}
    drop = {m for m in scores if n1_ice_finite(ice_scores.get(str(m))) > 0}
    return {m: v for m, v in scores.items() if m not in drop}, drop


try:
    import math
    _n1_h1_gl = isinstance(GL_SCORES, dict) and any(isinstance(g, dict) and any(v is not None for v in g.values())
                                                  for g in GL_SCORES.values())
    if not _n1_h1_gl:
        raise RuntimeError('H1 GLACIER produced no scores (GL failed / not run) -> N1 not attempted')
    os.makedirs(N1_WORK, exist_ok=True)
    for _n1_fn, _n1_s, _n1_h in (('glb_core.py', N1_CORE_SRC, N1_CORE_SHA256), ('glb_driver.py', N1_DRIVER_SRC, N1_DRIVER_SHA256)):
        assert hashlib.sha256(_n1_s.encode('utf-8')).hexdigest() == _n1_h, ('embedded bench source changed', _n1_fn)
        with open(os.path.join(N1_WORK, _n1_fn), 'w', encoding='utf-8') as _n1_f:
            _n1_f.write(_n1_s)
    N1K = _n1_mod('glb_core', os.path.join(N1_WORK, 'glb_core.py'))
    N1DR = _n1_mod('glb_driver', os.path.join(N1_WORK, 'glb_driver.py'))
    print('[N1]', N1K.selftest(), flush=True)
    _n1_G = N1DR.load_gl(GL_PKG)            # attached gl_runner.py as a module (numpy / numba only; no torch here)
    print('[N1]', N1DR.selftest(_n1_G), flush=True)
    _n1_sg = sha256(os.path.join(GL_PKG, 'gl_runner.py'))
    print(f'[N1] code: glb_core {N1_CORE_SHA256[:12]} glb_driver {N1_DRIVER_SHA256[:12]} (= kdev_glbench_n1) | '
          f'gl_runner.py {_n1_sg[:12]} matches the B1/bench MANIFEST: {_n1_sg == N1_GL_RUNNER_SHA256} | arm {N1_ARM} '
          f'(tags, mode) {N1K.arm_tags(N1_ARM, dict(has_H=False))} | budget {N1_BUDGET:.0f}s', flush=True)
    _n1_items_all = ice_fuse.build_ice_input(te, cands, covered_only=False)
    _n1_items, N1_STATS = n1_select(_n1_items_all, N1K)
    print(f"[N1] molecules: GL/ICE input {N1_STATS['molecules']} | with real [M+H]+ {N1_STATS['with_H']} (H1 run, "
          f"unchanged) | blind {N1_STATS['blind']} (with NH4/WL spectra {N1_STATS['blind_nh4_wl']}) | N1 molecules "
          f"{N1_STATS['n1']} | proxies built {N1_STATS['proxies']} (NH4p {N1_STATS['NH4p']}, WLp {N1_STATS['WLp']}; "
          f"empty after the cut {N1_STATS['proxy_empty']})", flush=True)
    _n1_x_items, _n1_x_ref = [], {}
    if not IS_RERUN:                     # forced commit exercise: synthetic blind copies through the same code
        _n1_tx, _n1_x_ref = n1_synthetic_te(te, list(cands), N1K)
        _n1_x_all = ice_fuse.build_ice_input(_n1_tx, {f'n1x:{m}': c for m, c in cands.items() if f'n1x:{m}' in _n1_x_ref},
                                          covered_only=False)
        _n1_x_items, N1X_STATS = n1_select(_n1_x_all, N1K)
        N1X_STATS['proxy_checked'] = n1_check_proxies(_n1_x_items, _n1_x_ref, N1K)
        assert N1X_STATS['blind'] == N1X_STATS['molecules'] == len(_n1_x_ref) >= 1 and N1X_STATS['with_H'] == 0, N1X_STATS
        assert N1X_STATS['n1'] >= 1 and N1X_STATS['proxy_checked'] == N1X_STATS['proxies'] >= N1X_STATS['n1'], N1X_STATS
        assert N1X_STATS['proxies'] + N1X_STATS['proxy_empty'] == sum(k != 'keep' for v in _n1_x_ref.values() for k, *_ in v)
        # arm-B guard: a molecule WITH a real [M+H]+ plus NH4 / water-loss spectra must NOT become an N1 molecule
        _n1_src = sorted(_n1_x_ref)[0].split(':', 1)[1]
        _n1_gdf = pd.concat([te[te.molecule_id.astype(str) == _n1_src], _n1_tx[_n1_tx.molecule_id == f'n1x:{_n1_src}']],
                            ignore_index=True).assign(molecule_id=f'n1b:{_n1_src}')
        _n1_gi, _n1_gs = n1_select(ice_fuse.build_ice_input(_n1_gdf, {f'n1b:{_n1_src}': {str(m): c for m, c in cands.items()}[_n1_src]},
                                                           covered_only=False), N1K)
        assert _n1_gi == [] and _n1_gs['with_H'] == 1 and _n1_gs['n1'] == 0, ('arm-B guard: [M+H]+ molecule selected', _n1_gs)
        N1X_STATS['armB_guard'] = 'ok'
        N1X_MIDS = {it['mid'] for it in _n1_x_items}
    _n1_run = _n1_items + _n1_x_items
    _n1_exp_merged = sum(bool(N1DR.merged_buckets(_n1_G, s)) for it in _n1_run for s in it['spectra'])
    _n1_out, N1_DRV, _n1_done = n1_run(_n1_run, N1_BUDGET) if _n1_run else ({}, {'status': 'nothing to score'}, set())
    print(f"[N1] driver: status {N1_DRV.get('status')} | molecules sent {len(_n1_run)} (real {len(_n1_items)}, synthetic "
          f"{len(_n1_x_items)}) done {len(_n1_done)} | spectra covered {N1_DRV.get('n_spec_covered')} (merged-CE "
          f"{N1_DRV.get('n_spec_merged')}, expected {_n1_exp_merged}) | predictions {N1_DRV.get('n_pred')} (fail "
          f"{N1_DRV.get('n_pred_fail')}) | {N1_DRV.get('seconds')}s | errors {(N1_DRV.get('errors') or [])[:2]}", flush=True)
    _n1_sc = n1_scores(_n1_out, _n1_done, _n1_run, N1K)
    _n1_real = {m: v for m, v in _n1_sc.items() if not m.startswith('n1x:')}
    _n1_clash = sorted(m for m in _n1_real if any(x is not None for x in (GL_SCORES.get(m) or {}).values()))
    if not IS_RERUN:
        assert not _n1_clash, ('N1 molecule already scored by the H1 run', _n1_clash[:5])
        N1X_GL = {m: v for m, v in _n1_sc.items() if m.startswith('n1x:')}
        assert N1_DRV.get('status') == 'ok' and N1X_MIDS <= _n1_done, (N1_DRV.get('status'), sorted(N1X_MIDS - _n1_done)[:5])
        assert len(N1X_GL) >= 1 and N1_DRV.get('n_spec_merged') == _n1_exp_merged, (len(N1X_GL), N1_DRV.get('n_spec_merged'))
        _n1_nb1 = _n1_nbm = 0
        for _n1_m in N1X_MIDS:              # single-CE spectra: merged-CE mode == mean (production gl_runner) exactly;
            for _n1_sp in (_n1_out[_n1_m].get('spec') or {}).values():     # merged-CE ones: the I14b path acts
                if _n1_sp.get('nb') == 1:
                    assert _n1_sp['mean'] == _n1_sp['merged'], _n1_m
                    _n1_nb1 += 1
                else:
                    _n1_nbm += int(_n1_sp['mean'] != _n1_sp['merged'])
        # the dummy commit molecules carry 20,40,60 eV [M+H]+ spectra -> merged-CE proxies (8 in the local dry run): the
        # per-bucket prediction + merge() must run on them with the real model and change their scores vs mean CE
        assert _n1_exp_merged >= 1 and _n1_nbm >= 1, ('merged-CE path not exercised on the commit', _n1_exp_merged, _n1_nbm)
        _n1_rho = []                        # proxies (= the [M+H]+ peaks, cut) vs the real H1 GL scores of the source
        _n1_mean = n1_scores(_n1_out, _n1_done, _n1_x_items, N1K, mode='mean')
        for _n1_m, _n1_d in _n1_mean.items():
            _n1_h = GL_SCORES.get(_n1_m.split(':', 1)[1]) or {}
            _n1_p = [(v, _n1_h.get(c)) for c, v in _n1_d.items() if v is not None and _n1_h.get(c) is not None]
            if len(_n1_p) >= 4:
                _n1_r = _n1_spearman([a for a, _ in _n1_p], [b for _, b in _n1_p])
                if math.isfinite(_n1_r):
                    _n1_rho.append(_n1_r)
        N1X_STATS.update(gl_scored=len(N1X_GL), single_ce_identical=_n1_nb1, merged_changed=_n1_nbm, rho_n=len(_n1_rho),
                         rho_median=float(np.median(_n1_rho)) if _n1_rho else float('nan'))
        print(f"[N1X] synthetic exercise: molecules {N1X_STATS['molecules']} | N1 molecules {N1X_STATS['n1']} | proxies "
              f"built {N1X_STATS['proxies']} (NH4p {N1X_STATS['NH4p']}, WLp {N1X_STATS['WLp']}; empty "
              f"{N1X_STATS['proxy_empty']}) | proxy checks OK {N1X_STATS['proxy_checked']} | arm-B guard "
              f"{N1X_STATS['armB_guard']} | merged-CE spectra "
              f"{N1_DRV.get('n_spec_merged')} (expected {_n1_exp_merged}; merged != mean CE {_n1_nbm}) | single-CE "
              f"merged==mean {_n1_nb1} | GL-scored "
              f"synthetic molecules {len(N1X_GL)} | proxy (mean CE) vs H1 GL Spearman median "
              f"{N1X_STATS['rho_median']:.3f} over {len(_n1_rho)}", flush=True)
        assert not _n1_rho or N1X_STATS['rho_median'] >= 0.3, ('proxy scores do not track the H1 GL scores', _n1_rho)
    else:
        _n1_real = {m: v for m, v in _n1_real.items() if m not in _n1_clash}
    if N1_COMPLEMENT:                    # k2 variant A: E006's ICE fallback keeps the blind molecules ICEBERG covers
        _n1_n0 = len(_n1_real)
        _n1_real, N1_ICE_DROPPED = n1_complement(_n1_real, ICE_SCORES)
        if not IS_RERUN:                 # forced commit exercise of the filter on THIS commit's real ICE output: a
            #                              synthetic copy 'n1x:<mid>' stands for a blind molecule with <mid>'s ICE dict
            _n1_xi = {m: (ICE_SCORES.get(m.split(':', 1)[1]) if isinstance(ICE_SCORES, dict) else None) for m in N1X_GL}
            _n1_xk, _n1_xd = n1_complement(N1X_GL, _n1_xi)
            assert _n1_xd == {m for m, v in _n1_xi.items() if n1_ice_finite(v) > 0}, _n1_xd
            assert set(_n1_xk) == set(N1X_GL) - _n1_xd and all(_n1_xk[m] is N1X_GL[m] for m in _n1_xk)
            assert _n1_xd, ('complement filter not exercised: no synthetic N1 molecule whose source has a finite ICE '
                            'score', len(N1X_GL), sum(n1_ice_finite(v) for v in _n1_xi.values()))
            _n1_t = n1_complement({'f': {}, 'n': {}, 'x': {}, 'b': {}, 'm': {}, 'e': {}},
                                  {'f': {'p': 0.5, 'q': None}, 'n': {'p': None}, 'x': {'p': float('nan'), 'q': float('inf')},
                                   'b': {'p': 'bad', 'q': [1]}, 'e': {}})
            assert set(_n1_t[0]) == {'n', 'x', 'b', 'm', 'e'} and _n1_t[1] == {'f'}, _n1_t
            assert n1_complement({}, ICE_SCORES) == ({}, set()) and n1_complement({'f': {}}, None) == ({'f': {}}, set())
            N1X_STATS['complement'] = dict(synthetic=len(N1X_GL), dropped=len(_n1_xd), kept=len(_n1_xk))
            print(f"[N1X] complement filter exercise: synthetic N1 molecules with GL {len(N1X_GL)} | source ICE dict has a "
                  f"finite score -> dropped {len(_n1_xd)} | kept {len(_n1_xk)} | unit cases OK", flush=True)
        print(f"[N1] complement (k2 variant A): N1 molecules with GL scores {_n1_n0} | dropped (finite ICE score, E006 ICE "
              f"fallback kept) {len(N1_ICE_DROPPED)} | kept {len(_n1_real)}", flush=True)
    _n1_health = (f"N1 OK: {len(_n1_real)} of {len(_n1_items)} N1 molecules GL-scored "
                  f"({sum(sum(v is not None for v in d.values()) for d in _n1_real.values())} candidates), driver "
                  f"{N1_DRV.get('status')}, clashes dropped {len(_n1_clash)}")
    N1_MIDS, N1_GL_MIDS = {str(it['mid']) for it in _n1_items}, set(_n1_real)
    GL_SCORES.update(_n1_real)           # last statement: N1 scores exist only if everything above succeeded
    N1_HEALTH = _n1_health
except Exception as e:
    for _n1_m in list(N1_GL_MIDS):
        GL_SCORES.pop(_n1_m, None)
    N1_MIDS, N1_GL_MIDS = set(), set()
    N1_HEALTH = f'N1 FAILED: {e!r}'
    print('[N1] FAILED -> H1 behaviour (no N1 GL scores):', repr(e)[:600], flush=True)
    if not IS_RERUN:
        raise
print(f'[N1] GL-scored N1 molecules: {len(N1_GL_MIDS)} of {len(N1_MIDS)} | health: {N1_HEALTH} | '
      f'{time.time()-T0:.0f}s', flush=True)
# Counts distinguish selected proxies from completed, retained forward scores.
N1_CHALLENGER_COVERAGE = dict(
    complement=bool(N1_COMPLEMENT), eligible_molecules=len(N1_MIDS),
    proxy_covered_molecules=len(N1_GL_MIDS),
    proxy_covered_with_finite_ice=sum(n1_ice_finite(ICE_SCORES.get(str(m), {})) > 0
                                       for m in N1_GL_MIDS),
    real_h_molecules_skipped=int(N1_STATS.get('with_H', 0)), health=N1_HEALTH)
print('N1_CHALLENGER_COVERAGE', json.dumps(N1_CHALLENGER_COVERAGE), flush=True)
# ---- /N1A_MCE ---------------------------------------------------------------------------------------------------
def gl_of(m):
    g = GL_SCORES.get(str(m), {}) if isinstance(GL_SCORES, dict) else {}
    return g if isinstance(g, dict) and any(v is not None for v in g.values()) else {}
def gl_rerank(order0, smis, keys, scs, forms, ice, gl, top_n, tag=''):
    # z(scs) + ICE_LAM z(ice) + GL_LAM z(gl) in the same slots; no GL scores / any failure -> order0 (= v4g order)
    if not gl:
        return order0
    try:
        o = gl_fuse.rerank_multi(smis, keys, scs, forms, [ice, gl], [ICE_LAM, GL_LAM], top_n=top_n)
    except Exception as e:
        print('gl rerank failed', tag, repr(e)); return order0
    for k, v in (('molecules', 1), ('changed_vs_ice_top25', int(o[:25] != order0[:25])), ('changed_vs_ice_top1', int(o[:1] != order0[:1]))):
        gl_stats[tag + k] = gl_stats.get(tag + k, 0) + v
    return o
for m in list(BASE):
    smis, keys, lib_max, scs, forms = BASE[m]
    ice = ICE_SCORES.get(str(m), {}) if ICE_SCORES else {}
    gl = gl_of(m)
    if BASE_ICE and ice and any(v is not None for v in ice.values()):
        try:
            order = ice_fuse.rerank(smis, keys, scs, forms, ice, lam=ICE_LAM, top_n=TOPN)
            order = gl_rerank(order, smis, keys, scs, forms, ice, gl, TOPN)
            s2 = [smis[i] for i in order]; k2 = [keys[i] for i in order]
            ice_stats['molecules'] += 1
            ice_stats['changed_top25'] += int(s2[:25] != smis[:25]); ice_stats['changed_top1'] += int(bool(s2) and s2[0] != smis[0])
            smis, keys = s2, k2
        except Exception as e:
            print('rerank failed', m, repr(e))
    BASE[m] = (smis[:25], keys[:25], lib_max)
    p = PC.get(m) if (ICE_PC and isinstance(PC, dict)) else None
    if p and p.get('pc_form') and ice:
        try:                             # re-order the PubChem list by z(f.z) + lam z(ice) inside same-formula groups;
            o = ice_fuse.rerank(p['pc'], p['pc_keys'], p['pc_fz'], p['pc_form'], ice, lam=ICE_LAM, top_n=25)
            o = gl_rerank(o, p['pc'], p['pc_keys'], p['pc_fz'], p['pc_form'], ice, gl, 25, 'pc_')
            fz0 = p['pc_fz'][0]          # the gate keeps using the ORIGINAL top f.z (rel), so gate decisions are unchanged
            p['pc'] = [p['pc'][i] for i in o]; p['pc_keys'] = [p['pc_keys'][i] for i in o]
            p['pc_fz'] = [fz0] + [p['pc_fz'][i] for i in o][1:]
            ice_stats['pc_changed'] = ice_stats.get('pc_changed', 0) + int(o[:1] != [0])
        except Exception as e:
            print('pc rerank failed', m, repr(e))
print('ICE rerank stats', ice_stats, f'{time.time()-T0:.0f}s')
print('GL rerank stats', gl_stats, f'{time.time()-T0:.0f}s')
