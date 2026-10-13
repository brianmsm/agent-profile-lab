"""NaN monthly quota-aware subtask selector; pure, quality-gated, no provider calls.

The same versioned policy is used by the TypeScript dashboard. A decision is not
an inference, observed usage, proof of model equivalence or native profile update.
"""
from __future__ import annotations
from datetime import datetime,timezone
from calendar import monthrange
from copy import deepcopy
from pathlib import Path
import json,math,re
ROOT=Path(__file__).resolve().parents[1]
POLICY_PATH=ROOT/'policies/nan-quota-balancing.json'
INVENTORY_PATH=ROOT/'catalog/account-inventory.json'
OFFERINGS_PATH=ROOT/'catalog/offerings.json'
KEYS=('nan_qwen','nan_ds','nan_mf','nan_glm')
SOURCES=('hypothetical','account-screenshot','user-entered','provider-normalized')

def load_config(root=ROOT):
    policy=json.loads((root/'policies/nan-quota-balancing.json').read_text())
    inv=json.loads((root/'catalog/account-inventory.json').read_text())
    offers=json.loads((root/'catalog/offerings.json').read_text())['offerings']
    rows={row['offeringKey']:row for row in inv['models']}
    functions=set(json.loads((root/'policies/functions.json').read_text())['functions'])
    if (policy['schemaVersion']!=1 or inv['schemaVersion']!=1 or set(rows)!=set(KEYS)
            or set(policy['labels'])!=set(KEYS) or set(policy['concurrency']['byOffering'])!=set(KEYS)
            or not set(policy['functions']).isdisjoint(policy['excludedFunctions'])
            or not set(policy['functions'])<=functions or not set(policy['excludedFunctions'])<=functions
            or not all(set(choices)<=set(KEYS) and set(choices.values())<=set(('eligible','trial')) for choices in policy['functions'].values())):
        raise ValueError('NaN policy and actual account inventory do not agree')
    for key,row in rows.items():
        if row['monthlyTokens']<=0 or row['resetCadence']!='monthly' or key not in offers or offers[key]['defaultAccessRouteId']!='nan':
            raise ValueError('Quota must come from one current monthly NaN offering')
        if row['modelId']!=offers[key]['modelId']:
            raise ValueError('NaN monthly quota attached to the wrong model identity')
    return policy,rows,offers

def current_month(instant):return instant.astimezone(timezone.utc).strftime('%Y-%m')
def parse_date(value):
    if not isinstance(value,str):raise ValueError('Invalid usage timestamp')
    try:d=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError as exc:raise ValueError('Invalid usage timestamp') from exc
    if d.tzinfo is None:raise ValueError('Usage timestamp requires explicit UTC offset')
    return d.astimezone(timezone.utc)

def nonnegative_int(value):return type(value) is int and 0<=value<=2**53-1

def validate_usage(usage):
    if not isinstance(usage,dict) or usage.get('schemaVersion')!=1 or usage.get('source') not in SOURCES or type(usage.get('approximate')) is not bool:
        raise ValueError('Usage snapshot schema or source is invalid')
    if set(usage)!={'schemaVersion','month','observedAt','source','consumed','verifiedOffers','approximate'}:
        raise ValueError('Unknown fields (possibly credentials) are not admitted to a quota snapshot')
    month=usage.get('month')
    if not isinstance(month,str) or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',month) or current_month(parse_date(usage.get('observedAt')))!=month:
        raise ValueError('Usage date must correspond to declared calendar month in UTC')
    c=usage.get('consumed')
    if not isinstance(c,dict) or set(c)!=set(KEYS) or not all(nonnegative_int(v) for v in c.values()):
        raise ValueError('All four NaN counters must be explicit nonnegative safe integers')
    verified=usage.get('verifiedOffers')
    if not isinstance(verified,list) or len(verified)!=len(set(verified)) or not set(verified)<=set(KEYS):
        raise ValueError('Invalid NaN verified offer list')
    return usage

def month_progress(now):
    now=now.astimezone(timezone.utc)
    a=datetime(now.year,now.month,1,tzinfo=timezone.utc)
    return max(0,min(1,(now-a).total_seconds()/(monthrange(now.year,now.month)[1]*86400)))

