"""v11 data: v10 cards with 5 dead-card buffs, 12 Fates with v11 conditions, cap 10, stack +1/+2."""
import copy
from ss_data_v8 import PAIRS, CARDS as _C8
from ss_data_v3 import describe_card

CARDS = copy.deepcopy(_C8)
CARD_BY_ID = {c['id']: c for c in CARDS}
CARD_BY_ID['c32'].update(self=5, recoil=1)            # Gorge: +5, lose 1
CARD_BY_ID['c41'].update(self=3, recoil=0)            # Overtime: +3
CARD_BY_ID['c10'].update(self=3)                      # Soup Kitchen: +3, everyone else +1
CARD_BY_ID['c26'].update(self=4)                      # Brawl: +4, each neighbour -2
CARD_BY_ID['c36'].update(self=3)                      # Slack Off: +3, Ward
for c in CARDS: c['text'] = describe_card(c)
CARD_BY_ID['c14']['text'] = "you +2, target -1, privately learn ONE random Fate of the target (name and family)"

FATES = {
    'saint': dict(reward=6, desc='Play a virtue in 6+ rounds AND finish top 3 on base VP.'),
    'peacemaker': dict(reward=6, desc='Settle with 2 different players, give a targeted virtue to 3 different players, and never play a card with a harmful effect (a Final Strike is not a card).'),
    'redeemed': dict(reward=7, desc='Play a sin in 3+ of rounds 1-4, then a virtue in 3+ of rounds 5-7, including a targeted virtue on a player you harmed earlier.'),
    'fallen': dict(reward=9, desc='Play a virtue in 3+ of rounds 1-4, then play a sin in ALL of rounds 5-7, and earn at least 1 Betrayal.'),
    'heretic': dict(reward=6, desc='Land real harm with a targeted card on a Haloed player (virtue streak of 2+ at the start of the round) in 2+ different rounds (a Final Strike does not count).'),
    'wolf': dict(reward=7, desc='Land real harm with cards (at least 1 VP actually lost by the victim) in 4+ different rounds, on 3+ different players in total (a Final Strike does not count).'),
    'glutton': dict(reward=5, desc='Play a sin from Pride, Greed, Lust or Gluttony 5+ times.'),
    'backstabber': dict(reward=7, desc='Earn 1 Betrayal AND land a Smite (targeted real harm on a Haloed player) at least once. A Smite counts even when the Betrayal bonus was paid instead of the Smite bonus.'),
    'inquisitor': dict(reward=6, desc='Make 1 correct Accusation. (A wrong Accusation costs an inquisitor holder 0 VP.)'),
    'bulwark': dict(reward=6, desc='Lose at most 1 VP to other players\' cards in each of 5+ rounds. You also gain one Ward at the start of round 3 (only if held by then; taking it after round 2 gives that Ward at once, after round 4 none).'),
    'late_bloomer': dict(reward=7, desc='Offered only to a player in the bottom 3 on VP. Gain more VP in rounds 5-7 combined than any other player (strictly the most).'),
    'survivor': dict(reward=7, desc='Offered only to a player outside the top 3 on VP. Lose 6+ VP in total to other players\' cards over the game AND finish in the top 3 on base VP.'),
}
STACK_BONUS = {2: 1, 3: 2}
FATE_CAP = 10
FAMILY = {'PURE': ['saint', 'peacemaker'], 'ARC': ['fallen', 'redeemed'],
          'HUNT': ['heretic', 'wolf', 'glutton', 'backstabber', 'inquisitor'], 'SHIELD': ['bulwark', 'late_bloomer', 'survivor']}
FAMILY_OF = {n: f for f, l in FAMILY.items() for n in l}
VIRTUE_PATH = ['saint', 'peacemaker', 'redeemed']
AGGRESSIVE = ['glutton', 'wolf', 'heretic', 'backstabber']
SIN_PAIRS_GLUTTON = {0, 1, 2, 5}
