"""Conservative contradiction detector, NOT a proof of operational enforcement.

Text-only policy claims are not executable controls. This module catches
explicit permissive overrides in a dated and bounded grammar and fails closed
when a protected gate contradicts its prohibitions. Unknown wording requires
human policy review, not unearned semantic certification.
"""
from __future__ import annotations
import re,unicodedata

def fold(text: str) -> str:
    if not isinstance(text,str):return ''
    return ''.join(ch for ch in unicodedata.normalize('NFKD',text.casefold()) if not unicodedata.combining(ch))

def explicit_permission_contradiction(text: str) -> bool:
    for clause in re.split(r'[.;\n]+',fold(text)):
        if not clause.strip():continue
        if re.search(r'\b(?:no|nunca|jam[aá]s)\s+(?:se\s+)?(?:permite|permiten|autoriza|autorizan|puede|pueden|ejecutar)\b',clause):
            continue
        allowed=bool(re.search(r'\b(?:se\s+permit\w*|permitid\w*|se\s+autoriza\w*|puede\w*|ejecut\w*)\b',clause))
        dangerous=bool(re.search(r'\b(?:destructiv\w*|persisten\w*|sistemas?\s+reales?|efectos?\s+reales?)\b',clause))
        unauthorized=bool(re.search(r'\b(?:sin\s+autorizacion|sin\s+confirmacion|sin\s+revision|sin\s+permiso|no\s+requiere\s+autorizacion)\b',clause))
        if allowed and dangerous and unauthorized:return True
    return False
