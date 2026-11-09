"""Synthetic-only EXP003 feature definitions; never read labels, real traces or models."""
from pathlib import Path
from unittest import TestCase
import copy
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import export_gl_support_features as feature


class SupportTests(TestCase):
    def fixture(self,duplicate=False):
        raw=[dict(mz=[100.+i],it=[1.],prec=200.,adduct='[M+H]+',mode=1) for i in range(3)]
        if duplicate:raw.append(copy.deepcopy(raw[0]))
        items=[dict(mid='synthetic',cands=['A','B','C'],spectra=raw)]
        identities={'A':'A'*14,'B':'B'*14,'C':'C'*14};coverage=[];scores=[]
        values={'A':[.9,.1,.1,.9],'B':[.35,.35,.35,.35],'C':[.05]*4}
        for i,sp in enumerate(raw):
            payload={name:sp.get(name) for name in ('mz','it','prec','adduct','mode')}
            event=dict(mid='synthetic',spectrum_index=i,covered=True,
                spectrum_content_sha256=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                adduct='[M+H]+',instrument_token='QTOF',ce_units='eV',
                prediction_mode='single_ce',ce_bucket=[20.,40.,60.,20.][i])
            coverage.append(event)
            for candidate in identities:
                scores.append(dict(event,candidate_smiles=candidate,candidate_official_identity=identities[candidate],
                    score=values[candidate][i],status='scored'))
        return items,identities,coverage,scores

    def test_support_is_new_information_and_exact_duplicates_do_not_add_votes(self):
        fixture=self.fixture();rows,audit=feature.derive(*fixture,lambda _: 'same_formula')
        rates={row['candidate_smiles']:row['candidate_support_rate'] for row in rows}
        self.assertAlmostEqual(rates['A'],4/6);self.assertAlmostEqual(rates['B'],5/6)
        self.assertEqual(audit['winner_conflicts']['original_mean_winner_sets_disjoint'],1)
        more=self.fixture(duplicate=True);extra,dup_audit=feature.derive(*more,lambda _:'same_formula')
        self.assertEqual(rates,{row['candidate_smiles']:row['candidate_support_rate'] for row in extra})
        self.assertEqual(dup_audit['counts']['duplicate_spectrum_aliases'],1)
        self.assertEqual(dup_audit['groups'][0]['ce_groups'],3)

    def test_missing_evidence_and_duplicate_identities_are_not_fake_defeats(self):
        fixture=self.fixture()
        for event in fixture[3]:
            if event['candidate_smiles']=='A' and event['spectrum_index'] in (1,2):
                event.update(status='prediction_missing',score=None)
        rows,audit=feature.derive(*fixture,lambda _:'same_formula')
        self.assertTrue(all(row['candidate_support_rate'] is None for row in rows))
        self.assertEqual(audit['groups'][0]['ineligible_reason'],'fewer_than_two_common_finite_ce_groups')
        fixture=self.fixture();fixture[1]['B']=fixture[1]['A']
        for event in fixture[3]:event['candidate_official_identity']=fixture[1][event['candidate_smiles']]
        rows,audit=feature.derive(*fixture,lambda _:'same_formula')
        self.assertEqual(audit['groups'][0]['ineligible_reason'],'duplicate_official_identity')

    def test_metadata_conflict_excludes_duplicate_cluster_and_incomplete_trace_fails(self):
        fixture=self.fixture(duplicate=True);fixture[2][3]['ce_bucket']=40.
        for event in fixture[3]:
            if event['spectrum_index']==3:event['ce_bucket']=40.
        rows,audit=feature.derive(*fixture,lambda _:'same_formula')
        self.assertEqual(audit['groups'][0]['excluded_spectrum_clusters']['duplicate_metadata_conflict'],1)
        self.assertEqual(audit['groups'][0]['ce_groups'],2)
        fixture[3].pop()
        with self.assertRaises(ValueError):feature.derive(*fixture,lambda _:'same_formula')
