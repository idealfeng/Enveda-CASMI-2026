# LightGBM lambdarank: five-fold out-of-fold scores (folds over molecules) for the report and the thresholds, then one
# model on every molecule with its answer among the candidates. Fixed rounds, deterministic, no early stopping.
import lightgbm as lgb

PARAMS = dict(objective='lambdarank', metric='ndcg', eval_at=[1, 5], learning_rate=0.05, num_leaves=31,
              min_data_in_leaf=50, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
              lambdarank_truncation_level=20, verbose=-1, seed=SEED, deterministic=True, num_threads=os.cpu_count() or 2)
NROUND = 400
F = IR.FEATS


def fit(idx):
    idx = [i for i in idx if MOLS[i]['y'].any()]
    X = np.concatenate([MOLS[i]['X'] for i in idx])
    y = np.concatenate([MOLS[i]['y'] for i in idx])
    return lgb.train(PARAMS, lgb.Dataset(X, y, group=[len(MOLS[i]['y']) for i in idx], feature_name=F), NROUND)


n = len(MOLS)
fold_of = np.random.default_rng(SEED).permutation(n) % 5
OOF = [None] * n
for k in range(5):
    m = fit([i for i in range(n) if fold_of[i] != k])
    for i in np.where(fold_of == k)[0]:
        OOF[i] = m.predict(MOLS[i]['X'])
    print(f'fold {k} done, {time.time() - T0:.0f} s', flush=True)
MODEL = fit(list(range(n)))