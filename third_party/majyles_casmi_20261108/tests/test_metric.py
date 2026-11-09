import numpy as np
import pandas as pd
import pytest

from casmi.metric import evaluate, mrr_at_25, random_mrr, rank_candidates, rank_of_truth, reciprocal_rank


def test_reciprocal_rank():
    assert reciprocal_rank(["A", "B", "C"], "A") == 1.0
    assert reciprocal_rank(["A", "B", "C"], "C") == pytest.approx(1 / 3)
    assert reciprocal_rank(["A", "B"], "Z") == 0.0


def test_invalid_guess_still_takes_its_rank():
    assert reciprocal_rank([None, "A"], "A") == 0.5


def test_only_the_first_25_guesses_count():
    guesses = [f"k{i}" for i in range(30)]
    assert reciprocal_rank(guesses, "k24") == pytest.approx(1 / 25)
    assert reciprocal_rank(guesses, "k25") == 0.0
    assert rank_of_truth(guesses, "k25") == 26


def test_molecule_without_prediction_scores_zero():
    assert mrr_at_25({"m1": ["A"]}, {"m1": "A", "m2": "B"}) == 0.5


def test_rank_candidates_sorts_by_decreasing_score():
    ranked = rank_candidates({"m": {"A": 0.1, "B": 0.9, "C": 0.5}}, n=2)
    assert ranked == {"m": ["B", "C"]}


def test_evaluate():
    scores = {"m1": {"A": 1.0, "B": 2.0}, "m2": {"C": 1.0}}
    val = pd.DataFrame({"molecule_id": ["m1", "m2", "m3"], "key": ["A", "Z", "D"], "subset": "S"})
    ev = evaluate(scores, val)
    assert ev["rank"].tolist()[0] == 2
    assert ev["rr"].tolist() == [0.5, 0.0, 0.0]
    assert ev["n_candidates"].tolist() == [2, 1, 0]


def test_random_mrr():
    assert random_mrr(np.array([1]), np.array([True])) == 1.0
    assert random_mrr(np.array([2]), np.array([True])) == pytest.approx((1 + 1 / 2) / 2)
    assert random_mrr(np.array([5]), np.array([False])) == 0.0
    # Beyond 25 candidates, the answer is out of the list with probability (n - 25) / n
    assert random_mrr(np.array([50]), np.array([True])) == pytest.approx(sum(1 / r for r in range(1, 26)) / 50)
