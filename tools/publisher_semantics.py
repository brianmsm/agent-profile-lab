"""Bounded, structural editorial provenance checks. No JavaScript execution.

A deliberately incomplete static interpreter recognizes direct object/JSX/XML
records, simple constant propagation, spreads, index assignments and encoded
literal JSON. Ambiguous executable encodings are rejected for independent
manual rights review. Sibling records are NEVER merged into invented scores.
"""
from __future__ import annotations
import base64
import html
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

LOCAL={"br-bfcl-data","local","synthetic"}
UNITS={"reference-links","reference-count","references","rows","source-count"}
METRICS={"score","scores","scorevalues","accuracy","scorepct","scorepercent",
         "intelligenceindex","benchmarkscore","benchmarkaccuracy","overallacc",
         "overallaccuracy","latency","tokenspersecond","modelscore","passrate",
         "datascore","winfraction"}
PROVENANCE={"sourceid","publisher","datasource","datasourceid","datapublisher","sourceurl"}
NUMERIC=re.compile(r"[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?%?\Z")
MAX_TOKENS=450000
MAX_ENCODED=200000

def norm(v:str)->str:
    return re.sub(r"[^a-z0-9]","",v.lower())

def external(v:object)->bool:
    return isinstance(v,str) and bool(v.strip()) and v.strip().lower() not in LOCAL

def numeric(v:object)->bool:
    if isinstance(v,bool) or v is None:
        return False
    if type(v) in (float,int):
        return True
    if isinstance(v,(list,tuple)):
        return any(numeric(x) for x in v)
    if isinstance(v,str):
        return bool(NUMERIC.fullmatch(v.strip())) or v=="<expression>"
    return False

def aggregate(d:dict)->bool:
    return (d.get("kind")=="aggregate-count" and d.get("unit") in UNITS
            and not any(k in d for k in METRICS)
            and type(d.get("value")) is int and d["value"]>=0)

def metric(d:dict)->bool:
    if any(k in METRICS and (numeric(v) or v=="<unknown-variable>")
           for k,v in d.items()):
        return True
    if d.get("name") in METRICS and numeric(d.get("observed")):
        return True
    v=d.get("value")
    return numeric(v)

def check(d:dict)->bool:
    return (any(external(d[k]) or d[k]=="<unknown-variable>" for k in PROVENANCE if k in d)
            and not aggregate(d) and metric(d))

def json_score(data:object)->bool:
    """Direct provenance flows to descendants, never sideways to siblings."""
    stack=[(data,False)]
    scanned=0
    while stack:
        value,prior=stack.pop()
        scanned+=1
        if scanned>5_000_000:
            raise ValueError("JSON provenance inspection budget exceeded")
        if isinstance(value,list):
            stack.extend((x,prior) for x in value)
            continue
        if not isinstance(value,dict):
            continue
        d={norm(str(k)):v for k,v in value.items()}
        origins=[d[k] for k in PROVENANCE if k in d]
        origin=prior
        if origins:
            own_external=any(external(x) for x in origins)
            # Conflicting nested local labels may be provenance laundering.
            if prior and not own_external and metric(d):
                return True
            origin=own_external
        if any(isinstance(v,str) and any(domain in v.lower() for domain in
               ("slopalytics","artificialanalysis","frontiercode"))
               for k,v in d.items() if k in ("source","url","sourceurl","provider")):
            origin=True
        if origin and not aggregate(d) and metric(d):
            return True
        # A sources/observations cross-link cannot be certified as benign
        # statically. Fail closed for human review rather than invent a join.
        if ("sources" in d and "observations" in d and
            _has_external(d["sources"]) and _contains_metric(d["observations"])):
            return True
        stack.extend((v,origin) for v in value.values() if isinstance(v,(list,dict)))
    return False

def _has_external(value:object)->bool:
    if isinstance(value,list):return any(_has_external(v) for v in value)
    if isinstance(value,dict):
        d={norm(str(k)):v for k,v in value.items()}
        return (any(external(d[k]) for k in PROVENANCE if k in d)
                or any(_has_external(v) for v in value.values() if isinstance(v,(dict,list))))
    return False

def _contains_metric(value:object)->bool:
    if isinstance(value,list):return any(_contains_metric(v) for v in value)
    if isinstance(value,dict):
        d={norm(str(k)):v for k,v in value.items()}
        return metric(d) or any(_contains_metric(v) for v in value.values() if isinstance(v,(dict,list)))
    return False

@dataclass(frozen=True)
class Token:
    kind:str
    value:str

