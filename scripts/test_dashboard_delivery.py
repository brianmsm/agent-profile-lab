import gzip,hashlib,json,tempfile,unittest
from pathlib import Path
from copy import deepcopy
from dashboard_delivery import build_delivery,pack_core,unpack_core,EVIDENCE_FIELDS
ROOT=Path(__file__).resolve().parents[1]
class DeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.s=json.loads((ROOT/'dashboard/tests/fixtures/activity-fixture.json').read_text())
    def test_dictionary_roundtrip_is_lossless_and_inputs_unmodified(self):
        before=deepcopy(self.s);p=pack_core(self.s)
        restored=unpack_core(p)
        self.assertEqual({**restored,**{k:self.s[k] for k in EVIDENCE_FIELDS if k in self.s}},self.s)
        self.assertEqual(self.s,before)
        self.assertLessEqual(len(p['routes']),sum(len(m) for m in self.s['routeDetails'].values())+sum(len(st['routes']) for st in self.s['strategies'].values()))
    def test_arbitrary_precision_strings_and_fractional_values_survive(self):
        s=deepcopy(self.s);r=next(iter(next(iter(s['routeDetails'].values())).values()))
        r['rationale']='á\n\"zero\" Ω 0.12345678901234567';r['extra']=0.12345678901234567
        self.assertEqual(unpack_core(pack_core(s))['routeDetails'],s['routeDetails'])
    def test_content_addressed_gzip_reproducible_and_resolves_same_revision(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'snapshot.json';source.write_text(json.dumps(self.s,ensure_ascii=False))
            one=build_delivery(self.s,source);two=build_delivery(self.s,source)
            self.assertEqual(one,two)
            for part in one['parts'].values():
                data=(source.parent/part['path']).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(),part['sha256'])
                self.assertEqual(len(data),part['bytes']);self.assertEqual(len(gzip.decompress(data)),part['decodedBytes'])
            self.assertEqual(one['sourceSha256'],hashlib.sha256(source.read_bytes()).hexdigest())
    def test_revision_changes_cannot_overwrite_old_fragments(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'snapshot.json';source.write_text(json.dumps(self.s))
            old=build_delivery(self.s,source);old_bytes=(source.parent/old['parts']['core']['path']).read_bytes()
            s=deepcopy(self.s);s['stats']['session']='new revision';source.write_text(json.dumps(s))
            new=build_delivery(s,source)
            self.assertNotEqual(old['parts']['core']['path'],new['parts']['core']['path'])
            self.assertEqual(old_bytes,(source.parent/old['parts']['core']['path']).read_bytes())
if __name__=='__main__':unittest.main()
