#!/usr/bin/env python3
"""R3j focal, bounded tri-state security checks; no release authorizations.

All fixtures are synthetic, isolated and independently runnable in public CI.
No trust roots, signing identities or external source rights are created.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from audit_public_distribution import audit_history, inspect_payload, path_reason
from publisher_semantics import js_classify

def decision(reasons: list[str]) -> str:
    if not reasons:return "LEGITIMATE"
    if any("unreviewed" in r or "non-allowlisted" in r for r in reasons):
        return "PROHIBITED"
    return "REVIEW"

JAVASCRIPT=[
    ('assign-return','const r=Object.assign({sourceId:"aa"},{score:97});','PROHIBITED'),
    ('anonymous-spreads','const r={...{sourceId:"aa"},...{score:97}};','PROHIBITED'),
    ('bracket-assign','const r={sourceId:"aa"};Object["assign"](r,{score:97});','PROHIBITED'),
    ('bracket-reflect','const r={sourceId:"aa"};Reflect["set"](r,"score",97);','PROHIBITED'),
    ('define-properties','const r={sourceId:"aa"};Object.defineProperties(r,{score:{value:97}});','PROHIBITED'),
    ('assign-from-known','const knownSource={sourceId:"aa"};const r=Object.assign({},knownSource,{score:97});','PROHIBITED'),
    ('assign-result-discarded','const r={sourceId:"aa"};Object.assign({},r,{score:97});','PROHIBITED'),
    ('assign-numeric-conversion','const r={sourceId:"aa"};Object.assign(r,{score:Number("97")});','PROHIBITED'),
    ('literal-computed-key','const k="score";const r={sourceId:"aa",[k]:97};','PROHIBITED'),
    ('spread-known-var','const a={sourceId:"aa"};const b={score:97};const r={...a,...b};','PROHIBITED'),
    ('dynamic-key-reverse','const row={};row[k]="aa";row.score=97;','REVIEW'),
    ('unknown-source','const src=fromRuntime();const r={sourceId:src,score:97};','REVIEW'),
    ('unknown-value','const r={sourceId:"aa"};r.score=readRuntime();','REVIEW'),
    ('opaque-direct','const r=JSON.parse(atob(payload));','REVIEW'),
    ('opaque-window','const r=JSON.parse(window.atob(payload));','REVIEW'),
    ('opaque-global','const r=JSON.parse(globalThis["atob"](payload));','REVIEW'),
    ('function-shadow','const r={sourceId:"aa"};function f(r){r.score=97;}','LEGITIMATE'),
    ('arrow-shadow','const r={sourceId:"aa"};const f=(r)=>{r.score=97};','LEGITIMATE'),
    ('concise-arrow-shadow','const r={sourceId:"aa"};const f=(r)=>r.score=97;','LEGITIMATE'),
    ('unrelated-siblings','const a={sourceId:"aa"};const b={score:97};','LEGITIMATE'),
    ('illustrative-string','const example=\'{"sourceId":"aa","score":97}\';','LEGITIMATE'),
    ('document-string','const doc=\'{"sourceId":"aa","score":97}\';','LEGITIMATE'),
    ('typed-reference-count','const r={sourceId:"aa",kind:"aggregate-count",unit:"reference-links",value:19};','LEGITIMATE'),
    ('local-metric','const r={sourceId:"synthetic",score:97};','LEGITIMATE'),
    ('comment-only','// const r={sourceId:"aa",score:97};\nconst x=1;','LEGITIMATE'),
]
STRUCTURED=[
    ('indexed-bracket','docs/score.csv','sourceId,score_values[0]\naa,97\n','PROHIBITED'),
    ('indexed-dot','docs/score.csv','sourceId,score_values.0\naa,97\n','PROHIBITED'),
    ('tsv-indexed','docs/score.tsv','sourceId\tscore_values.0\naa\t97\n','PROHIBITED'),
    ('normalized-score-collision','docs/score.csv','sourceId,score_values[0],score_values.0\naa,97,98\n','REVIEW'),
    ('unresolvable-alias','docs/score.csv','sourceId,score_values0\naa,97\n','REVIEW'),
    ('opaque-value','docs/score.csv','sourceId,score_values\naa,fetchMetric()\n','REVIEW'),
    ('qualitative','docs/score.csv','sourceId,score_values\naa,unavailable\n','LEGITIMATE'),
    ('new-bfcl-is-not-rights','docs/score.csv','sourceId,score_values\nBR-BFCL-DATA,"[97,98]"\n','REVIEW'),
    ('typed-reference','docs/score.csv','sourceId,kind,unit,value\naa,aggregate-count,reference-links,19\n','LEGITIMATE'),
    ('local-only','docs/score.csv','model,score\nsynthetic,97\n','LEGITIMATE'),
    ('json-source','docs/score.json','{"sourceId":"aa","score":97}','PROHIBITED'),
    ('json-alias','docs/score.json','{"sourceId":"aa","SOURCE_ID":"local","score":97}','REVIEW'),
    ('json-reverse-alias','docs/score.json','{"SOURCE_ID":"local","sourceId":"aa","score":97}','REVIEW'),
    ('json-unlinked','docs/score.json','{"sources":[{"sourceId":"aa"}],"other":{"score":97}}','LEGITIMATE'),
    ('json-metadata-link','docs/score.json','{"metadata":{"sourceId":"aa"},"observation":{"score":97}}','REVIEW'),
    ('json-nested-local','docs/score.json','{"sourceId":"aa","child":{"sourceId":"local","score":97}}','REVIEW'),
    ('xml-direct','docs/score.xml','<root><g sourceId="aa" score="97"/></root>','PROHIBITED'),
    ('xml-ambiguous','docs/score.xml','<root><sources><sourceId>aa</sourceId></sources><observations><score>97</score></observations></root>','REVIEW'),
    ('html-opaque','index.html','<script>const r=JSON.parse(window.atob(payload));</script>','REVIEW'),
    ('html-direct','index.html','<script>const r={sourceId:"aa",score:97};</script>','PROHIBITED'),
    ('html-benign','index.html','<script>const r={kind:"reference-links",value:19};</script>','LEGITIMATE'),
    ('esm','src/score.mjs','const r={sourceId:"aa",score:97};','PROHIBITED'),
    ('commonjs','src/score.cjs','const r={sourceId:"aa",score:97};','PROHIBITED'),
    ('typescript-module','src/score.mts','const r={sourceId:"aa",score:97};','PROHIBITED'),
    ('json-lines','src/score.jsonl','{"sourceId":"aa","score":97}\n','PROHIBITED'),
    ('json-lines-local','src/local.jsonl','{"sourceId":"local","score":97}\n','LEGITIMATE'),
    ('json-lines-joined','src/scores.jsonl','{"sourceId":"aa"}\n{"score":97}\n','REVIEW'),
    ('json-lines-invalid','src/scores.jsonl','{"sourceId":"aa"}\n{"score":\n','REVIEW'),
]

def git(repo: Path,*args: str) -> str:
    env={**os.environ,'GIT_AUTHOR_NAME':'Synthetic',
         'GIT_AUTHOR_EMAIL':'synthetic@example.invalid',
         'GIT_COMMITTER_NAME':'Synthetic',
         'GIT_COMMITTER_EMAIL':'synthetic@example.invalid'}
    p=subprocess.run(['/usr/bin/git','-C',str(repo),*args],env=env,text=True,
                     capture_output=True,check=True)
    return p.stdout.strip()

class DirectR3j(unittest.TestCase):
    def test_javascript_tri_state(self):
        for name,source,expected in JAVASCRIPT:
            with self.subTest(name=name):
                self.assertEqual(js_classify(source),expected)
                self.assertEqual(decision(inspect_payload('src/probe.js',source.encode())),expected)
    def test_structured_tri_state(self):
        for name,path,text,expected in STRUCTURED:
            with self.subTest(name=name):
                self.assertEqual(decision(inspect_payload(path,text.encode())),expected)
    def test_source_modules_without_pages_allowlist_expansion(self):
        for extension in ('.mjs','.cjs','.mts','.jsonl'):
            self.assertIsNone(path_reason('docs/local'+extension))
        self.assertIsNotNone(path_reason('internal-research/source.jsonl'))
    def test_provenance_only_never_grants_new_bfcl_rights(self):
        self.assertEqual(decision(inspect_payload('docs/score.csv',
            b'sourceId,score_values\nBR-BFCL-DATA,"[97,98]"\n')), 'REVIEW')
    def test_all_opaque_variants_same_html_and_js_decision(self):
        for expr in ('atob(payload)','window.atob(payload)',
                     'globalThis["atob"](payload)'):
            src='const r=JSON.parse('+expr+');'
            js=decision(inspect_payload('app.js',src.encode()))
            html=decision(inspect_payload('index.html',('<script>'+src+'</script>').encode()))
            self.assertEqual((js,html),('REVIEW','REVIEW'))
    def test_public_boundary_cli_without_inherited_pythonpath(self):
        # Every public CI checkout runs the actual 57+ test executable via
        # its own checked-in scripts, independently of the private overlay.
        root=Path(__file__).resolve().parents[1]
        env=os.environ.copy()
        env.pop('PYTHONPATH',None)
        env.pop('PYTHONHOME',None)
        result=subprocess.run([os.sys.executable,'-B','tools/test_public_boundary.py'],
                              cwd=root,env=env,text=True,capture_output=True,
                              timeout=90)
        self.assertEqual(result.returncode,0,
                         'Public CLI import/execution failed without PYTHONPATH:\n'
                         +result.stdout[-2000:]+result.stderr[-5000:])

    def test_prohibited_is_never_only_review(self):
        for src in ('const r={sourceId:"aa",score:97};',
                    'const r=Object.assign({sourceId:"aa"},{score:97});'):
            self.assertEqual(decision(inspect_payload('app.js',src.encode())),'PROHIBITED')

class AuthenticatedHistoryR3j(unittest.TestCase):
    def test_add_then_delete(self):
        choices=[
            ('src/score.js',JAVASCRIPT[0][1]),('src/score.js',JAVASCRIPT[1][1]),
            ('src/score.js',JAVASCRIPT[13][1]),('src/score.csv',STRUCTURED[0][2]),
            ('src/score.mjs',STRUCTURED[21][2]),('src/score.jsonl',STRUCTURED[24][2]),
        ]
        for fmt in ('sha1','sha256'):
            for path,src in choices:
                with self.subTest(fmt=fmt,path=path,hash=hashlib.sha256(src.encode()).hexdigest()[:9]):
                    with tempfile.TemporaryDirectory(prefix='r3j-git-') as td:
                        repo=Path(td)
                        git(repo,'init','-q','--object-format='+fmt)
                        (repo/'README.md').write_text('Synthetic baseline\n')
                        git(repo,'add','-A');git(repo,'commit','-qm','baseline')
                        base=git(repo,'rev-parse','HEAD')
                        file=repo/path;file.parent.mkdir(exist_ok=True,parents=True)
                        file.write_text(src)
                        git(repo,'add','-A');git(repo,'commit','-qm','synthetic added')
                        file.unlink()
                        git(repo,'add','-A');git(repo,'commit','-qm','synthetic removed')
                        with self.assertRaises(ValueError):
                            audit_history(repo,base=base)

if __name__=='__main__':unittest.main(verbosity=2)
