"""Independent regression: descriptive labels may not contradict canonical IDs."""
import csv,json,unittest
from copy import deepcopy
from metadata_contracts import ROOT,label_contract,validate_labels,expected_labels
from verify_source_amendment import normalized_digest
class Labels(unittest.TestCase):
 def setUp(self):self.contract=label_contract()
 def row(self,domain='research',objective='best',portfolio='nan'):
  r={'profile_id':'synthetic','role':'commit','domain':domain,'objective':objective,'portfolio':portfolio};r.update(expected_labels(r,self.contract));return r
 def test_all_source_rows_and_index(self):
  for p in [ROOT/'data/profile-index.csv',*sorted((ROOT/'data/assignment-shards').glob('*/*.csv'))]:
   with p.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
   validate_labels(rows,self.contract,str(p.relative_to(ROOT)))
 def test_all_domains_and_objectives(self):
  for domain in self.contract['domain_label']:
   for objective in self.contract['objective_label']:validate_labels([self.row(domain,objective)],self.contract,'test')
 def test_empty_or_misleading_labels_fail(self):
  for field in ('domain_label','objective_label','portfolio_label'):
   for wrong in ('','Economía','Apps','unknown'):
    r=self.row();r[field]=wrong
    with self.assertRaises(ValueError):validate_labels([r],self.contract,'test')
 def test_best_alias_is_explicit_not_wrong_objective(self):
  r=self.row();self.assertEqual(r['objective_label'],'Máxima calidad');r['objective_label']='Economía'
  with self.assertRaises(ValueError):validate_labels([r],self.contract,'test')
 def test_unknown_dimension_rejected(self):
  r=self.row();r['domain']='fake'
  with self.assertRaises(ValueError):expected_labels(r,self.contract)
 def test_amendment_cannot_hide_model_effort_id_or_condition_changes(self):
  row={**self.row(),'model':'synthetic/model','thinking':'high','fallback_model':'synthetic/fallback','quality_gate':'explicit permission','profile_context':'original context'}
  for key in ('model','thinking','fallback_model','quality_gate','profile_id','profile_context'):
   changed=deepcopy(row);changed[key]='different'
   self.assertNotEqual(normalized_digest([row]),normalized_digest([changed]),key)
 def test_amendment_excludes_only_descriptive_labels(self):
  row=self.row();changed=deepcopy(row);changed.update(domain_label='',objective_label='',portfolio_label='')
  self.assertEqual(normalized_digest([row]),normalized_digest([changed]))
 def test_validation_is_not_an_implicit_repair(self):
  r=self.row();r['domain_label']='';before=deepcopy(r)
  with self.assertRaises(ValueError):validate_labels([r],self.contract,'test')
  self.assertEqual(r,before)
if __name__=='__main__':unittest.main()
