"""Meaningful alignment/fallback guards for fixed-candidate scorer comparisons."""
from unittest import TestCase
import numpy as np
import pandas as pd

from scripts.run_public_neural_comparison import align_frame, query_zscore


class PublicNeuralComparisonTests(TestCase):
    def frame(self):
        return pd.DataFrame(dict(molecule_id=['a','a','b','b'],smiles=['C','CC','O','CO'],
            baseline_rank=[1,2,1,2],library_max=[.9,.4,.7,.3],processed=[True]*4,
            neural_ok=[True]*4,neural_score=[1.,3.,7.,7.],n_spectra=[2]*4))

    @property
    def core(self):
        return ['molecule_id','smiles','baseline_rank','library_max','processed']

    def test_shuffled_rows_are_aligned_by_query_and_candidate(self):
        original=self.frame()
        result=align_frame(original,original.iloc[[3,1,0,2]],self.core)
        self.assertEqual(result[['molecule_id','smiles']].values.tolist(),
                         original[['molecule_id','smiles']].values.tolist())

    def test_population_zscore_is_per_query_and_constant_group_is_zero(self):
        result=query_zscore(self.frame()).to_numpy()
        np.testing.assert_allclose(result,[-1.,1.,0.,0.],rtol=0,atol=1e-15)

    def test_missing_or_duplicate_candidates_are_rejected(self):
        original=self.frame()
        for changed in (original.iloc[:-1],pd.concat([original.iloc[:-1],original.iloc[[0]]])):
            with self.subTest():
                with self.assertRaises(ValueError):
                    align_frame(original,changed,self.core)

    def test_changed_upstream_evidence_is_rejected(self):
        original=self.frame();changed=original.copy();changed.loc[0,'library_max']=.8
        with self.assertRaises(AssertionError):
            align_frame(original,changed,self.core)

    def test_failed_or_nonfinite_scorer_cannot_become_an_ensemble(self):
        original=self.frame()
        for column,value in [('neural_ok',False),('processed',False),('neural_score',np.nan),('n_spectra',0)]:
            changed=original.copy();changed.loc[0,column]=value
            with self.subTest(column=column):
                with self.assertRaises(ValueError):
                    align_frame(original,changed,self.core)
