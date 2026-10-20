"""HTTP server for the play client. JSON API + static page. A seat only ever receives its own view."""
import json
import os
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .engine import N, RuleError
from .rules import load_rules
from .session import Session

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')


class App:
    def __init__(self, store_dir, bots='llm', model=None, bot_factory=None):
        self.store_dir, self.bots, self.model, self.bot_factory = store_dir, bots, model, bot_factory
        self.sessions = {}
        self.lock = threading.Lock()
        os.makedirs(store_dir, exist_ok=True)
        for fn in sorted(os.listdir(store_dir)):
            if fn.endswith('.json'):
                try:
                    s = Session.load(os.path.join(store_dir, fn), bot_factory=bot_factory, store_dir=store_dir)
                    self.sessions[s.g.s['game_id']] = s
                    s.start()
                except Exception:
                    pass

    def create(self, body):
        seat = body.get('seat', 0)
        if not isinstance(seat, int) or not 0 <= seat < N:
            raise RuleError('bad seat')
        seed = body.get('seed')
        seed = seed if isinstance(seed, int) else secrets.randbelow(10 ** 6)
        bots = body.get('bots', self.bots)
        if bots not in ('llm', 'stub'):
            raise RuleError('bots must be llm or stub')
        gid = f"g{seed}-{secrets.token_hex(2)}"
        sess = Session.create(seed, human_seats=(seat,), bots=bots, model=body.get('model') or self.model, store_dir=self.store_dir,
                              bot_factory=self.bot_factory, game_id=gid, rules_version=body.get('rules', 'v14'))
        with self.lock:
            self.sessions[gid] = sess
        sess.start()
        return dict(id=gid, seat=seat)

    def get(self, gid):
        s = self.sessions.get(gid)
        if not s:
            raise KeyError(gid)
        return s


def make_handler(app):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, obj, ctype='application/json'):
            body = obj if isinstance(obj, bytes) else (json.dumps(obj).encode() if ctype == 'application/json' else str(obj).encode())
            self.send_response(code)
            self.send_header('Content-Type', ctype + ('; charset=utf-8' if ctype.startswith('text') else ''))
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def _body(self):
            n = int(self.headers.get('Content-Length') or 0)
            if n > 100_000:
                raise RuleError('body too large')
            return json.loads(self.rfile.read(n) or b'{}')

        def _route(self, method):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            parts = [p for p in u.path.split('/') if p]
            if method == 'GET' and (not parts or parts == ['index.html']):
                return self._send(200, open(os.path.join(STATIC, 'table.html'), 'rb').read(), 'text/html')
            if parts[:1] != ['api']:
                return self._send(404, dict(error='not found'))
            parts = parts[1:]
            if method == 'GET' and parts == ['rules']:
                r = load_rules(q.get('version', 'v14'))
                return self._send(200, dict(version=r.version, brief=r.brief, cards=r.cards, fates=r.fates, pairs=r.pairs))
            if method == 'POST' and parts == ['games']:
                return self._send(200, app.create(self._body()))
            if method == 'GET' and parts == ['games']:
                return self._send(200, [dict(id=k, round=s.g.s['round'], phase=s.g.s['phase'], seats=s.g.s['human_seats']) for k, s in app.sessions.items()])
            if len(parts) == 3 and parts[0] == 'games':
                sess = app.get(parts[1])
                if method == 'GET' and parts[2] == 'view':
                    return self._send(200, sess.view(int(q.get('seat', 0))))
                if method == 'POST' and parts[2] in ('talk', 'act'):
                    b = self._body()
                    seat = b.get('seat')
                    if not isinstance(seat, int):
                        raise RuleError('seat required')
                    if parts[2] == 'talk':
                        sess.submit_talk(seat, b)
                        return self._send(200, dict(ok=True))
                    return self._send(200, dict(ok=True, fixes=sess.submit_act(seat, b)))
            return self._send(404, dict(error='not found'))

        def _guard(self, method):
            try:
                self._route(method)
            except RuleError as e:
                self._send(400, dict(error=str(e)))
            except KeyError:
                self._send(404, dict(error='unknown game'))
            except (ValueError, TypeError) as e:
                self._send(400, dict(error=f'bad request: {e}'))

        def do_GET(self):
            self._guard('GET')

        def do_POST(self):
            self._guard('POST')
    return H


def run(host, port, store, bots, model):
    app = App(store, bots, model)
    srv = ThreadingHTTPServer((host, port), make_handler(app))
    print(f'Saints and Sinners: http://{host}:{port}/  (bots={bots}, saves in {store}/)')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
