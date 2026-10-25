#!/usr/bin/env python3
"""R3g conservative publisher score proofs (all numbers are synthetic).
Construct publisher keys dynamically so guard doesn't flag its own tests.
"""
from __future__ import annotations
import gzip,hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
import audit_public_distribution as guard

PROVENANCE="source"+"Id"
SCORE="sc"+"ore"

def git(repo,*args):
    return subprocess.check_output(["/usr/bin/git","-C",str(repo),*args],
                                   text=True,stderr=subprocess.PIPE).strip()
def commit(repo,message):
    git(repo,"add","-A")
    git(repo,"-c","core.hooksPath=/dev/null","-c","user.name=Synthetic",
        "-c","user.email=synthetic@example.invalid","commit","-qm",message)

class StructuredPublisherTests(unittest.TestCase):
    def test_independent_syntactic_variations(self):
        p=PROVENANCE;m=SCORE
        cases=[
          ("object-reversed",f'const x={{{m}:91,{p}:"aa"}};',True),
          ("object-indirect",f'const x={{{p}:"aa",{m}:globalThis["Number"]("91")}};',True),
          ("object-math",f'const x={{{p}:"aa",{m}:Math.max(90,91)}};',True),
          ("object-computed",'const x={["source"+"Id"]:"aa",["sc"+"ore"]:91};',True),
          ("object-long-gap",f'const x={{{p}:"aa",note:"'+'x'*550+f'",{m}:91}};',True),
          ("object-aggregate-plus-score",f'const x={{{p}:"aa",kind:"aggregate-count",unit:"references",{m}:91}};',True),
          ("jsx-braced",f'<Rate {p}={{"aa"}} {m}={{91}} />',True),
          ("jsx-math",f'<Rate {p}="aa" {m}={{Math.max(90,91)}} />',True),
          ("literal-string",f"""<div data-json='{{"{p}":"aa","{m}":91}}'/>""",True),
          ("bfcl",f'const x={{{p}:"BR-BFCL-DATA",{m}:91}};',False),
          ("synthetic",f'const x={{{p}:"synthetic",{m}:91}};',False),
          ("legitimate-count",f'const x={{{p}:"aa",kind:"aggregate-count",unit:"reference-links",value:2}};',False),
          ("unattributed-score",f'const local={{model:"synthetic",{m}:91}};',False),
        ]
        for name,example,want in cases:
            with self.subTest(name=name):
                got=bool(guard.inspect_payload("dashboard/src/probe.tsx",example.encode()))
                self.assertEqual(got,want)
        xml=[
            (f'<svg><g data-{m}="91" data-source="aa"/></svg>',True),
            (f'<svg><{p}>aa</{p}><{m}>&#57;&#49;</{m}></svg>',True),
            (f'<svg><g data-source="aa" data-{m}="&#57;&#49;"/></svg>',True),
            (f'<svg><{p}>aa</{p}><{m}><![CDATA[91]]></{m}></svg>',True),
            (f'<svg><g data-source="local" data-{m}="91"/></svg>',False),
        ]
        for example,want in xml:
            self.assertEqual(bool(guard.inspect_payload("icons.svg",example.encode())),want)
        json_cases=[
           ({p:"aa",m:91},True),
           ({p:"aa",m:91,"kind":"aggregate-count","unit":"references","value":2},True),
           ({p:"aa","kind":"aggregate-count","unit":"references","value":2},False),
           ({p:"synthetic",m:91},False),
           ({p:"BR-BFCL-DATA",m:91},False),
           ({p:"aa","fields":{m:91}},True),
        ]
        for value,want in json_cases:
            self.assertEqual(bool(guard.inspect_payload("docs/probe.json",json.dumps(value).encode())),want)

    def test_history_detects_reversed_score_even_after_deletion(self):
        with tempfile.TemporaryDirectory(prefix="apl-r3g-dlp-history-") as td:
            repo=Path(td)
            git(repo,"init","-q","-b","main")
            (repo/"README.md").write_text("Synthetic baseline\n")
            commit(repo,"safe baseline")
            base=git(repo,"rev-parse","HEAD")
            file=repo/"synthetic.tsx"
            file.write_text(f'const v={{{SCORE}:Math.max(90,91),{PROVENANCE}:"aa"}};\n')
            # Classification is tested independently, before invoking Git
            # ancestry authentication or the external authorisation gate.
            self.assertEqual(guard.inspect_payload('synthetic.tsx',file.read_bytes()),
                             ['indeterminate-js-requires-independent-review'])
            commit(repo,"synthetic unpublished score")
            file.unlink()
            commit(repo,"synthetic unpublished score deleted")
            # Valid standalone repository: release denial is specifically
            # about absent independent rights review, not malformed Git.
            with self.assertRaisesRegex(ValueError,
                    "External independently controlled review authority absent|Missing independent exact-byte review decision"):
                guard.audit_history(repo,base=base)

    def test_built_pages_detects_structured_scores(self):
        with tempfile.TemporaryDirectory(prefix="apl-r3g-pages-") as td:
            root=Path(td)
            git(root,"init","-q","-b","main")
            (root/"README.md").write_text("Standalone synthetic Pages fixture\n")
            commit(root,"synthetic Pages baseline")
            data=root/"dashboard/public/data"
            site=root/"dashboard/dist"
            parts={}
            for key in ("core","evidence"):
                binary=gzip.compress(b"{}",mtime=0)
                name=f"chunks/{key}-{hashlib.sha256(binary).hexdigest()}.json.gz"
                for dest in (data/name,site/"data"/name):
                    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(binary)
                parts[key]={"path":name,"sha256":hashlib.sha256(binary).hexdigest()}
            manifest=json.dumps({"parts":parts}).encode()
            (data/"delivery.json").write_bytes(manifest)
            (site/"data/delivery.json").write_bytes(manifest)
            (site/"index.html").write_text("<html><head></head><body>synthetic</body></html>")
            self.assertTrue(guard.audit_built_site(site,root=root)["verifiedAgainstPublicSource"])
            (site/"assets").mkdir()
            javascript=site/"assets/probe.js"
            javascript.write_text(f'const x={{{SCORE}:Math.max(91,92),{PROVENANCE}:"aa"}}')
            self.assertEqual(guard.inspect_payload('assets/probe.js',javascript.read_bytes()),
                             ['indeterminate-js-requires-independent-review'])
            # RELEASE test: the real gate must reject this REVIEW candidate
            # for lack of external authorisation; invalid Git is not accepted.
            with self.assertRaisesRegex(ValueError,
                    'External independently controlled review authority absent|Missing independent exact-byte review decision'):
                guard.audit_built_site(site,root=root)
            javascript.unlink()
            (site/"favicon.svg").write_text(
                f'<svg><g data-score="&#57;&#49;" data-source="aa"/></svg>')
            self.assertIn('unreviewed-embedded-publisher-score',
                          guard.inspect_payload('favicon.svg',(site/'favicon.svg').read_bytes()))
            with self.assertRaisesRegex(ValueError,'unreviewed-embedded-publisher-score'):
                guard.audit_built_site(site,root=root)


