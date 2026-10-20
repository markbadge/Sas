"""Saints and Sinners - static content: cards, plans, objectives, powers."""

PAIRS = [
    ("Pride", "Humility"),
    ("Greed", "Charity"),
    ("Lust", "Chastity"),
    ("Envy", "Kindness"),
    ("Wrath", "Patience"),
    ("Gluttony", "Temperance"),
    ("Sloth", "Diligence"),
]

S, V = "sin", "virtue"


def describe_card(c):
    parts = []
    if c["self"]:
        parts.append(f"you {c['self']:+d}")
    if c["steal"]:
        parts.append(f"steal {c['steal']} from target")
    if c["hit_leader"]:
        parts.append(f"take {c['hit_leader']} from the leader")
    if c["target"]:
        parts.append(f"target {c['target']:+d}")
    if c["nbr"]:
        parts.append(f"each neighbour {c['nbr']:+d}")
    if c["others"]:
        parts.append(f"everyone else {c['others']:+d}")
    if c["recoil"]:
        parts.append(f"you lose {c['recoil']} (recoil)")
    if c["ward"]:
        parts.append("you gain a Ward")
    if c["ward_target"]:
        parts.append("target gains a Ward")
    if c["expose"]:
        parts.append("peek at target's objective and plans")
    return ", ".join(parts)


CARDS = []


def _card(pair, kind, name, **kw):
    c = dict(pair=pair, kind=kind, name=name, self=0, target=0, nbr=0, others=0,
             steal=0, hit_leader=0, recoil=0, ward=False, ward_target=False,
             expose=False)
    c.update(kw)
    c["needs_target"] = bool(c["target"] or c["steal"] or c["expose"] or c["ward_target"])
    c["id"] = f"c{len(CARDS):02d}"
    c["text"] = describe_card(c)
    CARDS.append(c)


# Pride / Humility
_card(0, S, "Boast", self=3, nbr=-1)
_card(0, S, "Name-drop", self=4, target=-2)
_card(0, S, "Hubris", self=5, others=-1)
_card(0, V, "Share the Credit", self=2, nbr=1)
_card(0, V, "Step Aside", self=1, target=3)
_card(0, V, "Modest Gift", self=2, target=2)
# Greed / Charity
_card(1, S, "Embargo", self=3, target=-2)
_card(1, S, "Hoard", self=4, others=-1)
_card(1, S, "Shakedown", steal=3)
_card(1, V, "Alms", self=2, target=3)
_card(1, V, "Soup Kitchen", self=1, others=1)
_card(1, V, "Benefit Fund", self=2, nbr=2)
# Lust / Chastity
_card(2, S, "Seduce", self=3, target=-2)
_card(2, S, "Infatuate", self=1, steal=2)
_card(2, S, "Scandal", self=2, target=-1, expose=True)
_card(2, V, "Restraint", self=3)
_card(2, V, "Vow", self=1, ward=True)
_card(2, V, "Guidance", self=2, target=2)
# Envy / Kindness
_card(3, S, "Rumour", self=3, target=-2)
_card(3, S, "Sabotage", self=2, target=-3)
_card(3, S, "Covet", self=1, hit_leader=3)
_card(3, V, "Compliment", self=2, target=2)
_card(3, V, "Helping Hand", self=1, target=4)
_card(3, V, "Surprise Gift", self=3, nbr=1)
# Wrath / Patience
_card(4, S, "Smash", self=2, target=-4)
_card(4, S, "Rampage", self=1, others=-2)
_card(4, S, "Brawl", self=3, nbr=-2)
_card(4, V, "Deep Breath", self=2, ward=True)
_card(4, V, "Mediate", self=3, target=1)
_card(4, V, "Forgive", self=2, target=1, ward_target=True)
# Gluttony / Temperance
_card(5, S, "Feast", self=4, nbr=-1)
_card(5, S, "Raid the Pantry", self=1, steal=2)
_card(5, S, "Gorge", self=6, recoil=2)
_card(5, V, "Moderation", self=3)
_card(5, V, "Share Portions", self=2, nbr=1)
_card(5, V, "Ration", self=1, others=1)
# Sloth / Diligence
_card(6, S, "Slack Off", self=2, ward=True)
_card(6, S, "Shirk", self=3, target=-2)
_card(6, S, "Neglect", self=2, others=-1)
_card(6, V, "Hard Work", self=3)
_card(6, V, "Team Effort", self=2, target=2)
_card(6, V, "Overtime", self=4, recoil=1)

CARD_BY_ID = {c["id"]: c for c in CARDS}
POOL = {p: [c for c in CARDS if c["pair"] == p] for p in range(len(PAIRS))}

