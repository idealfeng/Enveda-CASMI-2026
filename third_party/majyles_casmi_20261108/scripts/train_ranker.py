"""Step 6 — LightGBM ranker (lambdarank) on the feature tables of step 5.

- training: the ranker set (2,000 molecules), cross-instrument class 1 and class 2, rows
  weighted by condition (0.16 class 1, 0.45 class 2) to mimic the test mix;
- number of trees chosen by grouped cross-validation **on the training set** (never on
  validation A/B);
- evaluation on validation A and B, draws 0 and 1, and a paired bootstrap comparison with
  the hand-tuned formula of submission v2.
Saves processed/ranker.txt.

With --final, also trains the submitted model (processed/ranker_final.txt): the same
training set plus validation subset A (timsTOF, the test's instrument), weight 3, then
evaluated on B only.
"""
import argparse

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

import casmi

WEIGHTS = {"class1": 0.16, "class2": 0.45}
PARAMS = dict(objective="lambdarank", learning_rate=0.05, num_leaves=31, min_child_samples=50,
              subsample=0.8, subsample_freq=1, colsample_bytree=0.8, lambdarank_truncation_level=25,
              verbose=-1, random_state=0)
FEATS = casmi.FEATURES + casmi.DERIVED_FEATURES


def load(name: str, cond: str) -> pd.DataFrame:
    table = casmi.cached(f"features_v2_{name}", None).assign(condition=cond)
    return casmi.add_derived_features(table)


def reachable_only(train: pd.DataFrame) -> pd.DataFrame:
    """Class 1: keep only molecules whose correct answer has visible spectra.

    The others are actually class-2 cases (no public spectrum), which would teach the ranker
    to distrust identity although a real class-1 molecule does have spectra.
    """
    pos = train[(train["label"] == 1) & (train["condition"] == "class1")]
    ok = set(pos.loc[pos["has_visible_spectra"] == 1, "molecule_id"])
    keep = (train["condition"] != "class1") | train["molecule_id"].isin(ok)
    return train[keep]


