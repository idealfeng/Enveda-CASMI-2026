"""Scoring boundary and official-source parity checks, without any model inference."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd

from validation import metric
from validation.evaluate import add_candidate_audit, audit_fixed_candidates, evaluate_frames, main, paired_bootstrap


class MetricBoundaries(unittest.TestCase):
    def test_official_stereo_tautomer_regression(self):
        plain = "C=C(C)C1CCC2CCC(=O)C=C2C1"
        stereo = "C=C(C)[C@@H]1CCC2CCC(=O)C=C2C1"
        self.assertEqual(metric.identity(plain), metric.identity(stereo))
        self.assertEqual(metric.identity("C[C@H](N)C(=O)O"), metric.identity("C[C@@H](N)C(=O)O"))
        self.assertEqual(metric.identity("CC(=O)C"), metric.identity("C=C(O)C"))
        self.assertNotEqual(metric.identity("CCCO"), metric.identity("CC(O)C"))

    def test_invalid_duplicate_and_empty_slots(self):
        truth = metric.identity("CCO")
        self.assertIsNone(metric.identity("not a molecule"))
        self.assertEqual(metric.first_correct_rank(truth, "not a molecule;CCO"), 2)
        self.assertEqual(metric.first_correct_rank(truth, "CC;CC;CCO;CCO"), 3)
        self.assertEqual(metric.first_correct_rank(truth, " ; ; CC ; ; CCO ;"), 2)
        self.assertEqual(metric.reciprocal_rank(truth, "CCO;CCO"), 1.0)
        self.assertEqual(metric.first_correct_rank(truth, ";".join(["CC"]*24+["CCO"])), 25)
        with self.assertRaises(ValueError):
            metric.parse_guesses(";".join(["CC"]*25+["CCO"]))
        with self.assertRaises(ValueError):
            metric.parse_guesses(" ; ; ")
        with self.assertRaises(ValueError):
            metric.first_correct_rank(None, "not a molecule")

    def test_charge_formula_is_not_metric_gate(self):
        acid, anion = "CC(=O)O", "CC(=O)[O-]"
        self.assertEqual(metric.identity(acid), metric.identity(anion))
        self.assertEqual(metric.heavy_atom_composition(acid), metric.heavy_atom_composition(anion))
        self.assertNotEqual(metric.molecular_formula(acid), metric.molecular_formula(anion))

    def test_version_guard(self):
        import rdkit
        with mock.patch.object(rdkit, "__version__", "2025.03.6"):
            with self.assertRaises(RuntimeError):
                metric.identity("CCO")

    def test_official_source_parity(self):
        path = Path(__file__).resolve().parents[1]/"validation/evidence/official_metric_20261104/source.ipynb"
        notebook = json.loads(path.read_text(encoding="utf-8"))
        source = notebook["cells"][0]["source"]
        scope = {"__name__": "archived_metric_test"}
        exec(compile("".join(source) if isinstance(source, list) else source, str(path), "exec"), scope)
        solution = pd.DataFrame({"molecule_id": ["a", "b", "c", "d"], "smiles": ["CCO", "c1ccccc1", "C=C(C)C1CCC2CCC(=O)C=C2C1", "CC(=O)O"]})
        predictions = pd.DataFrame({"molecule_id": ["a", "b", "c", "d"], "smiles": [";CC;bad molecule;CCO;;", "CC;CC;c1ccccc1;c1ccccc1", "C=C(C)[C@@H]1CCC2CCC(=O)C=C2C1", "CC(=O)[O-]"]})
        expected = scope["score"](solution.copy(), predictions.copy(), "molecule_id")
        truth = solution.rename(columns={"smiles": "normalized_smiles"})
        truth["identity"] = truth.normalized_smiles.map(metric.identity)
        result = evaluate_frames(truth, predictions)
        self.assertAlmostEqual(result["metrics"]["mrr_at_25"], expected)


class EvaluationBoundaries(unittest.TestCase):
    def setUp(self):
        self.truth = pd.DataFrame({"molecule_id": ["a", "b"], "normalized_smiles": ["CCO", "CCCO"], "source": ["x", "y"]})
        self.truth["identity"] = self.truth.normalized_smiles.map(metric.identity)
        self.control = pd.DataFrame({"molecule_id": ["a", "b"], "smiles": ["CC;CCO", "CC(O)C;CCCO"]})
        self.treatment = pd.DataFrame({"molecule_id": ["b", "a"], "smiles": ["CCCO;CC(O)C", "CCO;CC"]})

    def test_strict_truth_and_id_checks(self):
        broken = self.truth.copy(); broken.loc[0, "identity"] = metric.identity("CC")
        with self.assertRaises(ValueError): evaluate_frames(broken, self.control)
        with self.assertRaises(ValueError): evaluate_frames(self.truth, self.control.iloc[:1])
        with self.assertRaises(ValueError): evaluate_frames(self.truth, pd.concat([self.control,self.control.iloc[:1]]))

    def test_datasets_truth_aliases_and_conflicts(self):
        aliases = self.truth.rename(columns={"identity":"official_identity", "normalized_smiles":"smiles", "source":"query_source"})
        self.assertEqual(evaluate_frames(aliases, self.control), evaluate_frames(self.truth, self.control))
        for alias, canonical in (("official_identity","identity"),("smiles","normalized_smiles"),("query_source","source")):
            broken = aliases.copy(); broken[canonical] = broken[alias]; broken.loc[0,canonical] = "conflict"
            with self.assertRaises(ValueError): evaluate_frames(broken, self.control)

    def test_fixed_candidate_and_paired_alignment(self):
        control = evaluate_frames(self.truth, self.control)
        treatment = evaluate_frames(self.truth, self.treatment)
        self.assertTrue(audit_fixed_candidates(self.truth, self.treatment, self.control)["equal"])
        wrong = self.treatment.copy(); wrong.loc[0, "smiles"] = "CCCO;CCCC"
        self.assertFalse(audit_fixed_candidates(self.truth, wrong, self.control)["equal"])
        interval = paired_bootstrap(treatment["rows"], control["rows"], 100, 42)
        self.assertEqual(interval["metrics"]["mrr_at_25"], {"delta":0.5,"ci_low":0.5,"ci_high":0.5})
        self.assertEqual(interval, paired_bootstrap(treatment["rows"], list(reversed(control["rows"])), 100, 42))

    def test_candidate_recall_unknown_partial_and_empty(self):
        report = evaluate_frames(self.truth, self.control)
        self.assertEqual(report["candidate_recall_decomposition"]["status"], "unknown")
        add_candidate_audit(report, pd.DataFrame({"molecule_id":["a"], "candidate_smiles":["CC;CCO"]}))
        self.assertEqual(report["candidate_recall_decomposition"]["status"], "partial")
        self.assertEqual(report["candidate_recall_decomposition"]["unknown_molecules"], 1)
        misses = evaluate_frames(self.truth, pd.DataFrame({"molecule_id":["a","b"], "smiles":["CC","CC"]}))
        empty = evaluate_frames(self.truth, pd.DataFrame({"molecule_id":["a","b"], "smiles":["invalid", "CC"]}))
        add_candidate_audit(empty, pd.DataFrame({"molecule_id":["a","b"],"candidate_smiles":["", "CCCO;CC"]}))
        self.assertEqual(empty["candidate_recall_decomposition"]["candidate_recall"], 0.5)
        self.assertEqual(empty["candidate_recall_decomposition"]["recall_misses"], 1)
        with self.assertRaises(ValueError):
            add_candidate_audit(misses, pd.DataFrame({"molecule_id":["a"],"candidate_smiles":["CCCC"]}))

    def test_cli_report_and_failed_ablation_exit(self):
        temp_root = Path(__file__).resolve().parents[1]/".cache/tmp-linux"
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as temporary:
            root = Path(temporary)
            for name, frame in (("truth", self.truth), ("baseline", self.control), ("treatment", self.treatment)):
                frame.assign(panel=["np","cross"]).to_csv(root/f"{name}.csv", index=False)
            arguments = ["evaluate", "--truth", str(root/"truth.csv"), "--predictions", str(root/"treatment.csv"),
                         "--baseline", str(root/"baseline.csv"), "--require-fixed-candidates", "--bootstrap-resamples", "50",
                         "--output", str(root/"report.json")]
            with mock.patch("sys.argv", arguments):
                self.assertEqual(main(), 0)
            report = json.loads((root/"report.json").read_text())
            self.assertTrue(report["fixed_candidate_requirement_satisfied"])
            self.assertEqual(report["metrics"]["mrr_at_25"], 1.0)
            self.assertEqual(report["paired_bootstrap"]["metrics"]["mrr_at_25"]["delta"], 0.5)
            self.assertEqual(set(report["paired_bootstrap_by_panel"]), {"np", "cross"})
            changed = self.treatment.copy(); changed.loc[0, "smiles"] = "CCCO;CCCC"
            changed.to_csv(root/"treatment.csv", index=False)
            with mock.patch("sys.argv", arguments):
                self.assertEqual(main(), 2)
            self.assertFalse(json.loads((root/"report.json").read_text())["fixed_candidate_requirement_satisfied"])


if __name__ == "__main__":
    unittest.main()
