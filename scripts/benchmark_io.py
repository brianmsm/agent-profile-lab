"""Read verified public captures and structured tables without executing page code."""
from __future__ import annotations
from html.parser import HTMLParser
from pathlib import Path
import hashlib, json, re
ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def stable_id(prefix,value):return prefix+'-'+hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()[:24]
class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.skip=0;self.parts=[];self.tables=[];self.stack=[];self.links=[];self.scripts=[];self.title=[];self.in_title=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in {'script','style'}:self.skip+=1
        if tag=='script' and a.get('src'):self.scripts.append(a['src'])
        if tag=='a' and a.get('href'):self.links.append(a['href'])
        if tag=='title':self.in_title=True
        if tag=='table':self.stack.append({'rows':[],'row':None,'cell':None})
        elif self.stack:
            t=self.stack[-1]
            if tag=='tr':t['row']=[]
            elif tag in {'td','th'} and t['row'] is not None:t['cell']=[]
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)
        if self.in_title:self.title.append(data)
        if self.stack and not self.skip and self.stack[-1]['cell'] is not None:self.stack[-1]['cell'].append(data)
    def handle_endtag(self,tag):
        if tag in {'script','style'}:self.skip=max(0,self.skip-1)
        if tag=='title':self.in_title=False
        if not self.stack:return
        t=self.stack[-1]
        if tag in {'td','th'} and t['cell'] is not None:
            t['row'].append(' '.join(' '.join(t['cell']).split()));t['cell']=None
        elif tag=='tr' and t['row'] is not None:t['rows'].append(t['row']);t['row']=None
        elif tag=='table':self.tables.append(t['rows']);self.stack.pop()
    @property
    def text(self):return ' '.join(' '.join(self.parts).split())

def page(text):
    p=Page();p.feed(text);return p

def captures(root=ROOT):
    doc=json.loads((root/'sources/reviewed-captures.json').read_text())
    if doc.get('schemaVersion')!=1 or doc.get('updateMode')!='manual':raise ValueError('Unsupported capture catalog')
    result={}
    for r in doc['captures']:
        if r['id'] in result:raise ValueError('Duplicate capture identity')
        p=(root/r['path']).resolve()
        if not p.is_relative_to((root/'evidence/captures').resolve()) or not p.is_file():raise ValueError('Missing/out-of-scope capture')
        if r['httpStatus']!=200 or sha(p)!=r['sha256'] or p.stat().st_size!=r['bytes']:raise ValueError('Capture integrity mismatch: '+r['id'])
        result[r['id']]=r
    return result

def aa_models(text):
    """Decode JSON-serialized public Next data, never eval/execute JavaScript."""
    chunks=[]
    for m in re.finditer(r'self\.__next_f\.push\((\[.*?\])\)</script>',text,re.S):
        value=json.loads(m[1])
        if len(value)>1 and isinstance(value[1],str):chunks.append(value[1])
    full='\n'.join(chunks);decoder=json.JSONDecoder();models={}
    for m in re.finditer(r'\{"id":',full):
        try:value,_=decoder.raw_decode(full[m.start():])
        except ValueError:continue
        if not isinstance(value,dict) or 'intelligenceIndex' not in value or not value.get('slug'):continue
        key=value['slug']
        if key in models and models[key]!=value:raise ValueError('Conflicting AA model record: '+key)
        models[key]=value
    if not models:raise ValueError('No typed AA model records in capture; no fallback to invented scores')
    return models

NUMBER=r'[+-]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)'
def table_number(text):
    """Strict single value, optionally followed by a reported interval/uncertainty.

    Interval interpretation remains unclassified unless declared by an adapter.
    A number embedded in prose/model labels never becomes an observation.
    """
    clean=text.strip().replace('\u200b','')
    m=re.fullmatch(r'\$?('+NUMBER+r')\s*%?(?:\s*(\[[^\]]+\]|±\s*'+NUMBER+r'))?',clean)
    if not m:return None
    return float(m[1].replace(',','')),m[2]

def js_literal_object(text, variable):
    """Decode a declared object composed only of JSON-like literals; NEVER eval JS.

    Quoted strings, bare object keys, booleans, null, finite JSON numbers and
    punctuation only. Functions, interpolation, identifiers-as-values and code
    expressions are rejected. A source loader change requires review.
    """
    import ast
    m=re.search(r'\bconst\s+'+re.escape(variable)+r'\s*=\s*(?=\{)',text)
    if not m:raise ValueError('Declared literal object absent: '+variable)
    source=text[m.end():];position=0;depth=0;out=[]
    token=re.compile(r'\s+|//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[A-Za-z_$][\w$]*|[{}\[\],:]')
    while position<len(source):
        match=token.match(source,position)
        if not match:raise ValueError('Non-literal code in declared dataset')
        part=match[0];position=match.end()
        if part.isspace() or part.startswith(('//','/*')):continue
        if part[0] in {'"',"'"}:
            value=ast.literal_eval(part)
            if not isinstance(value,str):raise ValueError('Expected string')
            out.append(json.dumps(value))
        elif re.fullmatch(r'[A-Za-z_$][\w$]*',part):
            if source[position:].lstrip().startswith(':'):out.append(json.dumps(part))
            elif part in {'true','false','null'}:out.append(part)
            else:raise ValueError('Nonliteral value in dataset')
        else:
            if part in {'}',']'} and out and out[-1]==',':out.pop()
            out.append(part)
        if part in {'{','['}:depth+=1
        elif part in {'}',']'}:
            depth-=1
            if depth==0:break
    if depth!=0:raise ValueError('Unclosed literal dataset')
    serialized=''.join(out)
    return json.loads(serialized)
