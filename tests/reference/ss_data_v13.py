"""v13 data: v12 cards with dead-card buffs; rewards trimmed; cap 8; max 2 Fates per public family; wrong Accusation -2."""
import copy
from ss_data_v11 import PAIRS, CARDS, CARD_BY_ID, describe_card
from ss_data_v12 import FATES as _F12, FAMILY, FAMILY_OF, VIRTUE_PATH, AGGRESSIVE

CARDS = copy.deepcopy(CARDS)
CARD_BY_ID = {c['id']: c for c in CARDS}
CARD_BY_ID['c07'].update(self=4)                      # Hoard: +4, each player with VP >= yours -1
CARD_BY_ID['c02'].update(self=4)                      # Hubris: +4, each player with VP >= yours -1
CARD_BY_ID['c00'].update(self=4)                      # Boast: +4, each neighbour -1
CARD_BY_ID['c25'].update(self=2)                      # Rampage: +2, everyone else -2
CARD_BY_ID['c38'].update(self=3)                      # Neglect: +3, everyone else -1
CARD_BY_ID['c06'].update(target=-3)                   # Embargo: +3, target -3
CARD_BY_ID['c18'].update(rumour=True)                 # Rumour: +3, target -2, target's next Stash bonus is lost
for c in CARDS: c['text'] = describe_card(c)
CARD_BY_ID['c14']['text'] = "you +2, target -1, privately learn ONE random Fate of the target (name and family)"
CARD_BY_ID['c18']['text'] = "you +3, target -2, and the target loses the Stash bonus on the next stash card they play"

FATES = copy.deepcopy(_F12)
for n, v in dict(saint=5, bulwark=5, peacemaker=5, glutton=4, wolf=6, backstabber=6, fallen=8).items(): FATES[n]['reward'] = v
FATES['inquisitor'] = dict(reward=6, desc='Make 1 correct Accusation. (A wrong Accusation costs you 2 VP like everyone else.)')
STACK_BONUS = {2: 1, 3: 2}
FATE_CAP = 8
MAX_PER_FAMILY = 2