def lex(s:str)->list[Token]:
    """Bounded JS/JSX lexical pass. Regex contents are never quote delimiters.

    Incomplete string, RegExp or comment tokens require independent review.
    This does not execute untrusted JavaScript.
    """
    tokens=[];i=0;n=len(s)
    regex_after_words={
        "return","throw","case","delete","void","typeof","instanceof",
        "in","of","yield","await","else","do","new",
    }
    regex_after_punct=set("=(:,;[!&|?{}+*-~%^<>")
    def add(kind:str,value:str):
        tokens.append(Token(kind,value))
        if len(tokens)>MAX_TOKENS:
            raise ValueError("JavaScript structural inspection budget exceeded")
    def read_quote(at:int,quote:str)->tuple[str,int]:
        pos=at+1;value=[];closed=False
        while pos<n:
            ch=s[pos]
            if ch=="\\":
                if pos+1>=n:break
                nxt=s[pos+1]
                if nxt=="u" and pos+5<n:
                    try:
                        value.append(chr(int(s[pos+2:pos+6],16)))
                        pos+=6;continue
                    except ValueError:pass
                if nxt=="\n":pos+=2;continue
                value.append({"n":"\n","t":"\t","r":"\r"}.get(nxt,nxt))
                pos+=2;continue
            if ch==quote:
                pos+=1;closed=True;break
            value.append(ch);pos+=1
        if not closed:
            raise ValueError("Unterminated JavaScript string/template requires independent review")
        return "".join(value),pos
    def read_template(at:int,depth:int=0)->tuple[str,int]:
        if depth>32:
            raise ValueError("Nested JS template exceeds static inspection budget")
        pos=at+1
        while pos<n:
            ch=s[pos]
            if ch=="\\":
                pos+=2;continue
            if ch==chr(96):
                return s[at+1:pos],pos+1
            if ch=="$" and pos+1<n and s[pos+1]=="{":
                pos=skip_interpolation(pos+2,depth+1)
                continue
            pos+=1
        raise ValueError("Unterminated JavaScript template literal requires review")
    def skip_interpolation(pos:int,depth:int)->int:
        """Skip balanced JS interpolation, including nested string/templates."""
        braces=1
        allow_regex=True
        while pos<n:
            ch=s[pos]
            if ch.isspace():pos+=1;continue
            if s.startswith("//",pos):
                e=s.find("\n",pos+2);pos=n if e<0 else e+1;continue
            if s.startswith("/*",pos):
                e=s.find("*/",pos+2)
                if e<0:raise ValueError("Unterminated JS template comment")
                pos=e+2;continue
            if ch in ("'",'"'):
                _,pos=read_quote(pos,ch);allow_regex=False;continue
            if ch==chr(96):
                _,pos=read_template(pos,depth);allow_regex=False;continue
            if ch=="/" and allow_regex:
                pos=read_regex(pos);allow_regex=False;continue
            if ch=="{":braces+=1;allow_regex=True;pos+=1;continue
            if ch=="}":
                braces-=1;pos+=1
                if braces==0:return pos
                allow_regex=False;continue
            if ch in "=(:,;[!?&|+-*%~^<>":
                allow_regex=True
            elif ch.isalpha() or ch.isdigit() or ch in "_$)]":
                allow_regex=False
            pos+=1
        raise ValueError("Unterminated JavaScript template interpolation requires review")
    def regex_allowed()->bool:
        if not tokens:return True
        prev=tokens[-1]
        if prev.kind=="name":return prev.value in regex_after_words
        return prev.kind=="punct" and prev.value in regex_after_punct
    def read_regex(at:int)->int:
        pos=at+1;in_class=False
        while pos<n:
            ch=s[pos]
            if ch=="\\":
                if pos+1>=n:break
                pos+=2;continue
            if ch in "\r\n":
                raise ValueError("Unterminated JavaScript RegExp requires independent review")
            if ch=="[":in_class=True
            elif ch=="]":in_class=False
            elif ch=="/" and not in_class:
                pos+=1
                while pos<n and (s[pos].isalpha() or s[pos] in "_$"):
                    pos+=1
                return pos
            pos+=1
        raise ValueError("Unterminated JavaScript RegExp requires independent review")
    while i<n:
        c=s[i];start=i
        if c.isspace():i+=1;continue
        if s.startswith("//",i):
            e=s.find("\n",i+2);i=n if e<0 else e+1;continue
        if s.startswith("/*",i):
            e=s.find("*/",i+2)
            if e<0:raise ValueError("Unterminated JavaScript comment requires independent review")
            i=e+2;continue
        if c==chr(96):
            value,i=read_template(i)
            add("template",value)
        elif c in ("'",'"'):
            value,i=read_quote(i,c)
            add("string",value)
        elif (c=="/" and regex_allowed() and not s.startswith("/>",i)
              and not (i>0 and s[i-1]=="<")):
            i=read_regex(i)
            add("regex",s[start:i])
        elif c.isalpha() or c in "_$":
            i+=1
            while i<n and (s[i].isalnum() or s[i] in "_$"):i+=1
            add("name",s[start:i])
        elif c.isdigit():
            i+=1
            while i<n and s[i] in "0123456789.eE":i+=1
            add("number",s[start:i])
        else:
            add("punct",c);i+=1
    return tokens

def _pairs(ts:list[Token])->dict[int,int]:
    stack=[];match={}
    for i,t in enumerate(ts):
        if t.kind!="punct":continue
        if t.value in "{[(":
            stack.append((t.value,i))
        elif t.value in "}])" and stack:
            opening,j=stack[-1]
            if (opening,t.value) in (("{","}"),("[","]"),("(",")")):
                stack.pop();match[j]=i
    return match

