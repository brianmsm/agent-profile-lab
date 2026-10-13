"""Archive the explicitly curated public security sources; never execute remote content."""
from pathlib import Path
import concurrent.futures
import datetime
import hashlib
import json
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/supplemental'
REFERENCES = [
    ('CYBER_VALS_SOL61', 'https://www.vals.ai/models/openai_gpt-6.1-sol'),
    ('CYBER_VALS_LUNA', 'https://www.vals.ai/models/openai_gpt-6-luna'),
    ('CYBER_VALS_ASTRA', 'https://www.vals.ai/models/openai_gpt-6-astra'),
    ('CYBER_VALS_SOL56', 'https://www.vals.ai/models/openai_gpt-5.6-sol'),
    ('CYBER_VALS_FABLE51', 'https://www.vals.ai/models/anthropic_claude-fable-5-1'),
    ('CYBER_VALS_METHOD', 'https://www.vals.ai/benchmarks/cyber'),
    ('CYBER_DEEPSEEK', 'https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash'),
    ('CYBER_OPENAI_SOL61', 'https://deploymentsafety.openai.com/gpt-6-1-sol'),
    ('CYBER_OPENAI_ASTRA', 'https://deploymentsafety.openai.com/gpt-6-astra'),
    ('CYBER_ANTH_OPUS55', 'https://www-cdn.anthropic.com/fc1b44717c85dc068bc6ba5024219938094694bd/Claude%20Opus%205.5%20System%20Card.pdf'),
    ('CYBER_ANTH_SONNET55', 'https://www-cdn.anthropic.com/870c8f525702625d2c62fc6dd04c857e3250bec1/Claude%2520Sonnet%25205.5%2520System%2520Card.pdf'),
    ('CYBER_ANTH_FABLE51', 'https://www-cdn.anthropic.com/0339e6a7c5c7b87f5c07798616dc32c215d14235/Claude%20Fable%205.1%20&%20Claude%20Mythos%205.1%20System%20Card.pdf'),
]

# New captures use their aggregate adapters, not the legacy curated parser.
EXHAUSTIVE_CAPTURE_REGISTRY = ROOT / 'data/cybersecurity-exhaustive-capture-references.json'

def exhaustive_references():
    registry = json.loads(EXHAUSTIVE_CAPTURE_REGISTRY.read_text(encoding='utf-8'))
    if registry.get('schemaVersion') != 1:
        raise ValueError('Invalid exhaustive capture registry')
    references = registry['references']
    urls = [item['url'] for item in references]
    names = [item['name'] for item in references]
    if len(set(urls)) != len(urls) or len(set(names)) != len(names):
        raise ValueError('Duplicate exhaustive capture reference')
    if set(urls) & {url for _, url in REFERENCES}:
        raise ValueError('Exhaustive registry duplicates legacy capture URL')
    return [(item['name'], item['url']) for item in references]
CAPTURE_DATE = '2026-10-03'

def capture(item):
    name, url = item
    raw_path = OUT / f'{name}_PUBLIC_{CAPTURE_DATE}.raw'
    receipt_path = OUT / f'{name}_RECEIPT_{CAPTURE_DATE}.json'
    if raw_path.exists() or receipt_path.exists():
        raise FileExistsError(f'Immutable capture already exists: {name}')
    request = urllib.request.Request(url, headers={'User-Agent': 'Gentle-assess source audit (static public GET)'})
    with urllib.request.urlopen(request, timeout=90) as response:
        raw = response.read()
        receipt = {'sourceId': name, 'requestedUrl': url, 'finalUrl': response.url,
                   'capturedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   'httpStatus': response.status, 'headers': dict(response.headers), 'error': None,
                   'path': str(raw_path.relative_to(ROOT)), 'sha256': hashlib.sha256(raw).hexdigest(),
                   'bytes': len(raw), 'method': 'GET; static bytes only; no authentication, JavaScript execution or inference'}
    with raw_path.open('xb') as handle:
        handle.write(raw)
    if raw.startswith(b'%PDF-'):
        text_path = OUT / f'{name}_TEXT_{CAPTURE_DATE}.txt'
        if text_path.exists():
            raise FileExistsError(text_path)
        subprocess.run(['pdftotext', '-layout', str(raw_path), str(text_path)], check=True)
        text = text_path.read_bytes()
        receipt['textExtraction'] = {'path': str(text_path.relative_to(ROOT)), 'sha256': hashlib.sha256(text).hexdigest(),
                                     'bytes': len(text), 'method': 'pdftotext -layout; local static PDF text extraction'}
    with receipt_path.open('x') as handle:
        handle.write(json.dumps(receipt, indent=2) + '\n')
    print(name, receipt['httpStatus'], len(raw))

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(capture, REFERENCES))