# Persistent powers. "max" is the stack limit.
PLANS = {
    "patron":      dict(name="Patron", max=1, desc="Your card gains +4 VP in the round themed {pair}."),
    "zealot":      dict(name="Zealot", max=3, desc="Virtue right after a virtue: +1 VP per stack."),
    "hedonist":    dict(name="Hedonist", max=3, desc="Sin right after a sin: +1 VP per stack."),
    "teflon":      dict(name="Teflon", max=2, desc="Every loss you take is reduced by 1 per stack."),
    "vengeful":    dict(name="Vengeful", max=1, desc="Your harmful cards hit +2 harder against whoever harmed you last round."),
    "opportunist": dict(name="Opportunist", max=2, desc="Round end: +1 VP per stack if 3 or more other players played a sin this round."),
    "hoarder":     dict(name="Hoarder", max=2, desc="Game end: +10% of your VP per stack."),
    "underdog":    dict(name="Underdog", max=2, desc="Round start: if you are tied for last, +2 VP per stack."),
    "spoiler":     dict(name="Spoiler", max=2, desc="+1 VP per stack whenever your card hits the current leader."),
    "informant":   dict(name="Informant", max=1, desc="When taken: see a random opponent's objective and plans."),
    "cloak":       dict(name="Cloak", max=1, desc="Peeks at you (Spyglass, Scandal) fail."),
    "tiebreaker":  dict(name="Tiebreaker", max=1, desc="You win ties."),
    "martyr":      dict(name="Martyr", max=1, desc="If you lose 3+ VP in a round, gain 3 VP at round end."),
    "gambler":     dict(name="Gambler", max=1, desc="Round start: coin flip, +3 VP or -2 VP."),
    "wide_hand":   dict(name="Wide Hand", max=1, desc="See 4 cards each round instead of 3."),
    "bodyguard":   dict(name="Bodyguard", max=1, desc="Gain 2 Wards now (each Ward blocks one harmful effect)."),
    "bargain":     dict(name="Sinner's Bargain", max=1, desc="Your sins gain +2 VP, but you lose 4 VP at game end."),
    "halo":        dict(name="Halo", max=2, desc="Game end: +1 VP per stack for each virtue you played."),
    "alliance":    dict(name="Pact", max=1, desc="Choose an ally: when you both play a virtue in the same round, +2 VP each."),
    "pickpocket":  dict(name="Pickpocket", max=1, desc="Your sins that target someone steal 1 more VP from them."),
    "early_bird":  dict(name="Early Bird", max=1, desc="Rounds 1-3: +2 VP on every card you play."),
    "late_bloomer": dict(name="Late Bloomer", max=1, desc="Rounds 5-7: +2 VP on every card you play."),
    "magnet":      dict(name="Magnet", max=2, desc="When someone plays a virtue on you, +1 VP per stack."),
    "thorns":      dict(name="Thorns", max=2, desc="Whoever harms you for 2+ loses 1 VP per stack."),
    "witness":     dict(name="Witness", max=1, desc="You learn who played harmful cards against you."),
}

OBJECTIVES = {
    "saint":       dict(name="Saint", desc="Play a virtue in 6+ rounds.", reward="+10"),
    "sinner":      dict(name="Sinner", desc="Play a sin in 6+ rounds.", reward="+10"),
    "benefactor":  dict(name="Benefactor", desc="Play a targeted virtue on all 5 other players.", reward="+10"),
    "beloved":     dict(name="Beloved", desc="Receive a targeted virtue from 4+ different players.", reward="+8"),
    "judas":       dict(name="Judas", desc="Help a player with a virtue, then later harm them with a sin, for 3+ different players.", reward="+40% VP"),
    "comeback":    dict(name="Comeback", desc="Be last on the round 3 scoreboard, then finish top 3.", reward="+10"),
    "untouchable": dict(name="Untouchable", desc="Never lose VP to another player's card.", reward="+12"),
    "martyr":      dict(name="Martyr", desc="Lose 12+ VP to other players and still finish top 3.", reward="+8"),
    "rival":       dict(name="Rival", desc="Finish ahead of your secret rival.", reward="+8"),
    "kingslayer":  dict(name="Kingslayer", desc="Hit the round leader with harmful cards 3+ times.", reward="+8"),
    "balanced":    dict(name="Balanced", desc="Play at least 3 sins and 3 virtues.", reward="+6"),
    "honest":      dict(name="Honest", desc="Every declaration matched what you played.", reward="+10"),
    "liar":        dict(name="Liar", desc="Declare virtue but play a sin 3+ times.", reward="+8"),
    "wallflower":  dict(name="Wallflower", desc="Be targeted by cards at most once all game.", reward="+8"),
}

POWERS = {
    "spyglass":     dict(name="Spyglass", needs="target", desc="Peek at a player's objective and plans."),
    "absolution":   dict(name="Absolution", needs=None, desc="You take no harm this round."),
    "double":       dict(name="Double Down", needs=None, desc="Your card's effects are doubled this round (not plan bonuses)."),
    "veto":         dict(name="Veto", needs="target", desc="Cancel another player's card this round."),
    "mirror":       dict(name="Mirror", needs=None, desc="The first harmful effect aimed at you this round hits its source instead."),
    "redistribute": dict(name="Redistribute", needs=None, desc="Take 3 VP from the current leader (the runner-up if you lead)."),
    "hex":          dict(name="Hex", needs="target", desc="Another player's card gives them 0 self VP this round."),
    "tithe":        dict(name="Tithe", needs=None, desc="Take 1 VP from each other player."),
}


def plan_text(pid, param=None, stacks=1):
    meta = PLANS[pid]
    d = meta["desc"]
    if pid == "patron" and param is not None:
        d = d.format(pair="/".join(PAIRS[param]))
    if pid == "alliance" and param is not None:
        d = d.replace("Choose an ally", f"Ally is player {param}")
    name = meta["name"] + (f" x{stacks}" if stacks > 1 else "")
    return f"{name}: {d}"
