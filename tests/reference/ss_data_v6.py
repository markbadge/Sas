"""v6 data: v5 cards (self-only virtues capped at +2, targeted virtues +1 to target) with a reduced objective pool plus two role-linked objectives."""
from ss_data_v5 import PAIRS, CARD_BY_ID, CARDS

OBJECTIVES = {
    'sinner': dict(name='Sinner', desc='Play a sin card in 6+ rounds.', reward='+8'),
    'liar': dict(name='Liar', desc='Declare virtue but play a sin in 3+ rounds, and not be proven a liar for those rounds.', reward='+8'),
    'untouchable': dict(name='Untouchable', desc='Lose at most 6 VP in total to other players\' cards.', reward='+10'),
    'wallflower': dict(name='Wallflower', desc='Be targeted by SIN cards at most twice all game.', reward='+8'),
    'honest': dict(name='Honest', desc='Every declaration matches your card, with at least 3 sin and 3 virtue declarations.', reward='+8'),
    'prosecutor': dict(name='Prosecutor', desc='Win 3 Proofs (the named player\'s card did harm you).', reward='+8'),
    'hunter': dict(name='Hunter', desc='(Saints only) In BOTH Tribunals, name a player who really is a Sinner.', reward='+6'),
    'survivor': dict(name='Survivor', desc='(Sinners only) Never be Exposed in a Tribunal AND finish top 3 on base VP.', reward='+8'),
}
REWARD = dict(sinner=8, liar=8, untouchable=10, wallflower=8, honest=8, prosecutor=8, hunter=6, survivor=8)
FAMILY = {
    'CONDUCT': ['sinner', 'liar', 'honest'],
    'SOCIAL': ['wallflower', 'prosecutor'],
    'POSITION': ['untouchable'],
    'ROLE': ['hunter', 'survivor'],
}
FAMILY_OF = {o: f for f, l in FAMILY.items() for o in l}
DEALABLE = list(OBJECTIVES)
ROLE_ONLY = dict(hunter='saint', survivor='sinner')