def _split(ts:list[Token],start:int,end:int,pairs:dict[int,int])->list[tuple[int,int]]:
    result=[];i=start;piece=start
    while i<end:
        if i in pairs and pairs[i]<end:
            i=pairs[i]+1;continue
        if ts[i].kind=="punct" and ts[i].value==",":
            if piece<i:result.append((piece,i))
            piece=i+1
        i+=1
    if piece<end:result.append((piece,end))
    return result

def _literal(ts:list[Token],a:int,b:int,env:dict[str,object])->object:
    if a>=b:return None
    # A bounded subset of JS numeric coercion is statically decidable. Only
    # known literal strings are folded, never arbitrary calls or evaluated JS.
    def cast_static(v:object)->object:
        if isinstance(v,str) and NUMERIC.fullmatch(v.strip()):
            try:return float(v) if any(c in v for c in ".eE") else int(v)
            except (ValueError, OverflowError):pass
        if type(v) in (float,int):return v
        return "<expression>"
    if (b-a>=6 and ts[a].value=="globalThis" and ts[a+1].value=="."
            and ts[a+2].value=="Number" and ts[a+3].value=="("
            and ts[b-1].value==")"):
        return cast_static(_literal(ts,a+4,b-1,env))
    if (b-a>=4 and ts[a].value in ("+","-")
            and ts[a+1].value=="(" and ts[b-1].value==")"):
        v=cast_static(_literal(ts,a+2,b-1,env))
        return -v if type(v) in (float,int) and ts[a].value=="-" else v
    # Only a statically known numeric string is folded; no JS is evaluated.
    if (b==a+4 and ts[a].value in ("Number","parseFloat","parseInt")
        and ts[a+1].value=="(" and ts[b-1].value==")"):
        val=_literal(ts,a+2,b-1,env)
        if isinstance(val,str) and NUMERIC.fullmatch(val.strip()):
            try:return float(val) if any(x in val for x in ".eE") else int(val)
            except ValueError:pass
        return "<expression>"
    if ts[a].value=="{" and a+1<b and ts[b-1].value=="}" and b==a+3:
        return _literal(ts,a+1,b-1,env)
    if b==a+1:
        t=ts[a]
        if t.kind=="string":return html.unescape(t.value)
        if t.kind=="template":
            return "<expression>" if "${" in t.value else t.value
        if t.kind=="number":
            try:return float(t.value) if any(x in t.value for x in ".eE") else int(t.value)
            except ValueError:return "<expression>"
        if t.value in ("true","false"):return t.value=="true"
        if t.value in ("null","undefined"):return None
        if t.kind=="name":return env.get(t.value,"<unknown-variable>")
    chunks=[];i=a
    while i<b:
        t=ts[i]
        if t.kind in ("string","template","number"):
            chunks.append(str(_literal(ts,i,i+1,env)))
        elif t.kind=="name" and isinstance(env.get(t.value),str) and not env[t.value].startswith("<"):
            chunks.append(env[t.value])
        else:break
        i+=1
        if i==b: return "".join(chunks) if len(chunks)>1 else _literal(ts,a,a+1,env)
        if ts[i].value!="+":break
        i+=1
    if ts[a].value in ("+","-") and a+2==b and ts[a+1].kind=="number":
        try:return float(ts[a].value+ts[a+1].value)
        except ValueError:pass
    return "<expression>"

def _key(ts:list[Token],a:int,b:int,pairs:dict[int,int],env:dict[str,object])->tuple[str,int]|None:
    if a>=b:return None
    t=ts[a]
    if t.kind in ("name","string"):return norm(t.value),a+1
    if t.value=="[" and a in pairs and pairs[a]<b:
        k=_literal(ts,a+1,pairs[a],env)
        if isinstance(k,str) and not k.startswith("<"):
            return norm(k),pairs[a]+1
    return None

def _object(ts:list[Token],start:int,end:int,pairs:dict[int,int],
            scalars:dict[str,object],objects:dict[str,dict])->dict:
    result={}
    for a,b in _split(ts,start+1,end,pairs):
        if a+3<b and all(ts[a+j].value=="." for j in range(3)):
            token=ts[a+3]
            if token.value=="{" and pairs.get(a+3)==b-1:
                # A literal anonymous spread is deterministically the SAME
                # object; unlike a sibling, its properties must be joined.
                result.update(_object(ts,a+3,b-1,pairs,scalars,objects))
            elif token.kind=="name" and token.value in objects:
                result.update(objects[token.value])
            continue
        key=_key(ts,a,b,pairs,scalars)
        if not key:continue
        name,j=key
        if j==b:
            if ts[a].kind=="name" and ts[a].value in scalars:
                result[name]=scalars[ts[a].value]
            elif name in METRICS:
                result[name]="<unknown-variable>"
            continue
        if ts[j].value!=":":continue
        result[name]=_literal(ts,j+1,b,scalars)
        # Static array values indicate a potential metric, not a scalar label.
        if j+1<b and ts[j+1].value=="[" and name in METRICS:
            result[name]="<expression>"
    return result

