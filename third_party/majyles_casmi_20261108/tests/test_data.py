import numpy as np
import pandas as pd
import pytest

from casmi.data import TEST_ADDUCTS, instrument_family, molecule_masses, neutral_mass

GLUCOSE = 180.063388


def test_adducts_of_one_molecule_give_the_same_neutral_mass():
    adducts = ["[M+H]+", "[M+Na]+", "[M-H]-", "[M+Cl]-", "[M-H2O+H]+"]
    mz = [GLUCOSE + TEST_ADDUCTS[a] for a in adducts]
    np.testing.assert_allclose(neutral_mass(mz, adducts), GLUCOSE, atol=1e-9)


def test_neutral_mass_accepts_lists_and_series():
    assert neutral_mass([181.070664], ["[M+H]+"])[0] == pytest.approx(GLUCOSE, abs=1e-6)
    assert neutral_mass(np.array([181.070664]), pd.Series(["[M+H]+"]))[0] == pytest.approx(GLUCOSE, abs=1e-6)


def test_unknown_adduct_gives_nan():
    assert np.isnan(neutral_mass([200.0], ["[M+Li]+"])[0])


def test_molecule_mass_is_the_median_over_spectra():
    queries = pd.DataFrame({
        "molecule_id": ["a", "a", "a", "b"],
        "precursor_mz": [GLUCOSE + 1.007276, GLUCOSE + 22.989218, GLUCOSE + 1.007276 + 0.1, 100.0],
        "adduct": ["[M+H]+", "[M+Na]+", "[M+H]+", "[M-H]-"],
    })
    masses = molecule_masses(queries)
    assert masses["a"] == pytest.approx(GLUCOSE)
    assert masses["b"] == pytest.approx(101.007276)


@pytest.mark.parametrize("raw, family", [
    ("timsTOF Pro 2", "timsTOF"),
    ("LC-ESI-QTOF", "QTOF"),
    ("maXis plus UHR-ToF-MS", "QTOF"),
    ("Q Exactive Plus Orbitrap", "Orbitrap"),
    ("LC-ESI-ITFT", "IonTrap"),
    ("LTQ Orbitrap XL", "IonTrap"),
    ("LC-ESI-QQ", "QqQ"),
    ("MALDI-TOF", "other"),
])
def test_instrument_family(raw, family):
    assert instrument_family(pd.Series([raw]))[0] == family


def test_missing_instrument_is_other():
    assert instrument_family(pd.Series([None]))[0] == "other"
