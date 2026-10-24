#!/usr/bin/env python3
"""Audit public files and, optionally, every change after an approved Git baseline.

Read-only, offline and fail-closed. Findings contain paths/reasons, never matched
secrets. This is a release guard, not legal clearance or an adversarial DLP proof.
Pair it with verify_public_release.py, review, and the private transfer allowlist.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
# Two explicitly recognized layouts: the public checkout and the private
# overlay used by the sync planner.  Never search parent directories from the
# public checkout (where a private sibling may happen to be present).
if ROOT.name == "overlay" and ROOT.parent.name == "republication":
    STRICT_SCRIPTS = ROOT.parents[1] / "scripts"
else:
    STRICT_SCRIPTS = ROOT / "scripts"
if not (STRICT_SCRIPTS / "strict_data_formats.py").is_file():
    raise ImportError("Required strict data parser absent from checkout-local scripts")
sys.path.insert(0, str(STRICT_SCRIPTS))
from strict_data_formats import json_loads_strict
from git_object_integrity import git_bytes,verified_git_history_inventories,verified_git_objects
from publisher_semantics import js_classify,xml_score,json_score,xml_indeterminate_sibling_provenance,xml_requires_review,json_requires_review
# REVIEW remains a blocking finding; a single maintainer reviews exact bytes
# at release time. No external reviewer/signing infrastructure is needed
# to detect or reject ambiguous content during ordinary CI.
APPROVED_PUBLIC_BASE = "58a682d6ca6f3ed0b595d7daed5208bc56bd9385"
MAX_BYTES = 128 * 1024 * 1024
BAD_COMPONENTS = {"evidence", "sources", "internal-research", "republication"}
RUNTIME_DIRS = {"node_modules", "dist", "__pycache__", "validation", ".venv", ".pytest_cache"}
REGENERATED = {
    "data/assignments.csv", "data/assignments.csv.gz", "data/assignments.json",
    "data/profiles.json", "data/model-catalog.json", "data/omp-runtime-policies.json",
    "policies/functional-precedents.json",
}
BAD_SUFFIXES = {".raw", ".pdf", ".sqlite", ".sqlite3", ".db", ".env", ".bundle",
                ".zip", ".tar", ".tgz", ".bz2", ".xz", ".7z", ".pyc", ".pyo"}
MUST_EXIST = ["LICENSE", "README.md", "THIRD_PARTY_NOTICES.md",
              "data/assignment-shards/manifest.json", "data/public-evidence/source-links.json",
              "dashboard/public/data/snapshot.json", "tools/verify_public_release.py"]
CHUNK = re.compile(r"dashboard/public/data/chunks/(?:core|evidence)-([a-f0-9]{64})\.json\.gz\Z")
PATTERNS = {
    "private-user-home": re.compile(rb"/(?:home|Users)/[A-Za-z0-9_.-]+/(?:Documents|\.config|\.local|Library)/", re.I),
    "github-access-token": re.compile(rb"(?:ghp_|gho_|ghu_|ghs_|github_pat_)[A-Za-z0-9_]{25,}"),
    "provider-api-secret": re.compile(rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"),
    "private-key-PEM": re.compile(rb"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----"),
    "long-bearer-token": re.compile(rb"\bBearer[ \t]+[A-Za-z0-9_.~-]{40,}\b", re.I),
}


def git(root: Path, *args: str) -> bytes:
    return git_bytes(root,*args)


def path_reason(relative: str, *, tracked: bool = True) -> str | None:
    parts = PurePosixPath(relative).parts
    if (not parts or relative != PurePosixPath(relative).as_posix() or
            relative.startswith("/") or "\\" in relative or ".." in parts or
            any(ord(c) < 32 for c in relative)):
        return "unsafe-path"
    if ".git" in parts or ".gitmodules" in parts:
        return "nested-vcs-or-submodule"
    if any(p in BAD_COMPONENTS for p in parts) or parts[0] == "generated":
        return "private-source-archive-present"
    if tracked and (any(p in RUNTIME_DIRS for p in parts) or relative in REGENERATED):
        return "runtime-or-private-output-tracked"
    if any(p == ".env" or p.startswith(".env.") for p in parts):
        return "environment-file-not-approved"
    suffix = PurePosixPath(relative).suffix.lower()
    if suffix in BAD_SUFFIXES or (suffix == ".gz" and not CHUNK.fullmatch(relative)):
        return "archive-or-capture-not-authorized"
    return None


SCORE_FIELDS={'value','score','scores','scorevalues','accuracy','benchmarkaccuracy','scorepct','scorepercent','intelligenceindex','benchmarkscore','overallacc','overallaccuracy',
              'latency','tokenspersecond','modelscore','passrate'}
IDENTITY_FIELDS={'sourceid','publisher','sourceurl','source','provider','url','datasource','datasourceid','datapublisher'}
AGGREGATE_UNITS={'reference-links','reference-count','references','rows','source-count'}
NUMERIC=re.compile(r'[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?%?\Z')
SOURCE_TOKEN=re.compile(r'(?:sourceId|source_id|publisher)\s*["\x27\\]*\s*[:=]\s*["\x27\\]*([A-Za-z][A-Za-z0-9_-]{0,48})',re.I)
# Encoded numeric conversions are still editorial measurements when directly
# attached to a known publisher source marker. This remains a heuristic DLP.
METRIC_TOKEN=re.compile(
    r"""(?:value|score(?:_pct|Percent)?|accuracy|intelligence[_-]?index|benchmark[_-]?score)
         \s*["'\\]*\s*[:=]\s*
         (?:(?:Number|parseFloat)\s*\(\s*["']?\s*)?
         [+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)
    """,re.I|re.X)


# XML/SVG metadata and JSX expressions are not parsed by json_loads_strict.
# These lexical guards are intentionally conservative: they block suspicious
# publisher-score representation pending explicit independent rights review.
XML_SOURCE_TOKEN=re.compile(
    r'''<\s*(?:sourceId|source_id|publisher)\b[^>]*>\s*([A-Za-z][A-Za-z0-9_-]{0,48})\s*<\s*/\s*'''+
    r'''(?:sourceId|source_id|publisher)\s*>|\bdata[-_](?:source|sourceid|publisher)\s*=\s*["']([A-Za-z][A-Za-z0-9_-]{0,48})["']''',re.I)
METRIC_PROPERTY_TOKEN=re.compile(
    r'''\b(?:data[-_])?(?:value|score(?:_pct|Percent)?|accuracy|intelligence[_-]?index|benchmark[_-]?score|passrate)\b
        \s*(?:["']?\s*[:=]\s*["']?|\s*>\s*)\s*\{?\s*
        (?:(?:(?:globalThis|window)\s*\.\s*)?(?:Number|parseFloat|parseInt)\s*\(\s*)?
        (?:\+\s*\(\s*)?[+"']?\s*[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)
    ''',re.I|re.X)
METRIC_FIELD_TOKEN=re.compile(
    r'''\b(?:value|score(?:_pct|Percent)?|accuracy|intelligence[_-]?index|benchmark[_-]?score)\s*
        (?:["']?\s*[:=]|\s*>)
    ''',re.I|re.X)
NUMERIC_CONVERSION_TOKEN=re.compile(
    r'''(?:(?:globalThis|window)\s*\.\s*)?(?:Number|parseFloat|parseInt)
       \s*\(\s*["']?\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)
    ''',re.I|re.X)

def normalized_key(key: object) -> str:
    return re.sub('[^a-z0-9]','',str(key).lower())

def is_numeric_score(value: object) -> bool:
    return (isinstance(value,(int,float)) and not isinstance(value,bool)) or (
        isinstance(value,str) and bool(NUMERIC.fullmatch(value.strip())))

def legitimate_aggregate(row: dict) -> bool:
    kind=str(row.get('kind','')).lower()
    unit=str(row.get('unit','')).lower()
    return (kind=='aggregate-count' and unit in AGGREGATE_UNITS
            and isinstance(row.get('value'),int) and not isinstance(row.get('value'),bool)
            and not any(normalized_key(k) in ('model','benchmark','metric','evaluation') for k in row))

def numeric_source_rows(value: object) -> bool:
    """Detect typed direct and inherited publisher scores, not local oracles.

    An unknown sourceId by itself can identify a local test document; only
    carry numerical publisher context to descendants when the provenance is
    independently identified as external (AA/FCDATA or publisher website).
    """
    stack=[(value,False)]
    while stack:
        row,inherited_publisher=stack.pop()
        if isinstance(row,list):
            stack.extend((item,inherited_publisher) for item in row)
        elif isinstance(row,dict):
            lower={normalized_key(k):v for k,v in row.items()}
            source_id=str(lower.get('sourceid','')).lower()
            provenance=' '.join(str(lower.get(k,'')) for k in IDENTITY_FIELDS).lower()
            publisher=inherited_publisher or source_id in ('aa','fcdata') or any(
                x in provenance for x in ('artificialanalysis','slopalytics','frontiercode'))
            if source_id=='br-bfcl-data':publisher=False
            if legitimate_aggregate(row):continue
            numeric=any(k in SCORE_FIELDS or k.startswith(('scorepct','accuracy','benchmarkscore'))
                        for k,v in lower.items() if is_numeric_score(v))
            if numeric and (publisher or (source_id and source_id!='br-bfcl-data' and (
                 'sourceid' in lower and any(k in SCORE_FIELDS or k.startswith(('scorepct','accuracy'))
                                             for k,v in lower.items() if is_numeric_score(v))))):
                return True
            stack.extend((v,publisher) for v in row.values())
    return False

def indexed_score_header(raw: str) -> bool:
    """Score array indexes in CSV/TSV are real numeric score fields.

    Restrict proof to explicitly indexed spelling; other opaque score-like
    aliases are REVIEW rather than invented semantic certainty.
    """
    candidate=re.sub(r"\s+","",raw.strip().lower())
    return bool(re.fullmatch(r"(?:scores?|score_values?|scorevalues)(?:\[\d{1,3}\]|\.\d{1,3})",candidate))

def tabular_score_reasons(relative: str, text: str) -> list[str]:
    """Block unreviewed publisher score tables; allow typed aggregate counts.

    Unknown editorial sources should be reviewed rather than silently
    treated as authorized based only on a transport SHA.
    """
    header=text.splitlines()[0] if text.splitlines() else ''
    delimiter='\t' if relative.lower().endswith('.tsv') else ';' if header.count(';')>header.count(',') else ','
    try:
        reader=csv.DictReader(io.StringIO(text,newline=''),delimiter=delimiter,restkey='__EXTRA__')
        fields=reader.fieldnames
        if not fields or len(fields)>128:return ['invalid-tabular-schema']
        normalized=[normalized_key(x.strip()) for x in fields]
        if len(set(normalized))!=len(normalized):return ['duplicate-tabular-column']
        scores=[name for name,canonical in zip(fields,normalized)
                if canonical in SCORE_FIELDS or canonical.startswith(('scorepct','accuracy'))
                or indexed_score_header(name)]
        uncertain=[name for name,canonical in zip(fields,normalized)
                   if canonical.startswith(('score','scores','accuracy','benchmarkscore'))
                   and name not in scores]
        if not scores and not uncertain:return []
        has_origin=bool(set(normalized)&IDENTITY_FIELDS)
        if not has_origin:return []  # local synthetic fixtures without publisher provenance
        for row in reader:
            if '__EXTRA__' in row or any(v is None for v in row.values()):
                return ['malformed-tabular-score-row']
            normalized_row={normalized_key(k):v.strip() for k,v in row.items()}
            # Aggregate-count only excuses a NON-score value column.
            # A score field is an editorial measurement despite kind/unit.
            if (normalized_row.get('unit','').lower() in AGGREGATE_UNITS
                    and normalized_row.get('kind','aggregate-count').lower()=='aggregate-count'
                    and not any(k!='value' for k in (normalized_key(x) for x in scores))
                    and normalized_row.get('value','').isdecimal()):
                continue
            source=' '.join(normalized_row.get(k,'') for k in IDENTITY_FIELDS).lower()
            if not source:continue
            if any(is_numeric_score(row.get(field,'')) for field in uncertain):
                return ['indeterminate-tabular-score-alias-requires-independent-review']
            # SourceId alone is not an entitlement to redistribute new BFCL
            # tables. Only the approved typed BFCL evidence is authorized:
            # newly introduced score CSV needs independent review as well.
            definite=False
            unresolved=False
            for field in scores:
                raw_value=str(row.get(field,'')).strip()
                if not raw_value:
                    continue
                if is_numeric_score(raw_value):
                    definite=True
                elif normalized_key(field) in ('scorevalues','scores'):
                    if raw_value.strip().lower() in ('unavailable','not available','not measured','n/a','na','none','null'):
                        continue
                    if re.fullmatch(r'\s*[+-]?\d+(?:[.|,;]\s*[+-]?\d+)+\s*',raw_value):
                        definite=True
                    elif raw_value.startswith('['):
                        try:
                            arr=json.loads(raw_value)
                            if (isinstance(arr,list) and arr
                                and all(is_numeric_score(v) for v in arr)):
                                definite=True
                            else:unresolved=True
                        except (ValueError,TypeError):
                            unresolved=True
                    else:unresolved=True
                else:
                    # A purely qualitative scalar is not a measurement.
                    # Opaque functional/encoded scalar expressions are.
                    if re.search(r'\b(?:atob|parse|decode|Number|eval)\s*\(|\$\{|\[',raw_value):
                        unresolved=True
            if definite:
                if source.strip() == "br-bfcl-data":
                    # A new CSV self-label cannot grant rights to measurements.
                    # Its provenance is uncertain, unlike a proven external
                    # non-BFCL publisher score.
                    return ['indeterminate-bfcl-source-label-requires-independent-review']
                return ['unreviewed-tabular-publisher-score']
            if unresolved:
                return ['indeterminate-tabular-publisher-score-requires-independent-review']
        return []
    except (csv.Error,ValueError,TypeError):return ['invalid-tabular-schema']

def embedded_publisher_score(text: str) -> bool:
    """High-confidence visible literals, including JSX attributes and minified JS.

    This is a heuristic, not an exhaustive encoding-aware DLP system. Explicit
    pre-publication human source review remains mandatory.
    """
    flattened=text.replace('\\\"','"').replace("\\'", "'")
    hits=[(m.end(),m.group(1).lower()) for m in SOURCE_TOKEN.finditer(flattened)]
    hits.extend((m.end(),(m.group(1) or m.group(2)).lower())
                for m in XML_SOURCE_TOKEN.finditer(flattened))
    for start,source in hits:
        if source in ('br-bfcl-data','synthetic','local'):
            continue
        snippet=flattened[start:start+420]
        # Prevent false positives on reviewed publisher link counts.
        if (source=='aa' and 'aggregate-count' in snippet[:180].lower() and
            any(unit in snippet[:220].lower() for unit in AGGREGATE_UNITS)):
            continue
        if METRIC_TOKEN.search(snippet) or METRIC_PROPERTY_TOKEN.search(snippet):
            return True
        # Conservative guard for indirect numerical conversion in a JS/TSX
        # object with external sourceId and score:someLocalVariable.
        if METRIC_FIELD_TOKEN.search(snippet) and NUMERIC_CONVERSION_TOKEN.search(snippet):
            return True
    return False

def javascript_reasons(text:str)->list[str]:
    """Common effective tri-state policy for direct JS and embedded scripts."""
    classification=js_classify(text)
    if classification=="PROHIBITED":
        return ['unreviewed-embedded-publisher-score']
    if classification=="REVIEW":
        reasons=['indeterminate-js-requires-independent-review']
        # Retain the historic R3g diagnostic, now for every JS consumer.
        if re.search(r'JSON\s*\.\s*parse\s*\(\s*atob\s*\(\s*(?![\x27\x22])',text):
            reasons.append('opaque-editorial-encoding-requires-independent-review')
        return reasons
    return []


def html_score_reasons(text:str)->list[str]:
    """Inspect HTML script bodies and same-element data attributes, not HTML as JS."""
    from html.parser import HTMLParser
    from publisher_semantics import check
    findings=[]
    class HTMLRecords(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.script_type=None
            self.script_content=[]
        def handle_starttag(self,tag,attrs):
            if tag=="script":
                if self.script_type is not None:
                    findings.append("indeterminate-html-nested-script-requires-independent-review")
                d={str(k).lower():v for k,v in attrs}
                self.script_type=d.get("type","text/javascript").lower()
                self.script_content=[]
            fields={}
            for k,v in attrs:
                if v is None:continue
                key=normalized_key(k.removeprefix("data-"))
                fields[key]=v
                if v.lstrip().startswith(("{","[")) and len(v)<=200000:
                    try:
                        value=json_loads_strict(v)
                        if json_requires_review(value):
                            findings.append("indeterminate-json-alias-requires-independent-review")
                        elif json_score(value):
                            findings.append("unreviewed-embedded-publisher-score")
                    except (ValueError,TypeError):
                        if "sourceid" in v.lower() and "score" in v.lower():
                            findings.append("indeterminate-html-embedded-json-requires-independent-review")
            if check(fields):
                findings.append("unreviewed-embedded-publisher-score")
        def handle_data(self,data):
            if self.script_type is not None:self.script_content.append(data)
        def handle_endtag(self,tag):
            if tag!="script" or self.script_type is None:return
            content="".join(self.script_content)
            if self.script_type in ("application/json","application/ld+json"):
                try:
                    v=json_loads_strict(content)
                    if json_requires_review(v):
                        findings.append("indeterminate-json-alias-requires-independent-review")
                    elif json_score(v):
                        findings.append("unreviewed-embedded-publisher-score")
                except (ValueError,TypeError):
                    findings.append("indeterminate-html-json-script-requires-independent-review")
            elif self.script_type in ("text/javascript","application/javascript","module",""):
                findings.extend(javascript_reasons(content))
            elif content.strip():
                findings.append("indeterminate-html-script-type-requires-independent-review")
            self.script_type=None
            self.script_content=[]
    parser=HTMLRecords()
    try:
        parser.feed(text)
        parser.close()
    except (ValueError,RecursionError):
        findings.append("indeterminate-html-requires-independent-review")
    if parser.script_type is not None:
        findings.append("indeterminate-html-unclosed-script-requires-independent-review")
    return sorted(set(findings))

def inspect_payload(relative: str, data: bytes, *, max_bytes: int = MAX_BYTES) -> list[str]:
    reasons = []
    if len(data) > max_bytes:
        return ["file-size-limit"]
    match = CHUNK.fullmatch(relative)
    if match:
        if hashlib.sha256(data).hexdigest() != match[1]:
            reasons.append("compressed-name-hash-mismatch")
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
                decoded = stream.read(max_bytes + 1)
            if len(decoded) > max_bytes:
                return reasons + ["decompression-size-limit"]
            data = decoded
        except (OSError, EOFError):
            return reasons + ["invalid-compressed-json"]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return reasons + ["unexpected-binary-file"]
    if "\0" in text:
        reasons.append("unexpected-binary-file")
    for label, pattern in PATTERNS.items():
        if pattern.search(data):
            reasons.append(label)
    if relative.lower().endswith(('.csv','.tsv')):
        reasons.extend(tabular_score_reasons(relative,text))
    if relative.lower().endswith(('.txt','.md')):
        # Keep a narrow literal assignment guard for data-bearing plain text.
        # Do not group unrelated lexical JS objects, CSS comments or URLs.
        for line in text.splitlines():
            if re.search(
                r'\b(?:sourceid|publisher|datasource)\s*=\s*'
                r'[A-Za-z][A-Za-z0-9_-]{0,48}\s*[;,]\s*'
                r'(?:score|accuracy|value)\s*=\s*'
                r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)',line,re.I):
                reasons.append('unreviewed-embedded-publisher-score')
                break
    if relative.lower().endswith('.html'):
        reasons.extend(html_score_reasons(text))
    if relative.lower().endswith(('.ts','.tsx','.js','.jsx','.mjs','.cjs','.mts')):
        # Structural record-level JS/JSX/ESM/CJS/TS-module inspection. Unlike the former regex,
        # two sibling objects cannot be spuriously joined into one metric.
        vetted_test=(relative=='dashboard/tests/cybersecurityEvidence.test.tsx' and
                     hashlib.sha256(data).hexdigest()==
                     '7bef270f1a0d5b6dfa007936f0615548ede966b4c0fb85d2981ddd71b3498494')
        if not vetted_test:
            try:
                reasons.extend(javascript_reasons(text))
            except (ValueError,RecursionError):
                reasons.append('indeterminate-js-requires-independent-review')
    if relative.lower().endswith(('.svg','.xml')):
        try:
            if xml_score(text):
                reasons.append('unreviewed-embedded-publisher-score')
            elif (xml_indeterminate_sibling_provenance(text)
                  or xml_requires_review(text)):
                reasons.append('indeterminate-xml-provenance-requires-independent-review')
        except (ValueError,TypeError,RecursionError,ET.ParseError):
            reasons.append('invalid-svg-xml')
    if relative.lower().endswith(".jsonl"):
        # One strict JSON document per nonempty line. Multiple lines are
        # separate records: unknown cross-record joins are REVIEW, not a
        # fabricated same-object editorial score.
        has_source=False
        has_metric=False
        count=0
        for line in text.splitlines():
            if not line.strip():continue
            count+=1
            if count>200000:
                reasons.append("jsonl-record-budget-exceeded");break
            try:value=json_loads_strict(line)
            except (ValueError,RecursionError):
                reasons.append("invalid-jsonl");break
            if json_requires_review(value):
                reasons.append("indeterminate-json-alias-requires-independent-review")
            elif json_score(value):
                reasons.append("non-allowlisted-publisher-numeric-row")
            if isinstance(value,dict):
                fields={normalized_key(k):v for k,v in value.items()}
                if any(k in IDENTITY_FIELDS and v not in ('local','synthetic','BR-BFCL-DATA')
                       for k,v in fields.items()):
                    has_source=True
                if any(k in SCORE_FIELDS and is_numeric_score(v) for k,v in fields.items()):
                    has_metric=True
        if count>1 and has_source and has_metric and not any(
                r=="non-allowlisted-publisher-numeric-row" for r in reasons):
            reasons.append("indeterminate-jsonl-provenance-link-requires-independent-review")
        if not count:reasons.append("invalid-jsonl")
    if relative.endswith(".json") or match:
        # TypeScript's two existing JSONC configs permit comments/trailing commas.
        # Strip only outside strings, and still validate/inspect the resulting JSON.
        if relative in {"dashboard/tsconfig.app.json", "dashboard/tsconfig.node.json"}:
            text = re.sub(r'"(?:\\.|[^"\\])*"|//[^\r\n]*|/\*[\s\S]*?\*/',
                          lambda m: m[0] if m[0].startswith('"') else ' ', text)
            text = re.sub(r'("(?:\\.|[^"\\])*")|,(\s*[}\]])',
                          lambda m: m[1] if m[1] is not None else m[2], text)
        try:
            value = json_loads_strict(text)
        except (ValueError, RecursionError):
            reasons.append("invalid-json")
        else:
            if json_requires_review(value):
                reasons.append("indeterminate-json-alias-requires-independent-review")
            elif json_score(value):
                reasons.append("non-allowlisted-publisher-numeric-row")
    return reasons


def audit_built_site(built: Path, *, root: Path=ROOT, site_name: str|None=None) -> dict:
    """Independently check exactly what Pages uploads, after removing snapshot.json."""
    root=root.resolve();built=built.resolve()
    if site_name is None:
        html=built/"index.html"
        site_name=("reference" if html.is_file()
                   and 'name="robots" content="noindex' in html.read_text("utf-8")
                   else "public")
    if site_name not in ("public","reference"):
        raise ValueError("Invalid exact site audit name")
    manifest=root/'dashboard/public/data/delivery.json'
    try:approved=json_loads_strict(manifest.read_bytes())
    except (ValueError,OSError,TypeError) as e:raise ValueError('Missing reviewed public delivery manifest') from e
    if set(approved.get('parts',{}))!={'core','evidence'}:raise ValueError('Unexpected public Pages delivery parts')
    expected={'data/delivery.json'}
    expected_chunks={}
    for item in approved['parts'].values():
        rel='data/'+item['path']
        if not CHUNK.fullmatch('dashboard/public/'+rel):
            raise ValueError('Unapproved content-addressed Pages fragment')
        expected.add(rel);expected_chunks[rel]=root/'dashboard/public'/rel
    observed=set()
    if not built.is_dir():raise ValueError('Missing generated Pages artifact')
    for item in built.rglob('*'):
        relative=item.relative_to(built).as_posix()
        if item.is_symlink():raise ValueError('Symlink in Pages artifact')
        if item.is_dir():continue
        if not item.is_file() or item.stat().st_size>MAX_BYTES:raise ValueError('Invalid Pages file size or type')
        observed.add(relative)
        if (relative not in expected and relative not in {'index.html','icons.svg','favicon.svg'}
                and not (relative.startswith('assets/') and item.suffix in {'.js','.css'})):
            raise ValueError('Unapproved Pages output file: '+relative)
        if relative in expected_chunks:
            if item.read_bytes()!=expected_chunks[relative].read_bytes():
                raise ValueError('Pages chunk differs from reviewed public source: '+relative)
            reasons=inspect_payload('dashboard/public/'+relative,item.read_bytes())
        elif relative=='data/delivery.json':
            if item.read_bytes()!=manifest.read_bytes():raise ValueError('Pages delivery manifest differs')
            reasons=inspect_payload(relative,item.read_bytes())
        else:
            reasons=inspect_payload(relative,item.read_bytes())
        if reasons:raise ValueError('Unapproved Pages content type/pattern in '+relative+': '+','.join(reasons))
    if not expected.issubset(observed) or 'index.html' not in observed:
        raise ValueError('Pages is missing approved content-addressed files or its entrypoint')
    return {'pagesFilesScanned':len(observed),'approvedChunks':len(expected_chunks),'verifiedAgainstPublicSource':True}

def tracked_paths(root: Path) -> set[str]:
    # Never inherit a parent private repository when auditing a staging directory.
    if not (root / ".git").exists():
        return set()
    actual = Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if actual != root.resolve():
        raise ValueError("Audit root is not the Git worktree root")
    return {p.decode() for p in git(root, "ls-files", "-z").split(b"\0") if p}


def audit(root: Path | None = None) -> dict:
    root = (root or ROOT).resolve()
    failures = []
    tracked = tracked_paths(root)
    files = set(tracked)
    for directory, dirs, names in os.walk(root, followlinks=False):
        parent = Path(directory)
        for name in list(dirs):
            item = parent / name
            rel = item.relative_to(root).as_posix()
            if item.is_symlink():
                files.add(rel)
                dirs.remove(name)
            elif (parent == root and name == ".git") or name in RUNTIME_DIRS:
                dirs.remove(name)
        for name in names:
            item = parent / name
            rel = item.relative_to(root).as_posix()
            if rel == ".git" or (rel in REGENERATED and rel not in tracked):
                continue
            files.add(rel)
    for required in MUST_EXIST:
        if not (root / required).is_file():
            failures.append({"path": required, "reason": "required-public-file-missing"})
    allowed_chunks = set()
    delivery = root / "dashboard/public/data/delivery.json"
    if delivery.is_file() and not delivery.is_symlink():
        try:
            spec = json_loads_strict(delivery.read_bytes())
            allowed_chunks = {"dashboard/public/data/" + v["path"] for v in spec["parts"].values()}
        except (ValueError, KeyError, TypeError):
            failures.append({"path": delivery.relative_to(root).as_posix(), "reason": "invalid-delivery-manifest"})
    count = total = compressed = 0
    for relative in sorted(files):
        reason = path_reason(relative, tracked=relative in tracked)
        file = root / relative
        if reason:
            failures.append({"path": relative, "reason": reason})
            continue
        parts = PurePosixPath(relative).parts
        if any((root.joinpath(*parts[:i])).is_symlink() for i in range(1, len(parts) + 1)):
            failures.append({"path": relative, "reason": "symlink-not-approved"})
            continue
        if not file.exists() or not stat.S_ISREG(file.stat().st_mode):
            failures.append({"path": relative, "reason": "missing-or-nonregular-file"})
            continue
        if file.stat().st_size > MAX_BYTES:
            failures.append({"path": relative, "reason": "file-size-limit"})
            continue
        if CHUNK.fullmatch(relative) and relative not in allowed_chunks:
            failures.append({"path": relative, "reason": "unreferenced-compressed-payload"})
        data = file.read_bytes()
        reasons=inspect_payload(relative,data)
        failures.extend({"path": relative, "reason": r} for r in reasons)
        count += 1
        total += len(data)
        compressed += int(bool(CHUNK.fullmatch(relative)))
    report = {"filesScanned": count, "bytesScanned": total, "compressedFilesDecoded": compressed,
              "candidateFailures": failures, "publicBoundaryPassed": not failures,
              "providerInferenceCalls": 0,
              "caution": "Heuristic checks plus typed evidence contracts; not legal clearance or exhaustive DLP."}
    if failures:
        raise ValueError(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def audit_history(root: Path | None = None, *, base: str = APPROVED_PUBLIC_BASE,
                  head: str = "HEAD") -> dict:
    root = root or ROOT
    base_sha = git(root, "rev-parse", "--verify", base + "^{commit}").decode().strip()
    head_sha = git(root, "rev-parse", "--verify", head + "^{commit}").decode().strip()
    git(root, "merge-base", "--is-ancestor", base_sha, head_sha)
    fmt=git(root,"rev-parse","--show-object-format").decode().strip()
    # First authenticate ALL physically reachable commits, including those
    # omitted by a distorted Git presentation. Compare the selected set to
    # raw ancestry and parentage before trusting rev-list/diff-tree.
    revisions = git(root, "rev-list", "--reverse", f"{base_sha}..{head_sha}").decode().splitlines()
    parents_by_oid={}
    authenticated_history = verified_git_history_inventories(
        root,head_sha,fmt,[base_sha,*revisions],verified_parents=parents_by_oid)
    if base_sha not in parents_by_oid:
        raise ValueError("Approved baseline absent from authenticated physical Git ancestry")
    def ancestor_set(oid: str) -> set[str]:
        seen_anc=set()
        stack=[oid]
        while stack:
            current=stack.pop()
            if current in seen_anc:continue
            seen_anc.add(current)
            stack.extend(parents_by_oid[current])
        return seen_anc
    base_ancestors=ancestor_set(base_sha)
    physical_postbase=set(parents_by_oid)-base_ancestors
    if (len(revisions)!=len(set(revisions)) or
        set(revisions)!=physical_postbase):
        raise ValueError("Git rev-list diverges from authenticated physical commit ancestry")
    for revision in revisions:
        for parent in parents_by_oid[revision]:
            if base_sha not in ancestor_set(parent):
                raise ValueError("Git ancestry contains a parent outside approved baseline (authenticated physical graph)")
    seen = set()
    scanned = 0
    failures = []
    approved_merges = 0
    for revision in revisions:
        authenticated=authenticated_history[revision]
        commit_line = git(root, "rev-list", "--parents", "-n", "1", revision).decode().split()
        if not commit_line or commit_line[0] != revision:
            raise ValueError("Cannot resolve historical commit parentage")
        parents = commit_line[1:]
        if parents != parents_by_oid[revision]:
            raise ValueError("Git parent presentation differs from authenticated physical Git commit")
        if not 1 <= len(parents) <= 2:
            raise ValueError("Unsupported public history root/octopus merge after baseline: " + revision)
        for parent in parents:
            try:
                git(root, "merge-base", "--is-ancestor", base_sha, parent)
            except subprocess.CalledProcessError as exc:
                raise ValueError("Merged public branch contains history outside approved baseline: " + revision) from exc
        if len(parents) == 2:
            # Only content-preserving merges, as generated for the reviewed
            # PR tree, are accepted. A conflict-resolution merge whose tree
            # differs from the reviewed second parent needs separate approval.
            merge_tree = git(root, "rev-parse", revision + "^{tree}")
            reviewed_tree = git(root, "rev-parse", parents[1] + "^{tree}")
            if merge_tree != reviewed_tree:
                raise ValueError("Unreviewed merge resolution changed approved PR source tree: " + revision)
            approved_merges += 1
        # Scan every parent edge, not Git diff-tree's default empty output
        # for merge commits. Every introduced blob remains audited, even
        # when later deleted on the feature branch.
        changes = set()
        for parent in parents:
            changed = git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z",
                          "--diff-filter=ACMT", "--no-renames", parent, revision).split(b"\0")
            changes.update(item for item in changed if item)
        for raw in sorted(changes):
            if not raw:
                continue
            relative = raw.decode()
            reason = path_reason(relative)
            if reason:
                failures.append({"commit": revision, "path": relative, "reason": reason})
                continue
            record = git(root, "ls-tree", "-z", revision, "--", relative).split(b"\0")[0]
            mode, kind, oid = record.split(b"\t", 1)[0].decode().split()
            if kind != "blob" or mode not in {"100644", "100755"}:
                failures.append({"commit": revision, "path": relative, "reason": "nonregular-git-object"})
                continue
            if authenticated.get(relative)!=(mode,oid):
                raise ValueError("Git history ls-tree identity differs from authenticated commit/tree bytes")
            if (relative, oid) in seen:
                continue
            seen.add((relative, oid))
            kind,blob=verified_git_objects(root,[oid],fmt)[oid]
            if kind!="blob":
                raise ValueError("History Git leaf OID does not name a blob")
            if len(blob)>MAX_BYTES:
                reasons = ["file-size-limit"]
            else:
                reasons = inspect_payload(relative, blob)
            scanned += 1
            failures.extend({"commit": revision, "path": relative, "reason": r} for r in reasons)
    report = {"historyBoundaryPassed": not failures, "approvedBaseline": base_sha,
              "head": head_sha, "newCommits": len(revisions),
              "reviewedContentPreservingMerges": approved_merges,
              "changedBlobsScanned": scanned,
              "failures": failures, "scope": "All added/modified blobs in every commit after baseline, including later deletions."}
    if failures:
        raise ValueError(json.dumps(report, indent=2))
    return report


# The 34 exact R3j Pages bytes were independently verified locally. These are
# hashes of canonical path -> SHA-256 maps, not rights approvals or allowlists.
HISTORIC_PAGES_INVENTORY_SHA256 = {
    "public": "805a6608d563c2d0e767f0d0e2361d18d1119fb25f037b901645329114aaac4d",
    "reference": "6928921e244c7d2bfd56deecff9855d1934ef59d2a4acfab8895afc5e19d59f7",
}


def exact_site_inventory(folder: Path) -> dict[str, str]:
    """Inventory exact assets; never follow symlinks or silently omit files."""
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Pages inventory requires a real directory")
    entries = {}
    for item in folder.rglob("*"):
        if item.is_symlink() or not (item.is_file() or item.is_dir()):
            raise ValueError("Symlink or special Pages asset not reviewable")
        if item.is_file():
            if item.stat().st_size > MAX_BYTES:
                raise ValueError("Oversized Pages asset not reviewable")
            entries[item.relative_to(folder).as_posix()] = hashlib.sha256(item.read_bytes()).hexdigest()
    return dict(sorted(entries.items()))


def site_inventory_digest(entries: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(entries, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def compare_exact_pages(candidate: Path, previously_reviewed: Path,
                        *, historic_digest: str | None = None) -> dict:
    """No semantic guess: identify every changed, added and removed exact byte asset.

    Production CLI pins the historical baseline digest; synthetic tests may
    supply a different pinned digest without granting release authority.
    """
    old = exact_site_inventory(previously_reviewed)
    old_digest = site_inventory_digest(old)
    if historic_digest is None:
        matches = [name for name, digest in HISTORIC_PAGES_INVENTORY_SHA256.items()
                   if digest == old_digest]
        if len(matches) != 1 or len(old) != 17:
            raise ValueError("Pages reference is not the exact historical approved 17-file inventory")
        site = matches[0]
        html = candidate / "index.html"
        if not html.is_file() or html.is_symlink():
            raise ValueError("Pages entrypoint missing")
        candidate_site = ("reference" if 'name="robots" content="noindex' in
                          html.read_text("utf-8") else "public")
        if site != candidate_site:
            raise ValueError("Pages baseline site kind does not match candidate")
    elif historic_digest != old_digest:
        raise ValueError("Pages reference differs from supplied pinned test digest")
    else:
        site = "synthetic"
    now = exact_site_inventory(candidate)
    paths = sorted(set(old) | set(now))
    differences = [{"path": path, "beforeSHA256": old.get(path),
                    "candidateSHA256": now.get(path),
                    "change": ("ADDED" if path not in old else
                               "REMOVED" if path not in now else "MODIFIED")}
                   for path in paths if old.get(path) != now.get(path)]
    return {"site": site, "historicalFiles": len(old), "candidateFiles": len(now),
            "historicalInventorySHA256": old_digest,
            "candidateInventorySHA256": site_inventory_digest(now),
            "unchangedFiles": len(paths) - len(differences),
            "changedAssetsRequireExactReview": differences,
            "byteIdenticalToHistorical": not differences,
            "rightsClearanceGranted": False}


def checked_public_remote_main(root: Path) -> str:
    """Read public main without fetching or changing local refs. Fail closed."""
    expected = {"https://github.com/brianmsm/agent-profile-lab",
                "https://github.com/brianmsm/agent-profile-lab.git"}
    for setting in (("remote", "get-url", "origin"),
                    ("remote", "get-url", "--push", "origin")):
        if git(root, *setting).decode().strip() not in expected:
            raise ValueError("Unexpected public fetch/push remote; publication review refused")
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        p = subprocess.run(["git", "-C", str(root), "ls-remote", "--exit-code",
                            "origin", "refs/heads/main"], stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=20, env=env, check=True)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError("Cannot verify LIVE public remote main in read-only mode") from exc
    match = re.fullmatch(r"([0-9a-f]{40,64})\trefs/heads/main\n?", p.stdout)
    if not match:
        raise ValueError("Unexpected/ambiguous public remote main")
    return match[1]


def require_clean_candidate(root: Path, head: str) -> None:
    """Never report committed exposure while hidden worktree changes remain."""
    current = git(root, "rev-parse", "HEAD").decode().strip()
    selected = git(root, "rev-parse", "--verify", head + "^{commit}").decode().strip()
    if current != selected:
        raise ValueError("Release inventory must describe the checked-out HEAD")
    if git(root, "status", "--porcelain=v1", "--untracked-files=all").strip():
        raise ValueError("Release inventory requires a clean committed public checkout")


def candidate_object_inventory(root: Path, remote_main: str, *, head: str = "HEAD",
                               approved_base: str = APPROVED_PUBLIC_BASE,
                               verified_history: dict | None = None) -> dict:
    """Exact Git objects and historical changed blobs, including add-then-delete.

    Restricts the comparison to the verified remote MAIN, not other public
    branches. Authenticated post-approval history is a mandatory prerequisite.
    """
    head_sha = git(root, "rev-parse", "--verify", head + "^{commit}").decode().strip()
    base_sha = git(root, "rev-parse", "--verify", remote_main + "^{commit}").decode().strip()
    if verified_history is None:
        verified_history = audit_history(root, base=approved_base, head=head_sha)
    if verified_history.get("head") != head_sha or not verified_history.get("historyBoundaryPassed"):
        raise ValueError("Authenticated candidate history is required")
    git(root, "merge-base", "--is-ancestor", approved_base, base_sha)
    git(root, "merge-base", "--is-ancestor", base_sha, head_sha)
    commits = git(root, "rev-list", "--reverse", base_sha + ".." + head_sha).decode().splitlines()
    raw_objects = git(root, "rev-list", "--objects", "--no-object-names",
                      head_sha, "^" + base_sha).decode().splitlines()
    if len(set(raw_objects)) != len(raw_objects) or any(
            not re.fullmatch(r"[a-f0-9]{40,64}", item) for item in raw_objects):
        raise ValueError("Untrustworthy reachable object enumeration")
    # We display all newly reachable commit/tree/blob identities. No code
    # execution, secret prints, public writes or remote fetch happens here.
    p = subprocess.run(["git", "-C", str(root), "cat-file",
                        "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
                       input="".join(oid + "\n" for oid in raw_objects),
                       capture_output=True, text=True, check=True, timeout=60)
    object_list = []
    for oid, line in zip(raw_objects, p.stdout.splitlines(), strict=True):
        parts = line.split()
        if len(parts) != 3 or parts[0] != oid or parts[1] not in {"blob", "tree", "commit"}:
            raise ValueError("Git object identity/type cannot be verified")
        object_list.append({"oid": oid, "type": parts[1], "bytes": int(parts[2])})
    current_files = {p.decode() for p in git(root, "ls-tree", "-r", "-z", "--name-only",
                                               head_sha).split(b"\0") if p}
    object_format = git(root, "rev-parse", "--show-object-format").decode().strip()
    records = []
    queued_blobs = set()
    seen = set()
    for commit in commits:
        parts = git(root, "rev-list", "--parents", "-n", "1", commit).decode().split()
        if not parts or parts[0] != commit:
            raise ValueError("Unexpected candidate ancestry")
        for parent in parts[1:]:
            changed = git(root, "diff-tree", "--no-commit-id", "--name-status",
                          "--no-renames", "-r", "-z", parent, commit).split(b"\0")
            if changed[-1:] == [b""]:
                changed.pop()
            if len(changed) % 2:
                raise ValueError("Malformed historical Git diff")
            for i in range(0, len(changed), 2):
                action, raw_path = changed[i].decode(), changed[i+1]
                if action not in {"A", "M", "D", "T"}:
                    raise ValueError("Unexpected historical change kind")
                path = raw_path.decode("utf-8")
                listing = git(root, "ls-tree", "-z", commit, "--", path).split(b"\0")[0]
                if listing:
                    meta, actual = listing.split(b"\t", 1)
                    mode, kind, oid = meta.decode().split()
                    if actual.decode() != path or kind != "blob" or mode not in {"100644", "100755"}:
                        raise ValueError("Unreviewable historical Git path")
                    queued_blobs.add(oid)
                else:
                    oid = None
                key = (commit, path, action, oid)
                if key in seen: continue
                seen.add(key)
                records.append({"commit": commit, "path": path, "action": action,
                                "blobOid": oid, "presentAtCandidateHEAD": path in current_files})
    verified = verified_git_objects(root, sorted(queued_blobs), object_format)
    for entry in records:
        if entry["blobOid"] is not None:
            kind, content = verified[entry["blobOid"]]
            if kind != "blob":
                raise ValueError("Non-blob historical candidate content")
            entry["sha256"] = hashlib.sha256(content).hexdigest()
            entry["bytes"] = len(content)
    return {"candidateHEAD": head_sha, "livePublicMain": base_sha,
            "approvedHistoricalBoundary": approved_base,
            "newCommits": commits, "newReachableGitObjects": object_list,
            "historicalChangedFileVersions": records,
            "changedFileVersionsRequiringHumanReview": sum(r["blobOid"] is not None for r in records),
            "releaseReviewStatus": "EXACT_BYTES_AND_RIGHTS_REVIEW_REQUIRED",
            "signatureOrPermissionIssued": False,
            "scopeLimit": "Compared against live public main only; other public refs may already expose objects."}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true", help="Audit history from the fixed approved public baseline")
    parser.add_argument("--release-inventory", action="store_true", help="Read-only LIVE public-main comparison and exact historical object inventory")
    parser.add_argument("--built", type=Path, help="Inspect exact staged Pages dist after removing snapshot.json")
    parser.add_argument("--compare-pages-to", type=Path, help="Compare --built against pinned 17-file R3j historical Pages")
    parser.add_argument("--head", default="HEAD", help="PR head or HEAD; does not change the approved baseline")
    args = parser.parse_args()
    if args.compare_pages_to and not args.built:
        parser.error("--compare-pages-to requires --built")
    if args.release_inventory:
        require_clean_candidate(ROOT, args.head)
    result = audit()
    if args.history or args.release_inventory:
        result["history"] = audit_history(head=args.head)
    if args.release_inventory:
        result["releaseInventory"] = candidate_object_inventory(
            ROOT, checked_public_remote_main(ROOT), head=args.head,
            verified_history=result["history"])
    if args.built:
        result["pagesArtifact"] = audit_built_site(args.built)
        if args.compare_pages_to:
            result["pagesExactDiff"] = compare_exact_pages(args.built, args.compare_pages_to)
    if args.release_inventory:
        require_clean_candidate(ROOT, args.head)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
