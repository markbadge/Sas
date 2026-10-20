"""Property tests, hidden information, full stub-bot games, LLM bot plumbing and the HTTP API."""
import http.client
import json
import re
import threading
from http.server import ThreadingHTTPServer

import pytest

from ssengine import bots as B
from ssengine import views
from ssengine.engine import Game, RuleError
from ssengine.server import App, make_handler
from ssengine.session import Session


def play_all(seed, human_seat=None, check=None):
    """Run a game in-process. Every seat (incl. the 'human') is driven by StubBot from its VIEW."""
    g = Game.new(seed, human_seats=())
    stubs = [B.StubBot(seed * 10 + i) for i in range(6)]
    while g.s['phase'] != 'over':
        phase = g.s['phase']
        for seat in range(6):
            view = views.human_view(g, seat)
            if check:
                check(g, seat, view)
            raw = json.loads(stubs[seat].reply('', [], view))
            (g.submit_talk if phase == 'talk' else g.submit_act)(seat, raw)
    return g


@pytest.mark.parametrize('seed', range(1, 21))
def test_properties(seed):
    g = play_all(seed)
    s = g.s
    assert all(v >= 0 for h in s['hist'] for v in h)
    for r, lost in enumerate(s['lostr'], 1):
        assert max(lost) <= (7 if r == 7 else 5)
    assert all(len(f) <= 3 for f in s['fates'])
    assert all(sum(1 for n in f if g.family_of[n] == fam) <= 2 for f in s['fates'] for fam in ('LIGHT', 'SHADOW'))
    assert s['final']['winner'] in range(6)
    for r in s['final']['results']:
        assert r['bonus'] <= 8


def test_deterministic_from_seed():
    a, b = play_all(5), play_all(5)
    assert a.s['hist'] == b.s['hist'] and a.s['final'] == b.s['final']


def test_views_never_leak_other_seats():
    def check(g, seat, v):
        r = g.s['round']
        blob = json.dumps(v)
        exact_ok = g.s['phase'] == 'act' and r == 7 or g.s['phase'] == 'over'
        for x in v['seats']:
            if x['s'] != seat and not exact_ok:
                assert re.fullmatch(r'\d+-\d+', x['band']), x
        assert 'hands' not in blob and 'acts' not in blob
        for f in v['fates']:
            assert f['name'] in g.s['fates'][seat]
        for n in (views.bot_prompt(g, seat),):
            # a bot prompt may name other seats' bands but never their exact VP before round 7
            if not exact_ok:
                assert 'ALL EXACT VP' not in n
                m = re.search(r"Your VP: (\d+)\. Other players' VP \(bands of 5\): (.*?)\.", n)
                if m:
                    assert re.fullmatch(r'(S\d \d+-\d+(, )?)+', m.group(2))
        other_hands = [h for i, h in enumerate(g.s['hands'].get(str(r), [])) if i != seat]
        if g.s['phase'] == 'act' and other_hands:
            mine = {c['id'] for c in v['hand']}
            assert mine == set(g.s['hands'][str(r)][seat])
    play_all(11, check=check)


def test_phase_and_duplicate_submissions_rejected():
    g = Game.new(2, human_seats=())
    with pytest.raises(RuleError):
        g.submit_act(0, {})
    g.submit_talk(0, {'say': 'x'})
    with pytest.raises(RuleError):
        g.submit_talk(0, {'say': 'again'})


def test_act_normalisation_logged():
    g = Game.new(3, human_seats=())
    for i in range(6):
        g.submit_talk(i, {'say': 'x'})
    fixes = g.submit_act(0, {'play': 'c99', 'target': 0, 'stash': 'c99', 'accuse': {'seat': 1, 'fate': 'wolf'}, 'final_strike': 2})
    assert any('invalid play' in f for f in fixes) and any('invalid accuse' in f for f in fixes) and any('final_strike' in f for f in fixes)


def test_state_round_trips_through_json():
    g = play_all(4)
    g2 = Game(json.loads(json.dumps(g.s)))
    assert g2.finalize() == g.s['final']


def test_parse_json_repair():
    assert B.parse_json('```json\n{"a": 1,}\n```') == {'a': 1}
    assert B.parse_json('Here: {"say": "hi {x}"} done') == {'say': 'hi {x}'}
    assert B.parse_json('garbage') is None


