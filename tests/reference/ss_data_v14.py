"""v14 data: v13 cards, Fates rebalanced, Hubris/Hoard strict > (handled in moderator)."""
import copy
from ss_data_v13 import PAIRS, CARDS, CARD_BY_ID, FATES as _F13, STACK_BONUS, FATE_CAP, FAMILY, FAMILY_OF, VIRTUE_PATH, AGGRESSIVE, MAX_PER_FAMILY
FATES = copy.deepcopy(_F13)
for c in CARDS:
    if c['id'] in ('c02', 'c07'): c['text'] = 'you +4, each player with VP strictly greater than yours -1'
FATES['saint'] = dict(reward=6, desc='Play a virtue in 6+ rounds AND finish top 3 on base VP.')
FATES['peacemaker'] = dict(reward=6, desc='Give a targeted virtue to 3 different players, Settle with at least 1 player, and never play a card with a harmful effect (a Final Strike is not a card).')
FATES['late_bloomer'] = dict(reward=6, desc='Finish at least 2 places higher on base VP than your place after round 4 (place after round 4 uses VP at the end of round 4, ties share the better place).')
FATES['bulwark'] = dict(reward=5, desc="Lose at most 1 VP to other players' cards in each of 6+ rounds. You also gain one Ward at the start of round 3 (only if held by then; taking it after round 2 gives that Ward at once, after round 4 none).")
FATES['heretic'] = dict(reward=6, desc='Land real harm with a targeted card on a Haloed player (virtue streak of 2+ at the start of the round) in 3+ different rounds (a Final Strike does not count).')
FATES['backstabber'] = dict(reward=6, desc='Earn 2 Betrayals.')
FATES['glutton'] = dict(reward=4, desc='Play a sin (any theme pair) in 5+ different rounds.')