def _constants(ts:list[Token],pairs:dict[int,int])->dict[str,object]:
    scalar={}
    for _ in range(3):
        for i,t in enumerate(ts):
            if t.value not in ("const","let","var") or i+3>=len(ts):continue
            if ts[i+1].kind!="name" or ts[i+2].value!="=":continue
            a=i+3;b=a
            while b<len(ts) and b<a+45 and ts[b].value not in (";",","):
                if b in pairs:
                    b=pairs[b]+1
                else:b+=1
            if b==a:continue
            v=_literal(ts,a,b,scalar)
            if v!="<expression>" and v!="<unknown-variable>" and not isinstance(v,(dict,list)):
                scalar[ts[i+1].value]=v
    return scalar

def _literal_json_and_base64(ts:list[Token])->bool:
    for i,t in enumerate(ts):
        if t.kind not in ("string","template"):continue
        # A declared, unconsumed pedagogic example is not an active data
        # record. Keep the legacy generic serialized-text fail-closed policy.
        if (i>=2 and ts[i-1].value=="=" and
            ts[i-2].value in ("example","doc","illustration","documentationExample") and
            sum(x.kind=="name" and x.value==ts[i-2].value for x in ts)==1):
            continue
        val=html.unescape(t.value)
        if len(val)>MAX_ENCODED:continue
        if val.lstrip().startswith(("{","[")):
            try:
                if json_score(json.loads(val)):return True
            except (ValueError,TypeError):pass
        # Literal base64 is not silently trusted. Decode only small, bounded,
        # explicit atob(...) arguments and parse data without executing JS.
        if (i>=2 and ts[i-1].value=="(" and ts[i-2].value=="atob"
                and re.fullmatch(r"[A-Za-z0-9+/]+={0,2}",val)):
            try:
                raw=base64.b64decode(val,validate=True)
                if len(raw)>MAX_ENCODED:raise ValueError("Oversized encoded editorial payload")
                decoded=raw.decode("utf-8")
                try:
                    if json_score(json.loads(decoded)):return True
                except (ValueError,TypeError):
                    if js_score(decoded):return True
            except (ValueError,UnicodeDecodeError):
                return True
    return False

def _jsx_records(ts:list[Token],pairs:dict[int,int],scalars:dict[str,object])->list[dict]:
    result=[]
    for i,t in enumerate(ts):
        if t.value!="<" or i+1>=len(ts) or ts[i+1].kind!="name":continue
        j=i+2;attrs={};maxj=min(len(ts),i+180)
        while j<maxj and ts[j].value!=">":
            if j in pairs and ts[j].value=="{":
                j=pairs[j]+1;continue
            if ts[j].kind!="name":
                j+=1;continue
            # JSX hyphenated data-* attributes are several JS lexer tokens.
            name=ts[j].value;at=j+1
            while at+1<maxj and ts[at].value=="-" and ts[at+1].kind=="name":
                name+="-"+ts[at+1].value
                at+=2
            if at>=maxj or ts[at].value!="=":
                j+=1;continue
            name=norm(name);a=at+1
            if a in pairs and ts[a].value=="{":
                val=_literal(ts,a+1,pairs[a],scalars)
                if val=="<unknown-variable>":val="<expression>"
                j=pairs[a]+1
            else:
                val=_literal(ts,a,a+1,scalars);j=a+1
            attrs[name]=val
        if attrs:result.append(attrs)
    return result

