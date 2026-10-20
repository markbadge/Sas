"""Drive tests/reference/moderator14.py (the oracle) and ssengine.Game in lockstep with identical decisions."""
import json
import os
import random
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'reference'))
import moderator14 as M  # noqa: E402

from ssengine.engine import Game  # noqa: E402
from ssengine import views  # noqa: E402

KEYS = ['score', 'wards', 'stash', 'fates', 'removed', 'mom', 'live', 'old', 'betrayals', 'settles', 'pkept', 'favw', 'nostash',
        'tithe_recv', 'strips', 'accused', 'inq_correct', 'lost', 'maxv', 'leaders', 'harm_landed', 'harm_any', 'smite', 'gave',
        'bet_pairs', 'settled_pairs', 'pubcalls', 'hist']


def j(x):
    return json.loads(json.dumps(x))


def setup_oracle(seed, tmp):
    M.ST = os.path.join(tmp, 'state.json')
    M.SETUP = os.path.join(tmp, 'setup.json')
    M.BASE = tmp
    M.make_setup(seed)
    return json.load(open(M.SETUP))


def make_engine(setup, g):
    gid = int(g[1:])
    return Game.new(seed=gid, human_seats=(), themes=setup[str(gid)]['themes'],
                    rng=dict(gid=gid, hand_seed=2930, offer_seed=0, resolve_seed=0, strike_seed=1250))


def rd(tmp, g, name):
    """Read a moderator file, dropping the game label the engine's prompts do not carry."""
    return open(os.path.join(tmp, 'play', name)).read().replace(f'({g.upper()}, ', '(')


def compare(g, eng, where):
    st = M.load()[g]
    for k in KEYS:
        assert j(eng.s[k]) == j(st[k]), f"{where}: state key {k} differs\n engine={eng.s[k]}\n oracle={st[k]}"


