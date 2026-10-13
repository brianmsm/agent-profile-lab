"""Behavioral guardrails for derived strategies; no fixture snapshots or traffic claims."""
from copy import deepcopy
import unittest

from dashboard_strategies import build_strategy_collections, route_identity, validate_strategy


def fixture():
    models = [
        {'key': 'openai', 'selector': 'openai-codex/strong', 'pool': 'OAI', 'allowed_efforts': ['low', 'high']},
        {'key': 'nan', 'selector': 'nan/auxiliary', 'pool': 'NAN', 'allowed_efforts': ['low']},
        {'key': 'gateway', 'selector': 'commandcode/reserve', 'pool': 'CC', 'allowed_efforts': ['high']},
    ]
    portfolios = {
        'plus': {'openai': 'plus', 'gateway': 'none', 'anthropic': 'False', 'nan': 'False'},
        'nan': {'openai': 'none', 'gateway': 'none', 'anthropic': 'False', 'nan': 'True'},
        'plus-nan': {'openai': 'plus', 'gateway': 'none', 'anthropic': 'False', 'nan': 'True'},
    }
    rows, policies = [], []
    for portfolio in ('plus', 'nan'):
        pid = f'omp--{portfolio}-research-balanced'
        policies.append({
            'profile_id': pid, 'portfolio': portfolio, 'domain': 'research', 'objective': 'balanced',
            'advisor_enabled': 'False', 'task_max_concurrency': '2' if portfolio == 'plus' else '9',
        })
        for role in ('default', 'task', 'plan', 'slow', 'judge', 'smol', 'tiny', 'memory', 'commit', 'advisor', 'advisor_deep'):
            rows.append({
                'profile_id': pid, 'portfolio': portfolio, 'harness': 'omp', 'domain': 'research',
                'objective': 'balanced', 'role': role, 'model_key': 'openai' if portfolio == 'plus' else 'nan',
                'model': 'openai-codex/strong' if portfolio == 'plus' else 'nan/auxiliary',
                'thinking': 'high' if portfolio == 'plus' else 'low', 'fallback_model': '',
                'fallback_thinking': '', 'accelerator_model': '', 'warnings': '[]',
                'quality_gate': 'Source and acceptance oracle required.', 'rationale': 'Audited baseline rationale.',
            })
    return rows, models, portfolios, policies


class StrategyGuardrails(unittest.TestCase):
    def test_critical_decisions_and_fallbacks_stay_with_baseline_owner(self):
        rows, models, portfolios, policies = fixture()
        details, runtime, strategies = build_strategy_collections(rows, models, portfolios, policies)
        pid = 'omp--plus-research-balanced'
        baseline = details[pid]
        volume = strategies[pid + '::nan-volume']
        for role in ('default', 'task', 'plan', 'slow', 'judge', 'advisor', 'advisor_deep'):
            self.assertEqual(volume['routes'][role], baseline[role])
        for role in ('smol', 'tiny', 'memory', 'commit'):
            self.assertEqual(volume['routes'][role]['modelKey'], 'nan')
            self.assertEqual(volume['routes'][role]['fallback'], {'modelKey': 'openai', 'effort': 'high'})
        catalog = {model['key']: model for model in models}
        corrupted = deepcopy(volume)
        corrupted['routes']['task'] = deepcopy(volume['routes']['smol'])
        with self.assertRaisesRegex(ValueError, 'protected'):
            validate_strategy(corrupted, baseline, runtime[pid], catalog, portfolios, 'omp', 'research')
        corrupted = deepcopy(volume)
        corrupted['routes']['smol']['fallback']['effort'] = 'low'
        with self.assertRaisesRegex(ValueError, 'original OpenAI primary and effort'):
            validate_strategy(corrupted, baseline, runtime[pid], catalog, portfolios, 'omp', 'research')
        corrupted = deepcopy(volume)
        del corrupted['routes']['judge']
        with self.assertRaisesRegex(ValueError, 'complete baseline role set'):
            validate_strategy(corrupted, baseline, runtime[pid], catalog, portfolios, 'omp', 'research')
        for domain in ('agent-use', 'cybersecurity'):
            with self.assertRaisesRegex(ValueError, 'not eligible'):
                validate_strategy(volume, baseline, runtime[pid], catalog, portfolios, 'omp', domain)

    def test_volume_cannot_upgrade_quota_or_borrow_nan_runtime(self):
        rows, models, portfolios, policies = fixture()
        details, runtime, strategies = build_strategy_collections(rows, models, portfolios, policies)
        pid = 'omp--plus-research-balanced'
        self.assertNotEqual(
            route_identity(strategies[pid + '::nan-volume']['routes'], runtime[pid]),
            route_identity(strategies[pid + '::nan-volume']['routes'], runtime['omp--nan-research-balanced']),
        )
        source = strategies[pid + '::nan-volume']['sourceProfile']
        self.assertEqual(runtime[source], {'advisorEnabled': False, 'taskMaxConcurrency': 2})
        portfolios['plus-nan']['openai'] = 'pro100'
        with self.assertRaisesRegex(ValueError, 'quota tier'):
            build_strategy_collections(rows, models, portfolios, policies)

    def test_disabled_advisor_keeps_identity_but_cannot_hide_illegal_reserve(self):
        rows, models, portfolios, policies = fixture()
        details, runtime, _ = build_strategy_collections(rows, models, portfolios, policies)
        pid = 'omp--plus-research-balanced'
        self.assertFalse(details[pid]['advisor']['enabled'])
        self.assertFalse(details[pid]['advisor_deep']['enabled'])
        changed = deepcopy(details[pid])
        changed['advisor']['effort'] = 'low'
        self.assertNotEqual(route_identity(changed, runtime[pid]), route_identity(details[pid], runtime[pid]))
        advisor = next(row for row in rows if row['profile_id'] == pid and row['role'] == 'advisor')
        advisor['fallback_model'] = 'commandcode/reserve'
        advisor['fallback_thinking'] = 'high'
        with self.assertRaisesRegex(ValueError, 'fallback pool CC unavailable'):
            build_strategy_collections(rows, models, portfolios, policies)


if __name__ == '__main__':
    unittest.main()
