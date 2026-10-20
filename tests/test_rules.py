"""Unit tests per rule bullet (spec section 5), each on a small hand-built state."""
import copy

from ssengine.engine import Game

NAME = {}


def mk(**over):
    g = Game.new(1, human_seats=())
    g.cfg = copy.deepcopy(g.cfg)
    g.s['themes'] = [5] * 7              # Gluttony/Temperance: none of the cards used below are in theme
    for k, v in over.items():
        g.s[k] = v
    for c in g.rules.cards:
        NAME[c['name']] = c['id']
    return g


FILLER = 'Hard Work'                       # virtue, +3, no target, pair Sloth/Diligence


def act(card, target=None, **kw):
    d = dict(play=NAME[card], target=target, reserve=None, accuse=None, final_strike=None)
    d.update(kw)
    return d


def run(g, r, plays, hands=None):
    """plays: {seat: (card, target) | dict}; everyone else plays the filler. Hands are forced to contain the played cards."""
    acts = []
    for i in range(6):
        p = plays.get(i, (FILLER, None))
        acts.append(p if isinstance(p, dict) else act(p[0], p[1]))
    H = [[a['play']] + [c for c in ('c15', 'c25', 'c39') if c != a['play']][:2] for a in acts]
    for i, h in (hands or {}).items():
        H[i] = h
    g.s['hands'][str(r)] = H
    return g.resolve(r, acts)


def test_hubris_equal_scores_hits_nobody_and_strictly_greater_is_hit():
    g = mk(score=[5] * 6)
    run(g, 1, {0: ('Hubris', None)})
    assert g.s['score'][1:] == [8] * 5
    g = mk(score=[5, 9, 5, 5, 5, 5])
    run(g, 1, {0: ('Hubris', None)})
    assert g.s['score'][1] == 9 + 3 - 1 and g.s['score'][2] == 8


def test_ward_blocks_first_in_seat_order_and_is_consumed():
    g = mk(score=[10] * 6, wards=[0, 0, 0, 1, 0, 0])
    res = run(g, 2, {0: ('Smash', 3), 1: ('Sabotage', 3)})
    assert g.s['score'][3] == 10 + 3 - 3 + 2     # S1's hit lands (Wounded +2), S0's was blocked
    assert g.s['wards'][3] == 0
    assert any('blocked by a Ward' in x for x in res['priv'][0])


def test_sanctuary_only_if_haloed_victim_played_a_virtue():
    g = mk(score=[10] * 6, mom=[[None, 0]] * 3 + [['virtue', 2]] + [[None, 0]] * 2)
    run(g, 3, {0: ('Name-drop', 3)})
    assert g.s['lost'][3] == 1
    g = mk(score=[10] * 6, mom=[[None, 0]] * 3 + [['virtue', 2]] + [[None, 0]] * 2)
    run(g, 3, {0: ('Name-drop', 3), 3: ('Boast', None)})
    assert g.s['lost'][3] == 2


def test_own_gain_cap_is_config_driven():
    g = mk(score=[10] * 6)
    g.cfg['gain_cap'] = 4
    run(g, 1, {0: ('Boast', None)})
    assert g.s['score'][0] == 14                 # 4, not 4 + sin base


def test_receiving_cap_7():
    g = mk(score=[10] * 6)
    run(g, 1, {0: ('Helping Hand', 1), 2: ('Alms', 1)})
    assert g.s['score'][1] == 10 + 3 + 7


def test_round_loss_cap_5_and_final_cap_7():
    g = mk(score=[20] * 6)
    run(g, 2, {0: ('Smash', 3), 1: ('Smash', 3), 2: ('Smash', 3)})
    assert g.s['lost'][3] == 5
    g = mk(score=[20] * 6)
    run(g, 7, {0: ('Smash', 3), 1: ('Smash', 3), 2: ('Smash', 3)})
    assert g.s['lost'][3] == 7


