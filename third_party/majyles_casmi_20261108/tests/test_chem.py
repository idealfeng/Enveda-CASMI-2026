import numpy as np
import pytest

from casmi.chem import morgan_fingerprints, normalize_smiles, scorer_key, tanimoto


def test_normalize_removes_stereochemistry():
    assert normalize_smiles("C[C@H](N)C(=O)O") == normalize_smiles("CC(N)C(=O)O")
    assert "@" not in normalize_smiles("C[C@H](N)C(=O)O")


def test_normalize_salt_gives_neutral_parent():
    # Counter-ion removed first, then neutralization: sodium acetate -> acetic acid
    assert normalize_smiles("CC(=O)[O-].[Na+]") == "CC(=O)O"


def test_normalize_is_idempotent():
    s = normalize_smiles("OC1=CC=CC=C1C(=O)O")
    assert normalize_smiles(s) == s


@pytest.mark.parametrize("bad", [None, "not a smiles", 3.14])
def test_invalid_input_gives_none(bad):
    assert normalize_smiles(bad) is None
    assert scorer_key(bad) is None


def test_scorer_key_merges_tautomers():
    # 2-hydroxypyridine and 2-pyridone are tautomers: the metric counts them as one answer
    assert scorer_key("Oc1ccccn1") == scorer_key("O=c1cccc[nH]1")
    assert len(scorer_key("Oc1ccccn1")) == 14


def test_scorer_key_separates_isomers():
    assert scorer_key("CCO") != scorer_key("COC")


def test_tanimoto_bounds():
    fps = morgan_fingerprints(["c1ccccc1O", "c1ccccc1O", "CCCCCCCC"])
    t = tanimoto(fps, fps)
    assert t.shape == (3, 3)
    np.testing.assert_allclose(np.diag(t), 1.0)
    assert t[0, 1] == pytest.approx(1.0)
    assert t[0, 2] < 0.2


def test_unparsable_smiles_gets_empty_fingerprint():
    fps = morgan_fingerprints(["not a smiles"])
    assert fps.shape == (1, 256) and fps.sum() == 0
    assert tanimoto(fps, fps)[0, 0] == 0.0
