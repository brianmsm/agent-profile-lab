"""Pure selector-rich snapshot projection; derived routes are not calibrated evidence."""
from copy import deepcopy
import json


from harness_contracts import load_harnesses, bounded_roles
from profile_semantics import require_visual_capability
HARNESS_CONTRACTS = load_harnesses()
AUXILIARY_ROLES = {h: bounded_roles(c) for h,c in load_harnesses().items()}
EXCLUDED_VOLUME_DOMAINS = frozenset({'agent-use', 'cybersecurity'})
LIMITATIONS = [
    'Estrategia derivada de perfiles baseline; no calibración empírica ni ganador recomendado.',
    'Roles configurados no demuestran uso habitual, reparto de tokens, ahorro ni latencia.',
    'La cuota disponible no autoriza delegar decisiones críticas abiertas.',
    'Las condiciones de alcance se presentan como contrato; la configuración nativa no las impone automáticamente.',
    'La política de advisor y concurrencia se hereda del perfil OpenAI de origen; la concurrencia es un techo, no una orden de fan-out.',
]
BOUNDED_CONDITION = (
    'Sólo alcance auxiliar delimitado, con fuente y oráculo de aceptación explícitos; '
    'sin delegación de decisiones críticas abiertas. El dueño OpenAI verifica el resultado; '
    'si el alcance no está cerrado, conservar la ruta OpenAI de fallback. '
    'Condición declarativa, no impuesta automáticamente por el harness.'
)


def allowed_pools(portfolio):
    pools = set()
    if portfolio['openai'] != 'none':
        pools.add('OAI')
    if portfolio['gateway'] in ('go', 'cc'):
        pools.add(portfolio['gateway'].upper())
    if portfolio['gateway'] == 'anthropic' or portfolio['anthropic'] == 'True':
        pools.add('ANTHROPIC')
    if portfolio['nan'] == 'True':
        pools.add('NAN')
    return pools


def route_identity(routes, runtime):
    """Operational identity includes dormant selectors, but not explanatory prose."""
    config = {
        role: {key: route[key] for key in ('modelKey', 'effort', 'fallback', 'accelerator', 'enabled')}
        for role, route in routes.items()
    }
    return json.dumps({'routes': config, 'runtime': runtime}, sort_keys=True, separators=(',', ':'))


def validate_routes(routes, catalog, portfolio, context):
    pools = allowed_pools(portfolio)
    for role, route in routes.items():
        harness=context.split('--',1)[0]
        function=HARNESS_CONTRACTS.get(harness,{}).get('roles',{}).get(role,{}).get('functionId')
        references = [('primary', {'modelKey': route['modelKey'], 'effort': route['effort']})]
        references.extend((name, route[name]) for name in ('fallback', 'accelerator') if route[name] is not None)
        for name, reference in references:
            model = catalog.get(reference['modelKey'])
            if model is None:
                raise ValueError(f'{context}/{role}: unknown {name} catalog key {reference["modelKey"]!r}')
            if model['pool'] not in pools:
                raise ValueError(f'{context}/{role}: {name} pool {model["pool"]} unavailable in portfolio')
            if route['enabled']:
                require_visual_capability(function,model.get('vision'),f'{context}/{role}/{name}')
            if name!='primary' and reference['modelKey']==route['modelKey'] and reference['effort']==route['effort']:
                raise ValueError(f'{context}/{role}: {name} repeats the primary route; no independent alternative')
            if reference['effort'] and reference['effort'] not in model.get('allowed_efforts', []):
                raise ValueError(f'{context}/{role}: unsupported {name} effort {reference["effort"]!r}')


