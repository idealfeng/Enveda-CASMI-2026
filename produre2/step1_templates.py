"""Step 1 (阶段一): parse derive.py reaction templates into an inventory CSV."""
import sys, csv
from pathlib import Path

ROOT = Path("/mnt/d/Paper/casmi")
sys.path.insert(0, str(ROOT / "third_party/canqiang_e006/engine_source_v4b/code"))
from casmi import derive, chem  # noqa: E402

OUT = ROOT / "produre2" / "artifacts"
OUT.mkdir(parents=True, exist_ok=True)

CATEGORY = {
    "hydroxyl": "hydroxylation/oxidation", "oxidize": "hydroxylation/oxidation",
    "carboxyl": "hydroxylation/oxidation",
    "methyl": "methylation/methoxylation", "methoxy": "methylation/methoxylation",
    "ethyl": "methylation/methoxylation",
    "hexose": "glycosylation/deglycosylation", "pentose": "glycosylation/deglycosylation",
    "deoxyhexose": "glycosylation/deglycosylation", "glucuronyl": "glycosylation/deglycosylation",
    "dehexose": "glycosylation/deglycosylation", "depentose": "glycosylation/deglycosylation",
    "dedeoxyhexose": "glycosylation/deglycosylation",
    "acetyl": "acetylation/deacetylation", "deacetyl": "acetylation/deacetylation",
    "malonyl": "acetylation/deacetylation", "demalonyl": "acetylation/deacetylation",
    "sulfate": "sulfation/desulfation", "desulfate": "sulfation/desulfation",
    "hydrogenate": "hydrogenation/dehydrogenation", "dehydrogenate": "hydrogenation/dehydrogenation",
    "demethyl": "demethylation", "decarboxyl": "decarboxylation",
    "dehydroxyl": "dehydroxylation", "demethoxy": "demethoxylation",
}

def categorize(name):
    for k, v in CATEGORY.items():
        if name.startswith(k):
            return v
    return "other"


def main():
    rows = []
    for name, (smarts, formula_delta) in derive._TRANSFORMS.items():
        mass_delta = float(sum(chem.MASS[e] * n for e, n in formula_delta.items()))
        rows.append(dict(
            template_name=name, reaction_smarts=smarts,
            formula_delta=" ".join(f"{e}{n}" for e, n in sorted(formula_delta.items())),
            exact_mass_delta=round(mass_delta, 6),
            reaction_category=categorize(name),
            whether_single_step=True,
            whether_used_in_current_pipeline=True,
        ))
    rows.sort(key=lambda r: (r["reaction_category"], r["exact_mass_delta"]))
    path = OUT / "reaction_template_inventory.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    from collections import Counter
    print("templates:", len(rows))
    print("by category:", dict(Counter(r["reaction_category"] for r in rows)))
    print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
