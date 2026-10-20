"""Saints and Sinners engine (rules v14, data-driven by ssengine/rules/<version>).

Game state is one JSON-serialisable dict (`Game.s`); the engine does no file or network I/O.
Resolution logic is a port of moderator14.resolve and must match it (tests/test_oracle.py).

Pipeline per round r:  talk (submit_talk x6) -> act (submit_act x6) -> resolve -> offers -> next talk.
"""
import copy
import random

from .rules import load_rules

N = 6
TYPLAB = {'TARGETED': 'targeted', 'NEIGHBOUR': 'neighbour', 'AREA': 'area', 'FINAL': 'Final Strike'}


class RuleError(Exception):
    pass


def band(v):
    lo = 5 * (v // 5)
    return f"{lo}-{lo + 4}"


class Game:
    def __init__(self, state, rules=None):
        self.s = state
        self.rules = rules or load_rules(state['rules_version'])
        self.cfg = self.rules.cfg
        self.card = self.rules.card
        self.fates = self.rules.fates
        self.family_of = self.rules.family_of

    # ------------------------------------------------------------------ setup
    @classmethod
    def new(cls, seed, human_seats=(0,), rules_version='v14', themes=None, rng=None, game_id=None):
        rules = load_rules(rules_version)
        cfg = rules.cfg
        if themes is None:
            themes = list(range(len(rules.pairs)))
            random.Random(seed).shuffle(themes)
        rng_cfg = dict(gid=seed % 10, hand_seed=seed, offer_seed=seed, resolve_seed=seed, strike_seed=1250 + seed * 10)
        rng_cfg.update(rng or {})
        s = dict(
            rules_version=rules_version, game_id=game_id or f"g{seed}", seed=seed, rng=rng_cfg, themes=themes,
            human_seats=list(human_seats), phase='talk', round=1, hands={}, talks_in={}, acts_in={}, talks={}, news={},
            fixes={}, offer_stage=0, offer_repl=[], final=None, call_notes={},
            score=[cfg['start_vp']] * N, wards=[0] * N, lost=[0] * N, lostr=[], rounds=[], hist=[], log=[], leaders=[],
            stash=[None] * N, fates=[[] for _ in range(N)], offers=[[] for _ in range(N)], removed=[[] for _ in range(N)],
            gave=[], live=[], old=[], settled_pairs=[], settles=[0] * N, bet_pairs=[], bet_log=[],
            harm_landed=[], harm_any=[], smite=[], betrayals=[0] * N, inq_correct=[0] * N, accused=[0] * N,
            mom=[[None, 0] for _ in range(N)], maxv=[0] * N, acts=[], priv=[], pubcalls=[], pledges={},
            settle_rounds={}, stripped_last=[], pkept=[0] * N, strips=[0] * N, nostash=[0] * N, favw=[0] * N,
            tithe_recv=[0] * N, tithe_log=[])
        g = cls(s, rules)
        g.offers(0)
        return g

    # ------------------------------------------------------------ small helpers
    def harmful(self, c):
        return self.rules.harmful(c)

    def theme(self, r):
        return self.s['themes'][r - 1]

    def theme_names(self, r):
        sin, virtue = self.rules.pairs[self.theme(r)]
        return dict(sin=sin, virtue=virtue, label=f"{sin}/{virtue}")

    def haloed(self, i):
        m = self.s['mom'][i]
        return m[0] == 'virtue' and m[1] >= 2

    def hot(self, i):
        m = self.s['mom'][i]
        return m[0] == 'sin' and m[1] >= 2

    def loss_cap(self, r):
        return self.cfg['loss_cap_final'] if r == self.cfg['rounds'] else self.cfg['loss_cap']

    def strike_start(self):
        rg = self.s['rng']
        return random.Random(rg['strike_seed'] + rg['gid']).randrange(N)

    def families(self, i):
        return sorted({self.family_of[n] for n in self.s['fates'][i]})

    def rank_of(self, seat):
        s = self.s
        virt = [sum(1 for p in s['rounds'] if self.card[p[i][0]]['kind'] == 'virtue') for i in range(N)]
        order = sorted(range(N), key=lambda i: (-s['score'][i], -virt[i], i))
        return order.index(seat) + 1

    # ----------------------------------------------------------------- dealing
    def deal_hand(self, rng, th, exclude=None, need_sin=False):
        cards = self.rules.cards
        pool = [c['id'] for c in cards if c['id'] != exclude]
        while True:
            tc = rng.choice([c['id'] for c in cards if c['pair'] == th and c['id'] != exclude])
            h = [tc] + rng.sample([c for c in pool if c != tc], 2)
            cs = [self.card[x] for x in h]
            if need_sin and not any(c['kind'] == 'sin' and c['needs_target'] and self.harmful(c) for c in cs):
                continue
            if any(c['kind'] == 'virtue' for c in cs) and any(c['kind'] == 'sin' for c in cs) and any(c['needs_target'] for c in cs):
                rng.shuffle(h)
                return h

    def ensure_hand(self, r):
        s = self.s
        if str(r) not in s['hands']:
            rg = s['rng']
            rng = random.Random(rg['hand_seed'] * 1000 + r * 10 + rg['gid'])
            lo, hi = self.cfg['hand_guarantee_rounds']
            s['hands'][str(r)] = [
                self.deal_hand(rng, self.theme(r), s['stash'][i][0] if s['stash'][i] else None,
                               need_sin=(lo <= r <= hi and any(f[2] == i and r - f[0] <= self.cfg['favour']['live_rounds'] and f[0] < r for f in s['live'])))
                for i in range(N)]
        return s['hands'][str(r)]

    def legal_pledge_card(self, r, seat):
        s = self.s
        ids = list(self.ensure_hand(r)[seat]) + ([s['stash'][seat][0]] if s['stash'][seat] else [])
        return any(self.card[x]['kind'] == 'virtue' and self.card[x]['needs_target'] and (self.card[x]['target'] > 0 or self.card[x]['ward_target']) for x in ids)

    def stash_bonus(self, r, seat):
        st = self.s['stash'][seat]
        return min(self.cfg['stash_bonus_max'], max(0, r - st[1] - 1)) if st else 0

    # ------------------------------------------------------------------- fates
    def _fate_ok(self, seat, stage):
        """Feasibility of every Fate for `seat` (ported from moderator14.offers; thresholds from data params)."""
        s = self.s
        P = {n: f['params'] for n, f in self.fates.items()}
        rounds = s['rounds']
        k = len(rounds)
        rem = self.cfg['rounds'] - k
        kinds = [self.card[p[seat][0]]['kind'] for p in rounds]
        ev_ = kinds[:4].count('virtue')
        es = kinds[:4].count('sin')
        hm = sum(1 for p in rounds if self.harmful(self.card[p[seat][0]]))
        gl = sum(1 for p in rounds if self.card[p[seat][0]]['kind'] == 'sin')
        hv = len({v for r_, a, v, amt in s['harm_landed'] if a == seat})
        sm = len({r for r, a, v in s['smite'] if a == seat})
        return {
            'saint': kinds.count('virtue') + rem >= P['saint']['virtue_rounds'],
            'peacemaker': hm == 0 and rem >= 2,
            'heretic': sm + rem >= P['heretic']['rounds'],
            'wolf': hv + rem >= P['wolf']['victims'],
            'glutton': gl + rem >= P['glutton']['sin_rounds'],
            'backstabber': s['betrayals'][seat] < P['backstabber']['betrayals'] and rem >= 1,
            'fallen': ev_ + max(0, 4 - k) >= P['fallen']['early_virtues'],
            'redeemed': es + max(0, 4 - k) >= P['redeemed']['early_sins'],
            'inquisitor': not s['accused'][seat],
            'bulwark': True,
            'late_bloomer': stage > 0 and self.rank_of(seat) >= 3 and rem >= 3,
            'survivor': stage > 0 and self.rank_of(seat) >= 4 and rem >= 3,
        }

    def offers(self, stage, only=None, n=None):
        """stage 0 = start, 1/2 = scheduled, 3 = replacement after a strip. Stores and returns {seat: [names]}."""
        s = self.s
        n = n or self.cfg['fate']['offer_size']
        rg = s['rng']
        rng = random.Random(rg['offer_seed'] + stage * 101 + rg['gid'] * 7 + len(s['rounds']))
        out = {}
        maxfam = self.cfg['fate']['max_per_family']
        for seat in (range(N) if only is None else only):
            held = set(s['fates'][seat]) | set(s['removed'][seat])
            ok = self._fate_ok(seat, stage)
            fam_n = {}
            for h_ in s['fates'][seat]:
                fam_n[self.family_of[h_]] = fam_n.get(self.family_of[h_], 0) + 1
            pool = [x for x in self.fates if ok[x] and x not in held and fam_n.get(self.family_of[x], 0) < maxfam]
            pick = []
            ag = [x for x in pool if x in self.rules.aggressive]
            if ag:
                pick.append(rng.choice(ag))
            rest0 = [x for x in pool if self.family_of[x] == 'LIGHT' and x not in pick]
            if rest0:
                pick.append(rng.choice(rest0))
            rest = [x for x in pool if x not in pick]
            rng.shuffle(rest)
            pick += rest[:n - len(pick)]
            if len(pick) < n:
                extra = [x for x in self.fates if x not in held and x not in pick and x not in ('late_bloomer', 'survivor') and fam_n.get(self.family_of[x], 0) < maxfam]
                rng.shuffle(extra)
                pick += extra[:n - len(pick)]
            pick = pick[:n]
            rng.shuffle(pick)
            out[seat] = pick
            s['offers'][seat] = pick
        return out

    def pick_fates(self, picks, stage):
        s = self.s
        maxfam = self.cfg['fate']['max_per_family']
        for seat, name in picks.items():
            seat = int(seat)
            fam_n = sum(1 for h_ in s['fates'][seat] if name in self.family_of and self.family_of[h_] == self.family_of[name])
            if name in s['offers'][seat] and len(s['fates'][seat]) < self.cfg['fate']['max_held'] and name not in s['fates'][seat] and fam_n < maxfam:
                s['fates'][seat].append(name)
                if name == 'bulwark' and stage == 1:
                    s['wards'][seat] += 1
        s['offers'] = [[] for _ in range(N)]

    def offer_for(self, seat):
        """Offer the seat may pick from right now (empty if holding the max)."""
        s = self.s
        if len(s['fates'][seat]) >= self.cfg['fate']['max_held']:
            return []
        return list(s['offers'][seat])

    # -------------------------------------------------------------- submissions
    def _need(self, phase):
        if self.s['phase'] != phase:
            raise RuleError(f"game is in phase '{self.s['phase']}', not '{phase}'")

    @staticmethod
    def _seat_ok(x, me=None):
        return isinstance(x, int) and not isinstance(x, bool) and 0 <= x < N and x != me

    def submit_talk(self, seat, raw):
        self._need('talk')
        s = self.s
        if not isinstance(seat, int) or not 0 <= seat < N:
            raise RuleError('bad seat')
        if str(seat) in s['talks_in']:
            raise RuleError(f'S{seat} already submitted talk for round {s["round"]}')
        L = self.cfg['limits']
        raw = raw if isinstance(raw, dict) else {}
        say = raw.get('say')
        say = (say if isinstance(say, str) and say.strip() else '...').strip()[:L['say']]
        wh = {}
        if isinstance(raw.get('whisper'), dict):
            for k, v in raw['whisper'].items():
                try:
                    k = int(k)
                except (TypeError, ValueError):
                    continue
                if self._seat_ok(k, seat) and isinstance(v, str) and v.strip() and len(wh) < L['whispers']:
                    wh[str(k)] = v.strip()[:L['whisper_chars']]
        call = raw.get('call') if self._seat_ok(raw.get('call'), seat) and s['round'] > 1 else None
        pledge = raw.get('pledge') if self._seat_ok(raw.get('pledge'), seat) else None
        fate = raw.get('fate') if isinstance(raw.get('fate'), str) else None
        note = raw.get('note') if isinstance(raw.get('note'), str) else None
        s['talks_in'][str(seat)] = dict(say=say, whisper=wh, call=call, pledge=pledge, fate=fate, note=(note or '')[:L['note']])
        if len(s['talks_in']) == N:
            self._close_talk()

    def submit_act(self, seat, raw):
        """Returns the list of corrections made to this seat's choice (empty if none)."""
        self._need('act')
        s = self.s
        if not isinstance(seat, int) or not 0 <= seat < N:
            raise RuleError('bad seat')
        if str(seat) in s['acts_in']:
            raise RuleError(f'S{seat} already submitted act for round {s["round"]}')
        act, fixes = self.norm_act(s['round'], seat, raw)
        s['acts_in'][str(seat)] = act
        s['fixes'].setdefault(str(s['round']), {})[str(seat)] = fixes
        if len(s['acts_in']) == N:
            self._close_act()
        return fixes

    def pending(self):
        key = 'talks_in' if self.s['phase'] == 'talk' else 'acts_in' if self.s['phase'] == 'act' else None
        return [] if key is None else [i for i in range(N) if str(i) not in self.s[key]]

    # --------------------------------------------------------------- phases
    def _close_talk(self):
        s = self.s
        r = s['round']
        talks = [s['talks_in'][str(i)] for i in range(N)]
        self.pick_fates({i: t['fate'] for i, t in enumerate(talks) if t['fate']}, s['offer_stage'])
        s['offer_repl'] = []
        self.set_pledges(r, talks)
        news = ''
        s['call_notes'] = {}
        if r > 1:
            calls = {i: t['call'] for i, t in enumerate(talks) if isinstance(t['call'], int)}
            if calls:
                lines = self.apply_calls(r - 1, calls)
                for c, line in lines.items():
                    if 'INVALID' in line:
                        s['call_notes'][str(c)] = line
            ls = '; '.join(f"S{c} Called S{n}: {'YES' if h else 'NO'}" for rr, c, n, h in s['pubcalls'] if rr == r - 1)
            news = f'PUBLIC CALLS after round {r - 1}: {ls}.' if ls else ''
        s['news'][str(r)] = news
        s['talks'][str(r)] = [dict(say=t['say'], whisper=t['whisper'], pledge=t['pledge']) for t in talks]
        self.ensure_hand(r)
        s['phase'] = 'act'
        s['talks_in'] = {}
        s['acts_in'] = {}

    def _close_act(self):
        s = self.s
        r = s['round']
        acts = [s['acts_in'][str(i)] for i in range(N)]
        self.resolve(r, acts)
        s['acts_in'] = {}
        if r == self.cfg['rounds']:
            s['final'] = self.finalize()
            s['phase'] = 'over'
            return
        fo = self.cfg['fate']['offer_after_rounds']
        if str(r) in fo:
            self.offers(fo[str(r)])
            s['offer_stage'] = fo[str(r)]
        else:
            only = [i for i in s['stripped_last'] if len(s['fates'][i]) < self.cfg['fate']['max_held']]
            if only:
                self.offers(3, only=only, n=self.cfg['fate']['replacement_size'])
                s['offer_repl'] = only
                s['offer_stage'] = 3
        s['round'] = r + 1
        s['phase'] = 'talk'
        s['talks_in'] = {}

    # ---------------------------------------------------------- normalisation
    def norm_act(self, r, seat, raw):
        s = self.s
        H = self.ensure_hand(r)
        fixes = []
        a = dict(raw) if isinstance(raw, dict) else {}
        stc = s['stash'][seat][0] if s['stash'][seat] else None
        allowed = H[seat] + ([stc] if stc else [])
        if a.get('play') not in allowed:
            fixes.append(f"invalid play {a.get('play')} -> {H[seat][0]}")
            a['play'] = H[seat][0]
        c = self.card[a['play']]
        t = a.get('target')
        if c['needs_target']:
            if not self._seat_ok(t, seat):
                fixes.append(f"bad target {t} -> {(seat + 1) % N}")
                t = (seat + 1) % N
        else:
            t = None
        a['target'] = t
        rv = a.get('stash', a.get('reserve'))
        if rv is not None and (rv not in H[seat] or rv == a['play']):
            fixes.append(f"invalid stash {rv} dropped")
            rv = None
        a['reserve'] = rv
        ac = a.get('accuse')
        if ac:
            if r < self.cfg['accusation']['first_round'] or s['accused'][seat] or not isinstance(ac, dict) or not self._seat_ok(ac.get('seat'), seat):
                fixes.append("invalid accuse dropped")
                ac = None
        a['accuse'] = ac or None
        fs = a.get('final_strike')
        if fs is not None and (r != self.cfg['rounds'] or not self._seat_ok(fs, seat)):
            fixes.append("invalid final_strike dropped")
            fs = None
        a['final_strike'] = fs
        out = dict(play=a['play'], target=a['target'], reserve=a['reserve'], accuse=a['accuse'], final_strike=a['final_strike'],
                   note=(a.get('note') if isinstance(a.get('note'), str) else '')[:self.cfg['limits']['note']])
        return out, fixes

    def set_pledges(self, r, talks):
        out = {}
        for i in range(N):
            p = talks[i].get('pledge')
            if self._seat_ok(p, i):
                out[str(i)] = p
        self.s['pledges'][str(r)] = out
        return out

    # ------------------------------------------------------------------- calls
    def apply_calls(self, r, calls):
        """Calls made in the talk after round r. Returns {caller: line}."""
        s = self.s
        C = self.cfg['call']
        lines = {}
        valid = []
        for caller, named in sorted(calls.items()):
            caller = int(caller)
            if not self._seat_ok(named, caller):
                continue
            stake = C['stake']
            if s['score'][caller] < stake:
                continue
            got_targeted = any(rr == r and v == caller for rr, a, v, amt in s['harm_landed'])
            if not got_targeted:
                lines[caller] = f"S{caller}'s Call was INVALID (no targeted card hit them; area, neighbour and Final Strike effects cannot be Called): no stake paid"
                continue
            if [r, named, caller] in s['bet_log']:
                lines[caller] = f"S{caller}'s Call was INVALID (Betrayal Calls are not allowed; the report already names the betrayer): no stake paid"
                continue
            valid.append((caller, named, stake))
        for caller, named, stake in valid:
            s['score'][caller] -= stake
        for named in sorted({n for c, n, st_ in valid}):
            callers = sorted([(c, st_) for c, n, st_ in valid if n == named], key=lambda x: (x[0] - named) % N)
            rewarded = False
            for c, stake in callers:
                hit = any(rr == r and a == named and v == c for rr, a, v, amt in s['harm_landed'])
                if hit and not rewarded:
                    rewarded = True
                    s['score'][c] += stake + C['reward']
                    s['score'][named] = max(0, s['score'][named] - C['penalty'])
                    m = s['mom'][named]
                    s['mom'][named] = [m[0], m[1] - C['streak_drop']] if m[1] - C['streak_drop'] >= 1 else [None, 0]
                    lines[c] = f"S{c} Called S{named}: YES (S{named} -{C['penalty']} VP and their streak drops by {C['streak_drop']}; S{c} gets the stake back +{C['reward']})"
                    s['priv'][r - 1][c].append(f"Your Call on S{named} was right")
                    s['priv'][r - 1][named].append(f"S{c} Called you: YES. You lose {C['penalty']} VP and your streak drops by {C['streak_drop']}")
                elif hit:
                    s['score'][c] += stake
                    lines[c] = f"S{c} Called S{named}: YES but a Caller earlier in seat order already collected (stake returned, no further penalty)"
                else:
                    s['score'][named] += C['alibi']
                    lines[c] = f"S{c} Called S{named}: NO (stake lost, S{named} gains {C['alibi']} VP)"
                    s['priv'][r - 1][c].append(f"Your Call on S{named} was wrong: you lost your {stake} VP stake and S{named} gained {C['alibi']} VP")
                    s['priv'][r - 1][named].append(f"S{c} Called you wrongly: you gained {C['alibi']} VP")
                s['pubcalls'].append([r, c, named, hit])
        return lines

    # ----------------------------------------------------------------- resolve
    def resolve(self, r, acts):
        s = self.s
        cfg = self.cfg
        rg = s['rng']
        rng = random.Random(rg['resolve_seed'] + r * 13 + rg['gid'])
        final_round = cfg['rounds']
        th = self.theme(r)
        start = list(s['score'])
        wards = list(s['wards'])
        halo = [self.haloed(i) for i in range(N)]
        hlen = [s['mom'][i][1] for i in range(N)]
        plays = [[a['play'], a['target'], a.get('accuse')] for a in acts]
        gain = [0] * N
        own = [0] * N
        lostv = [0] * N
        det = [[] for _ in range(N)]
        recv = [0] * N
        ins = [False] * N
        top = max(start)
        s['leaders'].append([i for i in range(N) if start[i] == top])
        new_wards = [0] * N
        ev = [[] for _ in range(N)]
        kinds_now = [self.card[p[0]]['kind'] for p in plays]
        newmom = [list(m) for m in s['mom']]
        card = self.card
        vs = cfg['virtue_streak']
        for s_ in range(N):
            cid, t, _ = plays[s_]
            c = card[cid]
            nm = c['name']
            base = c['self'] - c['recoil']
            gain[s_] += base
            own[s_] += base
            det[s_].append(f"You played {nm}" + (f" on S{t}" if t is not None else "") + f": base {base:+d}")
            if c['pair'] == th:
                gain[s_] += cfg['theme_bonus']
                own[s_] += cfg['theme_bonus']
                det[s_].append(f"theme bonus +{cfg['theme_bonus']}")
            k = c['kind']
            prev = s['mom'][s_]
            n = prev[1] + 1 if prev[0] == k else 1
            if r != final_round and n >= 2:
                if k == 'sin':
                    gain[s_] += cfg['sin_streak']
                    own[s_] += cfg['sin_streak']
                    det[s_].append(f"sin streak (round {n} in a row) +{cfg['sin_streak']}")
                elif n <= len(vs):
                    sb_ = vs[n - 1]
                    gain[s_] += sb_
                    own[s_] += sb_
                    det[s_].append(f"{k} streak (round {n} in a row) +{sb_}")
                else:
                    det[s_].append(f"{k} streak (round {n} in a row): streak fatigue, no bonus this round (the public token stays)")
            newmom[s_] = [k, n]
            if k == 'virtue':
                s['maxv'][s_] = max(s['maxv'][s_], n)
            st = s['stash'][s_]
            if st and st[0] == cid:
                sb = self.stash_bonus(r, s_)
                if sb and s['nostash'][s_]:
                    s['nostash'][s_] = 0
                    det[s_].append(f"stash bonus +{sb} LOST (a Rumour hit you earlier)")
                elif sb:
                    gain[s_] += sb
                    own[s_] += sb
                    det[s_].append(f"stash bonus +{sb}")
            if c['ward']:
                new_wards[s_] += 1
                det[s_].append("you gain a Ward (protects from next round)")
            if c['ward_target'] and t is not None:
                new_wards[t] += 1
                det[t].append(f"S{s_}'s {nm} gave you a Ward (protects from next round)")
            for n_ in ((s_ - 1) % N, (s_ + 1) % N):
                if c['nbr'] > 0:
                    gain[n_] += c['nbr']
                    recv[n_] += c['nbr']
                    det[n_].append(f"S{s_}'s {nm} (neighbour) gave you +{c['nbr']}")
                elif c['nbr'] < 0:
                    ev[n_].append([s_, -c['nbr'], 'NEIGHBOUR', False, nm])
            for o in range(N):
                if o != s_:
                    if c['others'] > 0:
                        gain[o] += c['others']
                        recv[o] += c['others']
                        det[o].append(f"S{s_}'s {nm} gave you +{c['others']}")
                    elif c['others'] < 0 and (not c.get('others_geq') or start[o] > start[s_]):
                        ev[o].append([s_, -c['others'], 'AREA', False, nm])
            if t is not None and c['needs_target']:
                if c['target'] > 0:
                    gain[t] += c['target']
                    recv[t] += c['target']
                    det[t].append(f"S{s_}'s {nm} gave you +{c['target']}")
                elif c['target'] < 0:
                    ev[t].append([s_, -c['target'], 'TARGETED', False, nm, False, 'PLAIN HIT'])
                if c['steal']:
                    ev[t].append([s_, c['steal'], 'TARGETED', True, nm, False, 'STEAL'])
                if c['kind'] == 'virtue' and (c['target'] > 0 or c['ward_target']):
                    s['gave'].append([r, s_, t])
                    pair = sorted([s_, t])
                    SW = cfg['favour']['live_rounds']
                    back = [f for f in s['live'] if f[1] == t and f[2] == s_ and f[0] < r and r - f[0] <= SW]
                    if back and s['settles'][s_] < cfg['settle']['max'] and s['settles'][t] < cfg['settle']['max'] and pair not in s['settled_pairs']:
                        s['settled_pairs'].append(pair)
                        s['settle_rounds'][f'{pair[0]}-{pair[1]}'] = r
                        s['settles'][s_] += 1
                        s['settles'][t] += 1
                        gain[s_] += cfg['settle']['bonus']
                        gain[t] += cfg['settle']['bonus']
                        det[s_].append(f"SETTLE with S{t}: +{cfg['settle']['bonus']} each (Favours stay live, either of you can still Betray)")
                        det[t].append(f"SETTLE with S{s_}: +{cfg['settle']['bonus']} each (Favours stay live, either of you can still Betray)")
                    else:
                        anyfav = [f for f in s['live'] + s['old'] if f[1] == t and f[2] == s_ and f[0] < r]
                        if anyfav:
                            why = ('you already Settled with them' if pair in s['settled_pairs'] else ('one of you already has 2 Settles' if (s['settles'][s_] >= cfg['settle']['max'] or s['settles'][t] >= cfg['settle']['max']) else 'their Favour to you is older than 3 rounds (expired for Settling)'))
                            det[s_].append(f"No SETTLE with S{t}: {why}")
                        elif any(f[0] == r and f[1] == t and f[2] == s_ for f in s['live']):
                            det[s_].append(f"No SETTLE with S{t}: their Favour to you arrived this same round")
                    s['live'].append([r, s_, t])
                    if s['favw'][s_] < cfg['favour']['ward_max']:
                        s['favw'][s_] += 1
                        new_wards[s_] += 1
                        det[s_].append(f"FAVOUR WARD: giving a Favour to S{t} gave you a Ward (protects from next round; {s['favw'][s_]}/{cfg['favour']['ward_max']} Favour Wards this game)")
                    else:
                        det[s_].append(f"No Favour Ward (you already got {cfg['favour']['ward_max']} this game)")
                lo, hi = cfg['scandal_rounds']
                if c.get('expose') and not lo <= r <= hi:
                    det[s_].append(f"Scandal peek only works in rounds {lo}-{hi}: no peek this round")
                elif c.get('expose') and s['fates'][t]:
                    nmf = rng.choice(s['fates'][t])
                    det[s_].append(f"SCANDAL peek: S{t} holds '{nmf}' (family {self.family_of[nmf]})")
            if c['hit_leader']:
                m = max(start[i] for i in range(N) if i != s_)
                ld = [i for i in range(N) if i != s_ and start[i] == m]
                ev[min(ld)].append([s_, c['hit_leader'], 'TARGETED', True, nm, False, 'PLAIN HIT'])
        srt = sorted(start, reverse=True)
        runaway = [start[i] == srt[0] and srt[0] - srt[1] >= cfg['runaway_margin'] for i in range(N)]
        FS = cfg['final_strike']
        if r == final_round:
            cnt = {}
            for s_ in [(self.strike_start() + j) % N for j in range(N)]:
                fs = acts[s_].get('final_strike')
                if fs is not None:
                    cnt[fs] = cnt.get(fs, 0) + 1
                    if cnt[fs] > FS['max_per_target']:
                        det[s_].append(f"Your Final Strike on S{fs} was VOID (S{fs} already faced {FS['max_per_target']} Strikes): nothing paid")
                        continue
                    gain[s_] -= FS['cost']
                    det[s_].append(f"You paid {FS['cost']} VP for a Final Strike on S{fs}")
                    ev[fs].append([s_, FS['runaway_damage'] if runaway[fs] else FS['damage'], 'FINAL', False, 'Final Strike', True])
        for i in range(N):
            if own[i] > cfg['gain_cap']:
                ex = own[i] - cfg['gain_cap']
                gain[i] -= ex
                det[i].append(f"(round gain cap: {ex} VP of your own card, theme, streak and stash bonuses was ignored; the cap is {cfg['gain_cap']})")
        for i in range(N):
            if recv[i] > cfg['receive_cap']:
                ex = recv[i] - cfg['receive_cap']
                gain[i] -= ex
                det[i].append(f"(receiving cap: {ex} VP gained from other players' cards this round was ignored; the cap is {cfg['receive_cap']})")
        lostc = [0] * N
        leaders0 = s['leaders'][-1]
        reset = [False] * N
        smited = set()
        BT = cfg['betrayal']
        for v in range(N):
            events = sorted(ev[v], key=lambda x: x[0])
            ward_used = False
            sanct_used = False
            taken = 0
            landed = []
            for e in events:
                src, amt, typ, stl, nm = e[:5]
                unb = len(e) > 5 and e[5]
                if wards[v] and not ward_used and not unb:
                    ward_used = True
                    wards[v] -= 1
                    det[v].append(f"Your Ward blocked a {TYPLAB[typ]} effect ({amt} VP) from an unknown player")
                    det[src].append((f"Your {nm} on S{v} was blocked by a Ward" + (" (it would have been a Betrayal: no Betrayal earned)" if any(f[1] == v and f[2] == src and f[0] < r for f in s['live'] + s['old']) and typ == 'TARGETED' else "")) if typ == 'TARGETED' else f"Your {nm} ({TYPLAB[typ]}) hit on S{v} was blocked by a Ward")
                    continue
                a2 = amt
                if halo[v] and kinds_now[v] == 'virtue' and not sanct_used and not unb:
                    sanct_used = True
                    a2 = max(0, a2 - cfg['sanctuary'])
                    det[v].append(f"Sanctuary (you are Haloed): the first harmful effect against you this round was reduced by {cfg['sanctuary']} VP ({amt} -> {a2})")
                    if a2 <= 0:
                        det[src].append(f"Your {nm} on S{v} did nothing (Sanctuary: S{v} is Haloed)" + (" - no Betrayal: no VP was removed" if typ == 'TARGETED' and any(f[1] == v and f[2] == src and f[0] < r for f in s['live'] + s['old']) else ""))
                        continue
                room = (cfg['loss_cap_runaway_final'] if (r == final_round and runaway[v]) else self.loss_cap(r)) - taken
                if a2 > room:
                    det[v].append(f"(round cap: {a2 - room} VP of a {TYPLAB[typ]} effect ignored)")
                    a2 = room
                if a2 <= 0:
                    det[src].append(f"Your {nm} on S{v} did nothing (round cap)")
                    if typ == 'TARGETED':
                        landed.append((e, 0))
                    continue
                taken += a2
                landed.append((e, a2))
            for e, amt in landed:
                src, _, typ, stl, nm = e[:5]
                sub = e[6] if len(e) > 6 else ''
                real = amt > 0
                if real:
                    lostv[v] += amt
                    gain[v] -= amt
                    if typ != 'FINAL':
                        lostc[v] += amt
                    thm_ = (" (the attacker's card was " + ("" if card[plays[src][0]]['pair'] == th else "NOT ") + "the round's THEME card)") if typ == 'TARGETED' else ""
                    det[v].append(f"S{src}'s Final Strike cost you {amt} VP" if typ == 'FINAL' else f"a {TYPLAB[typ]} effect" + (f" [{sub}]" if sub else "") + thm_ + f" cost you {amt} VP (attacker and card unknown: only you and the attacker know it happened)")
                    if stl:
                        gain[src] += amt
                        det[src].append(f"your {nm} took {amt} VP from S{v}")
                    else:
                        det[src].append(f"your {nm} cost S{v} {amt} VP")
                    if typ == 'FINAL':
                        if v in leaders0:
                            gain[src] += FS['bounty']
                            det[src].append(f"FINAL STRIKE BOUNTY +{FS['bounty']} (S{v} was an exact leader at the start of the round)")
                    else:
                        s['harm_any'].append([r, src, v, amt])
                if typ == 'TARGETED':
                    if real:
                        s['harm_landed'].append([r, src, v, amt])
                    if real and nm == 'Rumour':
                        s['nostash'][v] = 1
                        det[v].append("Rumour: your next Stash bonus is lost")
                    sm_ = 0
                    if real and halo[v] and (src, v) not in smited:
                        sm_ = cfg['smite']['long'] if hlen[v] >= cfg['smite']['long_streak'] else cfg['smite']['base']
                        smited.add((src, v))
                        s['smite'].append([r, src, v])
                    favs = [f for f in s['live'] if f[1] == v and f[2] == src and f[0] < r and r - f[0] <= cfg['favour']['live_rounds']]
                    if r == final_round:
                        favs += [f for f in s['old'] if f[1] == v and f[2] == src and f[0] < r]
                    bt_ = 0
                    if favs and [src, v] not in s['bet_pairs'] and s['betrayals'][src] < BT['max']:
                        pk = f"{min(src, v)}-{max(src, v)}"
                        settled = pk in s['settle_rounds'] and r - s['settle_rounds'][pk] <= BT['settle_window']
                        bt_ = BT['settled'] if settled else BT['base']
                        s['bet_pairs'].append([src, v])
                        s['bet_log'].append([r, src, v])
                        s['betrayals'][src] += 1
                        gain[v] += BT['insurance']
                        ins[v] = True
                        det[v].append(f"That hit by S{src} was a BETRAYAL of your Favour (Favour insurance +{BT['insurance']} for you; Wounded does not pay this round). No Ward for you.")
                        det[src].append(f"BETRAYAL of S{v}'s Favour from round {favs[0][0]}" + (f" (you Settled with them within 3 rounds: Betrayal base is only +{BT['settled']})" if settled else f" (base +{BT['base']})"))
                    elif any(gg[0] == r and gg[1] == v and gg[2] == src for gg in s['gave']):
                        det[src].append(f"No Betrayal: S{v}'s Favour to you arrived this same round (a Favour must be from an earlier round)")
                    elif any(f[1] == v and f[2] == src and f[0] < r for f in s['live'] + s['old']):
                        why = ("you already Betrayed this player once (once per pair)" if [src, v] in s['bet_pairs'] else ("you already have 2 Betrayals" if s['betrayals'][src] >= BT['max'] else "their Favour is older than 3 rounds (the window expired)"))
                        det[src].append(f"No Betrayal of S{v}: {why}")
                    paid = max(sm_, bt_)
                    if paid:
                        gain[src] += paid
                    if bt_ and sm_:
                        det[src].append(f"SMITE counted (S{v} was Haloed) but Betrayal and Smite do not both pay on one card: you were paid the larger, +{paid}")
                    elif bt_:
                        det[src].append(f"BETRAYAL +{bt_}")
                    elif sm_:
                        det[src].append(f"SMITE +{sm_} (S{v} was Haloed)")
            if lostc[v] >= cfg['reset_threshold']:
                reset[v] = True
        # favours expire
        exp = [f for f in s['live'] if r - f[0] >= cfg['favour']['live_rounds']]
        s['old'] += exp
        s['live'] = [f for f in s['live'] if r - f[0] < cfg['favour']['live_rounds']]
        brk = []
        PL = cfg['pledge']
        for si, tg in sorted(s['pledges'].get(str(r), {}).items(), key=lambda x: int(x[0])):
            si = int(si)
            c_ = card[plays[si][0]]
            if c_['kind'] == 'virtue' and c_['needs_target'] and plays[si][1] == tg and (c_['target'] > 0 or c_['ward_target']):
                if s['pkept'][si] < PL['kept_max']:
                    s['pkept'][si] += 1
                    gain[tg] += PL['kept_bonus']
                    gain[si] += PL['kept_bonus']
                    det[si].append(f"Pledge to S{tg} KEPT: you and S{tg} each +{PL['kept_bonus']} (kept Pledge {s['pkept'][si]}/{PL['kept_max']} that pay)")
                    det[tg].append(f"S{si} kept a public Pledge to you: you +{PL['kept_bonus']}")
                else:
                    det[si].append(f"Pledge to S{tg} KEPT (no VP: only your first {PL['kept_max']} kept Pledges pay)")
                    det[tg].append(f"S{si} kept a public Pledge to you (no VP: they have used their {PL['kept_max']} paying Pledges)")
            else:
                if not self.legal_pledge_card(r, si):
                    det[si].append(f"Pledge to S{tg} VOID: you held no legal targeted virtue (no penalty, not announced)")
                    det[tg].append(f"S{si}'s public Pledge to you was VOID (they held no legal card; not announced to others)")
                else:
                    gain[si] -= PL['broken_penalty']
                    gain[tg] += PL['broken_award']
                    det[si].append(f"Pledge to S{tg} BROKEN: -{PL['broken_penalty']} VP (S{tg} gets +{PL['broken_award']})")
                    det[tg].append(f"S{si} BROKE a public Pledge to you: you +{PL['broken_award']}")
                    brk.append(f"S{si}'s Pledge to S{tg} was BROKEN")
        score = [max(start[i] + gain[i], 0) for i in range(N)]
        # wounded
        W = cfg['wounded']
        for i in range(N):
            if lostv[i] >= W['threshold'] and not ins[i] and not (start[i] == max(start) and start.count(max(start)) == 1):
                score[i] += W['bonus']
                det[i].append(f"Wounded +{W['bonus']} (you lost {W['threshold']}+ VP to others' cards)")
        # accusations: seat order; family test uses families held at the START of resolution
        AC = cfg['accusation']
        acc_pub = []
        fam0 = [set(self.families(i)) for i in range(N)]
        s['stripped_last'] = []
        acc_targets = set()
        for i, p in enumerate(plays):
            ac = p[2]
            if not ac:
                continue
            t, gs = ac['seat'], ac.get('fate')
            legal = gs in self.fates and self.family_of[gs] in fam0[t]
            if not legal:
                det[i].append(f"ACCUSATION of S{t} ('{gs}'): REJECTED (that family is not publicly held by S{t}); no cost, your Accusation is not used")
                continue
            if t in acc_targets:
                det[i].append(f"ACCUSATION of S{t} ('{gs}'): VOID (an earlier Accusation on S{t} already resolved this round); no cost, your Accusation is not used")
                continue
            if s['strips'][t] >= 1:
                det[i].append(f"ACCUSATION of S{t} ('{gs}'): VOID (S{t} already lost a Fate to an Accusation; one strip per player per game); no cost, your Accusation is not used")
                continue
            acc_targets.add(t)
            s['accused'][i] = 1
            if gs in s['fates'][t]:
                s['fates'][t].remove(gs)
                s['removed'][t].append(gs)
                s['strips'][t] += 1
                s['stripped_last'].append(t)
                score[i] += AC['correct']
                s['inq_correct'][i] += 1
                det[i].append(f"ACCUSATION of S{t} ('{gs}'): CORRECT +{AC['correct']}")
                det[t].append(f"S{i} accused you of '{gs}': CORRECT, Fate '{gs}' is LOST permanently (you will get a 2-Fate replacement offer in the next talk if you hold fewer than 3 Fates)")
                acc_pub.append(f"S{i} accused S{t} of '{gs}': CORRECT")
            else:
                score[i] = max(0, score[i] - AC['wrong'])
                det[i].append(f"ACCUSATION of S{t} ('{gs}'): WRONG -{AC['wrong']}")
                det[t].append(f"S{i} accused you of '{gs}': wrong, no effect")
                acc_pub.append(f"S{i} accused S{t} of '{gs}': wrong")
        TI = cfg['tithe']
        if r in TI['rounds']:
            order_ = sorted(range(N), key=lambda i: (-score[i], i))
            L = order_[0]
            if score[L] - score[order_[1]] >= TI['margin']:
                low = min((i for i in range(N) if i != L), key=lambda i: (score[i], i))
                if s['tithe_recv'][low] + TI['amount'] <= TI['recv_max']:
                    score[L] = max(0, score[L] - TI['amount'])
                    score[low] += TI['amount']
                    s['tithe_recv'][low] += TI['amount']
                    s['tithe_log'].append([r, L, low])
                    det[L].append(f"TITHE applied: you were the sole leader by {TI['margin']}+ VP, you lose {TI['amount']} VP (not announced)")
                    det[low].append(f"TITHE applied: you gain {TI['amount']} VP (not announced)")
        if r == cfg['bulwark_ward_round']:
            for i in range(N):
                if 'bulwark' in s['fates'][i]:
                    new_wards[i] += 1
                    det[i].append(f"Bulwark: you gain a Ward for round {r + 1}")
        for i, a in enumerate(acts):
            st = s['stash'][i]
            if st and st[0] == a['play']:
                s['stash'][i] = None
            if a.get('reserve'):
                if s['stash'][i]:
                    det[i].append(f"your old stash card {card[s['stash'][i][0]]['name']} was lost")
                s['stash'][i] = [a['reserve'], r]
        for i in range(N):
            if reset[i]:
                k_, n_ = newmom[i]
                newmom[i] = [k_, n_ - 1] if n_ - 1 >= 1 else [None, 0]
                det[i].append("A real hit of 2+ VP lowered your streak by 1")
        s['mom'] = newmom
        new_w = [wards[i] + new_wards[i] for i in range(N)]
        pub = [("No Accusations." if not acc_pub else "; ".join(acc_pub) + ".") + (" " + "; ".join(brk) + "." if brk else "") + " How many virtues or sins were played, who played what, targets, Favours, Betrayals and Wards are private."]
        pub.append(self.momentum_text() + ".")
        if r == final_round:
            pub.append("REVEAL: " + "; ".join(f"S{i} {card[p[0]]['name']}" + (f" on S{p[1]}" if p[1] is not None else "") + (f" + Final Strike on S{acts[i]['final_strike']}" if acts[i].get('final_strike') is not None else "") for i, p in enumerate(plays)) + ".")
        for i in range(N):
            det[i].append(f"Net VP change this round: {score[i] - start[i]:+d}")
        s['score'] = score
        s['wards'] = new_w
        s['lost'] = [a + b for a, b in zip(s['lost'], lostc)]
        s['lostr'].append(lostc)
        s['rounds'].append(plays)
        s['hist'].append(list(score))  # copy: later Calls mutate s['score']
        s['acts'].append(acts)
        s['log'].append(pub)
        s['priv'].append(det)
        return dict(score=score, wards=new_w, gain=gain, lost=lostv, pub=pub, plays=plays, priv=det, start=start)

    def momentum_text(self):
        return "MOMENTUM (public): " + "; ".join(f"S{i} {'HALOED' if self.haloed(i) else ('HOT' if self.hot(i) else 'none')}" for i in range(N))

    # ---------------------------------------------------------------- finalize
    def finalize(self):
        s = self.s
        R = s['rounds']
        base = s['score']
        FC = self.cfg['fate']
        cards = [[self.card[r[i][0]] for r in R] for i in range(N)]
        kind = [[c['kind'] for c in cs] for cs in cards]
        virt = [k.count('virtue') for k in kind]
        order = sorted(range(N), key=lambda i: (-base[i], -virt[i], i))
        P = {n: f['params'] for n, f in self.fates.items()}
        top = {n: set(order[:P[n]['top']]) for n in ('saint', 'survivor')}
        res = []
        for i in range(N):
            hm = [self.harmful(c) for c in cards[i]]
            earlyv = kind[i][:4].count('virtue')
            earlys = kind[i][:4].count('sin')
            late = kind[i][4:]

            def hit(n):
                if n == 'saint':
                    return virt[i] >= P[n]['virtue_rounds'] and i in top[n]
                if n == 'peacemaker':
                    return not any(hm) and s['settles'][i] >= P[n]['settles'] and len({t for rr, a, t in s['gave'] if a == i}) >= P[n]['targets']
                if n == 'heretic':
                    return len({r_ for r_, a, v in s['smite'] if a == i}) >= P[n]['rounds']
                if n == 'wolf':
                    return len({v for r_, a, v, amt in s['harm_landed'] if a == i}) >= P[n]['victims']
                if n == 'glutton':
                    return kind[i].count('sin') >= P[n]['sin_rounds']
                if n == 'backstabber':
                    return s['betrayals'][i] >= P[n]['betrayals']
                if n == 'fallen':
                    return earlyv >= P[n]['early_virtues'] and all(k == 'sin' for k in late) and s['betrayals'][i] >= P[n]['betrayals']
                if n == 'redeemed':
                    ok = earlys >= P[n]['early_sins'] and sum(1 for k in late if k == 'virtue') >= P[n]['late_virtues']
                    ok2 = any(f[1] == i and f[0] >= 5 and any(h[1] == i and h[2] == f[2] and h[0] < f[0] for h in s['harm_landed']) for f in s['gave'])
                    return ok and ok2
                if n == 'inquisitor':
                    return s['inq_correct'][i] >= P[n]['correct']
                if n == 'bulwark':
                    return sum(1 for x in s['lostr'] if x[i] <= P[n]['max_loss']) >= P[n]['rounds']
                if n == 'late_bloomer':
                    return (1 + sum(1 for j in range(N) if s['hist'][3][j] > s['hist'][3][i])) - (1 + sum(1 for j in range(N) if base[j] > base[i])) >= P[n]['places']
                if n == 'survivor':
                    return s['lost'][i] >= P[n]['lost'] and i in top[n]
                return False
            held = list(s['fates'][i])
            outs = [(n, hit(n)) for n in held]
            nh = sum(1 for n, ok in outs if ok)
            raw = sum(self.fates[n]['reward'] for n, ok in outs if ok)
            stack = FC['stack'].get(str(min(nh, 3)), 0)
            bonus = min(FC['cap'], raw + stack)
            res.append(dict(seat=i, base=base[i], held=held, removed=s['removed'][i], hits=[n for n, ok in outs if ok],
                            misses=[n for n, ok in outs if not ok], raw=raw, stack=stack, bonus=bonus, final=base[i] + bonus,
                            betrayals=s['betrayals'][i], settles=s['settles'][i], virtues=virt[i]))
        return dict(base=list(base), results=res, winner=max(range(N), key=lambda i: (res[i]['final'], virt[i], -i)))

    # -------------------------------------------------------------------- misc
    def snapshot(self):
        return copy.deepcopy(self.s)
