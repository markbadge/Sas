"""v7 data: v5 cards + Inquisition card + Fates."""
from ss_data_v5 import PAIRS, CARD_BY_ID, CARDS

INQ = dict(id='q0', name='Inquisition', kind='inq', pair=-1, self=1, steal=0, hit_leader=0, target=0, nbr=0, others=0,
           recoil=0, ward=0, ward_target=0, needs_target=True, others_geq=False,
           text='you +1; accuse ONE other player of holding a named Fate (give target seat and "guess")')
CARD_BY_ID['q0'] = INQ

FATES = {
    'saint': dict(reward=10, desc='Play a virtue card in 5+ rounds, never play a card with a harmful effect, and finish top 4 on base VP.'),
    'fallen': dict(reward=14, desc='Play a virtue in 3+ of rounds 1-4, then play a sin in ALL of rounds 5-7, and earn at least 1 Betrayal.'),
    'redeemed': dict(reward=12, desc='Play a sin in 3+ of rounds 1-4, then a virtue in 3+ of rounds 5-7, including a targeted virtue on a player you harmed earlier.'),
    'zealot': dict(reward=9, desc='Land a targeted harmful effect on the round-start leader in 3+ rounds (round 2 onward).'),
    'kingmaker': dict(reward=10, desc='The one player you gave the most targeted virtues to (at least 2, no tie) finishes with the highest base VP (not you).'),
    'martyr': dict(reward=8, desc='Give 5+ targeted virtues in total and finish in the bottom 3 on base VP.'),
    'glutton': dict(reward=8, desc='Play a sin from Pride, Greed, Lust or Gluttony 4+ times.'),
    'peacemaker': dict(reward=9, desc='Never play a card with a harmful effect, and give targeted virtues to 3+ different players.'),
    'inquisitor': dict(reward=8, desc='Make 2 correct Inquisition accusations.'),
    'backstabber': dict(reward=10, desc='Earn 2+ Betrayals (harm landed on a player who earlier gave you a targeted virtue).'),
    'untouchable': dict(reward=10, desc='Lose at most 6 VP in total to other players\' cards.'),
}
STACK_BONUS = {2: 3, 3: 6}
SIN_PAIRS_GLUTTON = {0, 1, 2, 5}  # Pride, Greed, Lust, Gluttony (indices in PAIRS)
