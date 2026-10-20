"""v9 data: v8 cards (no Inquisition card), 11 v9 Fates, families."""
import copy
from ss_data_v8 import PAIRS, CARDS as _C8, CARD_BY_ID as _B8

CARDS = copy.deepcopy(_C8)
CARD_BY_ID = {c['id']: c for c in CARDS}
CARD_BY_ID['c14']['text'] = "you +2, target -1, privately learn ONE random Fate of the target (name and family)"

FATES = {
    'saint': dict(reward=7, desc='Reach a virtue streak of 5 or more in a row (your Momentum streak, which a real hit of 2+ VP resets) and finish top 3 on base VP.'),
    'peacemaker': dict(reward=6, desc='Settle with two different players and never play a card with a harmful effect.'),
    'redeemed': dict(reward=7, desc='Play a sin in 3+ of rounds 1-4, then a virtue in 3+ of rounds 5-7, including a targeted virtue on a player you harmed earlier.'),
    'fallen': dict(reward=9, desc='Play a virtue in 3+ of rounds 1-4, then play a sin in ALL of rounds 5-7, and earn at least 1 Betrayal.'),
    'heretic': dict(reward=7, desc='Land real harm with a targeted card on a Haloed player (virtue streak of 2+ at the start of the round) in 3+ different rounds.'),
    'wolf': dict(reward=7, desc='Land real harm (any card, at least 1 VP actually lost by the victim) in 4+ different rounds, on 3+ different players in total.'),
    'glutton': dict(reward=5, desc='Play a sin from Pride, Greed, Lust or Gluttony 5+ times.'),
    'backstabber': dict(reward=7, desc='Earn 2 Betrayals.'),
    'inquisitor': dict(reward=5, desc='Make 1 correct Accusation.'),
    'bulwark': dict(reward=7, desc='Lose at most 1 VP to other players\' cards in each of 5+ rounds. You also gain one Ward at the start of round 3 (only if held by then; taking it after round 2 gives that Ward at once, after round 4 none).'),
    'late_bloomer': dict(reward=7, desc='Offered only to a player in the bottom 3 on VP. Gain more VP in rounds 5-7 combined than any other player (strictly the most).'),
}
STACK_BONUS = {2: 2, 3: 3}
FATE_CAP = 12
FAMILY = {'PURE': ['saint', 'peacemaker'], 'ARC': ['fallen', 'redeemed'],
          'HUNT': ['heretic', 'wolf', 'glutton', 'backstabber', 'inquisitor'], 'SHIELD': ['bulwark', 'late_bloomer']}
FAMILY_OF = {n: f for f, l in FAMILY.items() for n in l}
VIRTUE_PATH = ['saint', 'peacemaker', 'redeemed']
AGGRESSIVE = ['glutton', 'wolf', 'heretic', 'backstabber']
SIN_PAIRS_GLUTTON = {0, 1, 2, 5}