def _explicit_js_mutations(
    ts:list[Token],pairs:dict[int,int],scalars:dict[str,object],
    record_by_start:dict[int,dict],
)->tuple[bool,bool]:
    """Ordered updates to the *same* statically identified JS object.

    Scope-local names shadow outer bindings. Unknown computed writes, dynamic
    reflection or spreads affecting a record require REVIEW, not acceptance.
    No JavaScript, getters or candidate-supplied code are executed.
    """
    frames:[dict[str,dict|None]]=[{}]
    block_ends=[]
    reverse={right:left for left,right in pairs.items()}
    opaque_keys=set()
    review=False
    def locate(name:str)->dict|None:
        for frame in reversed(frames):
            if name in frame:return frame[name]
        return None
    def relevant(d:dict|None)->bool:
        return bool(d and (any(k in PROVENANCE and external(v) and v!="<unknown-variable>"
                               for k,v in d.items())
                           or any(k in METRICS and numeric(v) for k,v in d.items())))
    def has_unknown_metric(d:dict)->bool:
        return any(k in METRICS and v in ("<expression>","<unknown-variable>")
                   for k,v in d.items() if isinstance(v,str))
    def status(d:dict)->bool:
        nonlocal review
        if check(d):
            if (has_unknown_metric(d) or any(
                isinstance(v,str) and v.startswith("<")
                for k,v in d.items() if k in PROVENANCE
            )):
                review=True
                return False
            return True
        return False
    def expression_end(start:int)->int:
        end=start
        while end<len(ts) and end<start+90:
            if end in pairs:
                end=pairs[end]+1;continue
            if ts[end].value in (";",",","}","]"):break
            end+=1
        return end
    def method_at(start:int)->tuple[str,str,int]|None:
        if start>=len(ts) or ts[start].value not in ("Object","Reflect"):
            return None
        j=start+1
        if j+1<len(ts) and ts[j].value=="." and ts[j+1].kind=="name":
            method=ts[j+1].value
            j+=2
        elif j in pairs and ts[j].value=="[":
            method=_literal(ts,j+1,pairs[j],scalars)
            j=pairs[j]+1
        else:return None
        if not isinstance(method,str) or j not in pairs or ts[j].value!="(":
            return None
        return ts[start].value,method,j
    def args_for(open_at:int)->list[tuple[int,int]]:
        return _split(ts,open_at+1,pairs[open_at],pairs)
    def object_value(a:int,b:int,depth:int=0)->dict|None:
        if a>=b or depth>16:return None
        if ts[a].value=="{" and pairs.get(a)==b-1:
            return dict(record_by_start.get(a,{}))
        if b==a+1 and ts[a].kind=="name":
            return locate(ts[a].value)
        call=method_at(a)
        if call is not None and call[0:2]==("Object","assign") and pairs[call[2]]==b-1:
            args=args_for(call[2])
            if not args:return None
            target=object_value(*args[0],depth+1)
            if target is None:return None
            # Return a snapshot of the merged object, never combine siblings.
            merged=dict(target)
            for left,right in args[1:]:
                source=object_value(left,right,depth+1)
                if source is None:
                    if relevant(merged):nonlocal_review[0]=True
                else:merged.update(source)
            return merged
        return None
    nonlocal_review=[False]
    def parameter_names(at:int)->set[str]:
        # Bind parameters in their own frame rather than leaking the outer
        # record to a same-named uncalled function or arrow.
        tail=ts[at-1].value if at else ""
        close=None
        if tail==")":close=at-1
        if tail==">" and at>=3 and ts[at-2].value=="=":
            if ts[at-3].value==")":close=at-3
            elif ts[at-3].kind=="name":return {ts[at-3].value}
        if close is None or close not in reverse:return set()
        opening=reverse[close]
        head=[x.value for x in ts[max(0,opening-3):opening]]
        arrow=(tail==">")
        fn=("function" in head or "catch" in head)
        if not (arrow or fn):return set()
        return {ts[a].value for a,b in args_for(opening)
                if b==a+1 and ts[a].kind=="name"}
    # A concise arrow has a lexical parameter scope but no braces.
    # Identify its exact expression token range, excluding an unrelated
    # external object bound under the same parameter name.
    concise_shadowed=set()
    for j in range(1,len(ts)-2):
        if ts[j].value!="=" or ts[j+1].value!=">":continue
        body=j+2
        if ts[body].value=="{":continue
        names=set()
        if ts[j-1].value==")" and j-1 in reverse:
            opening=reverse[j-1]
            names={ts[a].value for a,b in args_for(opening)
                   if b==a+1 and ts[a].kind=="name"}
        elif ts[j-1].kind=="name":
            names={ts[j-1].value}
        for k in range(body,expression_end(body)):
            if ts[k].kind=="name" and ts[k].value in names:
                concise_shadowed.add(k)
    def descriptors(a:int,b:int)->dict|None:
        if a>=b or ts[a].value!="{" or pairs.get(a)!=b-1:return None
        values={}
        for l,r in _split(ts,a+1,b-1,pairs):
            key=_key(ts,l,r,pairs,scalars)
            if key is None:return None
            k,j=key
            if j>=r or ts[j].value!=":":return None
            desc=object_value(j+1,r)
            values[k]=desc.get("value","<unknown-variable>") if desc is not None else "<unknown-variable>"
        return values
    def mutating(d:dict|None,key:object,val:object,unknown:bool=False)->bool:
        nonlocal review
        if d is None:return False
        if not isinstance(key,str) or key.startswith("<") or unknown:
            opaque_keys.add(id(d))
            if relevant(d):review=True
            return False
        key=norm(key)
        if not key:
            if relevant(d):review=True
            return False
        d[key]=val
        if id(d) in opaque_keys and relevant(d):review=True
        return status(d)

    for i,t in enumerate(ts):
        # Only genuine lexical blocks create bindings. Object literal braces
        # (assignment, return value, property literal) are not new scopes.
        if t.value=="{" and i in pairs:
            prev=ts[i-1].value if i else ""
            lexical=(prev in (")","else","try","finally","do","=>")
                     or (prev==">" and i>=2 and ts[i-2].value=="="))
            if lexical:
                frames.append({name:None for name in parameter_names(i)})
                block_ends.append(pairs[i])
        if t.value=="}" and block_ends and block_ends[-1]==i:
            block_ends.pop();frames.pop()
        if (t.value in ("const","let","var") and i+2<len(ts)
                and ts[i+1].kind=="name"):
            name=ts[i+1].value
            d=None
            if ts[i+2].value=="=" and i+3<len(ts):
                j=i+3
                d=object_value(j,expression_end(j))
            frames[-1][name]=d
            if nonlocal_review[0]:review=True;nonlocal_review[0]=False
            if d is not None and status(d):return True,review
        if t.kind=="name":
            d=None if i in concise_shadowed else locate(t.value)
            if d is not None and i+2<len(ts):
                key=None;j=None
                if (ts[i+1].value=="." and ts[i+2].kind=="name"):
                    key=ts[i+2].value;j=i+3
                elif ts[i+1].value=="[" and i+1 in pairs:
                    e=pairs[i+1]
                    key=_literal(ts,i+2,e,scalars)
                    j=e+1
                if j is not None and j<len(ts):
                    if ts[j].value=="=":
                        a=j+1;b=expression_end(a)
                        value=_literal(ts,a,b,scalars)
                        # An unknown value is a review case if attributed to
                        # an external source; it is not a proven literal score.
                        if mutating(d,key,value,unknown=False):return True,review
                        if (isinstance(value,str) and value.startswith("<")
                            and relevant(d)):review=True
                    elif (j+1<len(ts) and ts[j+1].value=="="
                          and ts[j].value in ("+","-","*","/","%","&","|")):
                        if relevant(d):review=True
        # Statically recognizable reflective calls, including constant
        # bracket members. Never execute or infer the behavior of getters.
        call=method_at(i)
        if call is None:continue
        owner,method,opening=call
        args=args_for(opening)
        if not args:continue
        target=object_value(*args[0])
        if target is None:continue
        if method=="assign" and owner=="Object":
            for a,b in args[1:]:
                add=object_value(a,b)
                if add is None:
                    if relevant(target):review=True
                    continue
                target.update(add)
                if status(target):return True,review
        elif method in ("defineProperty","set") and len(args)>=3:
            if method=="defineProperty" and owner!="Object":continue
            if method=="set" and owner!="Reflect":continue
            key=_literal(ts,*args[1],scalars)
            a,b=args[2]
            if method=="defineProperty":
                desc=object_value(a,b)
                value=desc.get("value","<unknown-variable>") if desc else "<unknown-variable>"
            else:value=_literal(ts,a,b,scalars)
            if mutating(target,key,value):return True,review
            if isinstance(value,str) and value.startswith("<") and relevant(target):
                review=True
        elif method=="defineProperties" and owner=="Object" and len(args)>=2:
            values=descriptors(*args[1])
            if values is None:
                if relevant(target):review=True
            else:
                for key,val in values.items():
                    if mutating(target,key,val):return True,review
                    if isinstance(val,str) and val.startswith("<") and relevant(target):
                        review=True
    # Unknown object spreads are never silently taken as certified provenance.
    for i,t in enumerate(ts):
        if t.value!="{" or i not in pairs:continue
        d=record_by_start.get(i,{})
        if not relevant(d):continue
        for a,b in _split(ts,i+1,pairs[i],pairs):
            if a+3<b and all(ts[a+j].value=="." for j in range(3)):
                # Proven local spreads with known literal contents are resolved
                # by _object. Unknown ones could introduce a score/source.
                if a+4!=b or ts[a+3].kind!="name" or locate(ts[a+3].value) is None:
                    review=True
    return False,review

