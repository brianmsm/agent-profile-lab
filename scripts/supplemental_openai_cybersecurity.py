"""Literal OpenAI cyber capability and safeguard aggregates, never plotted bars."""
import re


def ingest(api, name, raw, text, locator, date, emit, metadata):
    flat = ' '.join(text.split())
    sol = name == 'CYBER_OPENAI_SOL61'
    target = 'GPT-6.1 Sol' if sol else 'GPT-6 Astra'

    def match(pattern):
        found = re.search(pattern, flat)
        if not found:
            raise ValueError('Missing literal OpenAI cybersecurity result: ' + name + ': ' + pattern)
        return found

    def score(model, benchmark, value, unit, fragment, settings, denominator=None,
              budget=None, version=None, limits=(), effort='not stated'):
        emit(model, benchmark, value, unit, fragment,
             metadata('vendor' if model == target else 'vendor-comparator', date,
                      settings, version=version, denominator=denominator, budget=budget, limits=limits),
             effort=effort)

    if sol:
        m = match(r'At maximum reasoning effort, GPT-6\.1 Sol scores ([\d.]+)%, compared with ([\d.]+)% for GPT-6 Sol and ([\d.]+)% for GPT-6 Astra')
        for model, value in zip(['GPT-6.1 Sol', 'GPT-6 Sol', 'GPT-6 Astra'], m.groups()):
            score(model, 'OpenAI ExploitBench Cap Percent (maximum effort comparison)', float(value), '%',
                  'exploitbench/maximum/' + model,
                  'Sol addendum maximum-effort comparison; ExploitBench capability coverage, not arbitrary-code-execution success rate. Addendum refers to Astra methods; exact per-model denominator/budget not restated here.',
                  limits=['Potential historical-vulnerability contamination may artificially inflate scores.', 'OpenAI updated Cap Percent scoring differs from Anthropic three-of-five-trial Cap%. Astra own lowest-effort observation is separate.'], effort='maximum (comparison paragraph)')
        m = match(r'GPT-6\.1 Sol reaches an arbitrary code-execution success rate of ([\d.]+)%, compared with ([\d.]+)% for GPT-6 Astra, ([\d.]+)% for GPT-6 Sol, and ([\d.]+)% for GPT-5\.6 Sol')
        for model, value in zip(['GPT-6.1 Sol', 'GPT-6 Astra', 'GPT-6 Sol', 'GPT-5.6 Sol'], m.groups()):
            score(model, 'OpenAI ExploitBench Internal Port ACE success rate', float(value), '%',
                  'exploitbench-internal-port-juneaugust-2026/ACE/' + model,
                  'Internal port uses recently disclosed vulnerabilities to reduce historical contamination; arbitrary code-execution rate. Addendum does not disclose denominator or attempt/token limit.',
                  version='June–August 2026 internal port')
        m = match(r'GPT-6\.1 Sol reaches a pass@1 score of ([\d.]+)%, compared with ([\d.]+)% for GPT-6 Astra, ([\d.]+)% for GPT-6 Sol, and ([\d.]+)% for GPT-5\.6 Sol')
        for model, value in zip(['GPT-6.1 Sol', 'GPT-6 Astra', 'GPT-6 Sol', 'GPT-5.6 Sol'], m.groups()):
            score(model, 'OpenAI SEC-Bench Pro Pass@1', float(value), '%', 'sec-bench-pro/pass-at-1/' + model,
                  'Vulnerability discovery in V8 and SpiderMonkey; Pass@1 in Sol addendum. Astra card describes May2026 dataset and improved root-cause grader, but denominator/version not automatically transferred to this addendum comparison.',
                  limits=['Do not compare directly with DeepSeek or MiMo SEC cells without establishing version/harness/grader parity.'])
        m = match(r'GPT-6\.1 Sol reaches an intended-vulnerability success rate of ([\d.]+)% per attempt, compared with ([\d.]+)% for GPT-6 Astra, ([\d.]+)% for GPT-6 Sol, and ([\d.]+)% for GPT-5\.6 Sol')
        for model, value in zip(['GPT-6.1 Sol', 'GPT-6 Astra', 'GPT-6 Sol', 'GPT-5.6 Sol'], m.groups()):
            score(model, 'OpenAI ExploitGym intended-vulnerability success per attempt', float(value), '%',
                  'exploitgym/intended-per-attempt/' + model,
                  'Sol addendum intended-vulnerability success rate per attempt; maximum observed performance at varying output-token budgets, not Anthropic fixed 2-hour/6-hour protocol. Exact token cap, task denominator and mitigations not stated in this paragraph.')
        m = match(r'GPT-6 Sol and GPT-6 Luna successfully develop working exploits on ([\d.]+)% and ([\d.]+)% of challenges, respectively')
        if float(m[1]) != 22.1:
            raise ValueError('Sol historical/current ExploitGym comparison requires reconciliation')
        api['exclude'](locator + '#exploitgym/repeated-GPT-6-Sol-22.1', 'Repeated exact GPT-6 Sol ExploitGym observation in same addendum paragraph; not an independent trial.')
        score('GPT-6 Luna', 'OpenAI ExploitGym challenge-success comparator', float(m[2]), '%',
              'exploitgym/luna-published-comparison', 'Published comparator challenge-success rate; no denominator, attempt/token limit or mitigations disclosed in addendum paragraph.')
    else:
        m = match(r'Astra achieves the full score of ([\d.]+)%, even at the lowest reasoning effort tested')
        score(target, 'OpenAI ExploitBench Cap Percent (lowest effort tested)', float(m[1]), '%',
              'exploitbench/lowest-effort/cap-percent',
              '41 V8 vulnerabilities; 16 capability flags; Cap Percent unions demonstrated flags across five attempts per vulnerability, with any ACE seed awarding full 16-of-16 credit, then averages over vulnerabilities. Updated scoring and internal execution infrastructure.',
              denominator=41, budget='five model attempts per vulnerability',
              limits=['Potential historical-vulnerability contamination; updated scoring not comparable to old OpenAI scoring or Anthropic three-of-five Cap%.'], effort='lowest reasoning effort tested (native value not stated)')
        m = match(r'At pass@4, Astra solves ([\d.]+)% of the reverse engineering challenges vs\. GPT-5\.6 Sol’s ([\d.]+)%')
        for model, value in zip([target, 'GPT-5.6 Sol'], m.groups()):
            score(model, 'OpenAI SRE-Bench full solve rate Pass@4', float(value), '%', 'sre-bench/pass-at-4/' + model,
                  '262 binary instances from19 privately developed programs; full solution satisfies all six objectives. Pass@4 reports maximum accuracy across four independent trials with total tokens across trials.',
                  denominator=262, budget='four independent trials')
        m = match(r'Astra succeeds on (\d+) of (\d+) targets \(([\d.]+)%\), compared with (one) of (\d+) \(([\d.]+)%\) for Sol')
        for model, count, denominator, rate in [(target, int(m[1]), int(m[2]), float(m[3])), ('Sol (Astra system-card comparator)', 1, int(m[5]), float(m[6]))]:
            settings = 'Sandbox Bench internal CTF-style evaluation; protected-flag recovery;22 targets across runtimes, parsers and egress proxies. Comparator publication only says Sol, so exact-version correspondence not inferred.'
            score(model, 'OpenAI Sandbox Bench successful targets', count, 'successful targets', 'sandbox-bench/overall/count/' + model, settings, denominator=denominator)
            score(model, 'OpenAI Sandbox Bench target success rate', rate, '%', 'sandbox-bench/overall/rate/' + model, settings, denominator=denominator)
        match(r'four of five runtime targets, five of fourteen parser targets, and one of three egress proxies\. Sol succeeds on one runtime target and no parser or proxy targets')
        for model, counts in [(target, [4, 5, 1]), ('Sol (Astra system-card comparator)', [1, 0, 0])]:
            for category, count, denominator in zip(['runtime', 'parser', 'egress proxy'], counts, [5, 14, 3]):
                score(model, 'OpenAI Sandbox Bench successful ' + category + ' targets', count, 'successful targets', 'sandbox-bench/category/' + category + '/' + model,
                      'Literal Sandbox Bench category counts; zero comparator parser/proxy successes explicitly published as no successes. Category subsets overlap the overall observation; never aggregate as independent evaluations.', denominator=denominator)
        external = 'Irregular externally conducted sandboxed evaluation without public internet; republished by OpenAI system card, not a separately archived independent report. '
        m = match(r'Astra solved (\d+)/(\d+) challenges, compared with (\d+)/(\d+) for GPT-5\.6-Sol')
        for model, count, denominator in [(target, int(m[1]), int(m[2])), ('GPT-5.6-Sol', int(m[3]), int(m[4]))]:
            score(model, 'Irregular FrontierCyber solved challenges (OpenAI report)', count, 'solved challenges', 'irregular/frontiercyber/' + model,
                  external + 'Vulnerability discovery/exploitation suite; no successful attacks on fully hardened targets reported.', denominator=denominator)
        match(r'neither model solved any of the seven Elite challenges')
        for model in [target, 'GPT-5.6-Sol']:
            score(model, 'Irregular FrontierCyber Elite solved challenges (OpenAI report)', 0, 'solved challenges', 'irregular/frontiercyber/elite/' + model,
                  external + 'Elite seven-challenge subset; explicit published zero; subset not another independent run.', denominator=7)
        m = match(r'Astra solved (\d+)/(\d+) challenges at least once, compared with (\d+)/(\d+) for GPT-5\.6-Sol\. Its average success rate was ([\d.]+)%')
        for model, count, denominator in [(target, int(m[1]), int(m[2])), ('GPT-5.6-Sol', int(m[3]), int(m[4]))]:
            score(model, 'Irregular CyScenarioBench challenges solved at least once (OpenAI report)', count, 'solved challenges', 'irregular/cyscenariobench/at-least-once/' + model,
                  external + 'At-least-once solved challenge count, distinct from average success rate; attempt budget unspecified.', denominator=denominator)
        score(target, 'Irregular CyScenarioBench average success rate (OpenAI report)', float(m[5]), '%', 'irregular/cyscenariobench/average',
              external + 'Average success rate; source reports32percentage-point gain, not a literal comparator rate. No comparator rate derived.', denominator=10)
        m = match(r'Astra also solved (\d+)/(\d+) Atomic challenges, with average success rates of ([\d.]+)% in vulnerability research and exploitation, ([\d.]+)% in network attack simulation, and ([\d.]+)% in evasion')
        score(target, 'Irregular Atomic Challenges solved challenges (OpenAI report)', int(m[1]), 'solved challenges', 'irregular/atomic/overall', external + 'Overall solved challenge count; category average rates distinct.', denominator=int(m[2]))
        for category, rate in zip(['vulnerability research and exploitation', 'network attack simulation', 'evasion'], m.groups()[2:]):
            score(target, 'Irregular Atomic Challenges average ' + category + ' success (OpenAI report)', float(rate), '%', 'irregular/atomic/category/' + category,
                  external + 'Published category average success rate; category denominator and attempts unspecified.')
        api['context'](api['ROWS'][-1]['sourceId'], locator + '#capabilities/protocol-only-and-expert-context',
                       {'SEC-Bench Pro': {'version': 'May2026', 'tasks': 183, 'grader': 'improved agent root-cause analysis'},
                        'ExploitGym': {'version': 'v1', 'tasks': 869, 'runtime': 'offline; runtime package installation disabled', 'budget': 'token cap unspecified; no wall-clock cap'},
                        'expertAssessments': 'Case studies with29hours initial browser success plus12hours adaptation and12hours OS success; not denominator-based benchmark scores.'},
                       'Astra SEC/ExploitGym plot values not inferred. Protocol metadata and expert-led case-study durations remain context, not numeric capability scores or Sol-denominator inheritance.', date)

    parser = api['Tables'](); parser.feed(raw)
    table = next(t for t in parser.tables if any(r and r[0] == 'Production Chat' for r in t))
    for ri, row in enumerate(table[1:], 1):
        for ci, model in enumerate(table[0][1:], 1):
            fragment = f'cybersecurity-safety/table/row/{ri}/column/{ci}'
            if row[ci] == '---':
                api['exclude'](locator + '#' + fragment, 'Published cybersecurity safety table dash; unavailable, not zero.')
                continue
            benchmark = 'OpenAI Cybersecurity Safety Evaluation ' + row[0]
            value = float(row[ci])
            existing = [r for r in api['ROWS'] if r['model'] == model and r['benchmark'] == benchmark]
            if existing:
                if len(existing) != 1 or existing[0]['value'] != value:
                    raise ValueError('OpenAI safety table overlap changed: ' + model + ': ' + benchmark)
                api['exclude'](locator + '#' + fragment, 'Exact safety-table observation already incorporated from Sol addendum; Astra card republishes same values, not an independent trial.')
                continue
            score(model, benchmark, value, 'safety score (0–1)', fragment,
                  'Model cybersecurity safety/refusal evaluation, higher is better; distinct from capability success. Production Chat, Synthetic Agentic Envs and Semi-Synthetic Agentic Envs are separate protocols. Model refusal is one safety layer, not full production safeguard efficacy.',
                  limits=['No task denominators/attempt budgets stated in public table.', 'Do not rank capability scores against safety/refusal scores.'])
    return 'Literal cybersecurity capability and model-safety aggregates incorporated with exact protocol/scoring distinctions; risk classification remains nonnumeric context. Plot-only values, relative gains and expert-led case-study times retained as context. Repeated exact safety-table observations explicitly excluded.'
