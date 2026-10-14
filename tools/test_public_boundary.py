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
            root=Path(temp);built=root/'dashboard/dist';d=root/'dashboard/public/data';d.mkdir(parents=True)
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
            (built/'docs').mkdir()
            (built/'docs/redteam-scores.csv').write_text('sourceId,model,value\nAA,local-synthetic,93.7\n')
            with self.assertRaisesRegex(ValueError,'Unapproved Pages output file'):
                guard.audit_built_site(built,root=root)

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
        self.assertIn('unreviewed-tabular-publisher-score',guard.inspect_payload('docs/invented-bfcl.csv',data))

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
        with self.assertRaisesRegex(ValueError, "nonregular-git-object"):
            guard.audit_history(self.root, base=self.base)

    def test_unrelated_base(self):
        command(self.root, "checkout", "--orphan", "other")
        (self.root / "README.md").write_text("Unrelated synthetic baseline")
        commit(self.root, "orphan")
        with self.assertRaises(subprocess.CalledProcessError):
            guard.audit_history(self.root, base=self.base)

    def test_merge_rejected(self):
        command(self.root, "checkout", "-qb", "side")
        (self.root / "side.txt").write_text("synthetic")
        commit(self.root, "side")
        command(self.root, "checkout", "main")
        (self.root / "main.txt").write_text("synthetic")
        commit(self.root, "main")
        command(self.root, "-c", "core.hooksPath=/dev/null", "merge", "--no-ff", "side", "-m", "synthetic merge")
        with self.assertRaisesRegex(ValueError, "Nonlinear public history"):
            guard.audit_history(self.root, base=self.base)


if __name__ == "__main__":
    unittest.main(verbosity=2)
