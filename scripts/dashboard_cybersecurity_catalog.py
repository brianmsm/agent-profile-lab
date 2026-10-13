"""Curated publication labels, not a model-name similarity classifier."""

# Each key is an exact catalog selector: a changed selector requires renewed review.
CATALOG_SELECTORS = {
    'oa_sol': 'openai-codex/gpt-6-sol',
    'oa_sol61': 'openai-codex/gpt-6.1-sol',
    'oa_luna': 'openai-codex/gpt-6-luna',
    'oa_astra': 'openai-codex/gpt-6-astra',
    'oa_oldsol': 'openai-codex/gpt-5.6-sol',
    'cc_oldsol': 'commandcode/gpt-5.6-sol',
    'go_luna': 'opencode-go/gpt-6-luna',
    'cc_luna': 'commandcode/gpt-6-luna',
    'cl_opus': 'anthropic/claude-opus-5-5',
    'cl_sonnet': 'anthropic/claude-sonnet-5-5',
    'cl_fable': 'anthropic/claude-fable-5-1',
    'go_mp': 'opencode-go/mimo-v2.6-pro',
    'cc_mp': 'commandcode/xiaomi/mimo-v2.6-pro',
    'go_mf': 'opencode-go/mimo-v2.6-flash',
    'cc_mf': 'commandcode/xiaomi/mimo-v2.6-flash',
    'go_ds': 'opencode-go/deepseek-v4.1-flash',
    'cc_ds': 'commandcode/deepseek/deepseek-v4.1-flash',
    'nan_ds': 'nan/deepseek-v4-flash',
    'nan_mimo': 'nan/mimo-v2.5',
    'go_glmf': 'opencode-go/glm-5.3',
    'cc_glmf': 'commandcode/zai-org/GLM-5.3',
    'go_glm': 'opencode-go/glm-5.3-flash',
    'cc_glm': 'commandcode/z-ai/glm-5.3-flash',
    'nan_glm': 'nan/glm5.3-flash',
    'go_kimi': 'opencode-go/kimi-k3',
    'cc_kimi': 'commandcode/moonshotai/Kimi-K3',
}

PUBLISHED_MODEL_KEYS = {
    'GPT-6 Sol': ('oa_sol',),
    'GPT-6.1 Sol': ('oa_sol61',),
    'GPT-6 Luna': ('oa_luna', 'go_luna', 'cc_luna'),
    'GPT-6 Astra': ('oa_astra',),
    'GPT-5.6 Sol': ('oa_oldsol', 'cc_oldsol'),
    'GPT-5.6-Sol': ('oa_oldsol', 'cc_oldsol'),
    'Claude Opus 5.5': ('cl_opus',),
    'Claude Sonnet 5.5': ('cl_sonnet',),
    'Claude Fable 5.1': ('cl_fable',),
    'MiMo-V2.6 Pro': ('go_mp', 'cc_mp'),
    'MiMo V2.6 Pro': ('go_mp', 'cc_mp'),
    'MiMo-V2.6 Flash': ('go_mf', 'cc_mf'),
    'MiMo V2.6 Flash': ('go_mf', 'cc_mf'),
    'DeepSeek V4.1 Flash': ('go_ds', 'cc_ds'),
    'DeepSeek-V4.1-Flash': ('go_ds', 'cc_ds'),
    'DS-V4.1-Flash': ('go_ds', 'cc_ds'),
    'GLM-5.3': ('go_glmf', 'cc_glmf'),
    'GLM 5.3': ('go_glmf', 'cc_glmf'),
    'GLM 5.3 Flash': ('go_glm', 'cc_glm', 'nan_glm'),
    'GLM-5.3-Flash': ('go_glm', 'cc_glm', 'nan_glm'),
    'Kimi K3': ('go_kimi', 'cc_kimi'),
    'K3': ('go_kimi', 'cc_kimi'),
}
CANDIDATE_ALIAS_KEYS = {
    'MiMo-V2.5 Pro': ('nan_mimo',),
    'MiMo V2.5 Pro': ('nan_mimo',),
    'DeepSeek V4.1 Flash': ('nan_ds',),
    'DeepSeek-V4.1-Flash': ('nan_ds',),
    'DS-V4.1-Flash': ('nan_ds',),
}


def catalog_matches(label, catalog):
    matches = []
    for relationship, registry in (('published-model', PUBLISHED_MODEL_KEYS),
                                   ('candidate-alias', CANDIDATE_ALIAS_KEYS)):
        for key in registry.get(label, ()):
            if key not in catalog:
                continue
            if catalog[key]['selector'] != CATALOG_SELECTORS[key]:
                raise ValueError(f'Cybersecurity catalog selector changed without link review: {key}')
            reason = (
                'La etiqueta literal publicada corresponde a este modelo del catálogo; no se ha establecido equivalencia de proveedor, checkpoint ni harness.'
                if relationship == 'published-model' else
                'Sólo alias candidato: la versión o el sufijo de la publicación difiere de la identidad del catálogo; el checkpoint servido y la equivalencia de proveedor y harness siguen sin resolverse.'
            )
            if label in ('DS-V4.1-Flash', 'K3'):
                reason += ' La correspondencia usa esta cabecera abreviada de la tabla del publicador, revisada explícitamente, no una coincidencia aproximada.'
            matches.append(dict(catalogKey=key, relationship=relationship, reason=reason))
    return matches
