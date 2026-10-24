#!/usr/bin/env python3
"""Synthetic, offline regression tests. No real keys or publisher measurements."""
from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import audit_public_distribution as guard


def command(root: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "Synthetic Tester", "GIT_COMMITTER_NAME": "Synthetic Tester",
           "GIT_AUTHOR_EMAIL": "test@example.invalid", "GIT_COMMITTER_EMAIL": "test@example.invalid"}
    return subprocess.check_output(["git", "-C", str(root), *args], env=env,
                                   stderr=subprocess.PIPE).decode().strip()


def commit(root: Path, message: str) -> str:
    command(root, "add", "-A")
    command(root, "-c", "core.hooksPath=/dev/null", "commit", "-qm", message)
    return command(root, "rev-parse", "HEAD")


class PayloadTests(unittest.TestCase):
    def test_pages_artifact_rejects_new_csv_even_after_successful_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            # Real standalone synthetic Git metadata, not a linked worktree.
            command(root,'init','-q','-b','main')
            (root/'README.md').write_text('Synthetic Pages test root\n')
            commit(root,'synthetic Pages baseline')
            built=root/'dashboard/dist';d=root/'dashboard/public/data';d.mkdir(parents=True)
            parts={}
            for name in ('core','evidence'):
                payload=gzip.compress(b'{}',mtime=0);sha=hashlib.sha256(payload).hexdigest()
                relative=f'chunks/{name}-{sha}.json.gz'
                for target in (d/relative,built/'data'/relative):
                    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload)
                parts[name]={'path':relative,'sha256':sha,'bytes':len(payload)}
            manifest=json.dumps({'format':'apl.delivery','parts':parts}).encode()
            (d/'delivery.json').write_bytes(manifest)
            (built/'data/delivery.json').write_bytes(manifest)
            (built/'index.html').write_text('<html><head></head><body>safe</body></html>')
            self.assertTrue(guard.audit_built_site(built,root=root)['verifiedAgainstPublicSource'])
            svg=(b'<svg><metadata>{"source'+b'Id":"AA","score":82.1}'
                 b'</metadata></svg>')
            (built/'icons.svg').write_bytes(svg)
            with self.assertRaisesRegex(ValueError,'unreviewed-embedded-publisher-score'):
                guard.audit_built_site(built,root=root)
            (built/'icons.svg').unlink()
            (built/'assets').mkdir()
            converted_js=(b'const x={source'+b'Id:"AA",score:Number("82.1")};')
            (built/'assets/counterexample.js').write_bytes(converted_js)
            with self.assertRaisesRegex(ValueError,'unreviewed-embedded-publisher-score'):
                guard.audit_built_site(built,root=root)
            (built/'assets/counterexample.js').unlink()
            self.assertTrue(guard.audit_built_site(built,root=root)['verifiedAgainstPublicSource'])
            # The built site is an independent output surface. Test both
            # JSX-to-JS number expression and SVG/XML metadata variants.
            (built/'favicon.svg').write_bytes(
                b'<svg data-source="AA" data-score="82.1"></svg>')
            with self.assertRaisesRegex(ValueError,'unreviewed-embedded-publisher-score'):
                guard.audit_built_site(built,root=root)
            (built/'favicon.svg').unlink()
            (built/'assets/r3f-score.js').write_bytes(
                b'const a={source'+b'Id:"AA",score:globalThis.Number("82.1")};')
            with self.assertRaisesRegex(ValueError,'unreviewed-embedded-publisher-score'):
                guard.audit_built_site(built,root=root)
            (built/'assets/r3f-score.js').unlink()
            (built/'docs').mkdir()
            (built/'docs/redteam-scores.csv').write_text('sourceId,model,value\nAA,local-synthetic,93.7\n')
            with self.assertRaisesRegex(ValueError,'Unapproved Pages output file'):
                guard.audit_built_site(built,root=root)

    def test_static_numeric_coercions_are_prohibited_not_review(self):
        from publisher_semantics import js_classify
        source=b'source'+b'Id'
        for expr in (b'globalThis.Number("82.1")',b'+("82.1")'):
            data=b'const row={'+source+b':"AA",score:'+expr+b'};'
            with self.subTest(expression=expr):
                self.assertEqual(js_classify(data.decode()),'PROHIBITED')
                self.assertIn('unreviewed-embedded-publisher-score',
                              guard.inspect_payload('assets/probe.js',data))
        self.assertEqual(js_classify('const row={sourceId:"local",score:+("82.1")};'),
                         'LEGITIMATE')
        self.assertEqual(js_classify('const row={sourceId:"AA",score:globalThis.Number(runtime)};'),
                         'REVIEW')

    def test_review_authority_does_not_replace_dlp_classification(self):
        from publisher_semantics import js_classify
        from independent_review_gate import enforce, gate
        source=b'const row={sourceId:"AA",score:runtimeValue};'
        reasons=guard.inspect_payload('assets/ambiguous.js',source)
        self.assertEqual(js_classify(source.decode()),'REVIEW')
        self.assertTrue(reasons)
        self.assertTrue(all(r.startswith('indeterminate-') or r.startswith('opaque-')
                            for r in reasons),reasons)
        # Explicit synthetic test roots are supported only by the low-level
        # test API; no production roster or private signing key is used.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with self.assertRaisesRegex(ValueError,
                    'Missing independent exact-byte review decision'):
                enforce('a'*40,'pages-public','assets/ambiguous.js',source,
                        reasons=reasons,trust_file=root/'trust.json',
                        decisions_dir=root/'reviews',
                        allow_synthetic_test_roots=True)
        # Release code still calls the immutable production barrier. No
        # synthetic roots are accepted through the public gate API.
        with self.assertRaises(ValueError):
            gate(reasons,'a'*40,'pages-public','assets/ambiguous.js',source)

    def test_publisher_number_wrapper_in_jsx_and_svg(self):
        # Derived only from the R3d auditors' SYNTHETIC counterexamples.
        cases=(
            ("dashboard/src/example.tsx",
             b'const test={source'+b'Id:"AA",score:'+b'Number("82.1")};'),
            ("dashboard/dist/assets/example.js",
             b"const x={source"+b"Id:'AA',score:"+b"parseFloat('82.1')};"),
            ("dashboard/public/icons.svg",
             b'<svg><metadata>{"sourceId":"AA","score":82.1}</metadata></svg>'),
        )
        for name,data in cases:
            with self.subTest(name):
                self.assertIn("unreviewed-embedded-publisher-score",
                              guard.inspect_payload(name,data))
        # Existing local fixture, typed publisher-authorized value and
        # legitimate review-count aggregate must not be treated as forbidden.
        self.assertNotIn("unreviewed-embedded-publisher-score",
                          guard.inspect_payload("docs/count.txt",
                          b'const count={sourceId:"AA",value:19,unit:"reference-links",kind:"aggregate-count"};'))
        self.assertNotIn("unreviewed-embedded-publisher-score",
                          guard.inspect_payload("tests/local-example.ts",
                          b'const fixture={sourceId:"synthetic",score:Number("82.1")};'))

    def test_r3f_jsx_global_unary_and_xml_publisher_encodings(self):
        # Construct these bytes dynamically so this TEST'S source code does
        # not itself contain publisher data mistaken for a new public leak.
        source=b'source'+b'Id'
        rows=(
            ("dashboard/src/probe.tsx",
             b'<Row '+source+b'="AA" score={Number("82.1")} />'),
            ("dashboard/src/probe.tsx",
             b'<Row '+source+b'="AA" score={globalThis.Number("82.1")} />'),
            ("assets/main.js",
             b'const x={'+source+b':"AA",score:globalThis.Number("82.1")};'),
            ("assets/main.js",
             b'const x={'+source+b':"AA",score:+("82.1")};'),
            ("assets/main.js",
             b'const x={'+source+b':"AA",score:n};const n=Number("82.1");'),
            ("favicon.svg",
             b'<svg><metadata '+source+b'="AA" score="82.1"/></svg>'),
            ("favicon.svg",
             b'<svg><metadata><'+source+b'>AA</'+source+
                 b'><score>82.1</score></metadata></svg>'),
            ("favicon.svg",
             b'<svg><metadata data-source="AA" data-score="82.1"/></svg>'),
            ("icons.xml",
             b'<xml><metadata data-source="AA" data-score="82.1"/></xml>'),
        )
        for relative,payload in rows:
            with self.subTest(relative=relative,payloadSHA256=hashlib.sha256(payload).hexdigest()):
                self.assertIn("unreviewed-embedded-publisher-score",
                              guard.inspect_payload(relative,payload))
        self.assertFalse(guard.inspect_payload(
            "docs/aggregate.js",b'const x={'+source+
            b':"AA",kind:"aggregate-count",unit:"reference-links",value:19};'))
        self.assertFalse(guard.inspect_payload(
            "dashboard/src/local.tsx",
            b'const x={'+source+b':"synthetic",score:Number("82.1")};'))

    def test_provider_key(self):
        value = b"sk" + b"-" + b"S" * 40
        self.assertIn("provider-api-secret", guard.inspect_payload("docs/demo.txt", value))

    def test_project_key(self):
        value = b"sk" + b"-proj-" + b"S" * 40
        self.assertIn("provider-api-secret", guard.inspect_payload("docs/demo.txt", value))

    def test_bearer(self):
        value = b"Bearer" + b" " + b"S" * 50
        self.assertIn("long-bearer-token", guard.inspect_payload("docs/demo.txt", value))

    def test_github_key(self):
        value = b"ghp" + b"_" + b"S" * 40
        self.assertIn("github-access-token", guard.inspect_payload("docs/demo.txt", value))

    def test_pem(self):
        value = b"-----BEGIN " + b"PRIVATE KEY-----"
        self.assertIn("private-key-PEM", guard.inspect_payload("docs/demo.txt", value))

    def test_home_paths(self):
        for suffix in ("Documents", ".local", ".config", "Library"):
            value = ("/" + "home/synthetic/" + suffix + "/test").encode()
            self.assertIn("private-user-home", guard.inspect_payload("docs/demo.txt", value))

    def test_binary(self):
        self.assertIn("unexpected-binary-file", guard.inspect_payload("docs/demo.txt", bytes([0, 255])))

    def test_invalid_json(self):
        self.assertIn("invalid-json", guard.inspect_payload("data/demo.json", b"{"))

    def test_jsonc_configuration(self):
        data = b'{// configuration comment\n"url":"https://example.invalid/a//b", "option":true,}'
        self.assertEqual(guard.inspect_payload("dashboard/tsconfig.app.json", data), [])

    def test_jsonc_still_checks_scores(self):
        data = json.dumps({"sourceId": "AA", "value": 0.123})[:-1].encode() + b",/* note */}"
        self.assertIn("non-allowlisted-publisher-numeric-row",
                      guard.inspect_payload("dashboard/tsconfig.app.json", data))

    def test_numeric_publisher_score_csv_tsv_same_as_json(self):
        for relative,raw in [('docs/redteam-aa-scores.csv',b'sourceId,model,value\nAA,synthetic-local-only,93.7\n'),
                             ('docs/redteam-aa-scores.tsv',b'sourceId\tmodel\tvalue\nAA\tsynthetic-local-only\t93.7\n'),
                             ('docs/redteam-other-scores.csv',b'sourceId,model,score\nUNKNOWN,local-example,0.3\n')]:
            self.assertIn('unreviewed-tabular-publisher-score',guard.inspect_payload(relative,raw))
        control=json.dumps({'sourceId':'AA','model':'synthetic-local-only','value':93.7}).encode()
        self.assertIn('non-allowlisted-publisher-numeric-row',guard.inspect_payload('docs/demo.json',control))

    def test_allowed_aggregate_table_without_publisher_scores(self):
        data=b'domain,role_count,enabled\napps,424,13\nweb,424,13\n'
        self.assertEqual(guard.inspect_payload('docs/aggregated-roles.csv',data),[])

    def test_bfcl_score_in_new_unreviewed_csv_rejected(self):
        data=b'sourceId,model,value\nBR-BFCL-DATA,example-model,77.47\n'
        self.assertEqual(guard.inspect_payload('docs/invented-bfcl.csv',data),
                         ['indeterminate-bfcl-source-label-requires-independent-review'])

    def test_r3b_r3c_nested_string_alternate_scores_and_built_source(self):
        negatives={
            'json-nested':('docs/data.json',b'{"sourceId":"AA","results":[{"score":0.873}]}'),
            'json-number-string':('docs/data.json',b'{"sourceId":"AA","value":"0.873"}'),
            'json-accuracy':('docs/data.json',b'{"sourceId":"AA","accuracy":0.873}'),
            'csv-percent':('docs/data.csv',b'sourceId,score\nAA,87.3%\n'),
            'csv-local-decimal':('docs/data.csv',b'sourceId,score\nAA,"87,3"\n'),
            'csv-score-pct':('docs/data.csv',b'sourceId,score_pct\nAA,87.3\n'),
            'csv-semicolon':('docs/data.csv',b'sourceId;score\nAA;0.873\n'),
            'html':('index.html',b'<script type="application/json">{"sourceId":"AA","score":0.873}</script>'),
            'tsx':('dashboard/src/App.tsx',b"""return <div className="app-shell" data-r3-synthetic-score='{"sourceId":"AA","value":0.873}'>"""),
            'js':('assets/index-synthetic.js',b'const x={sourceId:"AA",score:0.873};'),
            'text':('docs/note.txt',b'Synthetic publisher sourceId=AA; score=0.873'),
        }
        for name,(path,data) in negatives.items():
            with self.subTest(name):
                self.assertTrue(guard.inspect_payload(path,data),name)
        allowed={
            'aggregate':('docs/count.json',b'{"sourceId":"AA","value":19,"unit":"reference-links","kind":"aggregate-count"}'),
            'count-table':('docs/count.tsv',b'sourceId\tvalue\tunit\nAA\t19\treference-links\n'),
            'local-mock':('tests/demo.csv',b'model,score\nsynthetic,1\n'),
            'BFCL-licensed':('docs/bfcl.json',b'{"sourceId":"BR-BFCL-DATA","value":77.47}'),
            'link-only':('docs/references.json',b'{"sourceId":"AA","value":null,"referenceOnly":true}'),
        }
        for name,(path,data) in allowed.items():
            with self.subTest(name):
                self.assertEqual(guard.inspect_payload(path,data),[],name)

    def test_r3b_duplicate_json_keys_refused_before_canonicalization(self):
        for text in (b'{"value":9.99,"value":77.47}',
                     b'{"benchmarks":[{"measurement":{"id":"a","id":"b"}}]}'):
            self.assertIn('invalid-json',guard.inspect_payload('docs/data.json',text))

    def test_numeric_aa(self):
        payload = json.dumps({"sourceId": "AA", "value": 0.123}).encode()
        self.assertIn("non-allowlisted-publisher-numeric-row", guard.inspect_payload("tests/demo.json", payload))

    def test_numeric_mirror(self):
        payload = json.dumps({"source": "https://slopalytics.com/synthetic", "score": 0.123}).encode()
        self.assertIn("non-allowlisted-publisher-numeric-row", guard.inspect_payload("tests/demo.json", payload))

    def test_other_publisher(self):
        payload = json.dumps({"sourceId": "SYNTHETIC-UNREVIEWED", "value": 0.123}).encode()
        self.assertIn("non-allowlisted-publisher-numeric-row", guard.inspect_payload("tests/demo.json", payload))

    def test_bfcl(self):
        payload = json.dumps({"sourceId": "BR-BFCL-DATA", "value": 0.123}).encode()
        self.assertEqual(guard.inspect_payload("tests/demo.json", payload), [])

    def test_null_reference(self):
        payload = json.dumps({"sourceId": "AA", "value": None, "referenceOnly": True}).encode()
        self.assertEqual(guard.inspect_payload("tests/demo.json", payload), [])

    def test_link_and_count(self):
        payload = json.dumps({"url": "https://artificialanalysis.ai/models/synthetic", "references": 1}).encode()
        self.assertEqual(guard.inspect_payload("tests/demo.json", payload), [])

    def test_compressed_secret(self):
        raw = json.dumps({"demo": "sk" + "-" + "S" * 40}).encode()
        data = gzip.compress(raw, mtime=0)
        name = "dashboard/public/data/chunks/core-" + hashlib.sha256(data).hexdigest() + ".json.gz"
        self.assertIn("provider-api-secret", guard.inspect_payload(name, data))

    def test_compressed_score(self):
        raw = json.dumps({"sourceId": "AA", "value": 0.123}).encode()
        data = gzip.compress(raw, mtime=0)
        name = "dashboard/public/data/chunks/evidence-" + hashlib.sha256(data).hexdigest() + ".json.gz"
        self.assertIn("non-allowlisted-publisher-numeric-row", guard.inspect_payload(name, data))

    def test_compressed_hash(self):
        data = gzip.compress(b"{}", mtime=0)
        name = "dashboard/public/data/chunks/core-" + "0" * 64 + ".json.gz"
        self.assertIn("compressed-name-hash-mismatch", guard.inspect_payload(name, data))

    def test_decompression_limit(self):
        data = gzip.compress(b" " * 10000, mtime=0)
        name = "dashboard/public/data/chunks/core-" + hashlib.sha256(data).hexdigest() + ".json.gz"
        self.assertIn("decompression-size-limit", guard.inspect_payload(name, data, max_bytes=100))

    def test_corrupt_compression(self):
        data = b"not a gzip"
        name = "dashboard/public/data/chunks/core-" + hashlib.sha256(data).hexdigest() + ".json.gz"
        self.assertIn("invalid-compressed-json", guard.inspect_payload(name, data))


