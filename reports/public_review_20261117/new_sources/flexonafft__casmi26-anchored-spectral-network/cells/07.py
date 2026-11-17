# Candidates of each molecule's own formula from the PubChem tier (at most IR.CAP, most documented first), their
# fingerprints in a process pool, then the stage-1 selection and the features. Label: the candidate's stored
# InChIKey-14 equals the molecule's.
import multiprocessing as mp

BUDGET_S = 5.0 * 3600
tier = IR.Tier(P)
nbits = len(np.load(P['bits']))
by_f = {}
for k in KEYS:
    if k not in Z:
        continue
    f0, m0 = IR.formula_mass(g.loc[k, 'smiles'])
    if f0 is None:
        continue
    by_f.setdefault(f0, [m0, []])[1].append(k)
formulas = sorted(by_f, key=lambda f: -len(by_f[f][1]))
print(f'{sum(len(v[1]) for v in by_f.values()):,} molecules over {len(formulas):,} formulas')
MOLS = []   # dicts: key, formula, testlike, n_window, in_window, X, y
stats = dict(no_window=0, too_few=0, done=0)
with mp.get_context('fork').Pool(os.cpu_count() or 2, initializer=IR.fp_init, initargs=(P['code'], P['bits'])) as pool:
    for b in range(0, len(formulas), 50):
        if time.time() - T0 > BUDGET_S:
            print('time budget reached at formula', b)
            break
        batch = formulas[b:b + 50]
        wins = {f: tier.window(by_f[f][0]) for f in batch}
        cache = {}
        IR.fingerprints(tier, {f: [c[0] for c in wins[f]] for f in batch}, pool, cache)
        for f in batch:
            cands = wins[f]
            for k in by_f[f][1]:
                if not cands:
                    stats['no_window'] += 1
                    continue
                mm = IR.molecule_matrix(cands, [cache.get((c[0], f)) for c in cands], Z[k], nbits)
                if mm is None:
                    stats['too_few'] += 1
                    continue
                sc, X, _ = mm
                y = np.array([c[1] == k for c in sc], np.int8)
                MOLS.append(dict(key=k, formula=f, testlike=bool(g.loc[k, 'testlike']), n_window=len(cands),
                                 in_window=any(c[1] == k for c in cands), X=X, y=y))
                stats['done'] += 1
        if (b // 50) % 10 == 0:
            print(f'  formulas {b + len(batch):,}/{len(formulas):,}, molecules {stats["done"]:,}, {time.time() - T0:.0f} s', flush=True)
print(stats, f'{time.time() - T0:.0f} s')