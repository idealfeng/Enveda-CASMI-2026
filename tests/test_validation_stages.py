"""Candidate-recall boundaries: absent output is unknown, scopes stay explicit."""
from pathlib import Path
import unittest

import pandas as pd

from validation import metric
from validation.stages import _validate_stage_frame, summarize_stages


class CandidateStageBoundaries(unittest.TestCase):
    def setUp(self):
        self.truth = pd.DataFrame({'molecule_id': ['a', 'b'], 'smiles': ['CCO', 'CCCO'], 'panel': ['np', 'cross']})
        self.truth['official_identity'] = self.truth.smiles.map(metric.identity)

    def test_absent_rows_remain_unknown_and_pubchem_is_partial(self):
        frame = pd.DataFrame([{'molecule_id': 'a', 'stage': 'pubchem_top', 'rank': 1, 'smiles': 'CCO', 'identity': metric.identity('CCO')}])
        result = summarize_stages(self.truth, frame)
        summary = next(row for row in result['summaries'] if row['stage'] == 'pubchem_top' and row['panel'] == 'all')
        self.assertEqual(summary['coverage'], 'partial_top_output_only')
        self.assertEqual(summary['observed_molecules'], 1)
        self.assertEqual(summary['unknown_molecules'], 1)
        self.assertEqual(summary['cohort_truth_presence_lower_bound'], 0.5)
        self.assertEqual(summary['cohort_truth_presence_upper_bound'], 1.0)
        row = next(row for row in result['rows'] if row['stage'] == 'pubchem_top' and row['molecule_id'] == 'b')
        self.assertIsNone(row['truth_present'])
        self.assertEqual(result['global_source_candidate_recall']['status'], 'unknown')

    def test_truncation_loss_requires_both_stages_observed(self):
        rows = [{'molecule_id': 'a', 'stage': 'e2_ranked_all', 'rank': 41, 'smiles': 'CCO'},
                {'molecule_id': 'a', 'stage': 'e2_top40', 'rank': 1, 'smiles': 'CC'},
                {'molecule_id': 'b', 'stage': 'e2_ranked_all', 'rank': 1, 'smiles': 'CCCO'}]
        frame = pd.DataFrame(rows); frame['identity'] = frame.smiles.map(metric.identity)
        result = summarize_stages(self.truth, frame)
        transition = next(row for row in result['transitions'] if row['from_stage'] == 'e2_ranked_all' and row['to_stage'] == 'e2_top40' and row['panel'] == 'all')
        self.assertEqual(transition['paired_observed_molecules'], 1)
        self.assertEqual(transition['truth_lost_ids'], ['a'])
        self.assertEqual(transition['unknown_molecules'], 1)

    def test_explicit_top_list_empty_is_known_miss_only_for_that_stage(self):
        frame = pd.DataFrame(columns=['molecule_id', 'stage', 'rank', 'smiles', 'identity'])
        result = summarize_stages(self.truth, frame, explicit_empty={('e2_top40', 'a')})
        known = next(row for row in result['rows'] if row['stage'] == 'e2_top40' and row['molecule_id'] == 'a')
        unobserved_window = next(row for row in result['rows'] if row['stage'] == 'e2_mass_window' and row['molecule_id'] == 'a')
        self.assertTrue(known['observed'])
        self.assertFalse(known['truth_present'])
        self.assertEqual(known['valid_identity_count'], 0)
        self.assertFalse(unobserved_window['observed'])
        self.assertIsNone(unobserved_window['truth_present'])

    def test_rank_and_foreign_identity_guards(self):
        frame = pd.DataFrame([{'molecule_id': 'locked', 'stage': 'e1_ranked_all', 'rank': 1, 'smiles': 'CCO'}])
        with self.assertRaises(ValueError):
            _validate_stage_frame(frame, Path('fixture.jsonl'), {'a'})
        frame['molecule_id'] = 'a'; frame['rank'] = 1.25
        with self.assertRaises(ValueError):
            _validate_stage_frame(frame, Path('fixture.jsonl'), {'a'})
        frame['rank'] = 1
        with self.assertRaises(ValueError):
            _validate_stage_frame(pd.concat([frame, frame]), Path('fixture.jsonl'), {'a'})


if __name__ == '__main__':
    unittest.main()