def prepare(df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Sort by group (condition, molecule): the rows of a group must be contiguous."""
    df = df.sort_values(["condition", "molecule_id"], kind="stable").reset_index(drop=True)
    sizes = df.groupby(["condition", "molecule_id"], sort=False).size().to_numpy()
    return df, sizes


def evaluate_table(table: pd.DataFrame, col: str, val_structures: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (cond, seed), g in table.groupby(["condition", "seed"]):
        ev = casmi.evaluate(casmi.scores_from_table(g, col), val_structures)
        rows.append(ev.assign(condition=cond, seed=seed))
    return pd.concat(rows, ignore_index=True)


def summary(ev: pd.DataFrame) -> pd.DataFrame:
    """MRR@25 per subset and condition, and the expected test score (class 3 scores 0)."""
    r = ev.groupby(["subset", "condition", "seed"])["rr"].mean().groupby(["subset", "condition"]).mean().unstack()
    r["expected"] = WEIGHTS["class1"] * r["class1"] + WEIGHTS["class2"] * r["class2"]
    return r.round(4)


def choose_n_trees(train: pd.DataFrame) -> int:
    """Mean best iteration over a 4-fold cross-validation grouped by molecule."""
    X, y, groups = train[FEATS], train["label"].to_numpy(), train["molecule_id"].to_numpy()
    best_iters = []
    for fold, (tr, te) in enumerate(GroupKFold(n_splits=4).split(X, y, groups)):
        tr_df, tr_sizes = prepare(train.iloc[tr])
        te_df, te_sizes = prepare(train.iloc[te])
        m = lgb.LGBMRanker(n_estimators=2000, **PARAMS)
        m.fit(tr_df[FEATS], tr_df["label"], group=tr_sizes,
              sample_weight=tr_df["condition"].map(WEIGHTS),
              eval_set=[(te_df[FEATS], te_df["label"])], eval_group=[te_sizes], eval_at=[1, 5],
              callbacks=[lgb.early_stopping(100, verbose=False)])
        best_iters.append(m.best_iteration_)
        print(f"fold {fold}: best number of trees {m.best_iteration_}, "
              f"ndcg@1 {m.best_score_['valid_0']['ndcg@1']:.4f}", flush=True)
    return int(np.mean(best_iters))


def paired_bootstrap(ev_new: pd.DataFrame, ev_ref: pd.DataFrame, n_boot: int = 2000) -> None:
    """Gain in expected score, with a 95 % interval from resampling molecules."""
    d = ev_new.merge(ev_ref, on=["molecule_id", "subset", "condition", "seed"], suffixes=("_new", "_ref"))
    d["diff"] = (d["rr_new"] - d["rr_ref"]) * d["condition"].map(WEIGHTS)
    per_mol = d.groupby(["subset", "molecule_id"])["diff"].sum() / d["seed"].nunique()
    rng = np.random.default_rng(0)
    for sub, s in per_mol.groupby(level="subset"):
        v = s.to_numpy()
        boots = [rng.choice(v, len(v)).mean() for _ in range(n_boot)]
        print(f"{sub}: expected gain of the ranker {v.mean():+.4f} "
              f"(95 % CI [{np.percentile(boots, 2.5):+.4f}, {np.percentile(boots, 97.5):+.4f}])")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--final", action="store_true", help="also train the submitted model (with subset A)")
    args = parser.parse_args()

    # Class 1: the cross-instrument version (class1x), closer to the test than class1
    train = reachable_only(pd.concat([load("class1x_rank", "class1"), load("class2_rank", "class2")],
                                     ignore_index=True))
    print("training groups:", train.groupby(["condition", "molecule_id"]).ngroups, flush=True)
    train, sizes = prepare(train)
    n_trees = choose_n_trees(train)

    model = lgb.LGBMRanker(n_estimators=n_trees, **PARAMS)
    model.fit(train[FEATS], train["label"], group=sizes, sample_weight=train["condition"].map(WEIGHTS))
    model.booster_.save_model(str(casmi.paths.processed / "ranker.txt"))

    val_structures, _ = casmi.load_validation()
    val = pd.concat([load(f"{c}_s{s}", c).assign(seed=s) for s in [0, 1] for c in WEIGHTS], ignore_index=True)
    val["formula"] = val["an16_rel"] + np.where(val["id_max"] >= 0.9, 10 * val["id_max"], 0.0)
    val["ranker"] = model.predict(val[FEATS])
    ev_formula = evaluate_table(val, "formula", val_structures)
    ev_ranker = evaluate_table(val, "ranker", val_structures)
    print(f"\nnumber of trees: {n_trees}")
    print("\nformula (submission v2):"); print(summary(ev_formula).to_string())
    print("\nranker:"); print(summary(ev_ranker).to_string())
    paired_bootstrap(ev_ranker, ev_formula)

    imp = pd.Series(model.booster_.feature_importance("gain"), index=FEATS)
    print("\nfeature importance (gain, %):")
    print((imp / imp.sum() * 100).sort_values(ascending=False).round(1).to_string())

    if args.final:
        # Subset A is timsTOF, like the test: worth more than its size. Each of its two query
        # draws becomes a distinct group. B stays out, to keep an honest evaluation.
        a_mols = set(val_structures.loc[val_structures["subset"] == "A_np_examples", "molecule_id"])
        a = val[val["molecule_id"].isin(a_mols)].copy()
        a["molecule_id"] = "A" + a["seed"].astype(str) + "_" + a["molecule_id"]
        full, full_sizes = prepare(pd.concat([train, a.drop(columns=["seed", "formula", "ranker"])],
                                             ignore_index=True))
        w = full["condition"].map(WEIGHTS) * np.where(full["molecule_id"].str.startswith("A"), 3.0, 1.0)
        final = lgb.LGBMRanker(n_estimators=n_trees, **PARAMS)
        final.fit(full[FEATS], full["label"], group=full_sizes, sample_weight=w)
        final.booster_.save_model(str(casmi.paths.processed / "ranker_final.txt"))
        vb = val[~val["molecule_id"].isin(a_mols)].copy()
        vb["final"] = final.predict(vb[FEATS])
        print("\nfinal model (trained with A), evaluated on B:")
        b_structures = val_structures[~val_structures["molecule_id"].isin(a_mols)]
        print(summary(evaluate_table(vb, "final", b_structures)).to_string())
