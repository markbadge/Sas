"""What each seat is allowed to see. Views are built from engine state, never from raw state.

- bot_talk_text / bot_act_text: text prompts (ported from moderator14.result_file / act_files / talk_r1_files)
- human_view: structured VIEW object for the play client
Bots and humans get the same information.
"""
from .engine import N, band


def card_line(g, cid, th):
    c = g.card[cid]
    return f"{cid} {c['name']}{'*' if c['pair'] == th else ''} ({c['kind']}): {c['text']}" + (" [needs target]" if c['needs_target'] else "")


def hand_text(g, r, seat):
    return " | ".join(card_line(g, x, g.theme(r)) for x in g.ensure_hand(r)[seat])


def stash_text(g, r, seat):
    st = g.s['stash'][seat]
    if not st:
        return "empty"
    return card_line(g, st[0], g.theme(r)) + f" [stored since round {st[1]}; playing it now gives +{g.stash_bonus(r, seat)} VP stash bonus]"


def fates_text(g, seat):
    f = g.s['fates'][seat]
    return "; ".join(f"{n}: {g.fates[n]['desc']} (+{g.fates[n]['reward']})" for n in f) or "none yet"


def families_text(g):
    return "Public Fate families currently held: " + "; ".join(f"S{i}: {'/'.join(g.families(i)) or 'none'}" for i in range(N))


def score_view(g, seat, exact=False):
    sc = g.s['score']
    if exact:
        return "FINAL ROUND: ALL EXACT VP ARE REVEALED: " + ", ".join(f"S{i} {sc[i]}" for i in range(N)) + f" (you are S{seat})"
    return f"Your VP: {sc[seat]}. Other players' VP (bands of 5): " + ", ".join(f"S{i} {band(sc[i])}" for i in range(N) if i != seat)


def board_data(g, seat, r):
    """Structured private board (shared by the text view and the client)."""
    s = g.s
    live = g.cfg['favour']['live_rounds']
    given = [dict(seat=b, round=fr, expires=fr + live) for fr, a, b in s['live'] if a == seat]
    recv = [dict(seat=a, round=fr, expires=fr + live, betray=not [seat, a] in s['bet_pairs']) for fr, a, b in s['live'] if b == seat]
    if r == g.cfg['rounds']:
        recv += [dict(seat=a, round=fr, expires=None, betray=not [seat, a] in s['bet_pairs'], expired=True) for fr, a, b in s['old'] if b == seat]
    first = g.cfg['accusation']['first_round']
    return dict(given=given, received=recv, betrayals=s['betrayals'][seat], settles=s['settles'][seat],
                pledges_kept=s['pkept'][seat], ward=bool(s['wards'][seat]),
                streak=dict(kind=s['mom'][seat][0], length=s['mom'][seat][1]),
                accusation='used' if s['accused'][seat] else ('available' if r >= first else 'not yet'))


def private_board(g, seat, r):
    b = board_data(g, seat, r)
    given = [f"S{x['seat']} (round {x['round']}, expires after round {x['expires']})" for x in b['given']]
    recv = []
    for x in b['received']:
        if x.get('expired'):
            recv.append(f"S{x['seat']} (round {x['round']}, expired but counts in round 7)")
        else:
            recv.append(f"S{x['seat']} (round {x['round']}, expires after round {x['expires']}; " + ("Betrayal still available" if x['betray'] else "you already used a Betrayal on this player") + ")")
    st = b['streak']
    acc = {'used': 'USED', 'available': 'available (rounds 4-7)', 'not yet': 'not yet (from round 4)'}[b['accusation']]
    return (f"PRIVATE BOARD: Favours you gave that are still live: {', '.join(given) or 'none'}. Favours you received that are still live (you may Betray the giver): {', '.join(recv) or 'none'}. "
            f"Betrayals you earned {b['betrayals']}/2; Settles {b['settles']}/2; kept paying Pledges {b['pledges_kept']}/3 (a Settle does NOT remove Favours: you can still Betray a live Favour afterwards). Your Ward: {'yes' if b['ward'] else 'no'}. "
            f"Your own streak: {st['kind'] or 'none'} x{st['length']}. Accusation: {acc}.")