def test_tithe_pays_lowest_seat_and_respects_6_cap():
    g = mk(score=[20, 10, 10, 10, 10, 10])
    run(g, 3, {})
    assert g.s['score'][0] == 21 and g.s['score'][1] == 15 and g.s['score'][2] == 13
    g = mk(score=[20, 10, 10, 10, 10, 10], tithe_recv=[0, 6, 0, 0, 0, 0])
    run(g, 3, {})
    assert g.s['score'][0] == 23 and g.s['score'][1] == 13


def test_final_strike_7_on_runaway_3_strike_cap_and_refund():
    g = mk(score=[20, 10, 10, 10, 10, 10])
    order = [(g.strike_start() + j) % 6 for j in range(6)]
    strikers = [s for s in order if s != 0][:5]
    plays = {s: act(FILLER, final_strike=0) for s in strikers}
    res = run(g, 7, plays)
    valid, void = strikers[:3], strikers[3:]
    assert g.s['score'][0] == 20 + 3 - 12        # three 7s capped at 12
    for s in valid[:2]:
        assert g.s['score'][s] == 10 + 3 - 2 + 1  # cost 2, leader bounty 1
    assert g.s['score'][valid[2]] == 10 + 3 - 2   # cap already reached: no VP lost, so no bounty (as moderator14)
    for s in void:
        assert g.s['score'][s] == 10 + 3          # refunded
        assert any('VOID' in x for x in res['priv'][s])


def test_final_strike_5_on_non_runaway_ignores_ward():
    g = mk(score=[12, 10, 10, 10, 10, 10], wards=[1, 0, 0, 0, 0, 0])
    run(g, 7, {1: act(FILLER, final_strike=0)})
    assert g.s['score'][0] == 12 + 3 - 5 and g.s['wards'][0] == 1


def test_pledge_kept_broken_and_void():
    hand_with = ['c09', 'c15', 'c25']            # Alms is a legal targeted virtue
    g = mk(score=[10] * 6, pledges={'1': {'0': 1}})
    run(g, 1, {0: ('Alms', 1)}, hands={0: hand_with})
    assert g.s['score'][0] == 10 + 2 + 1 and g.s['score'][1] == 10 + 3 + 4 + 1
    g = mk(score=[10] * 6, pledges={'1': {'0': 1}})
    res = run(g, 1, {}, hands={0: hand_with})
    assert g.s['score'][0] == 10 + 3 - 2 and g.s['score'][1] == 10 + 3 + 2
    assert any('BROKEN' in x for x in res['pub'])
    g = mk(score=[10] * 6, pledges={'1': {'0': 1}})
    res = run(g, 1, {}, hands={0: ['c15', 'c25', 'c39']})
    assert g.s['score'][0] == 13 and not any('BROKEN' in x for x in res['pub'])


def betray_state(**over):
    return mk(score=[10] * 6, live=[[1, 1, 0]], gave=[[1, 1, 0]], **over)


def test_betrayal_pays_insurance_and_blocks_wounded():
    g = betray_state()
    res = run(g, 2, {0: ('Smash', 1)})
    assert g.s['betrayals'][0] == 1
    assert g.s['score'][0] == 10 + 2 + 3                 # Smash self +2, Betrayal +3 (filler excluded)
    assert g.s['score'][1] == 10 + 3 - 4 + 2             # insurance +2, no Wounded despite losing 4
    assert any('BETRAYAL' in x for x in res['priv'][1])


def test_betrayal_failure_reasons():
    g = betray_state(wards=[0, 1, 0, 0, 0, 0])
    res = run(g, 2, {0: ('Smash', 1)})
    assert any('would have been a Betrayal' in x for x in res['priv'][0]) and g.s['betrayals'][0] == 0
    g = betray_state(bet_pairs=[[0, 1]])
    res = run(g, 2, {0: ('Smash', 1)})
    assert any('once per pair' in x for x in res['priv'][0])
    g = betray_state(betrayals=[2, 0, 0, 0, 0, 0])
    res = run(g, 2, {0: ('Smash', 1)})
    assert any('2 Betrayals' in x for x in res['priv'][0])
    g = betray_state()
    res = run(g, 1, {0: ('Smash', 1)})                   # same-round: favour from round 1 is not earlier
    assert any('window' in x or 'same round' in x or 'once' in x for x in res['priv'][0]) or g.s['betrayals'][0] == 0


