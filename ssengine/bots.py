"""Bot seats: an LLM bot (Anthropic API) and a random stub bot for tests. Prompt = rules brief (system) + the seat's text view."""
import json
import os
import random
import re

DEFAULT_MODEL = os.environ.get('SS_MODEL', 'claude-sonnet-5-5')
PERSONAS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'personas.json')))

DEBRIEF_PROMPT = ("GAME OVER. FINAL RESULT: {result}\nSend your DEBRIEF now. Be critical: you are a playtester. "
                  'Reply JSON only: {{"fun":<1-10>,"outcome":"why you won or lost","confusing":"rules that were unclear or surprising",'
                  '"too_strong":"cards, Fates or rules that felt too strong","too_weak":"cards, Fates or rules that felt too weak or dead",'
                  '"changes":"your top 3 rule changes","strategy":"what you tried and whether it worked","missing_info":"information you wished you had"}}')


def persona_for(seat, seed):
    order = list(range(len(PERSONAS)))
    random.Random(seed).shuffle(order)
    return PERSONAS[order[seat]]


def persona_note(p):
    return f"TABLE NOTE (private to you, not a rule): your persona is the {p['name']}. {p['line']} Play to win within that style.\n\n"


def _strip_fences(text):
    text = text.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    return m.group(1) if m else text


def parse_json(text):
    """Strict parse with a repair pass: fences, surrounding prose, trailing commas. Returns dict or None."""
    if isinstance(text, dict):
        return text
    if not isinstance(text, str):
        return None
    cand = _strip_fences(text)
    for attempt in (cand, ):
        try:
            v = json.loads(attempt)
            return v if isinstance(v, dict) else None
        except ValueError:
            pass
    # repair: first balanced {...}, drop trailing commas
    start = cand.find('{')
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(cand)):
            ch = cand[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    blob = re.sub(r",\s*([}\]])", r"\1", cand[start:i + 1])
                    try:
                        v = json.loads(blob)
                        if isinstance(v, dict):
                            return v
                    except ValueError:
                        pass
                    break
        start = cand.find('{', start + 1)
    return None


class LLMBot:
    kind = 'llm'

    def __init__(self, model=None, client=None, max_tokens=1500, temperature=None, timeout=600.0):
        self.model = model or DEFAULT_MODEL
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = client
        self.timeout = timeout

    @property
    def client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(max_retries=4, timeout=self.timeout)
        return self._client

    def reply(self, system, messages, view=None):
        kw = dict(model=self.model, max_tokens=self.max_tokens,
                  system=[{'type': 'text', 'text': system, 'cache_control': {'type': 'ephemeral'}}], messages=messages)
        if self.temperature is not None:
            kw['temperature'] = self.temperature
        resp = self.client.messages.create(**kw)
        return ''.join(b.text for b in resp.content if getattr(b, 'type', '') == 'text')


class StubBot:
    """Random legal play from the same structured VIEW a human gets. Used for tests and dry runs."""
    kind = 'stub'

    def __init__(self, seed=0):
        self.rng = random.Random(seed)

    def reply(self, system, messages, view=None):
        rng = self.rng
        seat = view['seat']
        others = [i for i in range(6) if i != seat]
        if view['stage'] == 'talk':
            t = {'say': rng.choice(['Let us all play fair.', 'I am watching the leaders.', 'Anyone want a Favour?', 'Keep it clean this round.']),
                 'whisper': {str(rng.choice(others)): 'Work with me?'}}
            if rng.random() < .5:
                t['pledge'] = rng.choice(others)
            if view['can_call'] and rng.random() < .6:
                t['call'] = rng.choice(others)
            if view['offer']:
                t['fate'] = rng.choice(view['offer'])['name'] if rng.random() < .9 else None
            return json.dumps(t)
        cards = list(view['hand']) + ([view['stash']] if view['stash'] else [])
        c = rng.choice(cards)
        a = {'play': c['id'], 'target': rng.choice(others) if c['target'] else None}
        spare = [h['id'] for h in view['hand'] if h['id'] != c['id']]
        if spare and rng.random() < .5:
            a['stash'] = rng.choice(spare)
        if view['round'] >= 4 and not view['accused'] and rng.random() < .25:
            fam = [(i, f) for i, f in view['families'].items() if int(i) != seat and f]
            if fam:
                i, f = rng.choice(fam)
                pool = {'LIGHT': ['saint', 'peacemaker', 'bulwark', 'survivor', 'redeemed', 'late_bloomer'], 'SHADOW': ['glutton', 'wolf', 'heretic', 'backstabber', 'fallen', 'inquisitor']}[rng.choice(f)]
                a['accuse'] = {'seat': int(i), 'fate': rng.choice(pool)}
        if view['final'] and rng.random() < .5:
            a['final_strike'] = rng.choice(others)
        return json.dumps(a)
