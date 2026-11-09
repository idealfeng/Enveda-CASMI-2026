import numpy as np
import pandas as pd
import pytest

from casmi.candidates import candidates_in_window
from casmi.chem import morgan_fingerprints
from casmi.pipeline import write_submission
from casmi.ranking import analog_propagation, combine_scores, fill_slots


@pytest.fixture
def pool():
    """Three candidates in the same mass window and one analog of another mass."""
    smiles = ["COc1ccc(C=O)cc1O", "COc1cc(C=O)ccc1O", "OCc1ccc(O)c(O)c1C", "Oc1ccc(C=O)cc1O"]
    keys = ["isovanillin", "vanillin", "other", "protocatechualdehyde"]
    mass = [152.047, 152.047, 152.047, 138.032]
    df = pd.DataFrame({"key": keys, "smiles": smiles, "exact_mass": mass,
                       "in_coconut": [True, True, True, True]})
    return df.sort_values("exact_mass").reset_index(drop=True)


def test_candidates_in_window():
    masses = np.array([100.0, 150.0, 150.001, 150.01, 200.0])
    assert candidates_in_window(masses, 150.0, ppm=10).tolist() == [1, 2]


def test_analog_propagation_prefers_the_candidate_closest_to_the_analog(pool):
    fps = morgan_fingerprints(pool["smiles"].tolist())
    hits = [("q", {"protocatechualdehyde": 0.9})]  # hybrid search found this analog
    scores = analog_propagation(hits, pd.Series({"q": 152.047}), pool, fps, power=16)["q"]
    assert set(scores) == {"isovanillin", "vanillin", "other"}  # same-mass candidates only
    assert max(scores, key=scores.get) in {"isovanillin", "vanillin"}
    assert scores["other"] < scores["vanillin"]


def test_analog_propagation_masks_and_exclusion(pool):
    fps = morgan_fingerprints(pool["smiles"].tolist())
    hits = [("q", {"protocatechualdehyde": 0.9})]
    masses = pd.Series({"q": 152.047})
    keys = pool["key"].to_numpy()
    no_vanillin = analog_propagation(hits, masses, pool, fps, candidate_mask=keys != "vanillin")["q"]
    assert "vanillin" not in no_vanillin
    excluded = analog_propagation(hits, masses, pool, fps, excluded={"q": "isovanillin"})["q"]
    assert "isovanillin" not in excluded
    # Without allowed analogs, every candidate scores 0 (they remain proposable)
    no_analog = analog_propagation(hits, masses, pool, fps,
                                   analog_mask=keys != "protocatechualdehyde")["q"]
    assert set(no_analog.values()) == {0.0}


def test_identity_counts_only_above_threshold():
    analogs = {"m": {"A": 2.0, "B": 1.0, "C": 0.5}}
    identity = {"m": {"C": 0.95, "B": 0.6}}
    combined = combine_scores(identity, analogs, threshold=0.9)["m"]
    assert max(combined, key=combined.get) == "C"       # strong identity wins
    assert combined["B"] == pytest.approx(0.5)            # weak identity ignored, analogs normalized


def test_fill_slots_keeps_primary_order_and_avoids_duplicates():
    primary = {"m": {"A": 0.9, "B": 0.1}}
    secondary = {"m": {"B": 5.0, "C": 3.0, "D": 4.0}}
    out = fill_slots(primary, secondary, n=3)["m"]
    assert sorted(out, key=out.get, reverse=True) == ["A", "B", "D"]


def test_write_submission(tmp_path, pool):
    scores = {"m1": {"vanillin": 2.0, "isovanillin": 1.0}}
    sub = write_submission(scores, pool, ["m1", "m2"], tmp_path / "submission.csv")
    assert sub["smiles"].tolist() == ["COc1cc(C=O)ccc1O;COc1ccc(C=O)cc1O", "C"]
    assert pd.read_csv(tmp_path / "submission.csv").shape == (2, 2)
