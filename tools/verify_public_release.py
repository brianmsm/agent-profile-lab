#!/usr/bin/env python3
"""Fail-closed offline audit of the approved rights-scoped public release bytes.

Does not depend on private source captures, network calls or a Git repository.
Only validates the facts this rights-scoped release can prove.
"""
from __future__ import annotations
from pathlib import Path
from collections import Counter
import csv,gzip,hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from dashboard_delivery import unpack_core
from prepare_data import load_decisions,partition_decisions
from harness_contracts import load_harnesses
from reviewed_git_anchors import PUBLIC_BFCL_APPROVED,PUBLIC_BFCL_ROWS_SHA256,reviewed_anchor,reviewed_blob
from strict_data_formats import json_loads_strict

def read(path):return json_loads_strict(path.read_bytes())
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def assert_count(expr,msg):
    if not expr:raise ValueError(msg)

def verify_approved_bfcl_rows(rows: list[dict],root: Path=ROOT) -> dict:
    """Compare *values and identities* to the approved Git blob, not hashes reissued
    with a substituted snapshot. This pins R2 contents until a separate data
    review explicitly approves a new snapshot and trust root.
    """
    edition,anchor=reviewed_anchor(root)
    if edition!='public':raise ValueError('BFCL release anchor requires the public Git edition')
    source=json_loads_strict(reviewed_blob(root,PUBLIC_BFCL_APPROVED,'dashboard/public/data/snapshot.json'))
    approved=source.get('benchmarks')
    if not isinstance(approved,list) or len(approved)!=3241:
        raise ValueError('Approved historical BFCL corpus missing or incomplete')
    canonical=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    expected=canonical(approved)
    if expected!=PUBLIC_BFCL_ROWS_SHA256:raise ValueError('Pinned BFCL audit anchor differs from historic Git content')
    if not isinstance(rows,list) or canonical(rows)!=expected:
        raise ValueError('Public BFCL observation identities, values or metadata differ from independently approved Git corpus')
    return {'count':len(rows),'canonicalSHA256':expected,'approvedCommit':PUBLIC_BFCL_APPROVED,'identity':'independent-Git-blob-comparison-not-editorial-authentication'}

