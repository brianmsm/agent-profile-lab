#!/usr/bin/env python3
"""R3i exact counterexamples, synthetic Git ancestry and no-real-review probes."""
from __future__ import annotations
import os,subprocess,tempfile,unittest
from pathlib import Path
from audit_public_distribution import audit_history,inspect_payload
from publisher_semantics import js_classify

JS=[
 b"const row={sourceId:'AA'};row.score=91;",
 b"const row={score:91};row.sourceId='AA';",
 b"const row={sourceId:'AA'};row.score=Number('91');",
 b"const row={sourceId:'AA'};Object.assign(row,{score:91});",
 b'const row={sourceId:"AA"};Object.defineProperty(row,"score",{value:93});',
 b'const row={sourceId:"AA"};Reflect.set(row,"score",93);',
 b"const row={sourceId:'AA'};row['sc'+'ore']=93;",
 b'const re=/'+bytes([96])+b'/;const row={sourceId:"AA",score:91};',
 b'const re=/['+bytes([96])+b']/;const row={sourceId:"AA",score:91};',
 b'const re=/\\/\\//;const row={sourceId:"AA",score:91};',
 b'const re=/["\\\']/;const row={sourceId:"AA",score:91};',
]
DYNAMIC=[
 b"const row={sourceId:'AA'};row[key]=91;",
 b"const row={score:91};row[key]='AA';",
 b"const row={sourceId:'AA'};row.score=Number(remote);",
 b"const row={sourceId:'AA',...unknown};",
]
GOOD=[
 b"const a={sourceId:'AA'};const b={score:91};",
 b"const row={sourceId:'synthetic'};row.score=91;",
 b"function one(){const row={sourceId:'AA'};}function two(){const row={score:91};}",
 b"const row={sourceId:'AA',kind:'aggregate-count',unit:'reference-links',value:19};",
 b"// const row={sourceId:'AA',score:91};\nconst safe=19;",
]
CSV=b'sourceId,score_values\nAA,"[91,92]"\n'
def run(root,*args):
    env={**os.environ,"GIT_AUTHOR_NAME":"R3i Synthetic","GIT_COMMITTER_NAME":"R3i Synthetic",
         "GIT_AUTHOR_EMAIL":"fixture@example.invalid","GIT_COMMITTER_EMAIL":"fixture@example.invalid"}
    r=subprocess.run(["/usr/bin/git","-C",str(root),*args],text=True,
                     stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    if r.returncode:raise RuntimeError(str(args)+":"+r.stderr)
    return r.stdout.strip()
def fixture(root,fmt="sha1"):
    run(root,"init","-q","--object-format="+fmt)
    (root/"README.md").write_text("synthetic baseline\n")
    run(root,"add","-A");run(root,"commit","-qm","BASE")
    return run(root,"rev-parse","HEAD")
def mutate(root,path,data,message):
    f=root/path;f.parent.mkdir(parents=True,exist_ok=True)
    if data is None:f.unlink()
    else:f.write_bytes(data)
    run(root,"add","-A");run(root,"commit","-qm",message)
    return run(root,"rev-parse","HEAD")
class Direct(unittest.TestCase):
    def test_explicit_js_and_four_exact_regexes(self):
        for data in JS:
            with self.subTest(data):
                self.assertEqual(js_classify(data.decode()),"PROHIBITED")
                self.assertTrue(inspect_payload("assets/index.js",data))
    def test_unknown_static_semantics_require_review(self):
        for data in DYNAMIC:
            with self.subTest(data):
                self.assertEqual(js_classify(data.decode()),"REVIEW")
                self.assertIn("indeterminate-js-requires-independent-review",
                              inspect_payload("assets/index.js",data))
    def test_positive_unrelated_and_aggregates(self):
        for data in GOOD:
            with self.subTest(data):self.assertEqual(inspect_payload("assets/index.js",data),[])
    def test_arrays_and_qualitative_values(self):
        for suffix,sep in ((".csv",b","),(".tsv",b"\t")):
            data=b'sourceId'+sep+b'score_values\nAA'+sep+b'[91,92]\n' if sep==b"\t" else CSV
            self.assertIn("unreviewed-tabular-publisher-score",
                          inspect_payload("docs/probe"+suffix,data))
        self.assertEqual(inspect_payload("docs/qualitative.csv",b"sourceId,score\nAA,text-only\n"),[])
        self.assertTrue(inspect_payload("docs/bfcl.csv",b"sourceId,score_values\nBR-BFCL-DATA,91|92\n"))
    def test_alias_xml_html_and_unknown(self):
        self.assertIn("indeterminate-json-alias-requires-independent-review",
                      inspect_payload("docs/alias.json",
                        b'{"sourceId":"AA","SOURCE_ID":"local","score":91}'))
        self.assertTrue(inspect_payload("docs/xml.xml",
                        b"<root><sources><sourceId>AA</sourceId></sources><other><score>91</score></other></root>"))
        self.assertTrue(inspect_payload("index.html",
                        b'<div data-source-id="AA" data-score="91"></div>'))
        self.assertIn("indeterminate-tabular-publisher-score-requires-independent-review",
                      inspect_payload("docs/a.csv",b"sourceId,score_values\nAA,opaque\n"))
    def test_realistic_regex_and_minified_tail(self):
        safe=b"const re=/=/g;const root={sourceId:'local',score:1};"
        self.assertFalse(inspect_payload("assets/index-a.js",safe))
        self.assertTrue(inspect_payload("assets/index-a.js",safe+JS[0]))
    def test_broken_tokenization_is_review(self):
        for data in (b"const a='open",b"const re=/[unterminated;"):
            self.assertIn("indeterminate-js-requires-independent-review",
                          inspect_payload("assets/x.js",data))
class History(unittest.TestCase):
    def test_history_add_delete_metric_and_ambiguous(self):
        cases=[("docs/score.js",JS[0]),("docs/score.js",JS[3]),
               ("docs/score.js",JS[7]),("docs/score.csv",CSV),
               ("docs/score.json",b'{"sourceId":"AA","SOURCE_ID":"local","score":91}')]
        for path,data in cases:
            with self.subTest(path=path,sha=len(data)):
                with tempfile.TemporaryDirectory(prefix="r3i-add-delete-") as t:
                    repo=Path(t);base=fixture(repo)
                    mutate(repo,path,data,"BAD")
                    mutate(repo,path,None,"DELETED")
                    with self.assertRaises(ValueError):audit_history(repo,base=base)
    def test_graft_sha1_sha256_and_recovered_history(self):
        for fmt in ("sha1","sha256"):
            with self.subTest(fmt):
                with tempfile.TemporaryDirectory(prefix="r3i-grafts-") as t:
                    repo=Path(t);base=fixture(repo,fmt)
                    mutate(repo,"docs/score.csv",CSV,"BAD")
                    head=mutate(repo,"docs/score.csv",None,"HEAD")
                    with self.assertRaises(ValueError):audit_history(repo,base=base)
                    graft=repo/".git/info/grafts";graft.write_text(head+" "+base+"\n")
                    self.assertEqual(len(run(repo,"rev-list",base+".."+head).splitlines()),1)
                    self.assertEqual(run(repo,"status","--porcelain"),"")
                    with self.assertRaisesRegex(ValueError,"ancestry metadata"):
                        audit_history(repo,base=base)
                    graft.unlink()
                    self.assertEqual(len(run(repo,"rev-list",base+".."+head).splitlines()),2)
                    with self.assertRaises(ValueError):audit_history(repo,base=base)
    def test_valid_content_preserving_two_parent_merge(self):
        with tempfile.TemporaryDirectory(prefix="r3i-two-parent-") as t:
            repo=Path(t);base=fixture(repo)
            first=run(repo,"branch","--show-current")
            run(repo,"switch","-q","-c","feature")
            mutate(repo,"docs/feature.md",b"documented source link only\n","FEATURE")
            second=run(repo,"rev-parse","HEAD")
            run(repo,"switch","-q",first)
            run(repo,"commit","-qm","EMPTY","--allow-empty")
            run(repo,"merge","-q","--no-ff","--no-edit","-m","SYNTHETIC MERGE","feature")
            merge=run(repo,"rev-parse","HEAD")
            self.assertEqual(run(repo,"rev-parse",merge+"^{tree}"),run(repo,"rev-parse",second+"^{tree}"))
            report=audit_history(repo,base=base)
            self.assertEqual(report["newCommits"],3)
            self.assertEqual(report["reviewedContentPreservingMerges"],1)
            self.assertTrue(report["historyBoundaryPassed"])
    def test_residual_empty_graft_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="r3i-stale-graft-") as t:
            repo=Path(t);base=fixture(repo)
            mutate(repo,"docs/link.md",b"safe links\n","SAFE")
            graft=repo/".git/info/grafts"
            graft.touch()
            with self.assertRaisesRegex(ValueError,"ancestry metadata"):
                audit_history(repo,base=base)
            graft.unlink()
            self.assertTrue(audit_history(repo,base=base)["historyBoundaryPassed"])
    def test_positive_new_safe_commit(self):
        with tempfile.TemporaryDirectory(prefix="r3i-positive-") as t:
            repo=Path(t);base=fixture(repo)
            mutate(repo,"docs/link.md",b"local reference\n","SAFE")
            self.assertTrue(audit_history(repo,base=base)["historyBoundaryPassed"])
if __name__=="__main__":unittest.main(verbosity=2)
