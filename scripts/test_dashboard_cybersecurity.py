"""Consumer-visible evidence boundaries; no snapshots or benchmark execution."""
from copy import deepcopy
import unittest
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from dashboard_cybersecurity import (
    EVIDENCE_BOUNDARY, build_cybersecurity_evidence,
    validate_cybersecurity_evidence, validate_evidence_boundary,
)
from dashboard_cybersecurity_catalog import CATALOG_SELECTORS
from dashboard_source_coverage import family_area_coverage, validate_capture_reference_identity
from dashboard_cybersecurity_reconciliation import build_reconciliation, validate_reconciliation


def catalog():
    result = {key: {'selector': selector} for key, selector in CATALOG_SELECTORS.items()}
    result['cc_ultra'] = {'selector': 'commandcode/xiaomi/mimo-v2.6-pro-ultraspeed'}
    result['unused'] = {'selector': 'local/unmeasured'}
    return result


def row(model='MiMo-V2.5 Pro', value=0, result_type='vendor', benchmark='MiMo Cyber Bench'):
    return dict(model=model, family='supplemental', benchmark=benchmark, value=value,
                unit='%', effort='not stated', source='https://publisher.example/model-card',
                sourceId='PUBLISHER', provenance=f'card#table/{model}/{benchmark}',
                context={'cybersecurity': dict(resultType=result_type, benchmarkVersion=None,
                                              evaluationDate=None, captureDate='2026-10-02',
                                              taskDenominator=None, attemptBudget=None,
                                              settings='Publisher aggregate; route harness unknown.',
                                              limitations=['Capture date is not the evaluation date.'])})


class CybersecurityEvidenceGuardrails(unittest.TestCase):
    def test_versions_and_candidate_aliases_do_not_inherit_exact_evidence(self):
        rows = [row(), row('DS-V4.1-Flash'), row('GLM-5.3'), row('MiMo-V2.6 Pro'),
                row('Claude Opus 5'), row('GPT-6 Sol')]
        evidence = build_cybersecurity_evidence(rows, catalog())
        coverage = {item['catalogKey']: item for item in evidence['catalogCoverage']}
        self.assertEqual(coverage['nan_mimo']['state'], 'candidate-alias-only')
        self.assertEqual(coverage['nan_ds']['state'], 'candidate-alias-only')
        self.assertEqual(coverage['go_ds']['state'], 'measured-result')
        for key in ('go_glm', 'cc_glm', 'nan_glm', 'cc_ultra', 'cl_opus', 'oa_sol61'):
            self.assertEqual(coverage[key]['state'], 'no-mapped-result')
        self.assertEqual(coverage['go_glmf']['state'], 'measured-result')
        self.assertEqual(coverage['oa_sol']['state'], 'measured-result')
        self.assertEqual(evidence['results'][4]['catalogMatches'], [])

    def test_published_zero_unknown_metadata_and_editorial_are_distinct(self):
        rows = [row(), row('GPT-6.1 Sol', 90, 'editorial', 'BridgeBench Security')]
        evidence = build_cybersecurity_evidence(rows, catalog())
        result = evidence['results'][0]
        self.assertEqual(result['value'], 0)
        self.assertIsNone(result['taskDenominator'])
        self.assertIsNone(result['evaluationDate'])
        self.assertIsNone(result['attemptBudget'])
        coverage = {item['catalogKey']: item for item in evidence['catalogCoverage']}
        self.assertEqual(coverage['oa_sol61']['state'], 'editorial-only')
        self.assertEqual(coverage['unused']['resultIds'], [])
        with self.assertRaisesRegex(ValueError, 'missing is not zero'):
            build_cybersecurity_evidence([row(value=None)], catalog())

    def test_graph_omissions_score_inference_and_route_escalation_are_rejected(self):
        rows = [row(), row('MiMo-V2.6 Flash', 95.1)]
        sources = {'sources': [{'id': 'PUBLISHER'}]}
        evidence = build_cybersecurity_evidence(rows, catalog(), sources)
        mutations = []
        missing_key = deepcopy(evidence)
        missing_key['catalogCoverage'].pop()
        mutations.append(missing_key)
        stale_link = deepcopy(evidence)
        stale_link['catalogCoverage'][0]['resultIds'] = [evidence['results'][0]['id']]
        mutations.append(stale_link)
        promoted_alias = deepcopy(evidence)
        promoted_alias['results'][0]['catalogMatches'][0]['relationship'] = 'published-model'
        mutations.append(promoted_alias)
        escalated = deepcopy(evidence)
        escalated['results'][1]['routeValidation'] = 'validated'
        mutations.append(escalated)
        wrong_score = deepcopy(evidence)
        wrong_score['results'][0]['value'] = 40
        mutations.append(wrong_score)
        wrong_source = deepcopy(evidence)
        wrong_source['results'][0]['sourceUrl'] = 'https://other.example/card'
        mutations.append(wrong_source)
        for invalid in mutations:
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_cybersecurity_evidence(invalid, rows, catalog(), sources)
        with self.assertRaisesRegex(ValueError, 'sourceCoverage'):
            build_cybersecurity_evidence(rows, catalog(), {'sources': []})

    def test_annotations_include_exploit_metrics_without_claiming_old_absence(self):
        old = row(benchmark='CyberGym')
        old.pop('context')
        annotated = row(benchmark='SEC Bench Pro')
        exploit = row(benchmark='ExploitGym')
        coverage = family_area_coverage([old, annotated, exploit])
        self.assertEqual(coverage['supplemental']['cybersecurity'], 'ExploitGym; SEC Bench Pro')
        legacy = family_area_coverage([old])['supplemental']['cybersecurity']
        self.assertIn('no concluye ausencia', legacy)
        self.assertNotIn('Sin métricas específicas incorporadas', legacy)

    def test_typed_boundary_rejects_absence_or_efficacy_and_keeps_explanation_optional_wording(self):
        contract = dict(evidenceBoundary=deepcopy(EVIDENCE_BOUNDARY), evidenceNote='Published aggregates do not calibrate Apps-derived routes.')
        validate_evidence_boundary(contract)
        for field, misleading in (('publishedEvidence', 'no-benchmarks'),
                                  ('routeCalibration', 'validated'),
                                  ('validationMeaning', 'efficacy-established'),
                                  ('routingBasis', 'benchmark-selected')):
            invalid = deepcopy(contract)
            invalid['evidenceBoundary'][field] = misleading
            with self.assertRaises(ValueError):
                validate_evidence_boundary(invalid)
        with self.assertRaises(ValueError):
            validate_evidence_boundary({'evidenceNote': 'No benchmarks or calibration.'})

    def test_metadata_missing_dates_and_protocol_are_not_invented(self):
        for field, invalid in (('captureDate', '2026-02-30'), ('evaluationDate', '2026-10-03'),
                               ('taskDenominator', 0), ('attemptBudget', ''), ('limitations', [])):
            malformed = row()
            malformed['context']['cybersecurity'][field] = invalid
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    build_cybersecurity_evidence([malformed], catalog())
        duplicate = row()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            build_cybersecurity_evidence([duplicate, deepcopy(duplicate)], catalog())


