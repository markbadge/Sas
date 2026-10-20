# Saints and Sinners: engine and play client (rules v14)

One human (seat 0 by default) plays against five LLM bot seats. Spec: `docs/SPEC.md`. Rules change list: `docs/RULES_v14.md`.

## Run

    pip install anthropic            # only needed for LLM bots
    export ANTHROPIC_API_KEY=...
    python -m ssengine serve         # http://127.0.0.1:8000/  (add --bots stub for random-play opponents)
    python -m ssengine sim --seed 3 --bots stub            # all-bot game, prints the final table
    python -m ssengine sim --seed 3 --debrief              # LLM bots, asks each for a debrief (JSON)
    SS_MODEL=claude-opus-5-5 python -m ssengine serve      # bot model (default claude-sonnet-5-5)

Games are saved to `games/<id>.json` (engine state, per-seat bot conversation history, bot log, debriefs) and resume on restart.

## Layout

| Path | Role |
|---|---|
| `ssengine/rules/<version>/` | `data.json` (cards, pairs, Fates with params, families), `config.json` (every numeric rule), `brief.md` (bot system prompt). A new rules version is a new folder. |
| `ssengine/engine.py` | `Game`: one JSON-serialisable state dict; `submit_talk`, `submit_act`, `resolve`, `offers`, `finalize`. No I/O. |
| `ssengine/views.py` | Per-seat views: bot text prompts and the structured `VIEW` for the client. |
| `ssengine/bots.py`, `session.py` | LLM bot (Anthropic API, prompt-cached brief, per-seat history, strict JSON + repair + logged fallback), random stub bot, personas, parallel bot turns, persistence, debrief. |
| `ssengine/server.py`, `static/table.html` | stdlib HTTP API and the single-file client (mobile first, light/dark, rules drawer, card tooltips, end summary). |
| `tests/reference/` | The handoff `moderator14.py` + data chain, used only as the test oracle. |
| `tools/flatten_data.py`, `tools/ui_smoke.py` | Regenerate `data.json` from the layered data; headless-browser play-through. |

## Tests

    python -m pytest            # 101 tests
    python3 tools/ui_smoke.py   # needs playwright + chromium

- `test_oracle.py`: engine vs `moderator14` on 40 random-play seeds (80 games): full state after every phase, private reports, public lines, normalisation fixes, Fate offers, finalize. A second set compares the bot prompt text to the moderator's act/result/talk files.
- `test_rules.py`: one test per rule bullet on hand-built states. `test_game.py`: properties (no negative VP, caps, Fate limits), hidden-info checks, determinism, JSON round trip, full games with stub bots and with a fake Anthropic client, persistence, HTTP API.

Not tested: real Anthropic API calls (no key in the build environment). The request shape follows `messages.create` with a cached system block.

## Notes and decisions

- Rules are data: numeric rules in `config.json`, Fate thresholds in `data.json` params. Fate condition logic and offer feasibility remain code, reading those params. Rules not parameterised (Hubris `others_geq`, Rumour, Scandal behaviour) are card flags in the data.
- RNG is derived from the game seed (themes, hands, strike start, offers, Scandal). `Game.new(..., rng={...})` can reproduce moderator14's formulas; the oracle test does.
- Behaviour kept from `moderator14` even where it looks odd: a Final Strike that is fully absorbed by the round cap pays no bounty and its cost is not refunded; the four deviations listed in `RULES_v14.md`; stage-3 replacement offers are not made after rounds 2 and 4 (the scheduled offer covers it) or after round 7.
- Differences from `moderator14`: a self-pledge is ignored (the moderator would print a private note for it); Call outcomes that concern a seat privately (its own right/wrong Call, being Called) and an INVALID Call notice are added to that seat's next act prompt and client view, because they were otherwise only visible in a report already closed. Bots and the human see the same data.
- `hist` stores a copy of the scores at round end (the moderator's JSON round-trip made it a snapshot; in memory it would otherwise alias `score` and be changed by Calls).
- Bot prompts omit the "G29" game label. The brief is used verbatim, so it still mentions moderator files; the bot only ever receives its own prompt.