def test_settle_gives_both_two_and_keeps_favours():
    g = mk(score=[10] * 6, live=[[1, 1, 0]], gave=[[1, 1, 0]])
    run(g, 2, {0: ('Alms', 1)})
    assert g.s['settles'][0] == 1 and g.s['settles'][1] == 1
    assert [1, 1, 0] in g.s['live'] and [2, 0, 1] in g.s['live']


def test_wounded_pays_unless_sole_leader_or_insured():
    g = mk(score=[10, 10, 10, 10, 10, 10])
    run(g, 2, {0: ('Smash', 1)})
    assert g.s['score'][1] == 10 + 3 - 4 + 2
    g = mk(score=[10, 14, 10, 10, 10, 10])               # S1 sole leader
    run(g, 2, {0: ('Smash', 1)})
    assert g.s['score'][1] == 14 + 3 - 4


def test_call_yes_and_no():
    g = mk(score=[10] * 6)
    run(g, 1, {0: ('Smash', 1)})
    before = list(g.s['score'])
    g.apply_calls(1, {1: 0})
    assert g.s['score'][1] == before[1] - 1 + 1 + 2 and g.s['score'][0] == before[0] - 3
    g = mk(score=[10] * 6)
    run(g, 1, {0: ('Smash', 1)})
    before = list(g.s['score'])
    g.apply_calls(1, {1: 4})                              # S4 did not hit S1
    assert g.s['score'][1] == before[1] - 1 and g.s['score'][4] == before[4] + 1


def test_accusation_correct_wrong_and_rejected():
    g = mk(score=[10] * 6, fates=[[], ['wolf'], [], [], [], []])
    run(g, 4, {0: act(FILLER, accuse={'seat': 1, 'fate': 'wolf'})})
    assert g.s['fates'][1] == [] and 'wolf' in g.s['removed'][1] and g.s['score'][0] == 10 + 3 + 5
    g = mk(score=[10] * 6, fates=[[], ['wolf'], [], [], [], []])
    run(g, 4, {0: act(FILLER, accuse={'seat': 1, 'fate': 'glutton'})})
    assert g.s['score'][0] == 10 + 3 - 2
    g = mk(score=[10] * 6, fates=[[], ['wolf'], [], [], [], []])
    run(g, 4, {0: act(FILLER, accuse={'seat': 1, 'fate': 'saint'})})   # LIGHT not held: rejected, free
    assert g.s['score'][0] == 13 and g.s['accused'][0] == 0


def test_streak_virtue_and_sin_and_final_round():
    g = mk(score=[10] * 6, mom=[['virtue', 1]] * 6)
    run(g, 2, {})
    assert g.s['score'][0] == 10 + 3 + 1
    g = mk(score=[10] * 6, mom=[['virtue', 4]] * 6)
    run(g, 5, {})
    assert g.s['score'][0] == 13                          # fatigue
    g = mk(score=[10] * 6, mom=[['virtue', 2]] * 6)
    run(g, 7, {})
    assert g.s['score'][0] == 13                          # no streak in the last round


def test_stash_bonus():
    g = mk(score=[10] * 6, stash=[[NAME['Hard Work'], 1]] + [None] * 5)
    run(g, 4, {0: act('Hard Work')})
    assert g.s['score'][0] == 10 + 3 + 2


def test_fate_cap_and_stack():
    g = mk(score=[10] * 6)
    g.s['rounds'] = [[['c15', None, None]] * 6 for _ in range(7)]
    g.s['hist'] = [[10] * 6] * 7
    g.s['fates'][0] = ['saint', 'glutton']
    f = g.finalize()
    assert f['results'][0]['hits'] == ['saint'] and f['results'][0]['bonus'] == 6