def validate_strategy(strategy, baseline, runtime, catalog, portfolios, harness, domain):
    """Fail closed on protected-role drift, quota escalation and invalid reserves."""
    routes = strategy['routes']
    if set(routes) != set(baseline):
        raise ValueError('Strategy must preserve the complete baseline role set')
    validate_routes(routes, catalog, portfolios[strategy['portfolio']], strategy['sourceProfile'])
    if strategy['coordinatorPool'] != 'OAI':
        raise ValueError('Strategy coordinator must remain OpenAI')
    if strategy['kind'] == 'openai-led':
        if routes != baseline or strategy['offloadPool'] is not None:
            raise ValueError('OpenAI-led strategy must preserve baseline routes without offload')
        return
    if strategy['kind'] != 'nan-volume' or domain in EXCLUDED_VOLUME_DOMAINS:
        raise ValueError('NaN volume is not eligible for this strategy/domain')
    if strategy['offloadPool'] != 'NAN':
        raise ValueError('NaN volume must declare its actual offload pool')
    eligible = AUXILIARY_ROLES.get(harness, frozenset())
    changed = []
    for role, route in routes.items():
        original = baseline[role]
        if route == original:
            continue
        changed.append(role)
        if role not in eligible or not original['enabled']:
            raise ValueError(f'{role}: protected or dormant role cannot be offloaded')
        if catalog[route['modelKey']]['pool'] != 'NAN':
            raise ValueError(f'{role}: auxiliary candidate must be from the NaN pool')
        if route['fallback'] != {'modelKey': original['modelKey'], 'effort': original['effort']}:
            raise ValueError(f'{role}: auxiliary fallback must be the original OpenAI primary and effort')
        if catalog[original['modelKey']]['pool'] != 'OAI':
            raise ValueError(f'{role}: source primary must remain OpenAI')
        if route['accelerator'] != original['accelerator'] or route['enabled'] != original['enabled']:
            raise ValueError(f'{role}: auxiliary candidate must preserve accelerator/enabled state')
        if not route['condition'].startswith(BOUNDED_CONDITION):
            raise ValueError(f'{role}: missing bounded scope/source/oracle condition')
    if not changed or route_identity(routes, runtime) == route_identity(baseline, runtime):
        raise ValueError('NaN strategy must change at least one active auxiliary route')


