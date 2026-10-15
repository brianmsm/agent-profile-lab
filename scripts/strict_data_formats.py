"""Lossless structural checks before JSON/CSV are interpreted as trusted evidence."""
from __future__ import annotations
import csv,io,json,math

def _pairs_unique(pairs):
    out={}
    for key,value in pairs:
        if key in out:raise ValueError('Duplicate JSON key: '+key)
        out[key]=value
    return out

def _finite_float(raw: str) -> float:
    number=float(raw)
    if not math.isfinite(number):
        raise ValueError('Nonfinite JSON number: '+raw)
    return number

def schema_version_is_one(value) -> bool:
    # JSON Schema numeric integers include 1.0, but bool is not a number.
    return type(value) in (int,float) and math.isfinite(value) and value==1

def json_loads_strict(blob: str|bytes):
    return json.loads(blob,parse_float=_finite_float,object_pairs_hook=_pairs_unique,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON number: '+value)))

def json_load_strict(path):
    with open(path,'rb') as f:return json_loads_strict(f.read())

def unique_csv_header(fieldnames, *, approved=None, label='CSV'):
    if not isinstance(fieldnames,list) or not fieldnames or any(
        not isinstance(f,str) or not f or f!=f.strip() for f in fieldnames):
        raise ValueError(label+': malformed CSV header')
    if len(fieldnames)!=len(set(fieldnames)):
        raise ValueError(label+': duplicate CSV header')
    if approved is not None and fieldnames!=approved:
        raise ValueError(label+': CSV schema differs from approved historical header')
    return fieldnames

def strict_csv_rows(data: bytes,*,approved=None,label='CSV'):
    text=data.decode('utf-8-sig')
    reader=csv.DictReader(io.StringIO(text,newline=''),restkey='__UNEXPECTED_EXTRA_COLUMNS__')
    unique_csv_header(reader.fieldnames,approved=approved,label=label)
    rows=[]
    for row in reader:
        if '__UNEXPECTED_EXTRA_COLUMNS__' in row or any(value is None for value in row.values()):
            raise ValueError(label+': irregular CSV row width')
        rows.append(row)
    return rows,reader.fieldnames
