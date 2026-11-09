"""Small deterministic protocol checks; no asset loading or model execution."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np

path=Path(__file__).resolve().parents[1]/'scripts/run_component_neural_pilot.py'
spec=importlib.util.spec_from_file_location('component_protocol',path)
component=importlib.util.module_from_spec(spec);spec.loader.exec_module(component)


class ComponentProtocol(unittest.TestCase):
    def test_mass_window_does_not_force_truth(self):
        # The truth could be 200; the observed precursor implies 100. No label is
        # accepted by this helper, and an empty measured window remains empty.
        masses=np.array([100.,100.0005,200.])
        self.assertEqual(list(component.window_indices(masses,100.)),[0,1])
        self.assertEqual(list(component.window_indices(masses,150.)),[])

    def test_rrf_reorders_exact_same_candidate_indices(self):
        base=np.array([5.,4.,3.,2.]);neural=np.array([1.,4.,3.,2.])
        order=component.rrf_order(base,neural)
        self.assertEqual(set(order),set(range(4)))
        np.testing.assert_array_equal(component.rrf_order(base,base),np.arange(4))
        with self.assertRaises(ValueError):component.rrf_order(base,[float('nan')]*4)

    def test_spectrum_round_robin_has_fixed_cap_and_both_modes(self):
        records=[{'ionization_mode':mode,'adduct':adduct,'ce_bucket':energy,'source_row':f'{mode}_{energy}'}
                 for mode,adduct in [('positive','[M+H]+'),('negative','[M-H]-')] for energy in range(10)]
        chosen=component.choose_records(records,12)
        self.assertEqual(len(chosen),12)
        self.assertEqual({row['ionization_mode'] for row in chosen},{'positive','negative'})
        self.assertEqual(chosen,component.choose_records(list(reversed(records)),12))


if __name__=='__main__':unittest.main()
