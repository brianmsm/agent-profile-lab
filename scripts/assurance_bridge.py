"""Offline JSON bridge for Python/TypeScript assurance parity tests only."""
import json,sys
from pathlib import Path
from profile_assurance import assess_resolved
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
 value=json.load(sys.stdin);offers=json.loads((ROOT/'catalog/offerings.json').read_bytes())['offerings']
 print(json.dumps(assess_resolved(value['roles'],value['harness'],value['domain'],offers),ensure_ascii=False))
