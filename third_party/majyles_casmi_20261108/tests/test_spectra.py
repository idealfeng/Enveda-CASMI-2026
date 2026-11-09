import numpy as np
import pandas as pd
import pytest

from casmi.spectra import aggregate_hits, clean_peaks, clean_query_spectra, library_peaks


def test_clean_peaks_drops_precursor_and_noise_and_normalizes():
    mzs = [50.0, 100.0, 100.01, 150.0, 199.5, 200.0]
    intensities = [0.005, 1.0, 0.2, 0.5, 0.8, 1.0]
    peaks = clean_peaks(mzs, intensities, precursor_mz=200.0)
    assert peaks.dtype == np.float32
    assert peaks[:, 0].max() < 200.0 - 1.6         # precursor region removed
    assert not np.any(np.isclose(peaks[:, 0], 50.0))  # peak below 1 % of the base peak removed
    assert len(peaks) == 2                          # 100 and 100.01 merged, 150 kept
    assert peaks[:, 1].sum() == pytest.approx(1.0)


def _queries():
    return pd.DataFrame({
        "precursor_mz": [300.0, 300.0],
        "ms2_mzs": [np.array([100.0, 150.0]), np.array([], dtype=float)],
        "ms2_normalized_intensities": [np.array([1.0, 0.5]), np.array([], dtype=float)],
    })


def test_flat_library_round_trip():
    lib = clean_query_spectra(_queries())
    assert lib["offsets"].tolist() == [0, 2, 2]
    np.testing.assert_allclose(library_peaks(lib, 0), [[100.0, 2 / 3], [150.0, 1 / 3]], rtol=1e-6)
    assert library_peaks(lib, 1).shape == (0, 2)  # an empty spectrum stays an empty entry


def test_aggregate_hits():
    hits = [("m", {"A": 0.5, "B": 0.2}), ("m", {"A": 0.3}), ("n", {})]
    summed = aggregate_hits(hits, "sum")
    assert summed["m"] == pytest.approx({"A": 0.8, "B": 0.2}) and summed["n"] == {}
    assert aggregate_hits(hits, "max") == {"m": {"A": 0.5, "B": 0.2}, "n": {}}
