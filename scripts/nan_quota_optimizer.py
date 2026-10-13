"""Exact bounded role-to-NaN assignment beyond the small exhaustive grid.

For >10 eligible roles, use admissible branch-and-bound plus state dominance.
Never round token weights or silently truncate a search. If the explicit
complexity budget is exceeded, fail closed rather than return a fake optimum.
"""
from __future__ import annotations
from nan_quota_balance import KEYS
MAX_STATES=700_000
def solve_exact_expanded(rows,fixed,quotas,trial_cap_bps,max_states=MAX_STATES):
    """rows: ordered (expected_tokens, previous_model_key, tuple(candidate_keys)).
    Tie order: minimum total variation numerator, trial tokens, role changes,
    then lexicographically smallest key tuple. Equal states keep best prefix.
    """
    if not 1<=len(rows)<=32:raise ValueError('Exact NaN solver supports 1..32 roles with a bounded complexity budget')
    if max_states<1:raise ValueError('Complexity budget must be positive')
    if set(fixed)!=set(KEYS) or set(quotas)!=set(KEYS):raise ValueError('Unexpected quota model keys')
    if not 0<=trial_cap_bps<=10000:raise ValueError('Trial budget is invalid')
    if any(type(x) is not int or x<0 for x in fixed.values()) or any(type(x) is not int or x<=0 for x in quotas.values()):
        raise ValueError('Non-integer or negative quota and token counts')
    for burden,old,options in rows:
        if type(burden) is not int or burden<0 or old not in KEYS or not options or set(options)-set(KEYS):
            raise ValueError('Invalid eligible role or model options')
    Q=sum(quotas.values())
    total=sum(fixed.values())+sum(r[0] for r in rows)
    if not total:raise ValueError('No expected NaN work')
    allowance=total*trial_cap_bps
    desired={k:total*quotas[k] for k in KEYS}
    remaining=[0]*(len(rows)+1)
    for i in range(len(rows)-1,-1,-1):remaining[i]=remaining[i+1]+rows[i][0]
    current=dict(fixed)
    current_choices=[]
    best_key=None;best_totals=None
    memo={}
    seen=0
    def recurse(i,changes):
        nonlocal seen,best_key,best_totals
        seen+=1
        if seen>max_states:raise ValueError('Exact NaN optimization complexity budget exceeded; no approximate allocation emitted')
        trial=current['nan_qwen']+current['nan_mf']
        if trial*10000>allowance:return
        left=remaining[i]
        lower=0
        for key in KEYS:
            lower+=max(0,current[key]*Q-desired[key],desired[key]-(current[key]+left)*Q)
        if best_key is not None and lower>best_key[0]:return
        state=(i,tuple(current[k] for k in KEYS))
        prefix=(changes,tuple(current_choices))
        prev=memo.get(state)
        if prev is not None and prev<=prefix:return
        memo[state]=prefix
        if i==len(rows):
            err=sum(abs(current[k]*Q-desired[k]) for k in KEYS)
            candidate=(err,trial,changes,tuple(current_choices))
            if best_key is None or candidate<best_key:
                best_key=candidate;best_totals=dict(current)
            return
        burden,old,options=rows[i]
        for key in options:
            current[key]+=burden
            current_choices.append(key)
            recurse(i+1,changes+(old!=key))
            current_choices.pop()
            current[key]-=burden
    recurse(0,0)
    if best_key is None:raise ValueError('No quality-admissible exact NaN allocation')
    return {'choices':list(best_key[3]),'totals':best_totals,
        'errorNumerator':best_key[0],'trialTokens':best_key[1],
        'changes':best_key[2],'visitedStates':seen,'solver':'exact-branch-and-bound'}
