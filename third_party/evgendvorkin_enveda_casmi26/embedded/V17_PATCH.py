

# ---- v17 patch: popularity prior (log1p SID + log1p PMID from PubChem, mapped onto this store by stereo-stripped SMILES) ----
_POP_DIR = os.environ.get('CASMI_POP_DIR'); _POP_LAM = float(os.environ.get('CASMI_POP_LAM', '0')); _POP_UNION = int(os.environ.get('CASMI_POP_UNION', '0'))
_SRC_BONUS = float(os.environ.get('CASMI_SRC_BONUS', '0')); _SRC_BITS = int(os.environ.get('CASMI_SRC_BITS', '0'))   # v5 depositor-source bonus
_NP_BONUS = float(os.environ.get('CASMI_NP_BONUS', '0'))   # natural-product membership bonus (data notebook v5)
_LOTUS_W = float(os.environ.get('CASMI_LOTUS_W', '0'))   # pre-aligned literature prior
_SYN_W = 0.5
_PARENT_PENALTY = 0.0
_AMBIGUITY = False
_init_worker0 = init_worker


def init_worker(pc_dir, bits_path, pool_meta_path, code_dir=None):
    _init_worker0(pc_dir, bits_path, pool_meta_path, code_dir)
    if _POP_DIR:
        _n = len(_W['mass'])
        if _SYN_W:
            _W['syn'] = np.load(os.path.join(_POP_DIR, 'pc_lsynonyms.npy'), mmap_mode='r')
            assert _W['syn'].shape == (_n,), 'Synonym tier-row alignment differs'
        if _PARENT_PENALTY:
            _W['parent_rows'] = np.load(os.path.join(_POP_DIR, 'pc_different_parent_rows.npy'), mmap_mode='r')
            assert _W['parent_rows'].ndim == 1
            assert not len(_W['parent_rows']) or int(_W['parent_rows'][-1]) < _n
        if _AMBIGUITY:
            _W['formula_count'] = np.load(os.path.join(_POP_DIR, 'pc_formula_isomers.npy'), mmap_mode='r')
            assert _W['formula_count'].shape == (_n,), 'Formula tier-row alignment differs'
        _W['ls'] = np.load(os.path.join(_POP_DIR, 'pc_lsid.npy'), mmap_mode='r')
        _W['lp'] = np.load(os.path.join(_POP_DIR, 'pc_lpmid.npy'), mmap_mode='r')
        if _SRC_BONUS > 0 and _SRC_BITS:
            _W['sm'] = np.load(os.path.join(_POP_DIR, 'pc_src_mask.npy'), mmap_mode='r')
        if _NP_BONUS > 0:
            _W['np'] = np.load(os.path.join(_POP_DIR, 'pc_np.npy'), mmap_mode='r')
        if _LOTUS_W > 0:
            import sys as _sys
            _sys.path.insert(0, _POP_DIR)
            from aligned_public_priors import load_lotus_refs, lotus_log_prior
            _W['lotus'] = load_lotus_refs(_POP_DIR, tier_rows=len(_W['mass']))
            _W['lotus_log'] = lotus_log_prior


def probe_one(task):
    mid, target, z = task
    t0 = time.time()
    chem = _W['chem']; Chem = _W['Chem']; gen = _W['ecfp4']
    tol = float(target) * PPM * 1e-6
    smis, window_priors = _window_bundle(float(target))
    n = len(smis)
    diag = dict(molecule_id=mid, n_window=n, n_pass1=0, n_pass2=0, n_keyed=0, n_in_pool=0, n_listed=0, fz_top=None)
    if n == 0:
        diag['secs'] = time.time() - t0
        return mid, [], [], [], diag
    raw_e = _W['raw_e']; z_e = z[_W['sel_e']].astype(np.float32)
    E = np.zeros((n, len(raw_e)), np.float32); ok = np.zeros(n, bool)
    for i, s in enumerate(smis):
        m = Chem.MolFromSmiles(s)
        if m is None:
            continue
        E[i] = gen.GetFingerprintAsNumPy(m)[raw_e]; ok[i] = True
    sc1 = E @ z_e
    sc1[~ok] = -np.inf
    n1 = min(PC_N1, int(ok.sum()))
    diag['n_pass1'] = n1
    if n1 == 0:
        diag['secs'] = time.time() - t0
        return mid, [], [], [], diag
    top1 = np.argpartition(-sc1, n1 - 1)[:n1] if n1 < n else np.where(ok)[0]
    use_pop = ('ls' in _W) and _POP_LAM > 0
    pop = (np.asarray(window_priors['ls'], np.float32) + np.asarray(window_priors['lp'], np.float32)) if use_pop else np.zeros(n, np.float32)
    if use_pop and 'sm' in _W:
        pop = pop + _SRC_BONUS * ((np.asarray(window_priors['sm']) & _SRC_BITS) != 0).astype(np.float32)
    if use_pop and 'np' in _W:
        pop = pop + _NP_BONUS * (np.asarray(window_priors['np']) != 0).astype(np.float32)
    if use_pop and 'lotus' in _W:
        _lr = _W['lotus_log'](window_priors['lotus'])
        pop = pop + _LOTUS_W * _lr
    if use_pop and 'syn' in _W:
        pop = pop + _SYN_W * np.asarray(window_priors['syn'], np.float32)
    if use_pop and 'parent_rows' in _W:
        _flags = np.zeros(n, dtype=bool)
        pop = pop - _PARENT_PENALTY * _flags.astype(np.float32)
    if use_pop and _POP_UNION > 0:
        pp = np.where(ok, pop, -np.inf); ku = min(_POP_UNION, int(ok.sum()))
        top1 = np.union1d(top1, np.argpartition(-pp, ku - 1)[:ku])
    bits = _W['bits']
    fz, idx = [], []
    for i in top1:
        fp = chem.raw_fingerprint(smis[i])
        if fp is None:
            continue
        fz.append(float(fp[bits].astype(np.float32) @ z)); idx.append(int(i))
    diag['n_pass2'] = len(idx)
    if not idx:
        diag['secs'] = time.time() - t0
        return mid, [], [], [], diag
    fz = np.asarray(fz, np.float64); idx = np.asarray(idx)
    keyc = {}
    def key(j):
        if j not in keyc:
            keyc[j] = chem.score_key(smis[idx[j]]); diag['n_keyed'] += 1
        return keyc[j]
    for j in np.argsort(-fz, kind='stable'):        # gate quantity = v16's pc_fz[0] (best non-pool structure by raw f.z)
        k = key(j)
        if k is not None and k not in _W['pool_keys']:
            diag['fz_top'] = float(fz[j]); break
    zf = (fz - fz.mean()) / (fz.std() + 1e-9)
    _lam = _POP_LAM
    if use_pop and 'formula_count' in _W:
        _count = np.maximum(np.asarray(np.ones(n, dtype=np.uint16), np.float64)[idx], 1.0)
        _lam = _POP_LAM * np.clip(np.log1p(_count) / np.log1p(1000.0), 0.5, 1.5)
    sc = zf + _lam * pop[idx]
    order = np.argsort(-sc, kind='stable')
    out, out_s, out_k, out_p, out_sc, seen = [], [], [], [], [], set()
    for j in order:
        k = key(j)
        if k is None or k in seen:
            continue
        seen.add(k)
        if k in _W['pool_keys']:
            diag['n_in_pool'] += 1
            continue
        out.append(smis[idx[j]]); out_s.append(float(sc[j])); out_k.append(k); out_p.append(float(pop[idx[j]])); out_sc.append(float(sc[j]))
        if len(out) >= K:
            break
    diag['n_listed'] = len(out)
    diag['S'] = float(out_sc[0]) if out_sc else 0.0
    diag['top_pop'] = float(out_p[0]) if out_p else 0.0
    diag['secs'] = time.time() - t0
    return mid, out, out_s, out_k, diag