class CybersecurityReconciliationGuardrails(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.raw = self.root / 'card.raw'
        self.raw.write_bytes(b'published aggregate and limitations')
        self.receipt = self.root / 'receipt.json'
        self.receipt.write_text(json.dumps(dict(requestedUrl='https://publisher.example/model-card',
            finalUrl='https://publisher.example/model-card', capturedAt='2026-10-02T12:00:00+00:00',
            httpStatus=200, path='card.raw', sha256=hashlib.sha256(self.raw.read_bytes()).hexdigest())))
        self.coverage = dict(sources=[dict(id='PUBLISHER', url='https://publisher.example/model-card',
            artifacts=['card.raw', 'receipt.json'])], artifacts=[
            dict(path=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            for path in (self.raw, self.receipt)])
        self.catalog = {'model': {'selector': 'local/model'}}
        observation = row()
        observation['provenance'] = 'card.raw#table'
        self.results = build_cybersecurity_evidence([observation], self.catalog, self.coverage)['results']
        self.seed = dict(schemaVersion=1, asOf='2026-10-03',
            scope='Corpus público archivado delimitado; sin calibración de rutas.',
            searchBoundary='Publicaciones exactas revisadas hasta 2026-10-03.',
            reviewedSources=[dict(sourceId='PUBLISHER', sourceUrl=observation['source'],
                captureDate='2026-10-02', receiptPath='receipt.json', sections=['card.raw#table'],
                catalogKeys=['model'], limitations=['Sólo agregados publicados.'])],
            dispositions=[dict(sourceId='PUBLISHER', publishedModel=None, benchmark='Other track',
                metric='Other track', status='unresolved', reason='No numeric data in reviewed section.',
                locator='card.raw#table')],
            catalogReview=[dict(catalogKey='model', sourceIds=['PUBLISHER'],
                conclusion='Reviewed exact model publication; no route equivalence.')])

    def build(self):
        return build_reconciliation(self.seed, self.results, self.catalog, self.coverage, self.root)

    def test_zero_result_has_one_link_and_open_gap_does_not_force_closure(self):
        reconciliation = self.build()
        incorporated = [entry for entry in reconciliation['entries'] if entry['status'] == 'incorporated']
        self.assertEqual([entry['resultIds'] for entry in incorporated], [[self.results[0]['id']]])
        self.assertEqual(self.results[0]['value'], 0)
        self.assertEqual(reconciliation['closure'], 'open')
        self.seed['dispositions'][0]['status'] = 'context-only'
        self.assertEqual(self.build()['closure'], 'reconciled-corpus')

    def test_tampered_counts_closure_and_result_link_are_rejected(self):
        for change in ('counts', 'closure', 'result-link', 'omission', 'duplicate'):
            with self.subTest(change=change):
                reconciliation = self.build()
                if change == 'counts':
                    reconciliation['counts']['incorporated'] += 1
                elif change == 'closure':
                    reconciliation['closure'] = 'reconciled-corpus'
                elif change == 'result-link':
                    reconciliation['entries'][0]['resultIds'] = ['cyber-forged']
                elif change == 'omission':
                    reconciliation['entries'].pop(0)
                else:
                    reconciliation['entries'].append(deepcopy(reconciliation['entries'][0]))
                with self.assertRaises(ValueError):
                    validate_reconciliation(reconciliation, self.results, self.catalog, self.coverage, self.root)

    def test_capture_bytes_and_source_association_must_be_verified(self):
        self.raw.write_bytes(b'tampered after receipt')
        with self.assertRaises(ValueError):
            self.build()
        self.raw.write_bytes(b'published aggregate and limitations')
        self.coverage['sources'][0]['artifacts'].remove('receipt.json')
        with self.assertRaises(ValueError):
            self.build()

    def test_catalog_coverage_and_reviewed_sections_fail_closed(self):
        for change in ('missing-model', 'unknown-model', 'unknown-source', 'unreviewed-section'):
            with self.subTest(change=change):
                seed = deepcopy(self.seed)
                if change == 'missing-model':
                    seed['catalogReview'] = []
                elif change == 'unknown-model':
                    seed['reviewedSources'][0]['catalogKeys'] = ['unknown']
                elif change == 'unknown-source':
                    seed['catalogReview'][0]['sourceIds'] = ['unknown']
                else:
                    seed['dispositions'][0]['locator'] = 'unreviewed.raw#table'
                with self.assertRaises(ValueError):
                    build_reconciliation(seed, self.results, self.catalog, self.coverage, self.root)

    def test_pending_catalog_review_is_not_fabricated_linkage(self):
        self.seed['catalogReview'][0].update(sourceIds=[], reviewState='pending')
        self.seed['dispositions'][0]['status']='context-only'
        self.assertEqual(self.build()['closure'],'open')
        self.seed['catalogReview'][0]['sourceIds']=['PUBLISHER']
        with self.assertRaisesRegex(ValueError,'Pending review'):
            self.build()

    def test_failed_http_capture_cannot_back_numeric_result(self):
        receipt = json.loads(self.receipt.read_text())
        receipt['httpStatus'] = 403
        self.receipt.write_text(json.dumps(receipt))
        self.coverage['artifacts'][1]['sha256'] = hashlib.sha256(self.receipt.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):
            self.build()

    def test_archived_seed_cannot_be_replaced_by_an_unhashed_memory_claim(self):
        (self.root / 'data').mkdir()
        seed_file = self.root / 'data/cybersecurity-reconciliation.json'
        seed_file.write_text(json.dumps(self.seed))
        self.coverage['artifacts'].append(dict(path='data/cybersecurity-reconciliation.json',
            sha256=hashlib.sha256(seed_file.read_bytes()).hexdigest()))
        original = self.build()
        validate_reconciliation(original, self.results, self.catalog, self.coverage, self.root)
        self.seed['dispositions'][0]['reason'] = 'Different unarchived claim.'
        with self.assertRaises(ValueError):
            self.build()

    def test_reviewed_capture_alone_does_not_close_unclassified_source(self):
        self.seed['dispositions'] = []
        with self.assertRaises(ValueError):
            build_reconciliation(self.seed, [], self.catalog, self.coverage, self.root)

    def test_capture_label_and_url_hash_identities_do_not_allow_origin_splicing(self):
        reference = dict(name='PUBLISHER_CAPTURE', url='https://publisher.example/model-card')
        receipt = json.loads(self.receipt.read_text())
        url_hash = hashlib.sha256(reference['url'].encode()).hexdigest()[:20]
        for identity in (reference['name'], 'URL-' + url_hash, url_hash):
            receipt['sourceId'] = identity
            validate_capture_reference_identity(reference, receipt)
            forged = dict(receipt, requestedUrl='https://different.example/model-card')
            with self.assertRaises(ValueError):
                validate_capture_reference_identity(reference, forged)
        receipt['sourceId'] = 'different-publisher'
        with self.assertRaises(ValueError):
            validate_capture_reference_identity(reference, receipt)

    def test_failed_source_keeps_accessibility_open_without_fabricating_unrelated_gaps(self):
        receipt = json.loads(self.receipt.read_text())
        receipt['httpStatus'] = 403
        self.receipt.write_text(json.dumps(receipt))
        self.coverage['artifacts'][1]['sha256'] = hashlib.sha256(self.receipt.read_bytes()).hexdigest()
        self.results = []
        contextual = dict(self.seed['dispositions'][0], benchmark='Unrelated publication context',
                          metric='Unrelated publication context', status='context-only',
                          reason='Inventoried as unrelated context; not a pending capability metric.')
        self.seed['dispositions'].append(contextual)
        reconciled = self.build()
        self.assertEqual(reconciled['counts']['unresolved'], 1)
        self.assertEqual(reconciled['counts']['context-only'], 1)
        self.assertEqual(reconciled['closure'], 'open')
        self.seed['dispositions'] = [dict(contextual, status='excluded')]
        with self.assertRaises(ValueError):
            self.build()


if __name__ == '__main__':
    unittest.main()
