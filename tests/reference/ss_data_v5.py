"""v5 data: v4 cards/objectives with economy changes (self-only virtues capped at +2, targeted virtues +1 to target); 4 coordination objectives removed."""
from ss_data_v4 import PAIRS, CARD_BY_ID, CARDS, FAMILY_OF
from ss_data_v4 import OBJECTIVES as _O4
import copy
from ss_data_v3 import describe_card
OBJECTIVES = copy.deepcopy(_O4)
for _k in ('beloved', 'benefactor', 'comeback', 'martyr'):
    OBJECTIVES.pop(_k, None)
OBJECTIVES['prosecutor'] = dict(name='Prosecutor', desc='Win 1 Accusation (the accused declaration was FALSE).', reward='+6')
OBJECTIVES['masker'] = dict(name='Masker', desc='Declare sin but play a virtue 3+ times (found FALSE by an Accusation or Exhibit at most once).', reward='+8')
for _cid in ('c15', 'c33', 'c39'):
    CARD_BY_ID[_cid]['self'] = 2
for _cid in ('c04', 'c05', 'c09', 'c17', 'c21', 'c22', 'c28', 'c29', 'c40'):
    CARD_BY_ID[_cid]['target'] += 1
for _c in CARDS:
    _c['text'] = describe_card(_c)
FAMILY = {
 'CONDUCT': ['saint', 'sinner', 'balanced', 'honest', 'liar', 'masker'],
 'SOCIAL': ['judas', 'wallflower', 'prosecutor'],
 'POSITION': ['untouchable', 'kingslayer'],
}
FAMILY_OF = {o: f for f, l in FAMILY.items() for o in l}
DEALABLE = ['saint', 'sinner', 'judas', 'untouchable', 'kingslayer', 'balanced', 'honest', 'liar', 'wallflower', 'masker', 'prosecutor']
