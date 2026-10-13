"""Test bridge: compile a repository fixture, without publishing artifacts."""
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from profile_compiler import compile_request
from access_catalog import read_json
path=(ROOT/sys.argv[1]).resolve()
if not path.is_relative_to(ROOT/'examples/requests'):raise ValueError('Only repository request fixtures are accepted')
print(json.dumps(compile_request(read_json(path)),ensure_ascii=False))