def verify():
    evidence=read(ROOT/'data/public-evidence/release-manifest.json')
    links=read(ROOT/'data/public-evidence/source-links.json')
    snapshot=read(ROOT/'dashboard/public/data/snapshot.json')
    rights_policy=read(ROOT/'policies/public-evidence-redistribution.json')
    assert_count(rights_policy['schemaVersion']==1 and rights_policy['numericSourceIds']==['BR-BFCL-DATA'],
                 'Unreviewed publisher data added to the public numeric allowlist')
    bfcl_rights=rights_policy['reviewedSource']['BR-BFCL-DATA']
    assert_count(bfcl_rights['license']=='Apache-2.0' and
                 bfcl_rights['releaseDecision']=='cleared-with-attribution-and-original-source-metadata',
                 'No explicit licensed BFCL score data redistribution decision')
    assert_count(any('berkeley-function-call-leaderboard/README.md' in item['url']
                 for item in bfcl_rights['scoreRedistributionEvidence']),
                 'BFCL statistical data permission source not recorded')
    assert_count(evidence['sourcePolicySHA256']==digest(ROOT/'policies/public-evidence-redistribution.json'),
                 'Public source rights policy changed without release manifest approval')
    assert_count(evidence['schemaVersion']==1 and evidence['publicCandidateOnly'] is False and evidence['publicationAllowed'] is True and
                 evidence.get('releaseRepository')=='https://github.com/brianmsm/agent-profile-lab',
       'A published release requires explicit owner approval and a fixed public repository target')
    assert_count(len(snapshot['meta'])==evidence['publicProfileCount']==2496,'Source profiles were omitted or added')
    assert_count(len(snapshot['routeDetails'])==2496,'Detailed routing index was truncated')
    assert_count(snapshot['stats']['rows']==33414,'Native role source count changed')
    assert_count(sum(len(r) for r in snapshot['routeDetails'].values())==33414,'Detailed role slots changed')
    assert_count(sum(r['enabled'] for routes in snapshot['routeDetails'].values() for r in routes.values())==30918,
       'Enabled primary role count changed')
    assert_count(len(snapshot['strategies'])==160,'Stored baseline supplemental strategies were altered')
    assert_count(canonical(snapshot['routeDetails'])==evidence['originalProfileRoutesSHA256']==
                 evidence['publicProfileRoutesSHA256'],'Source reference routes differ from original private decisions')
    assert_count(canonical(snapshot['meta'])==evidence['originalProfileMetaSHA256']==
                 evidence['publicProfileMetaSHA256'],'Reference profile metadata differs from original source')
    amendment=evidence.get('metadataAmendment',{})
    assert_count(amendment.get('path')=='policies/source-metadata-amendment.json' and
                 amendment.get('kind')=='descriptive-source-amendment',
                 'A source metadata change requires a reviewed descriptive amendment')
    amendment_path=ROOT/amendment['path']
    assert_count(digest(amendment_path)==amendment.get('sha256'),'Metadata amendment receipt changed')
    amendment_receipt=read(amendment_path)
    assert_count(amendment_receipt['originalSourceManifestSHA256']==evidence['originalSourceManifestSHA256'],
                 'Original source-manifest history must be preserved')
    assert_count(digest(ROOT/'data/assignment-shards/manifest.json')==evidence['sourceManifestSHA256']==
                 amendment_receipt['currentSourceManifestSHA256'],'Amended source manifest differs from reviewed bytes')
    from verify_source_amendment import verify_amendment
    amendment_result=verify_amendment(ROOT)
    assert_count(amendment_result['nonlabelFieldsPreserved'] and amendment_result['nativeFilesByteIdentical']==3744,
                 'Source metadata amendment changed model selections or native outputs')
    decisions,_=load_decisions(ROOT)
    active,retired=partition_decisions(decisions,load_harnesses(ROOT))
    assert_count(len(decisions)==49638 and len(active)==33414 and len(retired)==16224,
                 'A source decision disappeared, was activated or was retired unexpectedly')
    for relative in ['LICENSE','README.md','THIRD_PARTY_NOTICES.md',
      'licenses/GORILLA_APACHE_2.0_LICENSE.txt','docs/EVIDENCE_AND_RIGHTS.md',
      'docs/REPRODUCIBILITY.md','docs/RELEASE_CHECKLIST.md','docs/DEVELOPMENT_PROVENANCE.md']:
        assert_count((ROOT/relative).is_file(),'Required public release documentation is missing: '+relative)
    license_text=(ROOT/'LICENSE').read_text()
    assert_count('MIT License' in license_text and 'Brian Peña Calero' in license_text,
                 'An explicit author-approved MIT source license is required')
    apache=(ROOT/'licenses/GORILLA_APACHE_2.0_LICENSE.txt').read_text()
    assert_count('Apache License' in apache and 'Version 2.0' in apache,
                 'Gorilla upstream attribution license missing')
    refs=read(ROOT/'policies/selection-evidence.json')
    assert_count(len(refs['observations'])==evidence['referenceOnlyReviewedRecipeEvidence']==42,
                 'Review evidence references were lost')
    assert_count(all(r.get('value') is None and r.get('referenceOnly') is True and
                 r.get('provenance')=='external-link-only' for r in refs['observations'].values()),
                 "Publisher numerical values from selection recipes have been redistributed")
    source_count=Counter(r['sourceId'] for r in refs['observations'].values())
    assert_count(source_count=={'AA':19,'FCDATA':23},'Original reviewed recipe evidence identity was changed')
    for r in refs['observations'].values():
        assert_count(r['sourceUrl'].startswith('https://'),'Reviewed external source is not a direct HTTPS link')
        if r['sourceId']=='AA':
            assert_count(r['sourceUrl'].startswith('https://artificialanalysis.ai/models/'),
                         'Artificial Analysis exact publisher model link missing')
    recipes=read(ROOT/'policies/selection-candidates.json')
    approval=read(ROOT/'policies/selection-approval.json')
    assert_count(recipes['evidenceSha256']==digest(ROOT/'policies/selection-evidence.json')==
                 approval['evidenceSha256'],'Selection-evidence source hashes are inconsistent')
    assert_count(digest(ROOT/'policies/selection-candidates.json')==approval['policySha256'],
                 'Reviewed candidate recipes and their approval have diverged')
    for path,expected in approval['inputSha256'].items():
        assert_count(digest(ROOT/path)==expected,'Reviewed candidate input changed: '+path)
    included=snapshot['benchmarks']
    approved_bfcl=verify_approved_bfcl_rows(included,ROOT)
    assert_count(len(included)==evidence['publicNumericCells']==3241,'Numeric cell inclusion changed')
    assert_count({r['sourceId'] for r in included}=={'BR-BFCL-DATA'},'Unapproved numerical publisher data present')
    for row in included:
        url=row['source'].lower()
        assert_count('artificialanalysis.ai' not in url and 'slopalytics.com' not in url and
                     row['value'] is not None,'AA or empty score incorrectly redistributed')
    assert_count(evidence['originalEvidenceCells']==72590 and
                 evidence['externalLinkOnlyCellsNotRedistributed']==69349,
                 'Evidence scope totals changed without a source policy review')
    assert_count(len(links['providerModelLinks'])==evidence['externalAAmodelPages']==853,
                 'Direct Artificial Analysis model references changed')
    assert_count(len(links['sourceLinks'])==evidence['clickableExternalSourceLinks']==315,
                 'Registered public source links changed')
    assert_count(all(row['url']=='https://artificialanalysis.ai/models/'+row['slug'] and
                 set(row)=={'model','slug','url','provider','status'} for row in links['providerModelLinks']),
                 'External-only model reference contains non-link observation fields')
    cov=snapshot['sourceCoverage']
    assert_count(cov['totals']=={'sources':322,'artifacts':0,'benchmarks':3241,'excluded':0} and evidence['sourceReferences']==322,
                 'Public source coverage falsely counts missing underlying artifacts')
    assert_count(any(s['id']=='AA' and s['benchmarkCount']==0 and
                     s['status']=='context-only' for s in cov['sources']),
                 'Artificial Analysis is not explicitly marked link-only')
    assert_count(not (ROOT/'evidence').exists() and not (ROOT/'sources').exists(),
                 'Raw research captures or historical private source registries present')
    # A fresh Git repository will naturally have a .git directory when CI runs.
    # The build process itself copies no VCS metadata from the private source.
    # Review initial Git history separately before the first public push.
    assert_count(not (ROOT/'dashboard/tests/fixtures/typed-evidence.json').exists(),
                 'Historical AA numeric benchmark test fixture leaked to public release')
    assert_count(all((ROOT/rel).is_file() for rel in
                 ['tests/vendor/gentle-shell-4.0.0/LICENSE','dashboard/src/ExternalEvidenceReferences.tsx']),
                 'Attribution or external-linked view missing')
    static=read(ROOT/'policies/nan-static-approval.json')
    for path,expected in static['inputSha256'].items():
        assert_count(digest(ROOT/path)==expected and
                     snapshot['access']['inputSha256'].get(path)==expected,
                     'Static NaN model/workload approval mismatch: '+path)
    for path in ['policies/selection-candidates.json','policies/selection-evidence.json']:
        assert_count(snapshot['access']['inputSha256'][path]==digest(ROOT/path),
                     'Browser selection-compatibility hash is stale')
    transport=read(ROOT/'dashboard/public/data/delivery.json')
    source=ROOT/'dashboard/public/data/snapshot.json'
    assert_count(transport['format']=='apl.delivery' and
                 transport['sourceSha256']==digest(source),'Delivery source integrity mismatch')
    contents={}
    for name in ('core','evidence'):
        item=transport['parts'][name]
        assert_count(item['path']=='chunks/'+name+'-'+item['sha256']+'.json.gz',
                     'Unsafe or stale delivery path')
        file=source.parent/item['path'];blob=file.read_bytes()
        assert_count(len(blob)==item['bytes'] and hashlib.sha256(blob).hexdigest()==item['sha256'],
                     'Compressed delivery content changed')
        raw=gzip.decompress(blob)
        assert_count(len(raw)==item['decodedBytes'],'Decompressed delivery size changed')
        contents[name]=json_loads_strict(raw)
    assert_count({**unpack_core(contents['core']),**contents['evidence']}==snapshot,
                 'Content-addressed public delivery is not lossless')
    return {'profileReferences':2496,'activeRoleAssignments':33414,
            'historicRetiredDecisions':16224,'storedBaselineStrategies':160,
            'numericPublishedBFCL':3241,'bfclPinnedSHA256':approved_bfcl['canonicalSHA256'],'externalNumericCellsNotRedistributed':69349,
            'reviewCitationsReferenceOnly':42,'AAmodelSourceLinks':853,'sourceRegistryLinks':322,
            'MIT':True,'ApacheAttribution':True,
            'byteIdenticalSourceAssignments':False,'sourceMetadataAmended':True,
            'originalNonlabelSourceFieldsPreserved':True,'canonicalProfileRoutesPreserved':True,
            'AAvaluesRedistributed':0,'rawCapturesRedistributed':0,
            'browserTransport':'verified-lossless-SHA256','inferencesSent':0,
            'githubPublicationPerformed':False}

if __name__=='__main__':print(json.dumps(verify(),indent=2))
