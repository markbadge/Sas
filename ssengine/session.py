"""A running game: engine + bot seats + persistence. Humans submit via submit_*; bots run in parallel threads.

Hidden information: `view(seat)` only works for human seats while the game is live.
"""
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import bots as B
from . import views
from .engine import N, Game, RuleError


class Session:
    def __init__(self, game, bot_kinds, bot_models=None, bot_factory=None, store_dir=None, debrief=True, max_workers=6):
        self.g = game
        self.lock = threading.RLock()
        self.store_dir = store_dir
        self.debrief_on = debrief
        self.bot_kinds = bot_kinds                      # {seat: 'llm'|'stub'}
        self.bot_models = bot_models or {}
        self.bot_factory = bot_factory or self._default_factory
        self.bots = {}
        self.hist = {str(i): [] for i in range(N)}      # per-seat conversation history (bots only)
        self.botlog = []                                # parse failures, fallbacks, errors
        self.debriefs = {}
        self.personas = {str(i): B.persona_for(i, game.s['seed']) for i in range(N)}
        self.inflight = set()
        self.pool = ThreadPoolExecutor(max_workers=max_workers)
        self.closed = False
        self.idle = threading.Condition(self.lock)

    # ------------------------------------------------------------ construction
    @classmethod
    def create(cls, seed, human_seats=(0,), bots='llm', model=None, rules_version='v14', store_dir=None, bot_factory=None, debrief=True, game_id=None):
        game = Game.new(seed, human_seats=human_seats, rules_version=rules_version, game_id=game_id)
        kinds = {i: bots for i in range(N) if i not in human_seats}
        models = {i: model for i in kinds} if model else {}
        sess = cls(game, kinds, models, bot_factory=bot_factory, store_dir=store_dir, debrief=debrief)
        sess.save()
        return sess

    def _default_factory(self, seat, kind, model):
        if kind == 'stub':
            return B.StubBot(seed=self.g.s['seed'] * 10 + seat)
        return B.LLMBot(model=model)

    def bot(self, seat):
        if seat not in self.bots:
            self.bots[seat] = self.bot_factory(seat, self.bot_kinds[seat], self.bot_models.get(seat))
        return self.bots[seat]

    # ------------------------------------------------------------- persistence
    def path(self):
        return os.path.join(self.store_dir, f"{self.g.s['game_id']}.json") if self.store_dir else None

    def save(self):
        p = self.path()
        if not p:
            return
        os.makedirs(self.store_dir, exist_ok=True)
        blob = dict(game=self.g.s, bot_kinds={str(k): v for k, v in self.bot_kinds.items()},
                    bot_models={str(k): v for k, v in self.bot_models.items()}, hist=self.hist, botlog=self.botlog,
                    debriefs=self.debriefs, personas=self.personas, debrief_on=self.debrief_on)
        tmp = p + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(blob, f)
        os.replace(tmp, p)

    @classmethod
    def load(cls, path, bot_factory=None, store_dir=None):
        blob = json.load(open(path))
        sess = cls(Game(blob['game']), {int(k): v for k, v in blob['bot_kinds'].items()}, {int(k): v for k, v in blob['bot_models'].items()},
                   bot_factory=bot_factory, store_dir=store_dir or os.path.dirname(path), debrief=blob.get('debrief_on', True))
        sess.hist, sess.botlog, sess.debriefs, sess.personas = blob['hist'], blob['botlog'], blob['debriefs'], blob['personas']
        return sess

    # ------------------------------------------------------------ human access
    def is_human(self, seat):
        return seat in self.g.s['human_seats']

    def view(self, seat):
        with self.lock:
            if not self.is_human(seat):
                raise RuleError('no view for a bot seat')
            v = views.human_view(self.g, seat)
            v['bots_running'] = len(self.inflight)
            return v

    def submit_talk(self, seat, raw):
        with self.lock:
            if not self.is_human(seat):
                raise RuleError('not a human seat')
            self.g.submit_talk(seat, raw)
            self._after_change()

    def submit_act(self, seat, raw):
        with self.lock:
            if not self.is_human(seat):
                raise RuleError('not a human seat')
            fixes = self.g.submit_act(seat, raw)
            self._after_change()
            return fixes

    # -------------------------------------------------------------- bot driver
    def start(self):
        with self.lock:
            self._after_change(save=False)

    def _after_change(self, save=True):
        if save:
            self.save()
        with self.idle:
            self.idle.notify_all()
        g = self.g
        phase = g.s['phase']
        if phase == 'over':
            if self.debrief_on and not self.debriefs:
                self._launch(('debrief', 0, -1), None)
            return
        for seat in g.pending():
            if seat in self.bot_kinds:
                self._launch((phase, g.s['round'], seat), seat)

    def _launch(self, key, seat):
        if key in self.inflight or self.closed:
            return
        self.inflight.add(key)
        self.pool.submit(self._job, key, seat)

    def _job(self, key, seat):
        phase, rnd, _ = key
        try:
            if phase == 'debrief':
                self._run_debrief()
            else:
                self._run_turn(phase, rnd, seat)
        except Exception as e:  # never let a bot thread die silently
            with self.lock:
                self.botlog.append(dict(round=rnd, phase=phase, seat=seat, error=repr(e)))
        finally:
            with self.idle:
                self.inflight.discard(key)
                self.idle.notify_all()

    def _build(self, seat):
        """Prompt, structured view (stub only) and messages so far, built under the lock."""
        g = self.g
        prompt = views.bot_prompt(g, seat)
        if not self.hist[str(seat)]:
            prompt = B.persona_note(self.personas[str(seat)]) + prompt
        return prompt, views.human_view(g, seat)

    def _run_turn(self, phase, rnd, seat):
        with self.lock:
            g = self.g
            if g.s['phase'] != phase or g.s['round'] != rnd or str(seat) in g.s['talks_in' if phase == 'talk' else 'acts_in']:
                return
            prompt, view = self._build(seat)
            messages = list(self.hist[str(seat)]) + [dict(role='user', content=prompt)]
        bot = self.bot(seat)
        raw, err = None, None
        try:
            raw = bot.reply(g.rules.brief, messages, view)
        except Exception as e:
            err = repr(e)
        parsed = B.parse_json(raw) if raw is not None else None
        with self.lock:
            g = self.g
            if g.s['phase'] != phase or g.s['round'] != rnd:
                return
            if parsed is None:
                self.botlog.append(dict(round=rnd, phase=phase, seat=seat, error=err or 'unparseable reply', raw=(raw or '')[:500]))
                parsed = {'say': '...'} if phase == 'talk' else {}
            self.hist[str(seat)] += [dict(role='user', content=prompt), dict(role='assistant', content=raw if raw else json.dumps(parsed))]
            try:
                if phase == 'talk':
                    g.submit_talk(seat, parsed)
                else:
                    fixes = g.submit_act(seat, parsed)
                    if fixes:
                        self.botlog.append(dict(round=rnd, phase=phase, seat=seat, fixes=fixes))
            except RuleError as e:
                self.botlog.append(dict(round=rnd, phase=phase, seat=seat, error=str(e)))
                return
            self._after_change()

    def _run_debrief(self):
        with self.lock:
            f = self.g.s['final']
            result = "; ".join(f"S{r['seat']} base {r['base']} + Fates {r['bonus']} = {r['final']} (held {','.join(r['held']) or 'none'}; met {','.join(r['hits']) or 'none'})" for r in f['results']) + f". Winner: S{f['winner']}."
            todo = [i for i in self.bot_kinds if self.bot_kinds[i] != 'stub']
            prompt = B.DEBRIEF_PROMPT.format(result=result)
        for seat in todo:
            with self.lock:
                msgs = list(self.hist[str(seat)]) + [dict(role='user', content=prompt)]
            try:
                raw = self.bot(seat).reply(self.g.rules.brief, msgs, None)
            except Exception as e:
                raw = None
                with self.lock:
                    self.botlog.append(dict(phase='debrief', seat=seat, error=repr(e)))
            with self.lock:
                self.debriefs[str(seat)] = B.parse_json(raw) or {'raw': raw}
        with self.lock:
            self.debriefs.setdefault('done', True)
            self.save()

    # ------------------------------------------------------------------- waits
    def wait(self, pred, timeout=60.0):
        """Block until pred(game) is true or timeout. Used by tests and the CLI."""
        end = time.time() + timeout
        with self.idle:
            while not pred(self.g):
                left = end - time.time()
                if left <= 0:
                    return False
                self.idle.wait(min(left, 0.5))
        return True

    def close(self):
        self.closed = True
        self.pool.shutdown(wait=False, cancel_futures=True)
