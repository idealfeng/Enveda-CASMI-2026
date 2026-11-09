import numpy as np
import pandas as pd
import pytest

from casmi.validation import reference_mask, sample_queries


@pytest.fixture
def meta():
    """Spectra of two structures: V (a validation molecule) and T (training only)."""
    return pd.DataFrame({
        "key": ["V", "V", "V", "T"],
        "source": ["gnps / QTOF", "mona / QTOF", "mona / Orbitrap", "gnps / QTOF"],
        "instrument_family": ["QTOF", "QTOF", "Orbitrap", "QTOF"],
    })


@pytest.fixture
def val_queries():
    return pd.DataFrame({"key": ["V"], "source": ["gnps / QTOF"], "instrument_family": ["QTOF"]})


def test_class1_hides_only_the_query_source(meta, val_queries):
    assert reference_mask(meta, val_queries, "class1").tolist() == [False, True, True, True]


def test_class1x_hides_the_query_instrument_family(meta, val_queries):
    assert reference_mask(meta, val_queries, "class1x").tolist() == [False, False, True, True]


@pytest.mark.parametrize("condition", ["class2", "class3"])
def test_class2_hides_every_spectrum_of_the_molecule(meta, val_queries, condition):
    assert reference_mask(meta, val_queries, condition).tolist() == [False, False, False, True]


def test_unknown_condition(meta, val_queries):
    with pytest.raises(ValueError):
        reference_mask(meta, val_queries, "class4")


def test_sample_queries_draws_feasible_counts():
    rows = pd.DataFrame({"molecule_id": ["a"] * 5 + ["b"] * 2 + ["c"], "x": range(8)})
    counts = np.array([1, 2, 3, 3, 4])
    for seed in range(20):
        draw = sample_queries(rows, counts, seed)
        n = draw.groupby("molecule_id").size()
        assert n["a"] in {1, 2, 3, 4} and n["b"] in {1, 2} and n["c"] == 1
        assert not draw.index.duplicated().any()
    pd.testing.assert_frame_equal(sample_queries(rows, counts, 0), sample_queries(rows, counts, 0))
