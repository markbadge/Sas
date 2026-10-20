"""v12 data: v11 cards; two Fate families (LIGHT/SHADOW); glutton/wolf reworked; cap 9."""
import copy
from ss_data_v11 import PAIRS, CARDS, CARD_BY_ID, FATES as _F11, describe_card

FATES = copy.deepcopy(_F11)
FATES['glutton'] = dict(reward=5, desc='Play a sin (any theme pair) in 4+ different rounds.')
FATES['wolf'] = dict(reward=7, desc='Land real harm (at least 1 VP actually lost by the victim) on 4 different players over the game (a Final Strike does not count).')
FATES['inquisitor'] = dict(reward=6, desc='Make 1 correct Accusation. (A wrong Accusation costs you 1 VP like everyone else.)')
STACK_BONUS = {2: 1, 3: 2}
FATE_CAP = 9
FAMILY = {'LIGHT': ['saint', 'peacemaker', 'bulwark', 'survivor', 'redeemed', 'late_bloomer'],
          'SHADOW': ['glutton', 'wolf', 'heretic', 'backstabber', 'fallen', 'inquisitor']}
FAMILY_OF = {n: f for f, l in FAMILY.items() for n in l}
VIRTUE_PATH = ['saint', 'peacemaker', 'redeemed']
AGGRESSIVE = ['glutton', 'wolf', 'heretic', 'backstabber']