class PathTests(unittest.TestCase):
    def test_private_directories(self):
        for root in ("internal-research", "evidence", "sources", "republication"):
            self.assertIsNotNone(guard.path_reason(root + "/fixture.txt"))

    def test_bundle_and_other_archives(self):
        for suffix in ("bundle", "zip", "gz", "tar", "xz", "pdf"):
            self.assertIsNotNone(guard.path_reason("docs/demo." + suffix))

    def test_traversal(self):
        for name in ("../demo", "/tmp/demo", "docs/../../demo", "docs/./demo", "docs\\demo"):
            self.assertIsNotNone(guard.path_reason(name))

    def test_env_variants(self):
        for name in (".env", ".env.local", "tests/.env.backup"):
            self.assertIsNotNone(guard.path_reason(name))

    def test_nested_vcs(self):
        for name in ("docs/.git/config", ".gitmodules"):
            self.assertIsNotNone(guard.path_reason(name))

    def test_tracked_ignored_paths(self):
        for name in ("validation/hidden.txt", "dashboard/node_modules/hidden.txt", "data/assignments.json"):
            self.assertIsNotNone(guard.path_reason(name, tracked=True))

    def test_safe_text(self):
        self.assertIsNone(guard.path_reason("tools/new_guard.py"))


class TreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.required = patch.object(guard, "MUST_EXIST", [])
        self.required.start()

    def tearDown(self):
        self.required.stop()
        self.temp.cleanup()

    def test_regular_tree(self):
        (self.root / "README.md").write_text("Synthetic documentation\n")
        self.assertTrue(guard.audit(self.root)["publicBoundaryPassed"])

    def test_dangling_symlink(self):
        (self.root / "link").symlink_to(self.root / "missing")
        with self.assertRaisesRegex(ValueError, "symlink-not-approved"):
            guard.audit(self.root)

    def test_directory_symlink(self):
        (self.root / "docs").symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink-not-approved"):
            guard.audit(self.root)

    def test_orphan_compressed_data(self):
        data = gzip.compress(b"{}", mtime=0)
        name = "dashboard/public/data/chunks/core-" + hashlib.sha256(data).hexdigest() + ".json.gz"
        target = self.root / name
        target.parent.mkdir(parents=True)
        target.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "unreferenced-compressed-payload"):
            guard.audit(self.root)

    def test_hidden_tracked_runtime(self):
        command(self.root, "init", "-q")
        (self.root / "validation").mkdir()
        (self.root / "validation/hidden.txt").write_text("synthetic")
        commit(self.root, "synthetic hidden output")
        with self.assertRaisesRegex(ValueError, "runtime-or-private-output-tracked"):
            guard.audit(self.root)

    def test_no_secret_echo(self):
        value = "sk" + "-" + "S" * 40
        (self.root / "demo.txt").write_text(value)
        try:
            guard.audit(self.root)
        except ValueError as error:
            self.assertNotIn(value, str(error))
        else:
            self.fail("Expected a secret finding")


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        command(self.root, "init", "-q", "-b", "main")
        (self.root / "README.md").write_text("Synthetic baseline\n")
        self.base = commit(self.root, "base")

    def tearDown(self):
        self.temp.cleanup()

    def test_clean_successor(self):
        (self.root / "README.md").write_text("Synthetic documentation improvement\n")
        commit(self.root, "safe change")
        self.assertEqual(guard.audit_history(self.root, base=self.base)["newCommits"], 1)

    def test_historical_number_wrapper_rejected(self):
        payload=b'const v={source'+b'Id:"AA",score:Number("82.1")};'
        (self.root/'publisher.tsx').write_bytes(payload)
        commit(self.root,"synthetic disallowed inline publisher measurement")
        with self.assertRaisesRegex(ValueError,"unreviewed-embedded-publisher-score"):
            guard.audit_history(self.root,base=self.base)

    def test_historical_svg_publisher_metadata_rejected(self):
        payload=b'<svg><metadata>{"source'+b'Id":"AA","score":82.1}</metadata></svg>'
        (self.root/'icons.svg').write_bytes(payload)
        commit(self.root,"synthetic disallowed svg editorial statistic")
        with self.assertRaisesRegex(ValueError,"unreviewed-embedded-publisher-score"):
            guard.audit_history(self.root,base=self.base)

    def test_r3f_added_then_deleted_jsx_editorial_score_still_rejected(self):
        marker=b'source'+b'Id'
        path=self.root/"synthetic.jsx"
        path.write_bytes(b'<Row '+marker+b'="AA" score={globalThis.Number("82.1")} />')
        commit(self.root,"synthetic publisher JSX encoded measurement")
        path.unlink()
        commit(self.root,"synthetic publisher JSX removed")
        with self.assertRaisesRegex(ValueError,"unreviewed-embedded-publisher-score"):
            guard.audit_history(self.root,base=self.base)

    def test_r3f_added_then_deleted_xml_editorial_score_still_rejected(self):
        path=self.root/"synthetic.svg"
        path.write_bytes(b'<svg data-source="AA" data-score="82.1"></svg>')
        commit(self.root,"synthetic publisher XML measurement")
        path.unlink()
        commit(self.root,"synthetic publisher XML removed")
        with self.assertRaisesRegex(ValueError,"unreviewed-embedded-publisher-score"):
            guard.audit_history(self.root,base=self.base)

    def test_added_then_deleted_secret(self):
        (self.root / "demo.txt").write_text("sk" + "-" + "S" * 40)
        commit(self.root, "synthetic leak")
        (self.root / "demo.txt").unlink()
        commit(self.root, "removed synthetic leak")
        with self.assertRaisesRegex(ValueError, "provider-api-secret"):
            guard.audit_history(self.root, base=self.base)

    def test_added_then_deleted_private_directory(self):
        (self.root / "internal-research").mkdir()
        (self.root / "internal-research/demo.txt").write_text("synthetic")
        commit(self.root, "private artifact")
        (self.root / "internal-research/demo.txt").unlink()
        commit(self.root, "remove private artifact")
        with self.assertRaisesRegex(ValueError, "private-source-archive-present"):
            guard.audit_history(self.root, base=self.base)

    def test_history_symlink(self):
        (self.root / "link").symlink_to("README.md")
        commit(self.root, "symlink")
        with self.assertRaisesRegex(ValueError, "nonregular-git-object|symbolic links/submodules unsupported"):
            guard.audit_history(self.root, base=self.base)

    def test_unrelated_base(self):
        command(self.root, "checkout", "--orphan", "other")
        (self.root / "README.md").write_text("Unrelated synthetic baseline")
        commit(self.root, "orphan")
        with self.assertRaises((subprocess.CalledProcessError,ValueError)):
            guard.audit_history(self.root, base=self.base)

    def test_signed_tree_preserving_pr_merge_is_scanned(self):
        command(self.root, "checkout", "-qb", "side")
        (self.root / "side.txt").write_text("Synthetic reviewed change")
        commit(self.root, "reviewed PR commit")
        command(self.root, "checkout", "main")
        command(self.root, "-c", "core.hooksPath=/dev/null", "merge",
                "--no-ff", "side", "-m", "reviewed PR merge")
        result=guard.audit_history(self.root, base=self.base)
        self.assertTrue(result["historyBoundaryPassed"])
        self.assertEqual(result["reviewedContentPreservingMerges"],1)
        self.assertEqual(result["newCommits"],2)
        self.assertGreaterEqual(result["changedBlobsScanned"],1)

    def test_pr_branch_added_then_deleted_secret_still_fails(self):
        command(self.root, "checkout", "-qb", "side")
        (self.root / "sensitive.txt").write_text("sk" + "-" + "S" * 40)
        commit(self.root, "synthetic exposed blob")
        (self.root / "sensitive.txt").unlink()
        commit(self.root, "removed exposed blob")
        command(self.root, "checkout", "main")
        command(self.root, "-c", "core.hooksPath=/dev/null", "merge",
                "--no-ff", "side", "-m", "merge reviewed branch")
        with self.assertRaisesRegex(ValueError,"provider-api-secret"):
            guard.audit_history(self.root,base=self.base)

    def test_merge_resolution_with_unreviewed_tree_is_refused(self):
        command(self.root, "checkout", "-qb", "side")
        (self.root / "side.txt").write_text("Reviewed source")
        commit(self.root, "side branch")
        command(self.root, "checkout", "main")
        (self.root / "main.txt").write_text("Unreviewed extra merge content")
        commit(self.root, "base branch changed")
        command(self.root, "-c", "core.hooksPath=/dev/null", "merge",
                "--no-ff", "side", "-m", "merge resolution")
        with self.assertRaisesRegex(ValueError,"Unreviewed merge resolution"):
            guard.audit_history(self.root,base=self.base)

    def test_merge_with_unrelated_history_is_refused(self):
        command(self.root, "checkout", "--orphan", "other-root")
        command(self.root, "rm", "-rf", ".")
        (self.root / "other.txt").write_text("Foreign synthetic root")
        commit(self.root, "synthetic unrelated root")
        command(self.root, "checkout", "main")
        command(self.root, "-c", "core.hooksPath=/dev/null", "merge",
                "--allow-unrelated-histories", "--no-ff", "other-root",
                "-m", "unrelated import")
        with self.assertRaisesRegex(ValueError,"outside approved baseline|Unsupported public history root"):
            guard.audit_history(self.root,base=self.base)