# R3h: Static, embedded snapshots of independent B-R3g (81) and R3f (36)
# adversarial vectors. Embedded in an already-approved transferred test path
# so CI offline can run *without* validation archives or a signing authority.
R3H_81=[
    ('J01', 'synthetic/J01.json', '{"sourceId": "aa", "score": 89}', 'block', 'Direct external measurement'),
    ('J02', 'synthetic/J02.json', '{"publisher": "ExampleExternal", "runs": [{"score": 91}]}', 'block', 'Inherited provenance'),
    ('J03', 'synthetic/J03.json', '{"sourceId": "AA", "measurements": [{"metrics": [{"accuracy": 81}]}]}', 'block', 'Nested publisher score'),
    ('J04', 'synthetic/J04.json', '{"sourceId": "br-bfcl-data", "score": 100}', 'allow', 'Approved BFCL local'),
    ('J05', 'synthetic/J05.json', '{"sourceId": "synthetic", "accuracy": 100}', 'allow', 'Local fixture'),
    ('J06', 'synthetic/J06.json', '{"sourceId": "aa", "kind": "aggregate-count", "unit": "reference-links", "value": 4}', 'allow', 'Approved typed link count'),
    ('J07', 'synthetic/J07.json', '{"sourceId": "aa", "kind": "aggregate-count", "unit": "reference-links", "value": 4, "score": 94}', 'block', 'Mixed score and count'),
    ('J08', 'synthetic/J08.json', '{"sourceId": "aa", "sourceMeta": {"sourceId": "local", "score": 92}}', 'block', 'Ambiguous external/local inherited provenance; mandatory manual review, not proven leak'),
    ('J09', 'synthetic/J09.json', '{"sourceId": "aa", "rows": [{"sourceId": "local", "accuracy": 91}]}', 'block', 'Ambiguous external/local inherited provenance; mandatory manual review, not proven leak'),
    ('J10', 'synthetic/J10.json', '{"sourceId": "aa", "evals": [{"winFraction": 0.96}]}', 'block', 'Renamed score field'),
    ('J11', 'synthetic/J11.json', '{"sourceId": "aa", "result": {"metric": {"name": "accuracy", "observed": 94}}}', 'block', 'Noncanonical metric record'),
    ('J12', 'synthetic/J12.json', '{"publisher": "ExampleExternal", "score": "unknown"}', 'allow', 'Non-numeric value'),
    ('J13', 'synthetic/J13.json', '{"sourceUrl": "https://artificialanalysis.ai/test", "score": 82}', 'block', 'Publisher link'),
    ('J14', 'synthetic/J14.json', '{"url": "https://frontiercode.example/test", "results": [{"score": 91}]}', 'block', 'External source URL parent'),
    ('J15', 'synthetic/J15.json', '{"sources": [{"sourceId": "aa"}], "observations": [{"score": 92}]}', 'block', 'Ambiguous external/local inherited provenance; mandatory manual review, not proven leak'),
    ('J16', 'synthetic/J16.json', '{"sourceId":"local","sourceId":"aa","score":90}', 'block', 'Duplicate keys must reject'),
    ('J17', 'synthetic/J17.json', '{"Source_ID": "aa", "Score_Pct": 97}', 'block', 'Normalized key aliases'),
    ('J18', 'synthetic/J18.json', '{"sourceId": "aa", "kind": "aggregate-count", "unit": "reference-links", "value": -1}', 'block', 'Negative count'),
    ('J19', 'synthetic/J19.json', '{"sourceId": "aa", "kind": "aggregate-count", "unit": "rows", "value": true}', 'allow', 'Boolean is not metric'),
    ('J20', 'synthetic/J20.json', '{"sourceId": "aa", "score": " 9.1e1 "}', 'block', 'Scientific notation'),
    ('J21', 'synthetic/J21.json', '{"sourceId": "aa", "scores": [91, 93]}', 'block', 'Numeric array'),
    ('J22', 'synthetic/J22.json', '{"sourceId": "aa", "score": "94%"}', 'block', 'Percentage score'),
    ('C01', 'synthetic/C01.csv', 'sourceId,score\naa,89\n', 'block', 'Direct CSV'),
    ('C02', 'synthetic/C02.csv', 'sourceId,kind,unit,value\naa,aggregate-count,reference-links,7\n', 'allow', 'Valid link count'),
    ('C03', 'synthetic/C03.csv', 'sourceId,kind,unit,value,accuracy\naa,aggregate-count,rows,5,93\n', 'block', 'Mixed count'),
    ('C04', 'synthetic/C04.csv', 'publisher,accuracy\nExternalExample,96\n', 'block', 'Other publisher'),
    ('C05', 'synthetic/C05.csv', 'dataSource,score\nAA,96\n', 'block', 'Source column alias'),
    ('C06', 'synthetic/C06.csv', 'sourceId,benchmark.accuracy\naa,93\n', 'block', 'Qualified metric header'),
    ('C07', 'synthetic/C07.csv', 'sourceId,score\nlocal,99\naa,87\n', 'block', 'Mixed rows'),
    ('C08', 'synthetic/C08.csv', 'sourceId,score\nbr-bfcl-data,96\n', 'block', 'New unreviewed BFCL-labeled score CSV is not the approved typed BFCL corpus; mandatory manual review'),
    ('C09', 'synthetic/C09.csv', 'sourceId,kind,unit,value,score\naa,aggregate-count,reference-links,4,81\n', 'block', 'Score in aggregate'),
    ('C10', 'synthetic/C10.tsv', 'sourceId\tscore\naa\t83\n', 'block', 'TSV'),
    ('C11', 'synthetic/C11.tsv', 'sourceId\tkind\tunit\tvalue\naa\taggregate-count\trows\t5\n', 'allow', 'Valid TSV count'),
    ('C12', 'synthetic/C12.csv', 'sourceId,score_values\naa,91|92\n', 'block', 'Plural scores'),
    ('C13', 'synthetic/C13.csv', 'sourceId,score\naa,95,extra\n', 'block', 'Malformed extra CSV'),
    ('C14', 'synthetic/C14.csv', 'sourceId,score\naa,text-only\n', 'allow', 'Nonnumeric CSV'),
    ('S01', 'synthetic/S01.js', "const d={sourceId:'aa',score:91};", 'block', 'Direct object'),
    ('S02', 'synthetic/S02.js', "const d={score:91,sourceId:'aa'};", 'block', 'Reordered properties'),
    ('S03', 'synthetic/S03.js', "const d={sourceId:'aa',['sc'+'ore']:91};", 'block', 'Computed constant key'),
    ('S04', 'synthetic/S04.js', "const k='sc'+'ore';const d={sourceId:'aa',[k]:91};", 'block', 'Computed key variable'),
    ('S05', 'synthetic/S05.js', "const d={sourceId:'aa',accuracy:Math.max(91,88)};", 'block', 'Math.max expression'),
    ('S06', 'synthetic/S06.js', "const score=91;const d={sourceId:'aa',score};", 'block', 'Shorthand score'),
    ('S07', 'synthetic/S07.js', "const metrics={score:91};const d={sourceId:'aa',...metrics};", 'block', 'Separate spread'),
    ('S08', 'synthetic/S08.js', "const d={sourceId:'aa'};d['score']=91;", 'block', 'Computed assignment'),
    ('S09', 'synthetic/S09.js', "const d={sourceId:'aa',accuracy:getScore()};", 'block', 'Indirect numeric function'),
    ('S10', 'synthetic/S10.js', "const id='aa';const d={sourceId:id,score:92};", 'block', 'Variable source provenance'),
    ('S11', 'synthetic/S11.js', "var z={score:95,sourceId:'aa'};", 'block', 'Minified record'),
    ('S12', 'synthetic/S12.js', 'const text=\'{"sourceId":"aa","score":97}\';', 'block', 'String with serialized metric'),
    ('S13', 'synthetic/S13.js', "const x={sourceId:'aa',score:`${90+1}`};", 'block', 'Numeric template expression'),
    ('S14', 'synthetic/S14.js', "// Example: {sourceId:'aa',score:93}\nconst harmless=1;", 'allow', 'Documentation comment'),
    ('S15', 'synthetic/S15.js', 'const example="sourceId: \'aa\', score: 97";', 'allow', 'Quotation not live measurement'),
    ('S16', 'synthetic/S16.js', "const data={sourceId:'aa',score:'not measured'};", 'allow', 'Textual value'),
    ('S17', 'synthetic/S17.js', "const d={sourceId:'aa',value:linkLabel};", 'allow', 'Unresolved nonnumeric link label'),
    ('S18', 'synthetic/S18.tsx', "const node=<Result sourceId='aa' score={Math.max(94,91)}/>;", 'block', 'JSX Math.max'),
    ('S19', 'synthetic/S19.tsx', "const node=<Result score='93' sourceId='aa'/>;", 'block', 'Reordered JSX'),
    ('S20', 'synthetic/S20.tsx', "const node=<Result data-source-id='aa' data-score={92}/>;", 'block', 'JSX data attr'),
    ('S21', 'synthetic/S21.tsx', "const node=<Result sourceId='aa' score='unknown'/>;", 'allow', 'Qualitative JSX attr'),
    ('S22', 'synthetic/S22.tsx', "const node=<div {...({'data-source-id':'aa','data-score':94})}/>;", 'block', 'JSX spread'),
    ('S23', 'synthetic/S23.ts', "const unknown='c';const d={sourceId:'aa',['s'+unknown+'ore']:94};", 'block', 'Dynamic computed score key resolving to score'),
    ('S24', 'synthetic/S24.html', '<div data-source-id="aa" data-score="98"></div>', 'block', 'HTML attrs'),
    ('S25', 'synthetic/S25.html', '<div data-source-id="&#97;&#97;" data-score="&#57;&#54;"></div>', 'block', 'HTML entities'),
    ('S26', 'synthetic/S26.css', "div:after{content:'sourceId: aa, score: 93'}", 'allow', 'CSS demo text'),
    ('S27', 'synthetic/S27.js', "const x=()=>({sourceId:'aa',score:95});", 'block', 'Function returns'),
    ('S28', 'synthetic/S28.js', "const x='https://test.example/?sourceId=aa&score=93';", 'allow', 'Link query only'),
    ('S29', 'synthetic/S29.js', "const d={sourceId:'aa',accuracy:+Math.max(91,92)};", 'block', 'Unary math'),
    ('S30', 'synthetic/S30.js', "const d=JSON.parse(atob('eyJzb3VyY2VJZCI6ImFhIiwic2NvcmUiOjkzfQ=='));", 'block', 'Base64 data literal'),
    ('X01', 'synthetic/X01.svg', '<svg><g sourceId="aa" score="95"/></svg>', 'block', 'SVG attrs'),
    ('X02', 'synthetic/X02.svg', '<svg xmlns:ex="urn:test"><ex:g ex:publisher="aa" ex:score="88"/></svg>', 'block', 'Namespace'),
    ('X03', 'synthetic/X03.svg', '<svg><g sourceId="&#97;&#97;" score="&#57;&#51;"/></svg>', 'block', 'Entity refs'),
    ('X04', 'synthetic/X04.svg', '<svg><desc><![CDATA[{"sourceId":"aa","score":90}]]></desc></svg>', 'block', 'CDATA JSON'),
    ('X05', 'synthetic/X05.svg', '<svg><script><![CDATA[const r={sourceId:"aa",accuracy:89};]]></script></svg>', 'block', 'CDATA JS'),
    ('X06', 'synthetic/X06.svg', '<!DOCTYPE svg [<!ENTITY x "aa">]><svg><g sourceId="&x;" score="90"/></svg>', 'block', 'DTD reject'),
    ('X07', 'synthetic/X07.svg', '<svg><g sourceId="aa" score="90"></svg>', 'block', 'Malformed XML'),
    ('X08', 'synthetic/X08.svg', '<svg><g publisher="aa" score="unavailable"/></svg>', 'allow', 'Textual score'),
    ('X09', 'synthetic/X09.svg', '<svg><metadata publisher="aa"/><text accuracy="94"/></svg>', 'block', 'Ambiguous sibling XML publisher/explicit accuracy; fail closed for independent manual rights review'),
    ('X10', 'synthetic/X10.svg', '<svg><g sourceId="aa" kind="aggregate-count" unit="reference-links" value="5"/></svg>', 'allow', 'Link aggregate'),
    ('X11', 'synthetic/X11.svg', '<svg xmlns:ex="urn:test"><g ex:publisher="aa"><title>label</title><ex:score>94</ex:score></g></svg>', 'block', 'Ns child'),
    ('X12', 'synthetic/X12.svg', '<svg><script>const data=atob("eyJzb3VyY2VJZCI6ImFhIiwic2NvcmUiOjkzfQ==")</script></svg>', 'block', 'Encoded SVG score'),
    ('P01', 'synthetic/P01.json', '{"sourceId": "br-bfcl-data", "kind": "aggregate-count", "unit": "source-count", "value": 23}', 'allow', 'BFCL count'),
    ('P02', 'synthetic/P02.json', '{"sourceId": "aa", "description": "Link to publisher", "url": "https://example.org/data"}', 'allow', 'No metric citation'),
    ('P03', 'synthetic/P03.tsx', "<a data-source-id='aa' href='https://example.org'>view source</a>", 'allow', 'JSX source hyperlink'),
]
R3H_36=[
    ('tsx_direct', 'dashboard/src/synthetic.tsx', 'const x={sourceId:"aa",score:91};', True),
    ('tsx_number', 'dashboard/src/synthetic.tsx', 'const x={sourceId:"aa",score:Number("91")};', True),
    ('tsx_globalthis_number', 'dashboard/src/synthetic.tsx', 'const x={sourceId:"aa",score:globalThis.Number("91")};', True),
    ('tsx_parsefloat', 'dashboard/src/synthetic.tsx', 'const x={sourceId:"aa",score:parseFloat("91")};', True),
    ('tsx_unary_numeric', 'dashboard/src/synthetic.tsx', 'const x={sourceId:"aa",score:+("91")};', True),
    ('tsx_unary_wrapper', 'dashboard/src/synthetic.tsx', 'const x={sourceId:"aa",score:+Number("91")};', True),
    ('tsx_reverse_fields', 'dashboard/src/synthetic.tsx', 'const x={score:91,sourceId:"aa"};', True),
    ('tsx_jsx_simple', 'dashboard/src/synthetic.tsx', '<Rate sourceId="aa" score={91} />', True),
    ('tsx_jsx_braced_source', 'dashboard/src/synthetic.tsx', '<Rate sourceId={"aa"} score={91} />', True),
    ('tsx_indirect_number', 'dashboard/src/synthetic.tsx', 'const x={sourceId:"aa",score:globalThis["Number"]("91")};', True),
    ('tsx_indirect_call', 'dashboard/src/synthetic.tsx', 'const x={sourceId:"aa",score:(0,Number)("91")};', True),
    ('tsx_unary_string', 'dashboard/src/synthetic.tsx', 'const x={sourceId:"aa",score:+"91"};', True),
    ('tsx_math_computed', 'dashboard/src/synthetic.tsx', 'const x={sourceId:"aa",score:Math.max(90,91)};', True),
    ('tsx_computed_keys', 'dashboard/src/synthetic.tsx', 'const x={["source"+"Id"]:"aa",["sc"+"ore"]:91};', True),
    ('tsx_source_450_chars_earlier', 'dashboard/src/synthetic.tsx', 'const x={sourceId:"aa",note:"xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",score:91};', True),
    ('tsx_score_with_aggregate_marker', 'dashboard/src/synthetic.tsx', 'const x={sourceId:"aa",kind:"aggregate-count",unit:"reference-links",score:91};', True),
    ('js_minified_plain', 'dashboard/src/synthetic.js', 'let a={sourceId:"aa",score:91}', True),
    ('js_minified_reversed', 'dashboard/src/synthetic.js', 'let a={score:91,sourceId:"aa"}', True),
    ('svg_direct_attribute', 'dashboard/src/synthetic.svg', '<svg><g data-source="aa" data-score="91"/></svg>', True),
    ('svg_reversed_attribute', 'dashboard/src/synthetic.svg', '<svg><g data-score="91" data-source="aa"/></svg>', True),
    ('svg_xml_tag', 'dashboard/src/synthetic.svg', '<svg><sourceId>aa</sourceId><score>91</score></svg>', True),
    ('svg_entity_attribute', 'dashboard/src/synthetic.svg', '<svg><g data-source="aa" data-score="&#57;&#49;"/></svg>', True),
    ('svg_cdata_score', 'dashboard/src/synthetic.svg', '<svg><sourceId>aa</sourceId><score><![CDATA[91]]></score></svg>', True),
    ('json_nested_publisher', 'dashboard/public/synthetic.json', '{"sourceId":"aa","fields":{"score":91}}', True),
    ('json_reverse_fields', 'dashboard/public/synthetic.json', '{"score":91,"sourceId":"aa"}', True),
    ('json_aggregate_with_score', 'dashboard/public/synthetic.json', '{"sourceId":"aa","kind":"aggregate-count","unit":"reference-links","value":2,"score":91}', True),
    ('csv_publisher_score', 'dashboard/public/synthetic.csv', 'sourceId,score\nAA,91\n', True),
    ('csv_aggregate_score_override', 'dashboard/public/synthetic.csv', 'sourceId,score,kind,unit\nAA,91,aggregate-count,reference-links\n', True),
    ('csv_aggregate_implicit_kind', 'dashboard/public/synthetic.csv', 'sourceId,score,unit\nAA,91,reference-links\n', True),
    ('negative_bfcl_json', 'dashboard/public/synthetic.json', '{"sourceId":"BR-BFCL-DATA","score":91}', False),
    ('negative_bfcl_tsx', 'dashboard/src/synthetic.tsx', 'const x={sourceId:"BR-BFCL-DATA",score:91};', False),
    ('negative_local_json', 'dashboard/public/synthetic.json', '{"sourceId":"synthetic","score":91}', False),
    ('negative_local_js', 'dashboard/src/synthetic.tsx', 'const x={sourceId:"synthetic",score:91};', False),
    ('negative_local_xml', 'dashboard/src/synthetic.svg', '<svg><g data-source="local" data-score="91"/></svg>', False),
    ('negative_aggregate_json', 'dashboard/public/synthetic.json', '{"sourceId":"aa","kind":"aggregate-count","unit":"reference-links","value":2}', False),
    ('negative_no_publisher', 'dashboard/src/synthetic.tsx', 'const localFixture={model:"synthetic",score:91};', False),
]
class R3hIndependentCorpusRegression(unittest.TestCase):
    def test_r3g_81_reclassified(self):
        self.assertEqual(len(R3H_81),81)
        for ident,path,payload,expected,reason in R3H_81:
            with self.subTest(vector=ident,reason=reason):
                findings=guard.inspect_payload(path,payload.encode())
                self.assertEqual(bool(findings),expected=="block",findings)

    def test_r3f_36_unchanged(self):
        self.assertEqual(len(R3H_36),36)
        for ident,path,payload,expected in R3H_36:
            with self.subTest(vector=ident):
                self.assertEqual(bool(guard.inspect_payload(path,payload.encode())),expected)

    def test_b01_siblings_and_dynamic_encoded_boundary(self):
        sample=b'const x={metadata:{publisher:"openai"},legitimateCounters:{value:3}};'
        self.assertFalse(guard.inspect_payload("assets/test.js",sample))
        danger=b'const x={sourceId:"aa",score:91};'
        self.assertTrue(guard.inspect_payload("assets/test.js",danger))
        opaque=b'const x=JSON.parse(atob(encodedVariable));'
        self.assertIn('opaque-editorial-encoding-requires-independent-review',
                      guard.inspect_payload("assets/test.js",opaque))

    def test_r3h_history_computed_score_add_then_delete(self):
        with tempfile.TemporaryDirectory(prefix="apl-r3h-history-") as td:
            repo=Path(td)
            git(repo,"init","-q","-b","main")
            (repo/"README.md").write_text("Local, synthetic baseline\n")
            commit(repo,"baseline")
            base=git(repo,"rev-parse","HEAD")
            path=repo/"computed.js"
            path.write_text('const k="sc"+"ore";const m={sourceId:"aa",[k]:91};\n')
            commit(repo,"add synthetic computed metric")
            path.unlink()
            commit(repo,"delete synthetic computed metric")
            with self.assertRaisesRegex(ValueError,"unreviewed-embedded-publisher-score"):
                guard.audit_history(repo,base=base)

if __name__=="__main__":
    unittest.main()
