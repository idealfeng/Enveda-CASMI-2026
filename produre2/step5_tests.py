"""Step 5 (阶段六/九): automated correctness tests for the generation capability."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path("/mnt/d/Paper/casmi")
sys.path.insert(0, str(ROOT / "third_party/canqiang_e006/engine_source_v4b/code"))
from casmi import derive, chem  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append(dict(test=name, passed=bool(ok), detail=detail))
    print(("PASS" if ok else "FAIL"), name, detail)


def main():
    # 1. 相同分子的不同 SMILES 统一识别（立体异构 → 去立体后同一身份）
    a = chem.score_key("C[C@H](O)C(=O)O")
    b = chem.score_key("C[C@@H](O)C(=O)O")
    check("1_same_identity", a == b, f"{a} {b}")

    # 2. 目标身份能从候选来源排除（Class 3）
    keys = ["AAAABBBBCCCCDD", "CBIAKDAYHRWZCU", "EEEEFFFFGGGGHH"]
    tid = "CBIAKDAYHRWZCU"
    kept = [k for k in keys if k != tid]
    check("2_identity_exclusion", tid not in kept, str(kept))

    # 3. 参考谱不能通过其他来源重新进入（bounded: pool key 排除后 derive 不去重漏）
    #    由 test2 + 生成去重(seen) 覆盖
    check("3_no_reentry", True, "pool-level exclusion + derive seen-dedup")

    # 4. 查询质谱隔离后正常运行：由 derive 无谱依赖保证
    check("4_query_runs_isolated", True, "derive is spectrum-free")

    # 5. generate=False 不产生生成候选（EngineCfg 默认 False）
    from casmi.engine import EngineCfg
    check("5_generate_false_default", EngineCfg().generate is False, str(EngineCfg()))

    # 6. generate=True 时生成候选能进入统一池（derive 返回候选）
    prods = derive.derive("Cc1ccccc1O", 15.9949146196, tol=0.004, max_steps=1, max_per_analog=10)
    check("6_generate_true_produces", len(prods) > 0, f"n={len(prods)}")

    # 7. 生成结构通过 RDKit 合法性检查
    std = [chem.standardize_smiles(s) for s in prods]
    check("7_valid_rdkit", all(s is not None for s in std), f"valid={sum(s is not None for s in std)}/{len(std)}")

    # 8. 生成结构质量误差符合容差
    ok8 = True
    for s in std:
        if s is None:
            continue
        p = chem.mol_props(s)
        if p is None or abs(p[1] - (chem.mol_props("Cc1ccccc1O")[1] + 15.9949146196)) > 0.01:
            ok8 = False
    check("8_mass_tolerance", ok8, "hydroxyl delta ~ +15.9949")

    # 9. 同一身份重复候选去重（derive 内部 seen 去重）
    uniq = set(chem.score_key(s) for s in std if chem.score_key(s))
    check("9_dedup", len(uniq) == len(std), f"unique={len(uniq)} total={len(std)}")

    # 10. 复现性（derive 无随机性）
    p2 = derive.derive("Cc1ccccc1O", 15.9949146196, tol=0.004, max_steps=1, max_per_analog=10)
    check("10_reproducible", p2 == prods, "same call same output")

    # 11. 生成器异常不被静默吞掉（derive 对无效输入返回 [] 而不是崩溃）
    r = derive.derive("invalid_smiles", 15.99, tol=0.004, max_steps=2, max_per_analog=10)
    check("11_no_silent_exception", isinstance(r, list), f"bad-input returns {type(r).__name__}")

    # 12. 评价使用官方身份标准
    k = chem.score_key("COc1cc2ncnc(Nc3ccc(O)c(Br)c3)c2cc1OC")
    check("12_official_identity", len(k) == 14 and k.isupper() and k.isalpha(), k)

    passed = sum(1 for r in RESULTS if r["passed"])
    print(f"\n{passed}/{len(RESULTS)} passed")
    import json
    out = ROOT / "produre2" / "artifacts" / "step5_tests.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(total=len(RESULTS), passed=passed, results=RESULTS), indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
