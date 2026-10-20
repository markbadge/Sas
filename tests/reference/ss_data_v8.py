"""v8 data: v7 cards with v8 economy edits, Inquisition card, 11 v8 Fates, families."""
import copy
from ss_data_v7 import PAIRS, CARDS as _C7, INQ as _INQ
from ss_data_v3 import describe_card

CARDS = copy.deepcopy(_C7)
CARD_BY_ID = {c['id']: c for c in CARDS}
for cid in ('c15', 'c33', 'c39'): CARD_BY_ID[cid]['self'] = 3        # Restraint, Moderation, Hard Work
CARD_BY_ID['c35']['self'] = 2                                         # Ration
for cid in ('c02', 'c07', 'c30'): CARD_BY_ID[cid]['self'] = 3        # Hubris, Hoard, Feast
CARD_BY_ID['c32']['self'] = 5                                         # Gorge (recoil stays 2)
for c in CARDS:
    c['text'] = describe_card(c)
CARD_BY_ID['c14']['text'] = "you +2, target -1, privately learn ONE random Fate of the target (name and family)"
INQ = copy.deepcopy(_INQ)
INQ['text'] = 'you +1; accuse ONE other player of holding a named Fate (give target seat and "guess")'
CARD_BY_ID['q0'] = INQ

FATES = {
    'saint': dict(reward=6, desc='Play a virtue card in 5+ rounds and finish top 4 on base VP.'),
    'peacemaker': dict(reward=6, desc='Never play a card with a harmful effect, and give targeted virtues to 4+ different players.'),
    'kingmaker': dict(reward=6, desc='The one player you gave the most targeted virtues to (at least 2, no tie) finishes top 2 on base VP (not you).'),
    'zealot': dict(reward=7, desc='Land a targeted harmful effect on a round-start leader (any co-leader) in 4+ rounds (round 2 onward).'),
    'glutton': dict(reward=5, desc='Play a sin from Pride, Greed, Lust or Gluttony 5+ times.'),
    'backstabber': dict(reward=7, desc='Earn 2 Betrayals.'),
    'fallen': dict(reward=9, desc='Play a virtue in 3+ of rounds 1-4, then play a sin in ALL of rounds 5-7, and earn at least 1 Betrayal.'),
    'redeemed': dict(reward=8, desc='Play a sin in 3+ of rounds 1-4, then a virtue in 3+ of rounds 5-7, including a targeted virtue on a player you harmed earlier.'),
    'inquisitor': dict(reward=5, desc='Make 1 correct Inquisition accusation.'),
    'bulwark': dict(reward=6, desc='You gain a Ward at the start of rounds 3 and 5 (if held by then), and lose at most 2 VP to other players\' cards in each of 4+ rounds.'),
    'underdog': dict(reward=8, desc='Offered only to a player in the bottom 3 on VP. Finish at least 2 ranks higher (on base VP) than your rank when you took it.'),
}
STACK_BONUS = {2: 2, 3: 4}
FATE_CAP = 14
FAMILY = {'PURE': ['saint', 'peacemaker', 'kingmaker'], 'ARC': ['fallen', 'redeemed'],
          'HUNT': ['zealot', 'glutton', 'backstabber', 'inquisitor'], 'SHIELD': ['bulwark', 'underdog']}
FAMILY_OF = {n: f for f, l in FAMILY.items() for n in l}
VIRTUE_PATH = ['saint', 'peacemaker', 'kingmaker', 'redeemed']
SIN_PAIRS_GLUTTON = {0, 1, 2, 5}
