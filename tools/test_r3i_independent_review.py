#!/usr/bin/env python3
"""R3i independent review gate: synthetic throwaway Ed25519 only.

No real reviewer, signer, permission, registration or release file is created.
No permission outside temp fixtures is read or changed.
"""
from __future__ import annotations

import base64
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import independent_review_gate as review

HEAD="0123456789abcdef0123456789abcdef01234567"

class SyntheticReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="r3i-ephemeral-review-")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.trust=self.root/"trust.json"
        self.decisions=self.root/"decisions"
        self.decisions.mkdir()
        self.secret=self.root/"SYNTHETIC_TEST_PRIVATE.pem"
        self.public=self.root/"SYNTHETIC_TEST_PUBLIC.pem"
        subprocess.run(["/usr/bin/openssl","genpkey","-algorithm","Ed25519",
                        "-out",str(self.secret)],check=True,capture_output=True)
        subprocess.run(["/usr/bin/openssl","pkey","-in",str(self.secret),
                        "-pubout","-out",str(self.public)],check=True,capture_output=True)
        self.roster={
            "schemaVersion":1,
            "reviewers":{
                "synthetic-independent-fixture":{
                    "publicKeyPEM":base64.b64encode(self.public.read_bytes()).decode(),
                    "active":True,"independent":True
                }
            },
            "revocations":[],
        }
        self.blob=b'const row={sourceId:"AA"};row[key]=91;'
        self.reasons=["indeterminate-js-requires-independent-review"]
        self.context=review._context(
            head=HEAD,surface="source",path="assets/row.js",
            blob=self.blob,reasons=self.reasons)
        self.doc={
            "schemaVersion":1,
            "kind":"APL_INDEPENDENT_RIGHTS_REVIEW",
            "decision":"APPROVE",
            "reviewerID":"synthetic-independent-fixture",
            "reviewID":"synthetic-test-approval-01",
            "issuedAt":"2026-01-01T00:00:00+00:00",
            "expiresAt":"2099-01-01T00:00:00+00:00",
            "revoked":False,
            "context":self.context,
            "rights":{
                "provenanceExamined":True,"licensesExamined":True,
                "attributionExamined":True,"redistributionAllowed":True,
                "scopeDescription":"SYNTHETIC fixture only, no real-world rights or release authority",
                "sourceDocuments":["synthetic fixture reference 000001"],
            }
        }
    def signed(self,doc=None,*,secret=None,roster=None):
        doc=doc or self.doc
        p=self.root/"to-sign.json"
        p.write_bytes(review.canonical(doc))
        sig=self.root/"signature"
        subprocess.run(["/usr/bin/openssl","pkeyutl","-sign","-rawin",
                        "-inkey",str(secret or self.secret),"-in",str(p),"-out",str(sig)],
                       check=True,capture_output=True)
        package={"document":doc,"ed25519Signature":base64.b64encode(sig.read_bytes()).decode()}
        context=doc["context"]
        name=hashlib.sha256(review.canonical(context)).hexdigest()+".json"
        (self.decisions/name).write_bytes(review.canonical(package))
        self.trust.write_bytes(review.canonical(roster or self.roster))
        return name
    def allow(self,**kw):
        return review.enforce(
            head=kw.get("head",HEAD),
            surface=kw.get("surface","source"),path=kw.get("path","assets/row.js"),
            blob=kw.get("blob",self.blob),
            reasons=kw.get("reasons",self.reasons),
            trust_file=self.trust,decisions_dir=self.decisions,
            allow_synthetic_test_roots=True,now=kw.get("now",datetime(2026,10,21,tzinfo=timezone.utc)))
    def test_valid_ephemeral_signed_decision(self):
        self.signed()
        result=self.allow()
        self.assertEqual(result["status"],"INDEPENDENT_SIGNED_EXACT_BYTES_REVIEW")
        self.assertEqual(result["reviewerID"],"synthetic-independent-fixture")
    def test_missing_record_and_uninstalled_authority(self):
        with self.assertRaisesRegex(ValueError,"Missing independent exact-byte review"):
            self.allow()
        with self.assertRaises(ValueError):
            review.enforce(HEAD,"source","assets/row.js",self.blob,reasons=self.reasons)
    def test_candidate_cannot_override_production_roots(self):
        self.signed()
        with self.assertRaisesRegex(ValueError,"Candidate cannot choose"):
            review.enforce(HEAD,"source","assets/row.js",self.blob,
                           reasons=self.reasons,trust_file=self.trust,
                           decisions_dir=self.decisions)
    def test_candidate_wrong_head_bytes_path_scope_reason(self):
        self.signed()
        for values in (
            {"head":"a"*40},
            {"blob":self.blob+b"x"},
            {"path":"assets/other.js"},
            {"surface":"history"},
            {"reasons":["indeterminate-different-review-scope"]},
        ):
            with self.subTest(values):
                with self.assertRaises(ValueError):
                    self.allow(**values)
    def test_unenrolled_self_issued_reviewer(self):
        self.signed()
        bad=dict(self.roster,reviewers={})
        self.trust.write_bytes(review.canonical(bad))
        with self.assertRaisesRegex(ValueError,"not independently enrolled"):
            self.allow()
    def test_forged_signature_wrong_key_and_modified_contents(self):
        self.signed()
        name=hashlib.sha256(review.canonical(self.context)).hexdigest()+".json"
        f=self.decisions/name
        packet=review.read_json(f.read_bytes())
        packet["document"]["rights"]["redistributionAllowed"]=False
        f.write_bytes(review.canonical(packet))
        with self.assertRaises(ValueError):
            self.allow()
        self.signed()
        packet=review.read_json(f.read_bytes())
        packet["document"]["rights"]["sourceDocuments"].append("synthetic tamper after signing")
        f.write_bytes(review.canonical(packet))
        with self.assertRaisesRegex(ValueError,"signature invalid"):
            self.allow()
    def test_expired_not_yet_issued_and_revoked(self):
        self.doc["expiresAt"]="2026-02-01T00:00:00+00:00"
        self.signed()
        with self.assertRaisesRegex(ValueError,"expiry"):self.allow()
        self.doc["expiresAt"]="2099-01-01T00:00:00+00:00"
        self.doc["issuedAt"]="2027-01-01T00:00:00+00:00"
        self.signed()
        with self.assertRaises(ValueError):self.allow()
        self.doc["issuedAt"]="2026-01-01T00:00:00+00:00"
        roster=dict(self.roster,revocations=["synthetic-test-approval-01"])
        self.signed(roster=roster)
        with self.assertRaisesRegex(ValueError,"revoked"):self.allow()
    def test_rights_and_independence_not_declared(self):
        self.doc["rights"]["licensesExamined"]=False
        self.signed()
        with self.assertRaisesRegex(ValueError,"Unexamined"):self.allow()
        self.doc["rights"]["licensesExamined"]=True
        roster=json.loads(json.dumps(self.roster))
        roster["reviewers"]["synthetic-independent-fixture"]["independent"]=False
        self.signed(roster=roster)
        with self.assertRaisesRegex(ValueError,"not independent"):self.allow()
    def test_malformed_record_duplicate_key(self):
        self.signed()
        name=hashlib.sha256(review.canonical(self.context)).hexdigest()+".json"
        (self.decisions/name).write_bytes(b'{"document":{},"document":{},"ed25519Signature":"A"}')
        with self.assertRaisesRegex(ValueError,"duplicate"):self.allow()
    def test_unequivocal_prohibited_cannot_be_downgraded(self):
        reasons=["unreviewed-embedded-publisher-score",
                 "indeterminate-js-requires-independent-review"]
        self.assertFalse(review.needs_review(reasons))
        self.assertEqual(
            review.gate(reasons,HEAD,"source","assets/row.js",self.blob),
            reasons)
    def test_synthetic_release_not_live_authority(self):
        sample={f"asset{i}.js":hashlib.sha256(str(i).encode()).hexdigest() for i in range(17)}
        with self.assertRaises(ValueError):
            review.pages_release_gate(HEAD,"public",sample)
        with self.assertRaises(ValueError):
            review.frozen_release_gate(HEAD,b"synthetic never signed")
    def test_outside_review_scope_rejected(self):
        for path in ("/etc/passwd","../bad.js","dir/../../bad.js"):
            with self.subTest(path):
                with self.assertRaises(ValueError):
                    review._context(head=HEAD,surface="source",path=path,
                                    blob=b"",reasons=self.reasons)

if __name__=="__main__":
    unittest.main(verbosity=2)