def _additional_js_review(ts:list[Token],pairs:dict[int,int],
                          scalars:dict[str,object],
                          records:dict[int,dict])->bool:
    """Narrow static indeterminacies from independently reproduced R3h cases."""
    named=list(records.values())
    has_provenance=any(
        any(k in PROVENANCE and external(v) for k,v in d.items())
        for d in named)
    has_score=any(
        any(k in METRICS and numeric(v) for k,v in d.items())
        for d in named)
    for i,d in records.items():
        if not any(k in PROVENANCE and external(v) for k,v in d.items()):
            continue
        end=pairs.get(i)
        if end is None:continue
        for a,b in _split(ts,i+1,end,pairs):
            if a>=b or ts[a].value!="[" or a not in pairs:continue
            closing=pairs[a]
            if closing+1>=b or ts[closing+1].value!=":":continue
            key=_literal(ts,a+1,closing,scalars)
            metric_value=_literal(ts,closing+2,b,scalars)
            if ((not isinstance(key,str) or key.startswith("<")) and
                (numeric(metric_value) or metric_value=="<expression>")):
                return True
    # Neither cross-linked record siblings nor shadowing a known external
    # parent source with a "local" child source proves legitimate rights.
    if has_provenance and has_score:
        if any({"sources","observations"}.issubset(d) for d in named):
            return True
    for i,t in enumerate(ts):
        if t.value not in ("window","globalThis","self"):continue
        if i+2>=len(ts) or ts[i+1].value!="[" or i+1 not in pairs:continue
        end=pairs[i+1]
        if _literal(ts,i+2,end,scalars)!="atob":continue
        if end+1>=len(ts) or ts[end+1].value!="(":continue
        if end+1 not in pairs:continue
        close=pairs[end+1]
        if any(x.kind=="string" and len(x.value)>=30 for x in ts[end+2:close]):
            return True
    # A deterministic string concatenation representing JSON record content
    # is REVIEW, not an executed metric, unless a known JSON.parse consumes it.
    for i,t in enumerate(ts):
        if t.kind!="string" or i+2>=len(ts) or ts[i+1].value!="+":continue
        j=i;parts=[t.value]
        while (j+2<len(ts) and ts[j+1].value=="+" and
               ts[j+2].kind=="string" and len(parts)<100):
            parts.append(ts[j+2].value);j+=2
        if len(parts)<2:continue
        combined="".join(parts)
        if len(combined)>100_000:continue
        if not combined.strip().startswith(("{","[")):continue
        try:
            value=json.loads(combined)
        except (ValueError,TypeError):continue
        if json_score(value):return True
    return False

