"""v10 data: v8 cards (no Inquisition card), 12 v10 Fates, families."""
import copy
from ss_data_v8 import PAIRS, CARDS as _C8, CARD_BY_ID as _B8

CARDS = copy.deepcopy(_C8)
CARD_BY_ID = {c['id']: c for c in CARDS}
CARD_BY_ID['c14']['text'] = "you +2, target -1, privately learn ONE random Fate of the target (name and family)"

FATES = {
    'saint': dict(reward=6, desc='Reach a virtue streak of 4 or more in a row (your Momentum streak; a real hit of 2+ VP lowers it by 1) at any time, OR play a virtue in 6+ rounds, AND finish top 4 on base VP.'),
    'peacemaker': dict(reward=6, desc='Settle with at least one player, give a targeted virtue to 3 different players, and never play a card with a harmful effect.'),
    'redeemed': dict(reward=7, desc='Play a sin in 3+ of rounds 1-4, then a virtue in 3+ of rounds 5-7, including a targeted virtue on a player you harmed earlier.'),
    'fallen': dict(reward=9, desc='Play a virtue in 3+ of rounds 1-4, then play a sin in ALL of rounds 5-7, and earn at least 1 Betrayal.'),
    'heretic': dict(reward=7, desc='Land real harm with a targeted card on a Haloed player (virtue streak of 2+ at the start of the round) in 3+ different rounds.'),
    'wolf': dict(reward=7, desc='Land real harm (any card, at least 1 VP actually lost by the victim) in 4+ different rounds, on 3+ different players in total.'),
    'glutton': dict(reward=5, desc='Play a sin from Pride, Greed, Lust or Gluttony 5+ times.'),
    'backstabber': dict(reward=7, desc='Earn 1 Betrayal AND land a Smite (targeted real harm on a Haloed player) at least once.'),
    'inquisitor': dict(reward=5, desc='Make 1 correct Accusation.'),
    'bulwark': dict(reward=6, desc='Lose at most 2 VP to other players\' cards in each of 4+ rounds. You also gain one Ward at the start of round 3 (only if held by then; taking it after round 2 gives that Ward at once, after round 4 none).'),
    'late_bloomer': dict(reward=7, desc='Offered only to a player in the bottom 3 on VP. Gain more VP in rounds 5-7 combined than any other player (strictly the most).'),
    'survivor': dict(reward=7, desc='Offered only to a player outside the top 3 on VP. Lose 6+ VP in total to other players\' cards over the game AND finish in the top 3 on base VP.'),
}
STACK_BONUS = {2: 2, 3: 3}
FATE_CAP = 12
FAMILY = {'PURE': ['saint', 'peacemaker'], 'ARC': ['fallen', 'redeemed'],
          'HUNT': ['heretic', 'wolf', 'glutton', 'backstabber', 'inquisitor'], 'SHIELD': ['bulwark', 'late_bloomer', 'survivor']}
FAMILY_OF = {n: f for f, l in FAMILY.items() for n in l}
VIRTUE_PATH = ['saint', 'peacemaker', 'redeemed']
AGGRESSIVE = ['glutton', 'wolf', 'heretic', 'backstabber']
SIN_PAIRS_GLUTTON = {0, 1, 2, 5}
