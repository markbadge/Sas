"""Moderator arithmetic helper for Saints and Sinners v14 playtests (games 29-30). Not an engine: each phase is run by hand.
Rules: RULES_v14.md. Data: ss_data_v14.py. Hidden info: own VP exact, others banded; plays/targets/Favours/Betrayals/Wards private.
Public: binary Momentum token (Haloed / Hot / none, length hidden), Calls, Accusations, broken Pledges (sin counts are NOT announced in v11)."""
import json, random
from ss_data_v14 import PAIRS, CARDS, CARD_BY_ID, FATES, STACK_BONUS, FATE_CAP, FAMILY, FAMILY_OF, VIRTUE_PATH, AGGRESSIVE, MAX_PER_FAMILY

BASE = '/home/claude/ss'
ST = '/tmp/g2930_state.json'
SETUP = '/tmp/g2930_setup.json'
NAMES = {'g29': '29', 'g30': '30'}
GAMES = ('g29', 'g30')
START_VP = 2
TYPLAB = {'TARGETED': 'targeted', 'NEIGHBOUR': 'neighbour', 'AREA': 'area', 'FINAL': 'Final Strike'}


def load(): return json.load(open(ST))
def save(s): json.dump(s, open(ST, 'w'))
def harmful(c): return bool(c['target'] < 0 or c['steal'] or c['hit_leader'] or c['nbr'] < 0 or c['others'] < 0)
def band(v): lo = 5 * (v // 5); return f"{lo}-{lo + 4}"
def cap_for(r): return 7 if r == 7 else 5


def make_setup(seed=2930):
    rng = random.Random(seed); setup = {}
    for g in ('29', '30'):
        themes = list(range(len(PAIRS))); rng.shuffle(themes); setup[g] = dict(themes=themes)
    json.dump(setup, open(SETUP, 'w'))
    st = {}
    for g in GAMES:
        st[g] = dict(score=[START_VP] * 6, wards=[0] * 6, lost=[0] * 6, lostr=[], rounds=[], hist=[], log=[], leaders=[],
                     stash=[None] * 6, fates=[[] for _ in range(6)], offers=[[] for _ in range(6)], removed=[[] for _ in range(6)],
                     gave=[], live=[], old=[], settled_pairs=[], settles=[0] * 6, bet_pairs=[], bet_log=[],
                     harm_landed=[], harm_any=[], smite=[], betrayals=[0] * 6, inq_correct=[0] * 6, accused=[0] * 6,
                     mom=[[None, 0] for _ in range(6)], maxv=[0] * 6, calls=[], acts=[], hands={}, priv=[], pubcalls=[], pledges={}, settle_rounds={}, stripped_last=[], retired=[0] * 6, repl_taken=[0] * 6, pkept=[0] * 6, strips=[0] * 6, nostash=[0] * 6, favw=[0] * 6, tithe_recv=[0] * 6, tithe_log=[])
    save(st)


def strike_start(g): return random.Random(1250 + int(g[1:])).randrange(6)


def legal_pledge_card(g, r, seat):
    s = load()[g]; ids = list(ensure_hand(g, r)[seat]) + ([s['stash'][seat][0]] if s['stash'][seat] else [])
    return any(CARD_BY_ID[x]['kind'] == 'virtue' and CARD_BY_ID[x]['needs_target'] and (CARD_BY_ID[x]['target'] > 0 or CARD_BY_ID[x]['ward_target']) for x in ids)


def theme(g, r): return json.load(open(SETUP))[NAMES[g]]['themes'][r - 1]


def set_pledges(g, r, talks):
    """Store the Pledges made in the talk before round r: {seat: target}. Invalid pledges are ignored."""
    S = load(); out = {}
    for i in range(6):
        p = talks[i].get('pledge')
        if isinstance(p, int) and p != i and 0 <= p < 6: out[str(i)] = p
    S[g]['pledges'][str(r)] = out; save(S); return out


def deal_hand(rng, th, exclude=None, need_sin=False):
    pool = [c['id'] for c in CARDS if c['id'] != exclude]
    while True:
        tc = rng.choice([c['id'] for c in CARDS if c['pair'] == th and c['id'] != exclude])
        h = [tc] + rng.sample([c for c in pool if c != tc], 2)
        cs = [CARD_BY_ID[x] for x in h]
        if need_sin and not any(c['kind'] == 'sin' and c['needs_target'] and harmful(c) for c in cs): continue
        if any(c['kind'] == 'virtue' for c in cs) and any(c['kind'] == 'sin' for c in cs) and any(c['needs_target'] for c in cs):
            rng.shuffle(h); return h


def ensure_hand(g, r):
    S = load(); s = S[g]
    if str(r) not in s['hands']:
        rng = random.Random(2930 * 1000 + r * 10 + int(g[1:]))
        s['hands'][str(r)] = [deal_hand(rng, theme(g, r), s['stash'][i][0] if s['stash'][i] else None,
                                         need_sin=(2 <= r <= 4 and any(f[2] == i and r - f[0] <= 3 and f[0] < r for f in s['live']))) for i in range(6)]
        save(S)
    return s['hands'][str(r)]


def card_line(cid, th):
    c = CARD_BY_ID[cid]
    return f"{cid} {c['name']}{'*' if c['pair'] == th else ''} ({c['kind']}): {c['text']}" + (" [needs target]" if c['needs_target'] else "")


def hand_text(g, r, seat):
    return " | ".join(card_line(x, theme(g, r)) for x in ensure_hand(g, r)[seat])


def stash_text(g, r, seat):
    st = load()[g]['stash'][seat]
    if not st: return "empty"
    bonus = min(2, max(0, r - st[1] - 1))
    return card_line(st[0], theme(g, r)) + f" [stored since round {st[1]}; playing it now gives +{bonus} VP stash bonus]"


def fates_text(g, seat):
    f = load()[g]['fates'][seat]
    return "; ".join(f"{n}: {FATES[n]['desc']} (+{FATES[n]['reward']})" for n in f) or "none yet"


def families(s, i): return sorted({FAMILY_OF[n] for n in s['fates'][i]})


def families_text(s):
    return "Public Fate families currently held: " + "; ".join(f"S{i}: {'/'.join(families(s, i)) or 'none'}" for i in range(6))


def haloed(s, i): return s['mom'][i][0] == 'virtue' and s['mom'][i][1] >= 2
def hot(s, i): return s['mom'][i][0] == 'sin' and s['mom'][i][1] >= 2


def momentum_text(s):
    return "MOMENTUM (public): " + "; ".join(f"S{i} {'HALOED' if haloed(s, i) else ('HOT' if hot(s, i) else 'none')}" for i in range(6))


def score_view(s, seat, exact=False):
    sc = s['score']
    if exact: return "FINAL ROUND: ALL EXACT VP ARE REVEALED: " + ", ".join(f"S{i} {sc[i]}" for i in range(6)) + f" (you are S{seat})"
    return f"Your VP: {sc[seat]}. Other players' VP (bands of 5): " + ", ".join(f"S{i} {band(sc[i])}" for i in range(6) if i != seat)


def private_board(s, seat, r):
    given = [f"S{b} (round {fr}, expires after round {fr + 3})" for fr, a, b in s['live'] if a == seat]
    recv = [f"S{a} (round {fr}, expires after round {fr + 3}; " + ("you already used a Betrayal on this player" if [seat, a] in s['bet_pairs'] else "Betrayal still available") + ")" for fr, a, b in s['live'] if b == seat]
    if r == 7:
        recv += [f"S{a} (round {fr}, expired but counts in round 7)" for fr, a, b in s['old'] if b == seat]
    return (f"PRIVATE BOARD: Favours you gave that are still live: {', '.join(given) or 'none'}. Favours you received that are still live (you may Betray the giver): {', '.join(recv) or 'none'}. "
            f"Betrayals you earned {s['betrayals'][seat]}/2; Settles {s['settles'][seat]}/2; kept paying Pledges {s['pkept'][seat]}/3 (a Settle does NOT remove Favours: you can still Betray a live Favour afterwards). Your Ward: {'yes' if s['wards'][seat] else 'no'}. "
            f"Your own streak: {s['mom'][seat][0] or 'none'} x{s['mom'][seat][1]}. Accusation: {'USED' if s['accused'][seat] else ('available (rounds 4-7)' if r >= 4 else 'not yet (from round 4)')}.")


def rank_of(s, seat):
    virt = [sum(1 for p in s['rounds'] if CARD_BY_ID[p[i][0]]['kind'] == 'virtue') for i in range(6)]
    order = sorted(range(6), key=lambda i: (-s['score'][i], -virt[i], i)); return order.index(seat) + 1


def tally(s, seat):
    R = s['rounds']; kinds = []; harm = 0
    for p in R:
        c = CARD_BY_ID[p[seat][0]]; kinds.append(c['kind']); harm += 1 if harmful(c) else 0
    low = sum(1 for x in s['lostr'] if x[seat] <= 1)
    low2 = sum(1 for x in s['lostr'] if x[seat] <= 2)
    hrounds = len({r for r, a, v, amt in s['harm_landed'] if a == seat}); hvict = len({v for r, a, v, amt in s['harm_landed'] if a == seat})
    smr = len({r for r, a, v in s['smite'] if a == seat})
    tv = len({t for rr, a, t in s['gave'] if a == seat})
    return (f"YOUR TALLIES: rounds with virtue {kinds.count('virtue')}, sin {kinds.count('sin')}, harmful cards {harm}; "
            f"best virtue streak so far {s['maxv'][seat]}; Settles {s['settles'][seat]}; Betrayals {s['betrayals'][seat]}; rounds you landed real harm {hrounds} (targeted harm only, on {hvict} different players, wolf needs 4); "
            f"rounds you hit a Haloed player (Smite) {smr}; targeted virtues given to {tv} different players; VP lost to others' cards {s['lost'][seat]} total, rounds with <=1 lost {low}, rounds with <=2 lost {low2}; correct Accusations {s['inq_correct'][seat]}.")


def offers(g, stage, seed=0, only=None, n=3):
    """stage 0 = start (random); 1 = after R2; 2 = after R4. Saves and returns {seat: [names]}."""
    S = load(); s = S[g]; rng = random.Random(seed + stage * 101 + int(g[1:]) * 7 + len(s['rounds'])); out = {}
    k = len(s['rounds']); rem = 7 - k
    for seat in (range(6) if only is None else only):
        held = set(s['fates'][seat]) | set(s['removed'][seat])
        kinds = [CARD_BY_ID[p[seat][0]]['kind'] for p in s['rounds']]
        ev_ = kinds[:4].count('virtue'); es = kinds[:4].count('sin')
        hm = sum(1 for p in s['rounds'] if harmful(CARD_BY_ID[p[seat][0]]))
        gl = sum(1 for p in s['rounds'] if CARD_BY_ID[p[seat][0]]['kind'] == 'sin')
        hv = len({v for r_, a, v, amt in s['harm_landed'] if a == seat})
        hr = len({r for r, a, v, amt in s['harm_any'] if a == seat}); sm = len({r for r, a, v in s['smite'] if a == seat})
        curv = s['mom'][seat][1] if s['mom'][seat][0] == 'virtue' else 0
        ok = {'saint': kinds.count('virtue') + rem >= 6, 'peacemaker': hm == 0 and rem >= 2,
              'heretic': sm + rem >= 3, 'wolf': hv + rem >= 4, 'glutton': gl + rem >= 5, 'backstabber': s['betrayals'][seat] < 2 and rem >= 1,
              'fallen': ev_ + max(0, 4 - k) >= 3, 'redeemed': es + max(0, 4 - k) >= 3, 'inquisitor': k + 4 >= 4 and not s['accused'][seat],
              'bulwark': True, 'late_bloomer': stage > 0 and rank_of(s, seat) >= 3 and rem >= 3,
              'survivor': stage > 0 and rank_of(s, seat) >= 4 and rem >= 3}
        fam_n = {}
        for h_ in s['fates'][seat]: fam_n[FAMILY_OF[h_]] = fam_n.get(FAMILY_OF[h_], 0) + 1
        pool = [n for n in FATES if ok[n] and n not in held and fam_n.get(FAMILY_OF[n], 0) < MAX_PER_FAMILY]
        pick = []
        ag = [n for n in pool if n in AGGRESSIVE]
        if ag: pick.append(rng.choice(ag))
        rest0 = [x for x in pool if FAMILY_OF[x] == 'LIGHT' and x not in pick]
        if rest0: pick.append(rng.choice(rest0))
        rest = [x for x in pool if x not in pick]; rng.shuffle(rest)
        pick += rest[:n - len(pick)]
        if len(pick) < n:
            extra = [x for x in FATES if x not in held and x not in pick and x not in ('late_bloomer', 'survivor') and fam_n.get(FAMILY_OF[x], 0) < MAX_PER_FAMILY]; rng.shuffle(extra); pick += extra[:n - len(pick)]
        pick = pick[:n]
        rng.shuffle(pick); out[seat] = pick; s['offers'][seat] = pick
    save(S); return out


def offer_text(offer): return " | ".join(f"{n} (+{FATES[n]['reward']}, family {FAMILY_OF[n]}): {FATES[n]['desc']}" for n in offer)


def can_retire(s, seat, stage=None): return False  # v14: Retire removed


def pick_fates(g, picks, stage, retire=None):
    """stage 0/1/2 = regular offers; 3 = replacement offer after a strip. retire: {seat: held_fate_to_drop} (stages 1-2 only, once per game)."""
    S = load(); s = S[g]; retire = retire or {}
    for seat, name in picks.items():
        seat = int(seat)
        rt = retire.get(seat, retire.get(str(seat)))
        if name in s['offers'][seat] and rt and stage in (1, 2) and can_retire(s, seat, stage) and rt in s['fates'][seat] and name not in s['fates'][seat]:
            s['fates'][seat].remove(rt); s['removed'][seat].append(rt); s['retired'][seat] = 1
            s['fates'][seat].append(name)
            if name == 'bulwark' and stage == 1: s['wards'][seat] += 1
            continue
        fam_n = sum(1 for h_ in s['fates'][seat] if name in FAMILY_OF and FAMILY_OF[h_] == FAMILY_OF[name])
        if name in s['offers'][seat] and len(s['fates'][seat]) < 3 and name not in s['fates'][seat] and fam_n < MAX_PER_FAMILY:
            s['fates'][seat].append(name)
            if stage == 3: s['repl_taken'][seat] = 1
            if name == 'bulwark' and stage == 1: s['wards'][seat] += 1
    s['offers'] = [[] for _ in range(6)]; save(S)


def talk_r1_files(g, offer):
    s = load()[g]; th = theme(g, 1)
    for seat in range(6):
        txt = (f"ROUND 1 TALK ({g.upper()}, you are S{seat}). Round 1 theme: {PAIRS[th][0]}/{PAIRS[th][1]}. All players start on 2 VP. No hidden roles: everyone is a free player. "
               f"FATE OFFER (pick ONE secret Fate to pursue, or null; you can hold up to 3 over the game, but at most 2 from the same public family (LIGHT or SHADOW)): {offer_text(offer[seat])}. "
               'Reply JSON only (TALK format): {"say":"...","whisper":{"<seat>":"..."},"pledge":<seat> or null,"fate":"<name from the offer>" or null,"note":"optional"}')
        open(f'{BASE}/play/{g}_r1_talk_S{seat}.txt', 'w').write(txt)


def act_files(g, r, talks, state, extra=''):
    th = theme(g, r); s = state[g]
    pub = "\n".join(f'S{i}: "{talks[i]["say"]}"' for i in range(6))
    pl = [f'S{i} PLEDGES a targeted virtue to S{talks[i]["pledge"]} this round (kept: BOTH get +1, for the pledger first 3 kept Pledges; broken while holding a legal card: pledger -2, the named player +2, announced)' for i in range(6) if isinstance(talks[i].get('pledge'), int) and talks[i]['pledge'] != i and 0 <= talks[i]['pledge'] < 6]
    if pl: pub += "\nPUBLIC PLEDGES: " + "; ".join(pl)
    for seat in range(6):
        wh = [f'S{i}: "{talks[i]["whisper"][str(seat)]}"' for i in range(6) if str(seat) in talks[i].get('whisper', {})]
        pn = ''
        if isinstance(talks[seat].get('pledge'), int) and not legal_pledge_card(g, r, seat):
            pn = f"\nPLEDGE NOTE (private): you hold no targeted virtue that could keep your Pledge to S{talks[seat]['pledge']}; the Pledge is VOID: no penalty, not announced."
        fs_fmt = ',"final_strike":null or seat (round 7 only)' if r == 7 else ''
        txt = (f"ROUND {r} ACT ({g.upper()}, you are S{seat}). Theme {PAIRS[th][0]}/{PAIRS[th][1]} (* = in-theme card: theme bonus +2 for the virtue, +2 for the sin). "
               f"{score_view(s, seat, exact=(r == 7))}. {momentum_text(s)}. {private_board(s, seat, r)} {families_text(s)}."
               + (f"\nNEWS: {extra}" if extra else "") + pn
               + ("\nFINAL ROUND RULES: no streak bonus is paid this round; the round cap is 7 VP (12 VP against a player 8+ ahead of second place); every Favour you hold counts for Betrayal even if older than 3 rounds; at the end every card played and every Final Strike is revealed publicly with its target. "
                  "FINAL STRIKE (optional): in addition to your card you may pay 2 VP and name ONE other player in the \"final_strike\" field: they lose 5 VP, or 7 VP if that player is 8 or more VP ahead of the second-highest player (a Ward and Sanctuary cannot reduce it; it counts toward the round cap, 7, or 12 for a player 8+ ahead; it is not a card: no Smite, no Betrayal, not harm for wolf/heretic/peacemaker; no Call). A player can suffer at most 3 Strikes (later ones are void and refunded). Strikes resolve in seat order starting from the seat set by a die roll: S" + str(strike_start(g)) + " goes first, then upward and wrapping. EACH valid Strike that lands on a player who was an exact leader at the start of this round (each co-leader counts) earns its striker a +1 bounty (so a Strike on a leader costs you net 1 VP). The attacker is named publicly at the end." if r == 7 else "") +
               f"\nYOUR FATES: {fates_text(g, seat)}\n{tally(s, seat) if s['rounds'] else ''}"
               f"\nPUBLIC TALK:\n{pub}\nWHISPERS TO YOU:\n" + ("\n".join(wh) or "none") +
               f"\nYOUR DEALT HAND: {hand_text(g, r, seat)}\nYOUR STASH (secret, one card, playable instead of a dealt card): {stash_text(g, r, seat)}\n"
               'Reply JSON only: {"play":"cNN","target":null or seat,"stash":"cNN" or null,"accuse":{"seat":N,"fate":"<fate name>"} (optional, once per game, rounds 4-7, no card slot)' + fs_fmt + ',"note":"optional"}  '
               '(play one card from your dealt hand or stash; optionally move ONE other DEALT card into your stash, replacing and losing any card already there; the rest are discarded)')
        open(f'{BASE}/play/{g}_r{r}_act_S{seat}.txt', 'w').write(txt)


def norm_acts(g, r, raw):
    S = load(); s = S[g]; H = ensure_hand(g, r); fixes = []; out = []
    for i in range(6):
        a = dict(raw[i]); stc = s['stash'][i][0] if s['stash'][i] else None; allowed = H[i] + ([stc] if stc else [])
        if a.get('play') not in allowed: fixes.append(f"S{i} invalid play {a.get('play')} -> {H[i][0]}"); a['play'] = H[i][0]
        c = CARD_BY_ID[a['play']]; t = a.get('target')
        if c['needs_target']:
            if not isinstance(t, int) or t == i or not 0 <= t < 6: fixes.append(f"S{i} bad target {t} -> {(i + 1) % 6}"); t = (i + 1) % 6
        else: t = None
        a['target'] = t
        rv = a.get('stash', a.get('reserve'))
        if rv is not None and (rv not in H[i] or rv == a['play']): fixes.append(f"S{i} invalid stash {rv} dropped"); rv = None
        a['reserve'] = rv
        ac = a.get('accuse')
        if ac:
            if r < 4 or s['accused'][i] or not isinstance(ac, dict) or not isinstance(ac.get('seat'), int) or ac['seat'] == i or not 0 <= ac['seat'] < 6:
                fixes.append(f"S{i} invalid accuse dropped"); ac = None
        a['accuse'] = ac
        fs = a.get('final_strike')
        if fs is not None and (r != 7 or not isinstance(fs, int) or fs == i or not 0 <= fs < 6):
            fixes.append(f"S{i} invalid final_strike dropped"); fs = None
        a['final_strike'] = fs
        out.append(a)
    return out, fixes


def apply_calls(g, r, calls):
    """v14: stake 1 for everyone (NO costs 1). YES: stake back +2, named -3 VP and streak -1."""
    S = load(); s = S[g]; lines = {}; valid = []
    played = s['rounds'][r - 1]
    for caller, named in sorted(calls.items()):
        caller = int(caller)
        if not isinstance(named, int) or named == caller or not 0 <= named < 6: continue
        stake = 1
        if s['score'][caller] < stake: continue
        got_targeted = any(rr == r and v == caller for rr, a, v, amt in s['harm_landed'])
        if not got_targeted:
            lines[caller] = f"S{caller}'s Call was INVALID (no targeted card hit them; area, neighbour and Final Strike effects cannot be Called): no stake paid"; continue
        if [r, named, caller] in s['bet_log']:
            lines[caller] = f"S{caller}'s Call was INVALID (Betrayal Calls are not allowed; the report already names the betrayer): no stake paid"; continue
        valid.append((caller, named, stake))
    for caller, named, stake in valid: s['score'][caller] -= stake
    for named in sorted({n for c, n, st_ in valid}):
        callers = sorted([(c, st_) for c, n, st_ in valid if n == named], key=lambda x: (x[0] - named) % 6); rewarded = False
        for c, stake in callers:
            hit = any(rr == r and a == named and v == c for rr, a, v, amt in s['harm_landed'])
            if hit and not rewarded:
                rewarded = True
                s['score'][c] += stake + 2; s['score'][named] = max(0, s['score'][named] - 3)
                m = s['mom'][named]; s['mom'][named] = [m[0], m[1] - 1] if m[1] - 1 >= 1 else [None, 0]
                lines[c] = f"S{c} Called S{named}: YES (S{named} -3 VP and their streak drops by 1; S{c} gets the stake back +2)"
                s['priv'][r - 1][c].append(f"Your Call on S{named} was right")
                s['priv'][r - 1][named].append(f"S{c} Called you: YES. You lose 3 VP and your streak drops by 1")
            elif hit:
                s['score'][c] += stake
                lines[c] = f"S{c} Called S{named}: YES but a Caller earlier in seat order already collected (stake returned, no further penalty)"
            else:
                s['score'][named] += 1
                lines[c] = f"S{c} Called S{named}: NO (stake lost, S{named} gains 1 VP)"
                s['priv'][r - 1][c].append(f"Your Call on S{named} was wrong: you lost your {stake} VP stake and S{named} gained 1 VP")
                s['priv'][r - 1][named].append(f"S{c} Called you wrongly: you gained 1 VP")
            s['pubcalls'].append([r, c, named, hit])
    save(S); return [lines[k] for k in sorted(lines)]


def resolve(g, r, acts, rng_seed=0):
    S = load(); s = S[g]; rng = random.Random(rng_seed + r * 13 + int(g[1:]))
    th = theme(g, r); start = list(s['score']); wards = list(s['wards']); CAPR = cap_for(r)
    halo = [haloed(s, i) for i in range(6)]; hlen = [s['mom'][i][1] for i in range(6)]
    anon = True
    who = lambda x: f'S{x}'
    plays = [[a['play'], a['target'], a.get('accuse')] for a in acts]
    gain = [0] * 6; own = [0] * 6; lostv = [0] * 6; det = [[] for _ in range(6)]; recv = [0] * 6; ins = [False] * 6
    top = max(start); s['leaders'].append([i for i in range(6) if start[i] == top])
    new_wards = [0] * 6; ev = [[] for _ in range(6)]
    kinds_now = [CARD_BY_ID[p[0]]['kind'] for p in plays]
    nv_pub = kinds_now.count('virtue'); ns_pub = kinds_now.count('sin')
    newmom = [list(m) for m in s['mom']]
    for s_ in range(6):
        cid, t, _ = plays[s_]; c = CARD_BY_ID[cid]; nm = c['name']
        base = c['self'] - c['recoil']; gain[s_] += base; own[s_] += base
        det[s_].append(f"You played {nm}" + (f" on S{t}" if t is not None else "") + f": base {base:+d}")
        if c['pair'] == th:
            gain[s_] += 2; own[s_] += 2; det[s_].append("theme bonus +2")
        k = c['kind']; prev = s['mom'][s_]
        n = prev[1] + 1 if prev[0] == k else 1
        if r != 7 and n >= 2:
            if k == 'sin': gain[s_] += 1; own[s_] += 1; det[s_].append(f"sin streak (round {n} in a row) +1")
            elif n <= 4: sb_ = 1 if n == 2 else 2; gain[s_] += sb_; own[s_] += sb_; det[s_].append(f"{k} streak (round {n} in a row) +{sb_}")
            else: det[s_].append(f"{k} streak (round {n} in a row): streak fatigue, no bonus this round (the public token stays)")
        newmom[s_] = [k, n]
        if k == 'virtue': s['maxv'][s_] = max(s['maxv'][s_], n)
        st = s['stash'][s_]
        if st and st[0] == cid:
            sb = min(2, max(0, r - st[1] - 1))
            if sb and s['nostash'][s_]: s['nostash'][s_] = 0; det[s_].append(f"stash bonus +{sb} LOST (a Rumour hit you earlier)")
            elif sb: gain[s_] += sb; own[s_] += sb; det[s_].append(f"stash bonus +{sb}")
        if c['ward']: new_wards[s_] += 1; det[s_].append("you gain a Ward (protects from next round)")
        if c['ward_target'] and t is not None: new_wards[t] += 1; det[t].append(f"S{s_}'s {nm} gave you a Ward (protects from next round)")
        for n_ in ((s_ - 1) % 6, (s_ + 1) % 6):
            if c['nbr'] > 0: gain[n_] += c['nbr']; recv[n_] += c['nbr']; det[n_].append(f"S{s_}'s {nm} (neighbour) gave you +{c['nbr']}")
            elif c['nbr'] < 0: ev[n_].append([s_, -c['nbr'], 'NEIGHBOUR', False, nm])
        for o in range(6):
            if o != s_:
                if c['others'] > 0: gain[o] += c['others']; recv[o] += c['others']; det[o].append(f"S{s_}'s {nm} gave you +{c['others']}")
                elif c['others'] < 0 and (not c.get('others_geq') or start[o] > start[s_]): ev[o].append([s_, -c['others'], 'AREA', False, nm])
        if t is not None and c['needs_target']:
            if c['target'] > 0:
                gain[t] += c['target']; recv[t] += c['target']; det[t].append(f"S{s_}'s {nm} gave you +{c['target']}")
            elif c['target'] < 0: ev[t].append([s_, -c['target'], 'TARGETED', False, nm, False, 'PLAIN HIT'])
            if c['steal']: ev[t].append([s_, c['steal'], 'TARGETED', True, nm, False, 'STEAL'])
            if c['kind'] == 'virtue' and (c['target'] > 0 or c['ward_target']):
                s['gave'].append([r, s_, t]); pair = sorted([s_, t])
                back = [f for f in s['live'] if f[1] == t and f[2] == s_ and f[0] < r and r - f[0] <= 3]
                if back and s['settles'][s_] < 2 and s['settles'][t] < 2 and pair not in s['settled_pairs']:
                    s['settled_pairs'].append(pair); s['settle_rounds'][f'{pair[0]}-{pair[1]}'] = r; s['settles'][s_] += 1; s['settles'][t] += 1
                    gain[s_] += 2; gain[t] += 2
                    det[s_].append(f"SETTLE with S{t}: +2 each (Favours stay live, either of you can still Betray)"); det[t].append(f"SETTLE with S{s_}: +2 each (Favours stay live, either of you can still Betray)")
                else:
                    anyfav = [f for f in s['live'] + s['old'] if f[1] == t and f[2] == s_ and f[0] < r]
                    if anyfav:
                        why = ('you already Settled with them' if pair in s['settled_pairs'] else ('one of you already has 2 Settles' if (s['settles'][s_] >= 2 or s['settles'][t] >= 2) else 'their Favour to you is older than 3 rounds (expired for Settling)'))
                        det[s_].append(f"No SETTLE with S{t}: {why}")
                    elif any(f[0] == r and f[1] == t and f[2] == s_ for f in s['live']):
                        det[s_].append(f"No SETTLE with S{t}: their Favour to you arrived this same round")
                s['live'].append([r, s_, t])
                if s['favw'][s_] < 3: s['favw'][s_] += 1; new_wards[s_] += 1; det[s_].append(f"FAVOUR WARD: giving a Favour to S{t} gave you a Ward (protects from next round; {s['favw'][s_]}/3 Favour Wards this game)")
                else: det[s_].append("No Favour Ward (you already got 3 this game)")
            if c.get('expose') and r in (1, 7): det[s_].append("Scandal peek only works in rounds 2-6: no peek this round")
            elif c.get('expose') and s['fates'][t]:
                nmf = rng.choice(s['fates'][t]); det[s_].append(f"SCANDAL peek: S{t} holds '{nmf}' (family {FAMILY_OF[nmf]})")
        if c['hit_leader']:
            m = max(start[i] for i in range(6) if i != s_); ld = [i for i in range(6) if i != s_ and start[i] == m]
            ev[min(ld)].append([s_, c['hit_leader'], 'TARGETED', True, nm, False, 'PLAIN HIT'])
    srt = sorted(start, reverse=True); runaway = [start[i] == srt[0] and srt[0] - srt[1] >= 8 for i in range(6)]
    if r == 7:
        cnt = {}
        for s_ in [(strike_start(g) + j) % 6 for j in range(6)]:
            fs = acts[s_].get('final_strike')
            if fs is not None:
                cnt[fs] = cnt.get(fs, 0) + 1
                if cnt[fs] > 3:
                    det[s_].append(f"Your Final Strike on S{fs} was VOID (S{fs} already faced 3 Strikes): nothing paid"); continue
                gain[s_] -= 2; det[s_].append(f"You paid 2 VP for a Final Strike on S{fs}")
                ev[fs].append([s_, 7 if runaway[fs] else 5, 'FINAL', False, 'Final Strike', True])
    for i in range(6):
        if own[i] > 11:
            ex = own[i] - 11; gain[i] -= ex; det[i].append(f"(round gain cap: {ex} VP of your own card, theme, streak and stash bonuses was ignored; the cap is 11)")
    for i in range(6):
        if recv[i] > 7:
            ex = recv[i] - 7; gain[i] -= ex; det[i].append(f"(receiving cap: {ex} VP gained from other players' cards this round was ignored; the cap is 7)")
    lostc = [0] * 6; bounty_done = set(); leaders0 = s['leaders'][-1]
    reset = [False] * 6; smited = set()
    for v in range(6):
        events = sorted(ev[v], key=lambda x: x[0]); ward_used = False; sanct_used = False; taken = 0; landed = []
        for e in events:
            src, amt, typ, stl, nm = e[:5]; unb = len(e) > 5 and e[5]
            if wards[v] and not ward_used and not unb:
                ward_used = True; wards[v] -= 1
                det[v].append(f"Your Ward blocked a {TYPLAB[typ]} effect ({amt} VP) from an unknown player"); det[src].append((f"Your {nm} on S{v} was blocked by a Ward" + (" (it would have been a Betrayal: no Betrayal earned)" if any(f[1] == v and f[2] == src and f[0] < r for f in s['live'] + s['old']) and typ == 'TARGETED' else "")) if typ == 'TARGETED' else f"Your {nm} ({TYPLAB[typ]}) hit on S{v} was blocked by a Ward")
                continue
            a2 = amt
            if halo[v] and kinds_now[v] == 'virtue' and not sanct_used and not unb:
                sanct_used = True; a2 = max(0, a2 - 1)
                det[v].append(f"Sanctuary (you are Haloed): the first harmful effect against you this round was reduced by 1 VP ({amt} -> {a2})")
                if a2 <= 0:
                    det[src].append(f"Your {nm} on S{v} did nothing (Sanctuary: S{v} is Haloed)" + (" - no Betrayal: no VP was removed" if typ == 'TARGETED' and any(f[1] == v and f[2] == src and f[0] < r for f in s['live'] + s['old']) else "")); continue
            room = (12 if (r == 7 and runaway[v]) else CAPR) - taken
            if a2 > room: det[v].append(f"(round cap: {a2 - room} VP of a {TYPLAB[typ]} effect ignored)"); a2 = room
            if a2 <= 0:
                det[src].append(f"Your {nm} on S{v} did nothing (round cap)")
                if typ == 'TARGETED': landed.append((e, 0))
                continue
            taken += a2; landed.append((e, a2))
        for e, amt in landed:
            src, _, typ, stl, nm = e[:5]; sub = e[6] if len(e) > 6 else ''; real = amt > 0
            if real:
                lostv[v] += amt; gain[v] -= amt
                if typ != 'FINAL': lostc[v] += amt
                thm_ = (" (the attacker's card was " + ("" if CARD_BY_ID[plays[src][0]]['pair'] == th else "NOT ") + "the round's THEME card)") if typ == 'TARGETED' else ""
                det[v].append(f"S{src}'s Final Strike cost you {amt} VP" if typ == 'FINAL' else f"a {TYPLAB[typ]} effect" + (f" [{sub}]" if sub else "") + thm_ + f" cost you {amt} VP (attacker and card unknown: only you and the attacker know it happened)")
                if stl: gain[src] += amt; det[src].append(f"your {nm} took {amt} VP from S{v}")
                else: det[src].append(f"your {nm} cost S{v} {amt} VP")
                if typ == 'FINAL':
                    if v in leaders0:
                        gain[src] += 1; det[src].append(f"FINAL STRIKE BOUNTY +1 (S{v} was an exact leader at the start of the round)")
                else: s['harm_any'].append([r, src, v, amt])
            if typ == 'TARGETED':
                if real: s['harm_landed'].append([r, src, v, amt])
                if real and nm == 'Rumour': s['nostash'][v] = 1; det[v].append("Rumour: your next Stash bonus is lost")
                sm_ = 0
                if real and halo[v] and (src, v) not in smited:
                    sm_ = 3 if hlen[v] >= 4 else 2; smited.add((src, v)); s['smite'].append([r, src, v])
                favs = [f for f in s['live'] if f[1] == v and f[2] == src and f[0] < r and r - f[0] <= 3]
                if r == 7: favs += [f for f in s['old'] if f[1] == v and f[2] == src and f[0] < r]
                bt_ = 0
                if favs and [src, v] not in s['bet_pairs'] and s['betrayals'][src] < 2:
                    pk = f"{min(src, v)}-{max(src, v)}"; settled = pk in s['settle_rounds'] and r - s['settle_rounds'][pk] <= 3
                    bt_ = 1 if settled else 3
                    s['bet_pairs'].append([src, v]); s['bet_log'].append([r, src, v]); s['betrayals'][src] += 1; gain[v] += 2; ins[v] = True
                    det[v].append(f"That hit by S{src} was a BETRAYAL of your Favour (Favour insurance +2 for you; Wounded does not pay this round). No Ward for you.")
                    det[src].append(f"BETRAYAL of S{v}'s Favour from round {favs[0][0]}" + (" (you Settled with them within 3 rounds: Betrayal base is only +1)" if settled else " (base +3)"))
                elif any(gg[0] == r and gg[1] == v and gg[2] == src for gg in s['gave']):
                    det[src].append(f"No Betrayal: S{v}'s Favour to you arrived this same round (a Favour must be from an earlier round)")
                elif any(f[1] == v and f[2] == src and f[0] < r for f in s['live'] + s['old']):
                    why = ("you already Betrayed this player once (once per pair)" if [src, v] in s['bet_pairs'] else ("you already have 2 Betrayals" if s['betrayals'][src] >= 2 else "their Favour is older than 3 rounds (the window expired)"))
                    det[src].append(f"No Betrayal of S{v}: {why}")
                paid = max(sm_, bt_)
                if paid: gain[src] += paid
                if bt_ and sm_: det[src].append(f"SMITE counted (S{v} was Haloed) but Betrayal and Smite do not both pay on one card: you were paid the larger, +{paid}")
                elif bt_: det[src].append(f"BETRAYAL +{bt_}")
                elif sm_: det[src].append(f"SMITE +{sm_} (S{v} was Haloed)")
        if lostc[v] >= 2: reset[v] = True
    # favours expire
    exp = [f for f in s['live'] if r - f[0] >= 3]; s['old'] += exp
    s['live'] = [f for f in s['live'] if r - f[0] < 3]
    brk = []
    for si, tg in sorted(s['pledges'].get(str(r), {}).items(), key=lambda x: int(x[0])):
        si = int(si); c_ = CARD_BY_ID[plays[si][0]]
        if c_['kind'] == 'virtue' and c_['needs_target'] and plays[si][1] == tg and (c_['target'] > 0 or c_['ward_target']):
            if s['pkept'][si] < 3:
                s['pkept'][si] += 1; gain[tg] += 1; gain[si] += 1; det[si].append(f"Pledge to S{tg} KEPT: you and S{tg} each +1 (kept Pledge {s['pkept'][si]}/3 that pay)"); det[tg].append(f"S{si} kept a public Pledge to you: you +1")
            else: det[si].append(f"Pledge to S{tg} KEPT (no VP: only your first 3 kept Pledges pay)"); det[tg].append(f"S{si} kept a public Pledge to you (no VP: they have used their 3 paying Pledges)")
        else:
            if not legal_pledge_card(g, r, si): det[si].append(f"Pledge to S{tg} VOID: you held no legal targeted virtue (no penalty, not announced)"); det[tg].append(f"S{si}'s public Pledge to you was VOID (they held no legal card; not announced to others)")
            else: gain[si] -= 2; gain[tg] += 2; det[si].append(f"Pledge to S{tg} BROKEN: -2 VP (S{tg} gets +2)"); det[tg].append(f"S{si} BROKE a public Pledge to you: you +2"); brk.append(f"S{si}'s Pledge to S{tg} was BROKEN")
    score = [max(start[i] + gain[i], 0) for i in range(6)]
    # wounded
    for i in range(6):
        if lostv[i] >= 3 and not ins[i] and not (start[i] == max(start) and start.count(max(start)) == 1): score[i] += 2; det[i].append("Wounded +2 (you lost 3+ VP to others' cards)")
    # accusations: resolved in seat order; family test uses families held at the START of resolution
    acc_pub = []; fam0 = [set(families(s, i)) for i in range(6)]; stripped_now = set(); s['stripped_last'] = []; acc_targets = set()
    for i, p in enumerate(plays):
        ac = p[2]
        if not ac: continue
        t, gs = ac['seat'], ac.get('fate')
        legal = gs in FATES and FAMILY_OF[gs] in fam0[t]
        if not legal:
            det[i].append(f"ACCUSATION of S{t} ('{gs}'): REJECTED (that family is not publicly held by S{t}); no cost, your Accusation is not used"); continue
        if t in acc_targets:
            det[i].append(f"ACCUSATION of S{t} ('{gs}'): VOID (an earlier Accusation on S{t} already resolved this round); no cost, your Accusation is not used"); continue
        if s['strips'][t] >= 1:
            det[i].append(f"ACCUSATION of S{t} ('{gs}'): VOID (S{t} already lost a Fate to an Accusation; one strip per player per game); no cost, your Accusation is not used"); continue
        acc_targets.add(t)
        s['accused'][i] = 1
        if gs in s['fates'][t]:
            s['fates'][t].remove(gs); s['removed'][t].append(gs); stripped_now.add((t, gs)); s['strips'][t] += 1; s['stripped_last'].append(t); score[i] += 5; s['inq_correct'][i] += 1
            det[i].append(f"ACCUSATION of S{t} ('{gs}'): CORRECT +5"); det[t].append(f"S{i} accused you of '{gs}': CORRECT, Fate '{gs}' is LOST permanently (you will get a 2-Fate replacement offer in the next talk if you hold fewer than 3 Fates)")
            acc_pub.append(f"S{i} accused S{t} of '{gs}': CORRECT")
        else:
            free = False
            if not free: score[i] = max(0, score[i] - 2)
            det[i].append(f"ACCUSATION of S{t} ('{gs}'): WRONG " + ("(no cost: you hold inquisitor)" if free else "-2")); det[t].append(f"S{i} accused you of '{gs}': wrong, no effect")
            acc_pub.append(f"S{i} accused S{t} of '{gs}': wrong")
    if 3 <= r <= 6:
        order_ = sorted(range(6), key=lambda i: (-score[i], i)); L = order_[0]
        if score[L] - score[order_[1]] >= 6:
            low = min((i for i in range(6) if i != L), key=lambda i: (score[i], i))
            if s['tithe_recv'][low] + 2 <= 6:
                score[L] = max(0, score[L] - 2); score[low] += 2; s['tithe_recv'][low] += 2; s['tithe_log'].append([r, L, low])
                det[L].append("TITHE applied: you were the sole leader by 6+ VP, you lose 2 VP (not announced)"); det[low].append("TITHE applied: you gain 2 VP (not announced)")
    if r == 2:
        for i in range(6):
            if 'bulwark' in s['fates'][i]: new_wards[i] += 1; det[i].append("Bulwark: you gain a Ward for round 3")
    for i, a in enumerate(acts):
        st = s['stash'][i]
        if st and st[0] == a['play']: s['stash'][i] = None
        if a.get('reserve'):
            if s['stash'][i]: det[i].append(f"your old stash card {CARD_BY_ID[s['stash'][i][0]]['name']} was lost")
            s['stash'][i] = [a['reserve'], r]
    for i in range(6):
        if reset[i]:
            k_, n_ = newmom[i]
            newmom[i] = [k_, n_ - 1] if n_ - 1 >= 1 else [None, 0]
            det[i].append("A real hit of 2+ VP lowered your streak by 1")
    s['mom'] = newmom
    new_w = [wards[i] + new_wards[i] for i in range(6)]
    pub = [("No Accusations." if not acc_pub else "; ".join(acc_pub) + ".") + (" " + "; ".join(brk) + "." if brk else "") + " How many virtues or sins were played, who played what, targets, Favours, Betrayals and Wards are private."]
    pub.append(momentum_text(s) + ".")
    if r == 7:
        pub.append("REVEAL: " + "; ".join(f"S{i} {CARD_BY_ID[p[0]]['name']}" + (f" on S{p[1]}" if p[1] is not None else "") + (f" + Final Strike on S{acts[i]['final_strike']}" if acts[i].get('final_strike') is not None else "") for i, p in enumerate(plays)) + ".")
    for i in range(6): det[i].append(f"Net VP change this round: {score[i] - start[i]:+d}")
    s['score'] = score; s['wards'] = new_w; s['lost'] = [a + b for a, b in zip(s['lost'], lostc)]; s['lostr'].append(lostc)
    s['rounds'].append(plays); s['hist'].append(score); s['acts'].append(acts); s['log'].append(pub); s['priv'].append(det); save(S)
    return dict(score=score, wards=new_w, gain=gain, lost=lostv, pub=pub, plays=plays, priv=det, start=start)


def result_file(g, r, res, offer=None, seed=0, calls_line='', repl=()):
    S = load(); s = S[g]; th = theme(g, r + 1) if r < 7 else None
    for seat in range(6):
        txt = (f"ROUND {r} RESULT" + (f" / ROUND {r + 1} TALK" if r < 7 else "") + f" ({g.upper()}, you are S{seat}). PUBLIC: " + " ".join(res['pub']) +
               f"\nPRIVATE REPORT (only you see this): " + "; ".join(res['priv'][seat]) +
               f"\n{score_view(s, seat)}. {private_board(s, seat, r)} {families_text(s)}." +
               (f" Round {r + 1} theme: {PAIRS[th][0]}/{PAIRS[th][1]}." if th is not None else "") +
               f"\nYour Fates: {fates_text(g, seat)}. {tally(s, seat)} Your stash for next round: {stash_text(g, r + 1, seat) if r < 7 else 'n/a'}."
               + (f"\n{'REPLACEMENT ' if seat in repl else ''}FATE OFFER ({'your Fate was stripped by an Accusation; ' if seat in repl else ''}pick ONE or null; you may hold at most 3 Fates, at most 2 from the same family): {offer_text(offer[seat])}" if offer and seat in offer and (len(s['fates'][seat]) < 3) else "")
               + (("\nCALL option: if a TARGETED card cost you VP this round (the report says 'targeted effect' plus a type in brackets: PLAIN HIT or STEAL, and whether the attacker's card was the round's THEME card; area, neighbour and Final Strike hits cannot be Called), and it was NOT a Betrayal (Betrayal Calls are not allowed), you may CALL a seat in your reply with \"call\":<seat>: you pay a 1 VP stake and the moderator says only YES/NO publicly. "
                   "YES (that player hit you with a targeted card): they lose 3 VP and their streak drops by 1, and you get your stake back plus 2. If several players Call the same target and are right, only the first in seat order after the target collects; the others just get their stake back. NO: you lose the stake and the named player gains 1 VP. Optional, once per round. "
                   "PLEDGE option (optional, one per round): add \"pledge\":<seat> to announce publicly that you will play a targeted virtue on that player next round: if you do, BOTH of you gain 1 VP (only your first 3 kept Pledges pay); if you hold a legal targeted virtue and do not play it, you lose 2 VP, the named player gains 2 VP, and it is announced as BROKEN; if your hand has none you are told privately and the Pledge is void with no penalty and only the named player is told. "
                   "Reply JSON only (TALK format): " + ('{"say":"...","whisper":{"<seat>":"..."},"call":<seat> or null,"pledge":<seat> or null,"fate":"<name from the offer>" or null,"note":"optional"}' if offer and seat in offer and (len(s['fates'][seat]) < 3) else '{"say":"...","whisper":{"<seat>":"..."},"call":<seat> or null,"pledge":<seat> or null,"note":"optional"}'))
                  if r < 7 else "\nThis was the final round. Send your DEBRIEF when asked."))
        open(f'{BASE}/play/{g}_r{r}_res_S{seat}.txt', 'w').write(txt)


def rank_order(score, virt): return sorted(range(6), key=lambda i: (-score[i], -virt[i], i))


def finalize(g):
    S = load(); s = S[g]; R = s['rounds']; base = s['score']
    cards = [[CARD_BY_ID[r[i][0]] for r in R] for i in range(6)]
    kind = [[c['kind'] for c in cs] for cs in cards]; virt = [k.count('virtue') for k in kind]
    order = rank_order(base, virt); top3 = set(order[:3]); top4 = set(order[:4]); res = []
    gains = [base[j] - s['hist'][3][j] for j in range(6)]
    for i in range(6):
        hm = [harmful(c) for c in cards[i]]
        earlyv = kind[i][:4].count('virtue'); earlys = kind[i][:4].count('sin'); late = kind[i][4:]
        def hit(n):
            if n == 'saint': return virt[i] >= 6 and i in top3
            if n == 'peacemaker': return not any(hm) and s['settles'][i] >= 1 and len({t for rr, a, t in s['gave'] if a == i}) >= 3
            if n == 'heretic': return len({r_ for r_, a, v in s['smite'] if a == i}) >= 3
            if n == 'wolf': return len({v for r_, a, v, amt in s['harm_landed'] if a == i}) >= 4
            if n == 'glutton': return kind[i].count('sin') >= 5
            if n == 'backstabber': return s['betrayals'][i] >= 2
            if n == 'fallen': return earlyv >= 3 and all(k == 'sin' for k in late) and s['betrayals'][i] >= 1
            if n == 'redeemed':
                ok = earlys >= 3 and sum(1 for k in late if k == 'virtue') >= 3
                ok2 = any(f[1] == i and f[0] >= 5 and any(h[1] == i and h[2] == f[2] and h[0] < f[0] for h in s['harm_landed']) for f in s['gave'])
                return ok and ok2
            if n == 'inquisitor': return s['inq_correct'][i] >= 1
            if n == 'bulwark': return sum(1 for x in s['lostr'] if x[i] <= 1) >= 6
            if n == 'late_bloomer': return (1 + sum(1 for j in range(6) if s['hist'][3][j] > s['hist'][3][i])) - (1 + sum(1 for j in range(6) if base[j] > base[i])) >= 2
            if n == 'survivor': return s['lost'][i] >= 6 and i in top3
            return False
        held = list(s['fates'][i]); outs = [(n, hit(n)) for n in held]; nh = sum(1 for n, ok in outs if ok)
        raw = sum(FATES[n]['reward'] for n, ok in outs if ok); stack = STACK_BONUS.get(min(nh, 3), 0); bonus = min(FATE_CAP, raw + stack)
        res.append(dict(seat=i, base=base[i], held=held, removed=s['removed'][i], hits=[n for n, ok in outs if ok], misses=[n for n, ok in outs if not ok],
                        raw=raw, stack=stack, bonus=bonus, final=base[i] + bonus, betrayals=s['betrayals'][i], settles=s['settles'][i]))
    return dict(base=base, results=res, winner=max(range(6), key=lambda i: (res[i]['final'], virt[i], -i)))
