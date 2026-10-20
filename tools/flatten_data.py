"""Flatten the layered ss_data_v14 chain (tests/reference) into ssengine/rules/v14/data.json.
Usage: python3 -I tools/flatten_data.py"""
import json, os, sys
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(root, 'tests', 'reference'))
import ss_data_v14 as D

PARAMS = {
    'saint': dict(virtue_rounds=6, top=3),
    'peacemaker': dict(targets=3, settles=1),
    'redeemed': dict(early_sins=3, late_virtues=3),
    'fallen': dict(early_virtues=3, betrayals=1),
    'heretic': dict(rounds=3),
    'wolf': dict(victims=4),
    'glutton': dict(sin_rounds=5),
    'backstabber': dict(betrayals=2),
    'inquisitor': dict(correct=1),
    'bulwark': dict(rounds=6, max_loss=1),
    'late_bloomer': dict(places=2),
    'survivor': dict(lost=6, top=3),
}
fates = {n: dict(reward=f['reward'], desc=f['desc'], family=D.FAMILY_OF[n], params=PARAMS[n]) for n, f in D.FATES.items()}
cards = []
for c in D.CARDS:
    c = dict(c)
    c.setdefault('rumour', False)
    cards.append(c)
data = dict(version='v14', pairs=[list(p) for p in D.PAIRS], cards=cards, fates=fates,
            families=D.FAMILY, aggressive=D.AGGRESSIVE)
out = os.path.join(root, 'ssengine', 'rules', 'v14', 'data.json')
json.dump(data, open(out, 'w'), indent=1)
print('wrote', out, len(cards), 'cards', len(fates), 'fates')