def tally(g, seat):
    s = g.s
    R = s['rounds']
    kinds = []
    harm = 0
    for p in R:
        c = g.card[p[seat][0]]
        kinds.append(c['kind'])
        harm += 1 if g.harmful(c) else 0
    low = sum(1 for x in s['lostr'] if x[seat] <= 1)
    low2 = sum(1 for x in s['lostr'] if x[seat] <= 2)
    hrounds = len({r for r, a, v, amt in s['harm_landed'] if a == seat})
    hvict = len({v for r, a, v, amt in s['harm_landed'] if a == seat})
    smr = len({r for r, a, v in s['smite'] if a == seat})
    tv = len({t for rr, a, t in s['gave'] if a == seat})
    return (f"YOUR TALLIES: rounds with virtue {kinds.count('virtue')}, sin {kinds.count('sin')}, harmful cards {harm}; "
            f"best virtue streak so far {s['maxv'][seat]}; Settles {s['settles'][seat]}; Betrayals {s['betrayals'][seat]}; rounds you landed real harm {hrounds} (targeted harm only, on {hvict} different players, wolf needs 4); "
            f"rounds you hit a Haloed player (Smite) {smr}; targeted virtues given to {tv} different players; VP lost to others' cards {s['lost'][seat]} total, rounds with <=1 lost {low}, rounds with <=2 lost {low2}; correct Accusations {s['inq_correct'][seat]}.")


def offer_text(g, offer):
    return " | ".join(f"{n} (+{g.fates[n]['reward']}, family {g.family_of[n]}): {g.fates[n]['desc']}" for n in offer)


def strike_text(g):
    FS = g.cfg['final_strike']
    return ("\nFINAL ROUND RULES: no streak bonus is paid this round; the round cap is 7 VP (12 VP against a player 8+ ahead of second place); every Favour you hold counts for Betrayal even if older than 3 rounds; at the end every card played and every Final Strike is revealed publicly with its target. "
            f"FINAL STRIKE (optional): in addition to your card you may pay {FS['cost']} VP and name ONE other player in the \"final_strike\" field: they lose {FS['damage']} VP, or {FS['runaway_damage']} VP if that player is 8 or more VP ahead of the second-highest player (a Ward and Sanctuary cannot reduce it; it counts toward the round cap, 7, or 12 for a player 8+ ahead; it is not a card: no Smite, no Betrayal, not harm for wolf/heretic/peacemaker; no Call). A player can suffer at most {FS['max_per_target']} Strikes (later ones are void and refunded). Strikes resolve in seat order starting from the seat set by a die roll: S{g.strike_start()} goes first, then upward and wrapping. EACH valid Strike that lands on a player who was an exact leader at the start of this round (each co-leader counts) earns its striker a +{FS['bounty']} bounty (so a Strike on a leader costs you net 1 VP). The attacker is named publicly at the end.")


CALL_RULES = ("CALL option: if a TARGETED card cost you VP this round (the report says 'targeted effect' plus a type in brackets: PLAIN HIT or STEAL, and whether the attacker's card was the round's THEME card; area, neighbour and Final Strike hits cannot be Called), and it was NOT a Betrayal (Betrayal Calls are not allowed), you may CALL a seat in your reply with \"call\":<seat>: you pay a 1 VP stake and the moderator says only YES/NO publicly. "
              "YES (that player hit you with a targeted card): they lose 3 VP and their streak drops by 1, and you get your stake back plus 2. If several players Call the same target and are right, only the first in seat order after the target collects; the others just get their stake back. NO: you lose the stake and the named player gains 1 VP. Optional, once per round. "
              "PLEDGE option (optional, one per round): add \"pledge\":<seat> to announce publicly that you will play a targeted virtue on that player next round: if you do, BOTH of you gain 1 VP (only your first 3 kept Pledges pay); if you hold a legal targeted virtue and do not play it, you lose 2 VP, the named player gains 2 VP, and it is announced as BROKEN; if your hand has none you are told privately and the Pledge is void with no penalty and only the named player is told. ")


def bot_talk_text(g, seat):
    """Talk prompt for the talk of g.s['round'] (round 1 intro, or the result of the previous round)."""
    s = g.s
    r = s['round']
    offer = g.offer_for(seat)
    repl = seat in s['offer_repl']
    if r == 1:
        th = g.theme_names(1)
        return (f"ROUND 1 TALK (you are S{seat}). Round 1 theme: {th['sin']}/{th['virtue']}. All players start on 2 VP. No hidden roles: everyone is a free player. "
                f"FATE OFFER (pick ONE secret Fate to pursue, or null; you can hold up to 3 over the game, but at most 2 from the same public family (LIGHT or SHADOW)): {offer_text(g, offer)}. "
                'Reply JSON only (TALK format): {"say":"...","whisper":{"<seat>":"..."},"pledge":<seat> or null,"fate":"<name from the offer>" or null,"note":"optional"}')
    pr = r - 1
    th = g.theme_names(r)
    pub = s['log'][pr - 1]
    priv = s['priv'][pr - 1][seat]
    return (f"ROUND {pr} RESULT / ROUND {r} TALK (you are S{seat}). PUBLIC: " + " ".join(pub) +
            "\nPRIVATE REPORT (only you see this): " + "; ".join(priv) +
            f"\n{score_view(g, seat)}. {private_board(g, seat, pr)} {families_text(g)}. Round {r} theme: {th['sin']}/{th['virtue']}."
            f"\nYour Fates: {fates_text(g, seat)}. {tally(g, seat)} Your stash for next round: {stash_text(g, r, seat)}."
            + (f"\n{'REPLACEMENT ' if repl else ''}FATE OFFER ({'your Fate was stripped by an Accusation; ' if repl else ''}pick ONE or null; you may hold at most 3 Fates, at most 2 from the same family): {offer_text(g, offer)}" if offer else "")
            + "\n" + CALL_RULES
            + "Reply JSON only (TALK format): " + ('{"say":"...","whisper":{"<seat>":"..."},"call":<seat> or null,"pledge":<seat> or null,"fate":"<name from the offer>" or null,"note":"optional"}' if offer else '{"say":"...","whisper":{"<seat>":"..."},"call":<seat> or null,"pledge":<seat> or null,"note":"optional"}'))


