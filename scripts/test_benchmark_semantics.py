from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import json,unittest
from benchmark_io import ROOT,page,table_number,captures,js_literal_object
from benchmark_semantics import build_semantics,metric_kind,model_link,typed_family_coverage
from normalize_reviewed_benchmarks import Corpus,normalize_frontier,normalize_cards,normalize_additional,normalize_aa,normalize_remaining_tables,normalize_harnessrank

class SemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=Corpus();normalize_frontier(cls.c);normalize_cards(cls.c)
        cls.links=json.loads((ROOT/'catalog/benchmark-model-links.json').read_text())
        cls.rows,cls.registry=build_semantics(cls.c.rows,{},ROOT)
    def row(self,**updates):return {'model':'Claude Haiku 5.5','family':'test','benchmark':'score','value':1.2,'unit':'%','effort':'max','source':'https://source.example','sourceId':'FCDATA','date':'2026-10-10','provenance':'source#/cell','methodology':'','note':'','context':{},**updates}
    def test_strict_table_parser_rejects_prose_booleans_absence(self):
        for value in ['not measured','N/A','-','true','Claude 5.5','1 2','~30%','1/20']:
            self.assertIsNone(table_number(value))
        self.assertEqual(table_number('.775'),(.775,None));self.assertEqual(table_number('1,200.00'),(1200.,None))
    def test_uncertainty_is_not_relabelled_as_another_score(self):self.assertEqual(table_number('54.31 ± 1.41'),(54.31,'± 1.41'))
    def test_html_script_not_executed_or_accepted_as_table_data(self):
        p=page('<script>throw Error("no");</script><table><tr><td>2.0</td></tr></table>');self.assertEqual(p.tables,[[['2.0']]]);self.assertNotIn('throw',p.text)
    def test_unknown_kind_not_promoted(self):self.assertEqual(metric_kind(self.row(benchmark='uninterpreted thing'),'uncatalogued'),('unclassified','unknown'))
    def test_slopalytics_mirror_is_a_typed_index_but_still_ineligible(self):
        mirror=self.row(benchmark='AA mirror — Intelligence index',unit='Artificial Analysis',
            provenance='evidence/slopalytics/SLOPALYTICS_AA_SNAPSHOT_2026-10-02.json#/models/0/intelligence',
            methodology='Slopalytics AA mirror (not primary/independent evaluation)',
            sourceId='URL-8cde042f42d2d2e566df',model='unknown-producer-model')
        self.assertEqual(metric_kind(mirror,'uncatalogued'),('index','higher'))
        rows,registry=build_semantics([mirror],{},ROOT)
        self.assertEqual(rows[0]['measurement']['kind'],'index')
        self.assertIn('opaque-protocol',rows[0]['measurement']['issueIds'])
        self.assertFalse(rows[0]['measurement']['decisionEligible'])
        self.assertIsNone(rows[0]['measurement']['modelId'])
        generic={**mirror,'methodology':'unrelated'}
        self.assertEqual(metric_kind(generic,'uncatalogued'),('unclassified','unknown'))
    def test_tokens_and_latency_are_not_capability(self):
        self.assertEqual(metric_kind(self.row(unit='tokens/task'),'frontiercode')[0],'tokens')
        self.assertEqual(metric_kind(self.row(unit='seconds/task'),'frontiercode')[0],'duration')
    def test_restricted_variant_not_inherited(self):
        for label in ['GPT-6 Sol (Daybreak Blue, max)','Claude Opus 5.5 (CVP)','Qwen Flash Maybe']:
            self.assertIsNone(model_link(self.row(model=label),self.links)[0])
    def test_qwen_flash_next_is_only_a_candidate(self):
        m,relation,ids=model_link(self.row(model='Qwen3.8-Flash-Next'),self.links)
        self.assertIsNone(m);self.assertEqual(relation,'candidate');self.assertEqual(ids,['qwen:qwen3.8-flash'])
    def test_fifty_new_frontier_haiku_cells_not_fifty_trials(self):
        rows=[r for r in self.rows if r['model']=='Claude Haiku 5.5' and r['sourceId']=='FCDATA']
        self.assertEqual(len(rows),50);self.assertEqual(len({r['measurement']['evaluationId'] for r in rows}),10)
    def test_frontier_score_and_cost_join_but_not_different_efforts(self):
        rows=[r for r in self.rows if r['model']=='Claude Haiku 5.5' and r['sourceId']=='FCDATA']
        scores=[r for r in rows if r['measurement']['kind']=='capability'];costs=[r for r in rows if r['measurement']['kind']=='cost']
        self.assertTrue(all(sum(c['measurement']['costLinkId']==r['measurement']['costLinkId'] for c in costs)==1 for r in scores))
        self.assertEqual(len({r['measurement']['costLinkId'] for r in costs}),10)
    def test_offline_and_full_partial_and_strict_never_collapse(self):
        rows=[r for r in self.rows if 'OSWorld' in r['benchmark'] and r['model']=='Claude Sonnet 5.5']
        self.assertEqual(len({r['measurement']['metricId'] for r in rows}),4)
        self.assertEqual(len({r['measurement']['protocolId'] for r in rows}),4)
        self.assertEqual({self.registry['protocols'][r['measurement']['protocolId']]['tasks'] for r in rows},{82,108})
    def test_capture_is_not_evaluation_date(self):
        protocols=[p for p in self.registry['protocols'].values() if p['sourceId']=='FCDATA']
        self.assertTrue(all(p['evaluationDate'] is None and p['capturedAt'].startswith('2026-10-10') for p in protocols))
    def test_repeated_capture_supersedes_not_independent(self):
        old=deepcopy(self.c.rows[0]);old['date']='2026-10-02';old['provenance']='legacy#/v1/data/'+old['model']+'/low/main/correct';old['context']['measurementSpec'].pop('captureId');old['context']['measurementSpec']['version']='test-shared'
        new=deepcopy(old);new['date']='2026-10-10';new['provenance']='new#/same-record'
        rows,registry=build_semantics([old,new],{},ROOT)
        self.assertEqual(rows[0]['measurement']['scope'],'superseded');self.assertFalse(rows[0]['measurement']['decisionEligible']);self.assertTrue(registry['revisions'][0]['notAnIndependentTrial'])
    def test_harnessrank_exact_historical_aggregates_with_source_local_cost_pairs(self):
        c=Corpus();normalize_harnessrank(c)
        self.assertEqual(len(c.rows),44)
        self.assertEqual({r['model'] for r in c.rows},{'gpt-5.5'})
        self.assertEqual({r['context']['measurementSpec']['protocol']['harnessVersion'] for r in c.rows},
            {'0.79.6','16.1.15','1.17.9','0.130.0'})
        score=[r for r in c.rows if r['context']['measurementSpec']['metricKey']=='pass-rate']
        self.assertEqual(len(score),4)
        self.assertTrue(all(0<=r['value']<=1 for r in score))
        self.assertTrue(all('harnessrank-historical-harness' in r['context']['measurementSpec']['issueIds'] for r in score))
        normalized,registry=build_semantics(c.rows,{},ROOT)
        self.assertEqual(len(normalized),44)
        self.assertTrue(all(not r['measurement']['decisionEligible'] for r in normalized))
        self.assertTrue(registry['suites']['harnessrank']['lifecycle']['normalized'])
        self.assertTrue(registry['suites']['harnessrank']['lifecycle']['captured'])
        costs=[r for r in normalized if r['measurement']['kind']=='cost']
        self.assertEqual(len(costs),4)
        self.assertTrue(all(c['measurement']['costLinkId'] for c in costs))
    def test_harnessrank_parser_rejects_embedded_code_without_execution(self):
        c=Corpus()
        from unittest.mock import patch as patcher
        source=(ROOT/c.captures['harnessrank-aggregates-20261012']['path']).read_text()
        original=c.raw
        with patcher.object(c,'raw',return_value=source+';evil()'):
            with self.assertRaisesRegex(ValueError,'wrapper'):normalize_harnessrank(c)
        self.assertEqual(c.rows,[])
    def test_source_capture_hashes_verified(self):self.assertGreaterEqual(len(captures()),43)
    def test_function_references_are_real_policy_ids(self):
        functions=json.loads((ROOT/'policies/functions.json').read_text())['functions']
        for s in self.registry['suites'].values():self.assertFalse(set(s['policyFunctionIds'])-functions.keys())
    def test_manual_fetch_is_never_in_project_rebuild(self):
        text=(ROOT/'scripts/check_project.py').read_text();self.assertNotIn('capture_benchmark_sources',text);self.assertNotIn('--fetch',text)
    def test_no_network_during_semantic_projection(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('Network during offline build')):build_semantics([self.c.rows[0]],{},ROOT)
    def test_bfcl_and_hashline_real_adapters_not_placeholder(self):
        c=Corpus();normalize_additional(c)
        self.assertGreater(sum(r['sourceId']=='BR-BFCL-DATA' for r in c.rows),3000)
        self.assertEqual(sum(r['sourceId']=='BR-HASHLINE' for r in c.rows),60)
    def test_aa_issue_metadata_does_not_leak_between_sibling_cells(self):
        c=Corpus();normalize_aa(c)
        rows=[r for r in c.rows if r['context'].get('slug')=='claude-haiku-5-5']
        by_name={r['benchmark']:r for r in rows}
        self.assertIn('haiku-aa-cost-provisional',by_name['AA intelligenceIndexCostPerTask/cost/total']['context']['issueIds'])
        self.assertIn('haiku-aa-automation-prerelease',by_name['AA automationBenchPartialScore']['context']['issueIds'])
        self.assertEqual(by_name['AA intelligenceIndex']['context']['issueIds'],[])

    def test_literal_dataset_parser_preserves_punctuation_inside_strings(self):
        self.assertEqual(js_literal_object("const data = {name: ',}', x:[true, null, 2,],};",'data'),{'name':',}','x':[True,None,2]})
    def test_literal_dataset_parser_rejects_executable_code(self):
        for text in ['const data = {x: process.exit()};','const data = {x: (()=>3)()};','const data = {x: `interpolated`};','const data = {x: otherVariable};']:
            with self.assertRaises(ValueError):js_literal_object(text,'data')
    def test_interactive_sources_preserve_units_and_conditions(self):
        c=Corpus();normalize_remaining_tables(c)
        by_source={sid:[r for r in c.rows if r['sourceId']==sid] for sid in ['BR-WORKARENA','BR-QWEN','BR-BIRD']}
        self.assertEqual(len(by_source['BR-WORKARENA']),112)
        self.assertEqual(sum(r['context']['measurementSpec']['kind']=='uncertainty' for r in by_source['BR-WORKARENA']),56)
        self.assertEqual(len(by_source['BR-QWEN']),74)
        self.assertTrue(all(r['context']['measurementSpec']['kind']=='unclassified' for r in by_source['BR-QWEN']))
        self.assertEqual(len(by_source['BR-BIRD']),524)
        self.assertEqual({r['context']['measurementSpec']['protocol']['condition'] for r in by_source['BR-BIRD']},{'freeLeaderboardData','stressLeaderboardData'})
        self.assertTrue(all(r['context']['measurementSpec']['protocol']['evaluationDate'] is None for r in by_source['BR-BIRD']))

    def test_coverage_ignores_tokens(self):
        rows=[r for r in self.rows if r['measurement']['kind']=='tokens']
        cov=typed_family_coverage(rows,self.registry)
        self.assertTrue(all('Sin resultados' in text for areas in cov.values() for text in areas.values()))
if __name__=='__main__':unittest.main()