def plan_nan_task(usage,task,now, inflight=None,require_verified=False, config=None):
    policy,inventory,offers=config or load_config()
    if not isinstance(now,datetime) or now.tzinfo is None:raise ValueError('A timezone-aware now is required')
    month=current_month(now)
    base={'status':'blocked','reason':'','candidates':[],'month':month,'usageSource':usage.get('source') if isinstance(usage,dict) else None,'usageStale':False,'usedAsActual':False}
    if not isinstance(task,dict):raise ValueError('Invalid task')
    if (task.get('highImpact') is True or task.get('closedTask') is not True or task.get('acceptanceOracle') is not True
            or task.get('domain') in policy['excludedDomains'] or task.get('functionId') not in policy['functions']):
        base['reason']='La tarea exige una decisión abierta, un dominio protegido o carece de oráculo de aceptación; se conserva el responsable original.'
        return base
    estimate=task.get('estimatedTotalTokens');input_tokens=task.get('estimatedInputTokens');fraction=task.get('headroomFraction')
    if (not nonnegative_int(input_tokens) or not nonnegative_int(estimate) or estimate==0 or estimate<input_tokens
            or not isinstance(fraction,(float,int)) or isinstance(fraction,bool) or not math.isfinite(fraction) or not 0<=fraction<=.25
            or task.get('modality') not in ('text','image','audio')):
        raise ValueError('Estimaciones o restricciones de la tarea inválidas.')
    if usage is None:
        base.update(status='unknown-usage',reason='Introduce contadores de los cuatro modelos o selecciona expresamente una simulación. No se presumen saldos cero.')
        return base
    usage=validate_usage(usage)
    age=(now.astimezone(timezone.utc)-parse_date(usage['observedAt'])).total_seconds()/3600
    stale=usage['month']!=month or age<0 or age>policy['maximumUsageAgeHoursForDispatch']
    actual=usage['source'] in ('provider-normalized','user-entered') and not usage['approximate'] and not stale
    common={'month':month,'usageSource':usage['source'],'usageStale':stale,'usedAsActual':actual}
    if require_verified and (not actual or not usage['verifiedOffers']):
        base.update(common,status='unknown-usage',reason='Para reservar un despacho se exige consumo exacto reciente, mes vigente y al menos una ruta confirmada. Una captura o simulación no sirve.')
        return base
    if usage['month']!=month:
        base.update(common,status='unknown-usage',reason='El contador pertenece a otro mes; no se arrastra ni se reinicia automáticamente.')
        return base
    inflight=inflight or {'reserved':{},'count':{}}
    pace=month_progress(now)
    choices=policy['functions'][task['functionId']]
    candidates=[]
    for key in KEYS:
        kind=choices.get(key,'excluded');quota=inventory[key]['monthlyTokens'];consumed=usage['consumed'][key];reserved=inflight['reserved'].get(key,0);count=inflight['count'].get(key,0)
        if not nonnegative_int(reserved) or not nonnegative_int(count):raise ValueError('Invalid reservation counters')
        projected=consumed+reserved+estimate;balance=quota-consumed-reserved
        reason='Admisible para esta función cerrada, condicionado a verificar resultado y ruta.'
        if kind=='excluded':reason='No hay justificación de calidad para esta función.'
        elif kind=='trial' and task.get('includeTrials') is not True:reason=policy['trialReasons'].get(key,'Prueba de calidad no autorizada.')
        elif task['modality']!='text' and key not in policy['requirements'][task['modality']]:reason='La modalidad no está documentada para esta oferta.'
        elif input_tokens>inventory[key]['reportedContext']*policy['maximumInputFractionOfReportedContext']:reason='Entrada por encima del límite conservador de contexto declarado.'
        elif projected>quota*(1-fraction):reason='La tarea proyectada excede el saldo disponible con reserva de seguridad.'
        elif require_verified and key not in usage['verifiedOffers']:reason='La vía de acceso aún no está verificada para despachar.'
        elif require_verified and (count>=policy['concurrency']['byOffering'][key] or sum(inflight['count'].values())>=policy['concurrency']['totalByApiKey']):
            reason='Concurrencia declarada ocupada; no se abre otra llamada.'
        candidates.append({'offeringKey':key,'label':policy['labels'][key],'selector':offers[key]['compatibility']['selector'],
            'classification':kind,'reason':reason,'quota':quota,'consumed':consumed,'reserved':reserved,'planned':estimate,'available':max(0,balance),
            'usedFraction':(consumed+reserved)/quota,'projectedFraction':projected/quota,'paceFraction':pace,
            'remainingAfter':max(0,quota-projected),'eligible':reason=='Admisible para esta función cerrada, condicionado a verificar resultado y ruta.',
            'aheadOfPace':(consumed+reserved)/quota>pace})
    eligible=sorted((r for r in candidates if r['eligible']),key=lambda r:(r['projectedFraction'],r['usedFraction'],r['offeringKey']))
    if not eligible:return {**common,'status':'no-eligible','reason':'Ninguna vía apta cumple simultáneamente calidad, contexto, cuota, modalidad y condiciones de acceso. No se sustituye por un modelo incompatible.','candidates':candidates}
    winner=eligible[0]
    return {**common,'status':'selected','selected':winner['offeringKey'],'selector':winner['selector'],
        'reason':f"{winner['label']} presenta la menor fracción proyectada de cuota entre las opciones admitidas ({winner['projectedFraction']*100:.3f} %). Es una elección para la siguiente subtarea, no un cambio de modelo a mitad de turno.",
        'candidates':candidates}

def simulate_nan_tasks(usage,task,count,now,config=None):
    if type(count) is not int or not 1<=count<=500:raise ValueError('Simulation limited to 1..500 tasks')
    consumed=deepcopy(usage)
    counts={k:0 for k in KEYS};decisions=[]
    for i in range(count):
        decision=plan_nan_task(consumed,{**task,'taskId':f"{task.get('taskId','sim')}-{i}"},now,config=config)
        if decision['status']!='selected':break
        key=decision['selected'];consumed['consumed'][key]+=task['estimatedTotalTokens'];counts[key]+=1
        decisions.append({'offeringKey':key,'estimatedTokens':task['estimatedTotalTokens']})
    return {'projected':consumed['consumed'],'counts':counts,'decisions':decisions,'requested':count,'planned':len(decisions),
        'note':'Simulación determinista de consumo estimado, no llamadas ejecutadas ni cuotas realmente descontadas.'}

if __name__=='__main__':
    print(json.dumps({'policy':load_config()[0]['id'],'models':list(KEYS),'mode':'offline-planner-only','inferencesSent':0}))