def public_talk_lines(g, r):
    t = g.s['talks'][str(r)]
    return [dict(s=i, t=t[i]['say']) for i in range(N)]


def public_pledges(g, r):
    t = g.s['talks'][str(r)]
    return [dict(s=i, to=t[i]['pledge']) for i in range(N) if t[i].get('pledge') is not None and t[i]['pledge'] != i]


def pledge_text(g, r):
    pl = [f'S{p["s"]} PLEDGES a targeted virtue to S{p["to"]} this round (kept: BOTH get +1, for the pledger first 3 kept Pledges; broken while holding a legal card: pledger -2, the named player +2, announced)' for p in public_pledges(g, r)]
    return pl


def whispers_to(g, r, seat):
    t = g.s['talks'][str(r)]
    return [dict(s=i, t=t[i]['whisper'][str(seat)]) for i in range(N) if str(seat) in t[i].get('whisper', {})]


def pledge_note(g, r, seat):
    t = g.s['talks'][str(r)][seat]
    if t.get('pledge') is not None and not g.legal_pledge_card(r, seat):
        return f"you hold no targeted virtue that could keep your Pledge to S{t['pledge']}; the Pledge is VOID: no penalty, not announced."
    return None


def news_for(g, r, seat):
    """NEWS lines for the act phase (public Calls plus this seat's own private Call outcomes)."""
    parts = []
    if g.s['news'].get(str(r)):
        parts.append(g.s['news'][str(r)])
    if r > 1:
        parts += [x for x in g.s['priv'][r - 2][seat] if x.startswith('Your Call') or ' Called you' in x]
    note = g.s['call_notes'].get(str(seat))
    if note:
        parts.append(note)
    return " ".join(parts)


def bot_act_text(g, seat):
    s = g.s
    r = s['round']
    th = g.theme_names(r)
    final = r == g.cfg['rounds']
    talks = s['talks'][str(r)]
    pub = "\n".join(f'S{i}: "{talks[i]["say"]}"' for i in range(N))
    pl = pledge_text(g, r)
    if pl:
        pub += "\nPUBLIC PLEDGES: " + "; ".join(pl)
    wh = [f'S{w["s"]}: "{w["t"]}"' for w in whispers_to(g, r, seat)]
    extra = news_for(g, r, seat)
    pn = pledge_note(g, r, seat)
    fs_fmt = ',"final_strike":null or seat (round 7 only)' if final else ''
    return (f"ROUND {r} ACT (you are S{seat}). Theme {th['sin']}/{th['virtue']} (* = in-theme card: theme bonus +2 for the virtue, +2 for the sin). "
            f"{score_view(g, seat, exact=final)}. {g.momentum_text()}. {private_board(g, seat, r)} {families_text(g)}."
            + (f"\nNEWS: {extra}" if extra else "") + (f"\nPLEDGE NOTE (private): {pn}" if pn else "")
            + (strike_text(g) if final else "")
            + f"\nYOUR FATES: {fates_text(g, seat)}\n{tally(g, seat) if s['rounds'] else ''}"
            + f"\nPUBLIC TALK:\n{pub}\nWHISPERS TO YOU:\n" + ("\n".join(wh) or "none")
            + f"\nYOUR DEALT HAND: {hand_text(g, r, seat)}\nYOUR STASH (secret, one card, playable instead of a dealt card): {stash_text(g, r, seat)}\n"
            'Reply JSON only: {"play":"cNN","target":null or seat,"stash":"cNN" or null,"accuse":{"seat":N,"fate":"<fate name>"} (optional, once per game, rounds 4-7, no card slot)' + fs_fmt + ',"note":"optional"}  '
            '(play one card from your dealt hand or stash; optionally move ONE other DEALT card into your stash, replacing and losing any card already there; the rest are discarded)')


