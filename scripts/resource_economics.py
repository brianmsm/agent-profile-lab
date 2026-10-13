"""Declared, dated economics. No balance lookup, inference, or spending enforcement."""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from pathlib import Path
import json, math, re
ROOT=Path(__file__).resolve().parents[1]

def iso_date(value, name):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError(f'{name}: explicit ISO date required')
    return date.fromisoformat(value)
def positive_amount(value, name, allow_zero=False):
    if type(value) not in (int,float) or not math.isfinite(value) or value<0 or (value==0 and not allow_zero):raise ValueError(f'{name}: finite positive amount required')
    return Decimal(str(value))

def estimate_request(model_id, token_counts, as_of, root=ROOT, cache_write_ttl='5-min'):
    """Price one request using *noncached* input, cached read/write and output tokens.

    A task-wide sum cannot select Haiku's per-request long-input tier. Call this
    separately for every request, using counts produced by the actual tokenizer.
    """
    fields={'input','cacheRead','cacheWrite','output'}
    if not isinstance(token_counts,dict) or set(token_counts)!=fields:raise ValueError('Supply four request-level token counts; aggregate task totals are not supported')
    if any(type(v) is not int or v<0 for v in token_counts.values()):raise ValueError('Token counts must be nonnegative integers, not booleans or estimates')
    when=iso_date(as_of,'asOf')
    doc=json.loads((root/'catalog/pricing.json').read_text())
    matches=[r for r in doc['rates'] if r['modelId']==model_id and iso_date(r['validFrom'],'validFrom')<=when and (r['validUntil'] is None or when<=iso_date(r['validUntil'],'validUntil'))]
    if len(matches)!=1:raise ValueError('No unique price contract for this model/date; do not extrapolate a historical rate')
    rate=matches[0]
    if token_counts['cacheWrite'] and cache_write_ttl!=rate['cacheWriteTtl']:raise ValueError('Cache TTL not covered by this price contract')
    total_input=token_counts['input']+token_counts['cacheRead']+token_counts['cacheWrite']
    tier=next(t for t in rate['tiers'] if t['maxInputInclusive'] is None or total_input<=t['maxInputInclusive'])
    parts={k:Decimal(str(tier[k]))*token_counts[k]/Decimal(1_000_000) for k in sorted(fields)}
    return {'kind':'dated-request-price-estimate','modelId':model_id,'asOf':as_of,'inputForTier':total_input,
            'tierMaxInputInclusive':tier['maxInputInclusive'],'currency':doc['currency'],'cost':str(sum(parts.values())),
            'components':{k:str(v) for k,v in parts.items()},'sourceUrls':doc['sources'],
            'limitations':['Not observed spend, a capability result, or an enforced cap.','Does not establish subscription consumption or the price of another gateway.','Token counts must come from this model and per-request cache accounting.']}

def validate_funding(funding, resources, catalog, authorization, as_of, root=ROOT):
    """Validate explicitly claimed API credit/prepaid funding at a declared date.

    No credit is granted merely because a subscription plan is named. Funding
    never replaces the separate authorization to consume an API resource.
    """
    if funding is None:return None
    if not isinstance(funding,dict) or not funding:raise ValueError('Funding must explicitly map API resources to declarations')
    when=iso_date(as_of,'fundingAsOf')
    doc=json.loads((root/'catalog/resource-benefits.json').read_text());result={}
    for rid,item in funding.items():
        allowed={'kind','availableAmount','currency','observedOn','expiresOn','organizationRef','claimed','benefitId','eligiblePlan','standardSeats','premiumSeats'}
        required=(allowed-{'standardSeats','premiumSeats'}) if isinstance(item,dict) and item.get('kind')=='included-credit' else allowed-{'benefitId','eligiblePlan','standardSeats','premiumSeats'}
        if not isinstance(item,dict) or set(item)-allowed or not required<=set(item):raise ValueError('Missing or unsupported funding fields')
        resource=resources.get(rid)
        if not resource or catalog['routes'][resource['accessRouteId']]['billing']!='metered':raise ValueError('Funding belongs to a declared API resource, not subscription OAuth')
        if item['kind'] not in {'included-credit','prepaid'} or item['claimed'] is not True:raise ValueError('Funding must be explicitly claimed; no inferred credit')
        balance=positive_amount(item['availableAmount'],'availableAmount',True)
        if not isinstance(item['organizationRef'],str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9._-]{0,95}',item['organizationRef']) or item['organizationRef'].startswith(('sk-','token-')):raise ValueError('Use a non-secret organization reference')
        observed=iso_date(item['observedOn'],'observedOn');expires=iso_date(item['expiresOn'],'expiresOn')
        if not observed<=when<expires:raise ValueError('Funding is expired, future-dated or not yet observed at fundingAsOf')
        if item['currency']!='USD':raise ValueError('This credit contract is USD only; no inferred conversion')
        if item['kind']=='included-credit':
            benefit=doc['benefits'].get(item['benefitId'])
            service=catalog['routes'][resource['accessRouteId']]['service']
            if not benefit or benefit['service']!=service or benefit['eligiblePlan']!=item['eligiblePlan']:raise ValueError('Ineligible plan or service for claimed API credit')
            monthly=benefit['monthlyAmount']
            if benefit['eligiblePlan']=='team':
                if any(type(item.get(k)) is not int or item[k]<0 for k in ['standardSeats','premiumSeats']):raise ValueError('Team credit requires explicit nonnegative seat counts')
                monthly=min(monthly,20*item['standardSeats']+100*item['premiumSeats'])
            elif any(k in item for k in ['standardSeats','premiumSeats']):raise ValueError('Seat counts belong to Team only')
            if balance>Decimal(str(monthly)):raise ValueError('Claimed remaining credit exceeds the published monthly benefit')
        elif any(k in item for k in ('benefitId','eligiblePlan')):raise ValueError('Prepaid funding does not infer a subscription benefit')
        if not authorization or authorization['currency']!=item['currency'] or Decimal(str(authorization['maxAmount']))>balance:raise ValueError('Explicit API budget must fit the declared remaining balance; overage is not authorized')
        result[rid]={**item,'validatedAsOf':as_of,'balanceVerification':'user-declared-not-inspected','enforcement':'not-enforced','overageAllowed':False}
    return result