def _opaque_json_decoder(ts:list[Token],pairs:dict[int,int])->bool:
    """REVIEW unresolved JSON.parse(atob(...)) across all JS consumers.

    Only inspect bounded static syntax. Literal decoded scores are handled
    independently; unknown runtime bytes are never fabricated.
    """
    for i,t in enumerate(ts):
        if t.value!="JSON" or i+3>=len(ts):continue
        if [x.value for x in ts[i+1:i+4]]!=[".","parse","("]:continue
        opening=i+3
        if opening not in pairs:continue
        args=_split(ts,opening+1,pairs[opening],pairs)
        if len(args)!=1:continue
        a,b=args[0]
        if a>=b:continue
        decoder=None;call_at=None
        if ts[a].value=="atob" and a+1<b and ts[a+1].value=="(":
            decoder="atob";call_at=a+1
        elif ts[a].value in ("window","globalThis","self"):
            if a+3<b and ts[a+1].value=="." and ts[a+2].value=="atob" and ts[a+3].value=="(":
                decoder="atob";call_at=a+3
            elif a+1 in pairs and ts[a+1].value=="[" and pairs[a+1]<b:
                close=pairs[a+1]
                if (close+1<b and ts[close+1].value=="(" and
                    _literal(ts,a+2,close,{})=="atob"):
                    decoder="atob";call_at=close+1
        if decoder is None or call_at not in pairs:continue
        close=pairs[call_at]
        if close>=b:continue
        inner=_split(ts,call_at+1,close,pairs)
        if len(inner)!=1:return True
        left,right=inner[0]
        # A literal can be decoded exactly; its parsed content is checked
        # by the existing bounded literal decoder, without running JS.
        if right==left+1 and ts[left].kind=="string":
            continue
        return True
    return False


def js_classify(source:str)->str:
    """PROHIBITED / REVIEW / LEGITIMATE, with no implicit rights grant."""
    ts=lex(source)
    if _literal_json_and_base64(ts):return "PROHIBITED"
    pairs=_pairs(ts)
    scalars=_constants(ts,pairs)
    indeterminate=_opaque_json_decoder(ts,pairs)
    objects={}
    record_by_start={}
    for i,t in enumerate(ts):
        if t.value!="{" or t.kind!="punct" or i not in pairs:continue
        d=_object(ts,i,pairs[i],pairs,scalars,objects)
        record_by_start[i]=d
        if i>=2 and ts[i-1].value=="=" and ts[i-2].kind=="name":
            objects[ts[i-2].value]=d
        if check(d):
            if any(isinstance(v,str) and v.startswith("<")
                   for k,v in d.items() if k in PROVENANCE|METRICS):
                indeterminate=True
            else:return "PROHIBITED"
    # Only ancestor context passes into child objects, not unrelated siblings.
    stack=[]
    inherited_local_override=False
    for i,t in enumerate(ts):
        if t.kind!="punct":continue
        if t.value=="{" and i in pairs:
            parent_external=stack[-1][1] if stack else False
            d=record_by_start.get(i,{})
            identities=[d[k] for k in PROVENANCE if k in d]
            current=(any(external(v) for v in identities) if identities
                     else parent_external)
            if parent_external and identities and not current and metric(d):
                inherited_local_override=True
            if current and not aggregate(d) and metric(d):
                if any(isinstance(v,str) and v.startswith("<")
                       for k,v in d.items() if k in PROVENANCE|METRICS):
                    indeterminate=True
                else:return "PROHIBITED"
            stack.append((pairs[i],current))
        elif t.value=="}" and stack and stack[-1][0]==i:
            stack.pop()
    prohibited,mutation_review=_explicit_js_mutations(ts,pairs,scalars,record_by_start)
    if prohibited:return "PROHIBITED"
    indeterminate=indeterminate or mutation_review
    if (inherited_local_override or
        _additional_js_review(ts,pairs,scalars,record_by_start)):
        indeterminate=True
    if any(check(d) for d in _jsx_records(ts,pairs,scalars)):
        return "PROHIBITED"
    # A template expression containing possible provenance and metric material
    # is not an independently verified numeric record.
    for t in ts:
        if (t.kind=="template" and "$"+"{" in t.value and
            re.search(r"source[_-]?id|dataSource|publisher",t.value,re.I) and
            re.search(r"score|accuracy|benchmark[_-]?score|value",t.value,re.I)):
            indeterminate=True
    return "REVIEW" if indeterminate else "LEGITIMATE"

def js_score(source:str)->bool:
    """Backward-compatible high-confidence score predicate."""
    return js_classify(source)=="PROHIBITED"