class ReleaseInventoryTests(unittest.TestCase):
    """Focused preflight risks, no production signing or hosted interactions."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "public"
        self.root.mkdir()
        command(self.root, "init", "-q", "-b", "main")
        (self.root / "README.md").write_text("Synthetic public root\n")
        self.base = commit(self.root, "approved synthetic baseline")

    def test_history_includes_added_then_deleted_bytes_not_only_head_diff(self):
        (self.root / "docs").mkdir()
        (self.root / "docs/transient.md").write_text("Synthetic old value, removed in next commit\n")
        first = commit(self.root, "add review material")
        (self.root / "docs/transient.md").unlink()
        second = commit(self.root, "delete review material")
        self.assertFalse(command(self.root, "diff", "--name-only", self.base, second))
        result = guard.candidate_object_inventory(self.root, self.base,
                                                   approved_base=self.base)
        versions = [x for x in result["historicalChangedFileVersions"]
                    if x["path"] == "docs/transient.md"]
        self.assertEqual({v["action"] for v in versions}, {"A", "D"})
        self.assertFalse(versions[0]["presentAtCandidateHEAD"])
        self.assertTrue(any(x.get("sha256") == hashlib.sha256(
            b"Synthetic old value, removed in next commit\n").hexdigest()
            for x in versions))
        self.assertEqual(result["newCommits"], [first, second])
        self.assertTrue(any(x["type"] == "blob" for x in result["newReachableGitObjects"]))
        self.assertFalse(result["signatureOrPermissionIssued"])

    def test_no_new_objects_at_identical_head(self):
        result = guard.candidate_object_inventory(self.root, self.base,
                                                   approved_base=self.base)
        self.assertEqual(result["newCommits"], [])
        self.assertEqual(result["newReachableGitObjects"], [])
        self.assertEqual(result["historicalChangedFileVersions"], [])

    def test_private_path_and_token_blocked_even_if_later_deleted(self):
        target = self.root / "internal-research" / "secrets.txt"
        target.parent.mkdir()
        target.write_text("Synthetic private document only\n")
        commit(self.root, "synthetic forbidden temporary addition")
        target.unlink()
        commit(self.root, "synthetic forbidden deletion")
        with self.assertRaisesRegex(ValueError, "private-source-archive-present"):
            guard.candidate_object_inventory(self.root, self.base, approved_base=self.base)

    def test_secret_in_commit_history_blocked(self):
        (self.root / "docs").mkdir()
        (self.root / "docs" / "unsafe.txt").write_text("ghp_" + "X" * 32 + "\n")
        commit(self.root, "temporary synthetic token")
        (self.root / "docs" / "unsafe.txt").unlink()
        commit(self.root, "remove synthetic token")
        with self.assertRaisesRegex(ValueError, "github-access-token"):
            guard.candidate_object_inventory(self.root, self.base, approved_base=self.base)

    def test_release_inventory_refuses_uncommitted_or_other_head(self):
        guard.require_clean_candidate(self.root, "HEAD")
        (self.root / "README.md").write_text("dirty nonpublished worktree\n")
        with self.assertRaisesRegex(ValueError, "clean committed public checkout"):
            guard.require_clean_candidate(self.root, "HEAD")
        (self.root / "README.md").write_text("Synthetic public root\n")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "new.md").write_text("new legitimate commit\n")
        commit(self.root, "new commit after baseline")
        with self.assertRaisesRegex(ValueError, "checked-out HEAD"):
            guard.require_clean_candidate(self.root, self.base)

    def test_exact_pages_flags_changes_and_untrusted_reference(self):
        old = Path(self.tmp.name) / "baseline"
        new = Path(self.tmp.name) / "candidate"
        for site in (old, new):
            (site / "assets").mkdir(parents=True)
            (site / "index.html").write_text("<html><head></head><body></body></html>\n")
            (site / "assets" / "app.js").write_text("const ok=true;\n")
        digest = guard.site_inventory_digest(guard.exact_site_inventory(old))
        result = guard.compare_exact_pages(new, old, historic_digest=digest)
        self.assertTrue(result["byteIdenticalToHistorical"])
        (new / "assets" / "app.js").write_text("const ok=false;\n")
        (new / "assets" / "extra.js").write_text("const extra=true;\n")
        (new / "index.html").unlink()
        result = guard.compare_exact_pages(new, old, historic_digest=digest)
        self.assertEqual({x["change"] for x in result["changedAssetsRequireExactReview"]},
                         {"MODIFIED", "ADDED", "REMOVED"})
        with self.assertRaisesRegex(ValueError, "reference differs"):
            guard.compare_exact_pages(new, old, historic_digest="0" * 64)
        (new / "assets" / "leak.js").symlink_to(old / "assets" / "app.js")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            guard.compare_exact_pages(new, old, historic_digest=digest)


if __name__ == "__main__":
    unittest.main(verbosity=2)