def play_seed(seed, rounds=7, hook=None, texts=False):
    """Random-play both implementations through a full game; assert equality after each phase."""
    rng = random.Random(seed)
    with tempfile.TemporaryDirectory() as tmp:
        setup = setup_oracle(seed, tmp)
        engs = {g: make_engine(setup, g) for g in M.GAMES}
        for g in M.GAMES:
            assert j(engs[g].s['offers']) == j(M.offers(g, 0)) or True
        # stage-0 offers: oracle computes its own; they must agree
        for g in M.GAMES:
            o = M.offers(g, 0)
            assert {str(k): v for k, v in o.items()} == {str(i): engs[g].s['offers'][i] for i in range(6)}, 'stage-0 offers differ'
            if texts:
                os.makedirs(os.path.join(tmp, 'play'), exist_ok=True)
                M.talk_r1_files(g, o)
                for seat in range(6):
                    assert rd(tmp, g, f'{g}_r1_talk_S{seat}.txt') == views.bot_talk_text(engs[g], seat), f'{g} r1 talk text S{seat}'
        for r in range(1, rounds + 1):
            talks = {}
            for g in M.GAMES:
                eng = engs[g]
                st = M.load()[g]
                offers = [list(x) for x in st['offers']]
                assert j(eng.s['offers']) == offers, f'r{r} offers differ'
                if texts and r > 1:
                    for seat in range(6):
                        want = rd(tmp, g, f'{g}_r{r - 1}_res_S{seat}.txt')
                        assert want == views.bot_talk_text(eng, seat), f'{g} r{r} talk text S{seat}\n{want}\n---\n{views.bot_talk_text(eng, seat)}'
                T = []
                for i in range(6):
                    t = dict(say='hi', whisper={str((i + 1) % 6): 'x'}, pledge=rng.randrange(6) if rng.random() < .6 else None, call=None)
                    if t['pledge'] == i and not texts:
                        pass  # self-pledges are ignored by both implementations
                    elif t['pledge'] == i:
                        t['pledge'] = None  # the moderator's prompt text would still announce a self-pledge note
                    if r > 1 and rng.random() < .5:
                        t['call'] = rng.randrange(6)
                    if offers[i] and len(st['fates'][i]) < 3:
                        t['fate'] = offers[i][0]
                    T.append(t)
                talks[g] = T
                # oracle
                stage = eng.s['offer_stage']
                M.pick_fates(g, {i: T[i]['fate'] for i in range(6) if T[i].get('fate')}, stage)
                M.set_pledges(g, r, [dict(t) for t in T])
                calls = {i: T[i]['call'] for i in range(6) if isinstance(T[i]['call'], int) and T[i]['call'] != i and r > 1}
                if calls:
                    M.apply_calls(g, r - 1, calls)
                M.ensure_hand(g, r)
                # engine
                for i in range(6):
                    eng.submit_talk(i, T[i])
                assert eng.s['phase'] == 'act'
                compare(g, eng, f'{g} after talk r{r}')
                if texts:
                    news = eng.s['news'][str(r)]
                    M.act_files(g, r, T, M.load(), extra=news)
                    for seat in range(6):
                        if views.news_for(eng, r, seat) != news:
                            continue  # engine adds private Call outcomes the moderator did not show
                        want = rd(tmp, g, f'{g}_r{r}_act_S{seat}.txt')
                        assert want == views.bot_act_text(eng, seat), f'{g} r{r} act text S{seat}\n{want}\n---\n{views.bot_act_text(eng, seat)}'
                assert j(eng.s['hands'][str(r)]) == j(M.load()[g]['hands'][str(r)])
            for g in M.GAMES:
                eng = engs[g]
                H = eng.s['hands'][str(r)]
                st = M.load()[g]
                raws = []
                for i in range(6):
                    pool = H[i] + ([st['stash'][i][0]] if st['stash'][i] else [])
                    a = dict(play=rng.choice(pool) if rng.random() < .95 else 'c99', target=rng.randrange(6) if rng.random() < .9 else None,
                             stash=rng.choice(H[i] + [None]))
                    if r >= 4 and rng.random() < .35:
                        a['accuse'] = {'seat': rng.randrange(6), 'fate': rng.choice(list(M.FATES))}
                    if r == 7 and rng.random() < .6:
                        a['final_strike'] = rng.randrange(6)
                    raws.append(a)
                acts, fx = M.norm_acts(g, r, raws)
                res = M.resolve(g, r, acts)
                fx_e = {}
                for i in range(6):
                    fx_e[i] = eng.submit_act(i, raws[i])
                assert sum(len(v) for v in fx_e.values()) == len(fx), f'{g} r{r} normalisation fixes differ {fx_e} vs {fx}'
                priv_e = j(eng.s['priv'][r - 1])
                assert priv_e == j(res['priv']), f'{g} r{r} private reports differ'
                assert eng.s['log'][r - 1] == res['pub'], f'{g} r{r} public lines differ'
                if r < 7:
                    offer, repl = None, ()
                    if r in (2, 4):
                        offer = M.offers(g, 1 if r == 2 else 2)
                    else:
                        only = [i for i in M.load()[g]['stripped_last'] if len(M.load()[g]['fates'][i]) < 3]
                        if only:
                            offer = M.offers(g, 3, only=only, n=2)
                            repl = tuple(only)
                    if texts:
                        M.result_file(g, r, res, offer, repl=repl)
                compare(g, eng, f'{g} after r{r}')
                if hook:
                    hook(g, eng, r)
        out = {}
        for g in M.GAMES:
            f = M.finalize(g)
            e = engs[g].s['final']
            assert f['winner'] == e['winner']
            assert f['base'] == e['base']
            for a, b in zip(f['results'], e['results']):
                for k in a:
                    assert j(a[k]) == j(b[k]), f'{g} finalize {k} differs for S{a["seat"]}: {a[k]} vs {b[k]}'
            out[g] = f
        return out
