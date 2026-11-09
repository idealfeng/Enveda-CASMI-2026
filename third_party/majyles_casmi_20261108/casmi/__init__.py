"""Molecule identification from MS/MS spectra (Kaggle CASMI 2026).

Pipeline, by module:
    data        loading the competition data, adduct masses, instrument families
    chem        the metric's identity key, SMILES normalization, fingerprints (RDKit)
    spectra     spectrum cleaning, reference library, FlashEntropy library search
    candidates  the candidate pool (training set ∪ COCONUT) and its masks
    ranking     analog propagation, identity gating, ranker features
    pipeline    end-to-end prediction and submission file
    metric      local MRR@25
    validation  query draws and simulated test classes

Everything is re-exported here, so `import casmi; casmi.predict(...)` works.
Data locations are in `casmi.paths` (mutable, e.g. redirected on Kaggle).
"""

from .candidates import (NP_THRESHOLD, SYNTHETIC_LIBS, candidate_pool, candidates_in_window,
                         pool_fingerprints, pool_masks, pool_np_likeness, pool_np_scores)
from .chem import (FP_BITS, compute_structure_table, key_table, morgan_fingerprints, normalize_many,
                   normalize_smiles, np_likeness_scores, scorer_key, structure_table, tanimoto)
from .data import (INSTRUMENT_PRIORITY, META_COLUMNS, TEST_ADDUCTS, instrument_family, load_coconut,
                   load_reference_meta, load_train_meta, load_train_spectra, molecule_masses,
                   neutral_mass)
from .metric import evaluate, mrr_at_25, random_mrr, rank_candidates, rank_of_truth, reciprocal_rank
from .paths import ROOT, cached, paths
from .pipeline import predict, predict_ranker, write_submission
from .ranking import (DERIVED_FEATURES, FEATURES, add_derived_features, analog_propagation,
                      candidate_features, combine_scores, fill_slots, scores_from_table)
from .spectra import (CLEAN_PARAMS, SpectralIndex, aggregate_hits, build_clean_library, clean_peaks,
                      clean_query_spectra, library_peaks, spectrum_hits)
from .validation import load_validation, reference_mask, sample_queries, spectra_count_distribution