"""Appended to the current embedded PubChem module; no full-tier reordering."""
_init_worker_single_store = init_worker

def init_worker(pc_dir, bits_path, pool_meta_path, code_dir=None):
    _init_worker_single_store(pc_dir, bits_path, pool_meta_path, code_dir)
    assert _POP_DIR, 'Aligned popularity dataset required for PubChem store union'
    assert not _AMBIGUITY and not _PARENT_PENALTY, 'Supplementary formula/parent priors have not been measured'
    base = dict(name='tier', mass=_W['mass'], off=_W['off'], buf=_W['buf'])
    for key in ('ls', 'lp', 'sm', 'np', 'lotus', 'syn'):
        if key in _W:
            assert _W[key].shape == (len(base['mass']),), (key, 'tier-row alignment')
            base[key] = _W[key]
    _W['pc_stores'] = [base]
    for prefix in ('delta_pc', 'growth_pc'):
        mass_path = os.path.join(_POP_DIR, prefix + '_mass.npy')
        if not os.path.isfile(mass_path):
            continue
        store = dict(name=prefix)
        for key, suffix in [('mass','mass'), ('off','off'), ('buf','smiles'), ('ls','lsid'), ('lp','lpmid'),
                            ('sm','src_mask'), ('np','np'), ('lotus','lotus_refs'), ('syn','lsynonyms'),
                            ('src_observed','src_observed')]:
            path = os.path.join(_POP_DIR, prefix + '_' + suffix + '.npy')
            assert os.path.isfile(path), 'Missing aligned supplementary prior: ' + path
            store[key] = np.load(path, mmap_mode='r')
        n = len(store['mass'])
        assert store['off'].shape == (n + 1,) and store['buf'].ndim == 1
        assert int(store['off'][0]) == 0 and int(store['off'][-1]) == len(store['buf'])
        assert np.all(store['mass'][1:] >= store['mass'][:-1]), prefix + ' masses are not sorted'
        for key in ('ls','lp','sm','np','lotus','syn','src_observed'):
            assert store[key].shape == (n,), (prefix, key, 'row alignment')
        _W['pc_stores'].append(store)

def _window_bundle(target):
    """Return SMILES and row-aligned priors gathered from independent sorted stores."""
    target = float(target)
    tol = target * PPM * 1e-6
    smis, parts, counts = [], {key: [] for key in ('ls','lp','sm','np','lotus','syn','src_observed')}, {}
    for store in _W['pc_stores']:
        a = int(np.searchsorted(store['mass'], target - tol, 'left'))
        b = int(np.searchsorted(store['mass'], target + tol, 'right'))
        counts[store['name']] = b - a
        if b <= a:
            continue
        off = np.asarray(store['off'][a:b + 1], np.int64)
        raw = bytes(store['buf'][off[0]:off[-1]])
        first = int(off[0])
        smis.extend(raw[int(off[i])-first:int(off[i+1])-first].decode('ascii') for i in range(b-a))
        for key in parts:
            if key in store:
                values = np.asarray(store[key][a:b])
            else:
                values = np.full(b-a, 1 if key == 'src_observed' else 0, np.float32)
            assert values.shape == (b-a,), (store['name'], key)
            parts[key].append(values)
    priors = {key: np.concatenate(values) if values else np.zeros(0, np.float32) for key, values in parts.items()}
    assert all(len(values) == len(smis) for values in priors.values())
    _W['last_window_counts'] = counts
    return smis, priors