def bot_prompt(g, seat):
    return bot_talk_text(g, seat) if g.s['phase'] == 'talk' else bot_act_text(g, seat)


# ------------------------------------------------------------------ human view
def _card_view(g, cid, th, **extra):
    c = g.card[cid]
    return dict(id=cid, name=c['name'], kind=c['kind'], text=c['text'], target=bool(c['needs_target']), theme=c['pair'] == th, **extra)


def _fate_view(g, n):
    f = g.fates[n]
    return dict(name=n, reward=f['reward'], family=f['family'], desc=f['desc'])


def human_view(g, seat):
    """Structured VIEW for the client. Contains only what `seat` may know."""
    s = g.s
    r = s['round']
    over = s['phase'] == 'over'
    last_round = g.cfg['rounds']
    stage = s['phase']
    shown = last_round if over else r  # round whose context we describe
    th_i = g.theme(min(shown, last_round))
    exact = (stage == 'act' and r == last_round) or over
    seats = []
    for i in range(N):
        token = 'HALOED' if g.haloed(i) else ('HOT' if g.hot(i) else 'none')
        seats.append(dict(s=i, band=str(s['score'][i]) if (i == seat or exact) else band(s['score'][i]), token=token,
                          fam='/'.join(g.families(i)), exact=bool(exact or i == seat)))
    v = dict(mode='live', game=s['game_id'], seat=seat, round=min(r, last_round), rounds=last_round, stage=stage,
             theme=g.theme_names(min(shown, last_round)), vp=s['score'][seat], seats=seats, final=(stage == 'act' and r == last_round),
             strike_first=g.strike_start() if (stage == 'act' and r == last_round) else None,
             board=board_data(g, seat, r if not over else last_round), fates=[_fate_view(g, n) for n in s['fates'][seat]],
             tallies=tally(g, seat) if s['rounds'] else '', families={str(i): g.families(i) for i in range(N)},
             accused=bool(s['accused'][seat]), momentum=g.momentum_text(), notices=[])
    _ = th_i
    # last-round private report and public lines
    done = len(s['rounds'])
    v['report'] = list(s['priv'][done - 1][seat]) if done else []
    v['report_round'] = done
    v['public'] = list(s['log'][done - 1]) if done else []
    v['notices'] = [f"Round {done}: your choice was altered: " + "; ".join(fx) for fx in [s['fixes'].get(str(done), {}).get(str(seat), [])] if fx]
    v['feed'], v['whispers'], v['pledges'], v['news'] = [], [], [], ''
    v['offer'], v['offer_label'] = [], 'Fate offer'
    v['hand'], v['stash'], v['can_call'] = [], None, False
    if stage in ('talk', 'act') and str(r) in s['talks']:
        v['feed'] = public_talk_lines(g, r)
        v['whispers'] = whispers_to(g, r, seat)
        v['pledges'] = public_pledges(g, r)
    if stage == 'talk':
        offer = g.offer_for(seat)
        v['offer'] = [_fate_view(g, n) for n in offer]
        v['offer_label'] = 'REPLACEMENT Fate offer' if seat in s['offer_repl'] else 'Fate offer'
        v['can_call'] = r > 1 and any(rr == r - 1 and vv == seat for rr, a, vv, amt in s['harm_landed']) and not any(b[0] == r - 1 and b[2] == seat for b in s['bet_log'])
        v['submitted'] = str(seat) in s['talks_in']
    if stage == 'act':
        th = g.theme(r)
        v['hand'] = [_card_view(g, cid, th) for cid in g.ensure_hand(r)[seat]]
        st = s['stash'][seat]
        if st:
            v['stash'] = _card_view(g, st[0], th, since=st[1], bonus=g.stash_bonus(r, seat))
        v['news'] = news_for(g, r, seat)
        pn = pledge_note(g, r, seat)
        if pn:
            v['notices'].append('Pledge note: ' + pn)
        v['submitted'] = str(seat) in s['acts_in']
    v['waiting_on'] = len(g.pending())
    if over:
        v['summary'] = summary(g)
    return v


def summary(g):
    """End-of-game summary: every seat's final score, Fates held/hit, round log. Only valid once the game is over."""
    s = g.s
    f = s['final']
    rounds = []
    for r, plays in enumerate(s['rounds'], 1):
        rounds.append(dict(round=r, theme=g.theme_names(r)['label'], public=s['log'][r - 1],
                           plays=[dict(seat=i, card=g.card[p[0]]['name'], kind=g.card[p[0]]['kind'], target=p[1]) for i, p in enumerate(plays)],
                           scores=s['hist'][r - 1]))
    return dict(winner=f['winner'], seats=f['results'], rounds=rounds)