class FakeClient:
    """Mimics anthropic.Anthropic().messages.create; alternates fenced JSON, prose-wrapped JSON and garbage."""
    def __init__(self):
        self.n = 0
        self.calls = []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        self.n += 1
        user = kw['messages'][-1]['content']
        if 'ACT' in user.split('\n')[0] and 'DEALT HAND' in user:
            m = re.search(r'YOUR DEALT HAND: (c\d\d)', user)
            text = json.dumps({'play': m.group(1), 'target': 1})
        else:
            text = json.dumps({'say': 'hello table'})
        if self.n % 5 == 0:
            text = 'I cannot decide.'
        elif self.n % 3 == 0:
            text = '```json\n' + text + '\n```'
        blk = type('B', (), {'type': 'text', 'text': text})
        return type('R', (), {'content': [blk]})


def test_llm_bots_with_fake_client_play_a_full_game_and_keep_history(tmp_path):
    fake = FakeClient()
    sess = Session.create(9, human_seats=(), bots='llm', store_dir=str(tmp_path), bot_factory=lambda seat, kind, model: B.LLMBot(client=fake), debrief=False)
    sess.start()
    assert sess.wait(lambda g: g.s['phase'] == 'over', timeout=60)
    assert any('unparseable' in e.get('error', '') for e in sess.botlog)          # fallback path was used and logged
    assert len(sess.hist['0']) == 2 * 14                                         # 7 talks + 7 acts, user+assistant each
    first = fake.calls[0]
    assert first['system'][0]['text'] == sess.g.rules.brief                      # brief verbatim as system prompt
    assert 'persona' in sess.hist['0'][0]['content']
    sess.close()


def test_session_persists_and_resumes(tmp_path):
    sess = Session.create(12, human_seats=(0,), bots='stub', store_dir=str(tmp_path), game_id='gx')
    sess.start()
    sess.wait(lambda g: str(1) in g.s['talks_in'] and len(g.s['talks_in']) == 5)
    sess.close()
    again = Session.load(str(tmp_path / 'gx.json'))
    again.start()
    again.submit_talk(0, {'say': 'back'})
    assert again.wait(lambda g: g.s['phase'] == 'act')
    again.close()


def test_view_refused_for_bot_seats(tmp_path):
    sess = Session.create(13, human_seats=(0,), bots='stub', store_dir=str(tmp_path))
    with pytest.raises(RuleError):
        sess.view(3)
    with pytest.raises(RuleError):
        sess.submit_talk(3, {'say': 'x'})
    sess.close()


@pytest.fixture
def server(tmp_path):
    app = App(str(tmp_path), bots='stub')
    srv = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(app))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv.server_address[1], app
    srv.shutdown()
    for s in app.sessions.values():
        s.close()


def call(port, method, path, body=None):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    c.request(method, path, json.dumps(body) if body is not None else None, {'Content-Type': 'application/json'})
    r = c.getresponse()
    return r.status, json.loads(r.read() or b'null')


def test_http_api_full_game_with_human(server):
    port, app = server
    st, j = call(port, 'POST', '/api/games', {'seat': 2, 'bots': 'stub', 'seed': 21})
    assert st == 200 and j['seat'] == 2
    gid = j['id']
    assert call(port, 'GET', f'/api/games/{gid}/view?seat=0')[0] == 400            # bot seat
    for _ in range(40):
        st, v = call(port, 'GET', f'/api/games/{gid}/view?seat=2')
        assert st == 200
        if v['stage'] == 'over':
            break
        if v.get('submitted'):
            app.get(gid).wait(lambda g: True, timeout=0.05)
            continue
        if v['stage'] == 'talk':
            assert call(port, 'POST', f'/api/games/{gid}/talk', {'seat': 2, 'say': 'hi'})[0] == 200
        else:
            c = v['hand'][0]
            body = {'seat': 2, 'play': c['id'], 'target': 3 if c['target'] else None}
            assert call(port, 'POST', f'/api/games/{gid}/act', body)[0] == 200
        app.get(gid).wait(lambda g: len(g.pending()) in (6, 1, 0) or g.s['phase'] == 'over', timeout=5)
    assert v['stage'] == 'over' and len(v['summary']['seats']) == 6
    assert call(port, 'GET', '/api/rules')[1]['version'] == 'v14'
    assert call(port, 'POST', f'/api/games/{gid}/talk', {'seat': 2, 'say': 'late'})[0] == 400
