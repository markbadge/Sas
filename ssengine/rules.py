"""Versioned rules: cards, Fates and numeric config are loaded from ssengine/rules/<version>/."""
import json
import os

RULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rules')
DEFAULT_VERSION = 'v14'


class Rules:
    def __init__(self, version=DEFAULT_VERSION):
        d = os.path.join(RULES_DIR, version)
        data = json.load(open(os.path.join(d, 'data.json')))
        self.version = version
        self.cfg = json.load(open(os.path.join(d, 'config.json')))
        self.brief = open(os.path.join(d, 'brief.md')).read()
        self.pairs = data['pairs']
        self.cards = data['cards']
        self.card = {c['id']: c for c in self.cards}
        self.fates = data['fates']
        self.families = data['families']
        self.family_of = {n: f['family'] for n, f in self.fates.items()}
        self.aggressive = data['aggressive']

    def harmful(self, c):
        return bool(c['target'] < 0 or c['steal'] or c['hit_leader'] or c['nbr'] < 0 or c['others'] < 0)


_cache = {}


def load_rules(version=DEFAULT_VERSION):
    if version not in _cache:
        _cache[version] = Rules(version)
    return _cache[version]