def build_strategy_collections(rows, models, portfolios, policy_rows):
    """Return canonical details/policies plus additive, minimally funded strategies.

    All inputs are immutable audited data. Candidate provenance is retained in
    each modified route rationale; runtime always belongs to sourceProfile.
    """
    catalog = {}
    selectors = {}
    for model in models:
        if model['key'] in catalog or model['selector'] in selectors:
            raise ValueError('Catalog contains duplicate keys/selectors')
        catalog[model['key']] = model
        selectors[model['selector']] = model['key']
    metadata = {}
    grouped = {}
    for row in rows:
        pid = row['profile_id']
        identity = tuple(row[key] for key in ('portfolio', 'harness', 'domain', 'objective'))
        if pid in metadata and metadata[pid] != identity:
            raise ValueError(f'{pid}: inconsistent profile identity')
        metadata[pid] = identity
        roles = grouped.setdefault(pid, {})
        if row['role'] in roles:
            raise ValueError(f'{pid}: duplicate role {row["role"]}')
        roles[row['role']] = row
    policies = {pid: None for pid in grouped}
    for row in policy_rows:
        pid = row['profile_id']
        if pid not in grouped or metadata[pid][1] != 'omp' or policies[pid] is not None:
            raise ValueError(f'{pid}: unknown, non-OMP or duplicate runtime policy')
        if tuple(row[key] for key in ('portfolio', 'domain', 'objective')) != (
            metadata[pid][0], metadata[pid][2], metadata[pid][3]
        ):
            raise ValueError(f'{pid}: runtime policy identity mismatch')
        if row['advisor_enabled'] not in ('True', 'False'):
            raise ValueError(f'{pid}: invalid advisor enabled value')
        concurrency = int(row['task_max_concurrency'])
        if concurrency < 1:
            raise ValueError(f'{pid}: invalid task concurrency ceiling')
        policies[pid] = {'advisorEnabled': row['advisor_enabled'] == 'True', 'taskMaxConcurrency': concurrency}

    def reference(row, selector_field, effort_field, context):
        selector = row.get(selector_field, '')
        effort = row.get(effort_field, '')
        if not selector:
            if effort:
                raise ValueError(f'{context}: effort without {selector_field}')
            return None
        if selector not in selectors:
            raise ValueError(f'{context}: unknown {selector_field} selector {selector!r}')
        return {'modelKey': selectors[selector], 'effort': effort}

    details = {}
    for pid, roles in grouped.items():
        portfolio_id, harness, _, _ = metadata[pid]
        if portfolio_id not in portfolios:
            raise ValueError(f'{pid}: unknown portfolio {portfolio_id}')
        if harness == 'omp' and policies[pid] is None:
            raise ValueError(f'{pid}: missing OMP runtime policy')
        details[pid] = {}
        for role, row in roles.items():
            context = f'{pid}/{role}'
            primary = reference(row, 'model', 'thinking', context)
            if primary is None or primary['modelKey'] != row['model_key']:
                raise ValueError(f'{context}: primary selector/catalog key mismatch')
            warnings = json.loads(row.get('warnings') or '[]')
            if not isinstance(warnings, list) or any(not isinstance(item, str) for item in warnings):
                raise ValueError(f'{context}: invalid warning conditions')
            details[pid][role] = {
                **primary,
                'fallback': reference(row, 'fallback_model', 'fallback_thinking', context),
                'accelerator': reference(row, 'accelerator_model', 'accelerator_thinking', context),
                'enabled': not (harness == 'omp' and role in ('advisor', 'advisor_deep') and not policies[pid]['advisorEnabled']),
                'condition': ' '.join([row.get('quality_gate', ''), *warnings]).strip(),
                'rationale': row.get('rationale', ''),
            }
        validate_routes(details[pid], catalog, portfolios[portfolio_id], pid)

    by_combination = {}
    for pid, identity in metadata.items():
        if identity in by_combination:
            raise ValueError(f'{pid}: duplicate profile combination')
        by_combination[identity] = pid
    strategies = {}
    for pid, (portfolio_id, harness, domain, objective) in metadata.items():
        if portfolio_id not in ('plus', 'pro100'):
            continue
        baseline = details[pid]
        if allowed_pools(portfolios[portfolio_id]) != {'OAI'}:
            raise ValueError(f'{pid}: OpenAI baseline portfolio is not OpenAI-only')
        strategy = {
            'kind': 'openai-led', 'sourceProfile': pid, 'portfolio': portfolio_id,
            'routes': deepcopy(baseline), 'coordinatorPool': 'OAI', 'offloadPool': None,
            'limitations': list(LIMITATIONS),
        }
        validate_strategy(strategy, baseline, policies[pid], catalog, portfolios, harness, domain)
        strategies[pid + '::openai-led'] = strategy
        if domain in EXCLUDED_VOLUME_DOMAINS:
            continue
        candidate_pid = by_combination.get(('nan', harness, domain, objective))
        if candidate_pid is None:
            continue
        routes = deepcopy(baseline)
        changed = False
        for role in AUXILIARY_ROLES.get(harness, frozenset()):
            candidate = details[candidate_pid].get(role)
            original = baseline.get(role)
            if original is None or candidate is None or not original['enabled']:
                continue
            if catalog[candidate['modelKey']]['pool'] != 'NAN':
                raise ValueError(f'{candidate_pid}/{role}: NaN candidate has wrong pool')
            routes[role] = {
                **deepcopy(original), 'modelKey': candidate['modelKey'], 'effort': candidate['effort'],
                'fallback': {'modelKey': original['modelKey'], 'effort': original['effort']},
                'condition': BOUNDED_CONDITION + ' ' + original['condition'],
                'rationale': (
                    f'Candidato auxiliar derivado de assignments.csv: {candidate_pid}/{role}. '
                    f'Coordinación y fallback conservan {pid}/{role}; no es un ganador empírico. '
                    + candidate['rationale']
                ),
            }
            changed = True
        if not changed or route_identity(routes, policies[pid]) == route_identity(baseline, policies[pid]):
            continue
        volume = {
            **strategy, 'kind': 'nan-volume', 'portfolio': portfolio_id + '-nan',
            'routes': routes, 'offloadPool': 'NAN',
        }
        if volume['portfolio'] not in portfolios:
            raise ValueError(f'{pid}: missing required NaN portfolio')
        if portfolios[volume['portfolio']]['openai'] != portfolios[portfolio_id]['openai']:
            raise ValueError(f'{pid}: NaN portfolio cannot change OpenAI quota tier')
        if allowed_pools(portfolios[volume['portfolio']]) != {'OAI', 'NAN'}:
            raise ValueError(f'{pid}: NaN strategy portfolio must be minimally funded')
        validate_strategy(volume, baseline, policies[pid], catalog, portfolios, harness, domain)
        strategies[pid + '::nan-volume'] = volume
    return details, policies, strategies
