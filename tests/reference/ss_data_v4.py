"""v4 data: v3 cards unchanged; objectives retuned; objective families added."""
from ss_data_v3 import PAIRS, CARD_BY_ID, CARDS
import copy
from ss_data_v3 import OBJECTIVES as _O3
OBJECTIVES = copy.deepcopy(_O3)
OBJECTIVES.pop('rival', None)
OBJECTIVES.update({
 'liar': dict(name='Liar', desc='Declare virtue but play a sin 3+ times.', reward='+8'),
 'masker': dict(name='Masker', desc='Declare sin but play a virtue 3+ times (found FALSE by a Challenge at most once).', reward='+8'),
 'honest': dict(name='Honest', desc='Every declaration matched the card, with at least 3 sin and 3 virtue declarations.', reward='+10'),
 'saint': dict(name='Saint', desc='Play a virtue in 5+ rounds and finish top 4.', reward='+10'),
 'martyr': dict(name='Martyr', desc='Lose 9+ VP to TARGETED and NEIGHBOUR harm only (area excluded) and finish top 4.', reward='+8'),
 'comeback': dict(name='Comeback', desc='Be in the bottom 2 on the round-3 scoreboard, then finish top 3.', reward='+10'),
 'beloved': dict(name='Beloved', desc='Receive a targeted virtue from 3+ different players.', reward='+8'),
})
FAMILY = {
 'CONDUCT': ['saint', 'sinner', 'balanced', 'honest', 'liar', 'masker'],
 'SOCIAL': ['benefactor', 'beloved', 'judas', 'wallflower', 'prosecutor'],
 'POSITION': ['comeback', 'martyr', 'kingslayer', 'untouchable'],
}
FAMILY_OF = {o: f for f, l in FAMILY.items() for o in l}