def xml_score(text:str)->bool:
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise ValueError("XML entity declarations require manual review")
    root=ET.fromstring(text)
    def local(name:str)->str:return norm(name.rsplit("}",1)[-1].rsplit(":",1)[-1])
    stack=[(root,False)];count=0
    while stack:
        el,prior=stack.pop();count+=1
        if count>200000:raise ValueError("XML traversal budget exceeded")
        d={local(k):v for k,v in el.attrib.items()}
        for child in el:
            key=local(child.tag);v=(child.text or "").strip()
            if key in PROVENANCE|METRICS|{"kind","unit","value"} and v:
                d[key]=v
        if d.get("kind")=="aggregate-count" and d.get("unit") in UNITS:
            v=d.get("value")
            if isinstance(v,str) and v.isdecimal():d["value"]=int(v)
        own=[d[k] for k in PROVENANCE if k in d]
        origin=any(external(v) for v in own) if own else prior
        if origin and not aggregate(d) and metric(d):return True
        body=(el.text or "").strip()
        if len(body)<=MAX_ENCODED and body:
            if body[:1] in ("{","["):
                try:
                    if json_score(json.loads(body)):return True
                except (ValueError,TypeError):pass
            if local(el.tag)=="script" and js_score(body):return True
        stack.extend((child,origin) for child in el)
    return False


def xml_indeterminate_sibling_provenance(text:str)->bool:
    """Ambiguous editorial score/provenance in different XML sibling nodes.

    Without a schema to prove the score belongs to an unrelated local
    observation, require independent manual review. This is *not* counted
    as a demonstrated joined external measurement.
    """
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        return True
    root=ET.fromstring(text)
    checked=0
    def local(name:str)->str:
        return norm(name.rsplit("}",1)[-1].rsplit(":",1)[-1])
    for parent in root.iter():
        checked+=1
        if checked>200000:
            raise ValueError("XML provenance review budget exceeded")
        children=list(parent)
        if len(children)<2:continue
        identities=set()
        metrics=set()
        for index,child in enumerate(children):
            attrs={local(k):v for k,v in child.attrib.items()}
            label=local(child.tag);text_value=(child.text or "").strip()
            has_external=any(external(v) for k,v in attrs.items() if k in PROVENANCE)
            has_score=any(numeric(v) for k,v in attrs.items() if k in METRICS)
            if label in PROVENANCE and external(text_value):has_external=True
            if label in METRICS and numeric(text_value):has_score=True
            if has_external:identities.add(index)
            if has_score:metrics.add(index)
        if any(a!=b for a in identities for b in metrics):
            return True
    return False

def json_requires_review(data:object)->bool:
    """Ambiguous normalized aliases and unresolved record provenance joins.

    Parent/child explicit numeric data with a local override is an uncertain
    rights attribution, not a proven externally supplied score. Never infer
    a join between unrelated siblings without relevant semantic structure.
    """
    stack=[(data,False)];seen=0
    while stack:
        node,prior=stack.pop();seen+=1
        if seen>5_000_000:raise ValueError("JSON review budget exceeded")
        if isinstance(node,list):
            stack.extend((v,prior) for v in node)
        elif isinstance(node,dict):
            keys=[norm(str(k)) for k in node]
            d={norm(str(k)):v for k,v in node.items()}
            critical=PROVENANCE|METRICS|{"value","kind","unit"}
            if len(keys)!=len(set(keys)):
                duplicated={k for k in keys if keys.count(k)>1}
                if duplicated&critical:return True
            # Provenance metadata belongs to the observation only if a schema
            # establishes the join: REVIEW until an independent adjudication.
            for a,b in (("metadata","observation"),("sources","observations")):
                if a in d and b in d and _has_external(d[a]) and _contains_metric(d[b]):
                    return True
            origins=[d[k] for k in PROVENANCE if k in d]
            current=prior
            if origins:
                external_own=any(external(v) for v in origins)
                if prior and not external_own and metric(d):
                    return True
                current=external_own
            stack.extend((v,current) for v in node.values() if isinstance(v,(dict,list)))
    return False

def xml_requires_review(text:str)->bool:
    """Unresolved ancestry/sibling provenance linkage, not a proven score."""
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        return True
    root=ET.fromstring(text)
    has_external=False;has_numeric=False;seen=0
    for el in root.iter():
        seen+=1
        if seen>200000:raise ValueError("XML review budget exceeded")
        d={norm(k.rsplit("}",1)[-1]):v for k,v in el.attrib.items()}
        tag=norm(el.tag.rsplit("}",1)[-1])
        body=(el.text or "").strip()
        if tag in PROVENANCE and external(body):has_external=True
        if tag in METRICS and numeric(body):has_numeric=True
        if any(k in PROVENANCE and external(v) for k,v in d.items()):
            has_external=True
        if any(k in METRICS and numeric(v) for k,v in d.items()):
            has_numeric=True
        # A free value needs explicit editorial measurement evidence.
        if "value" in d and numeric(d["value"]) and d.get("kind")!="aggregate-count":
            has_numeric=True
        if has_external and has_numeric:return True
        if tag=="script" and ("atob" in body or "decode" in body) and "parse" in body:
            return True
    return False
