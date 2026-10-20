# Saints and Sinners: engine + play client spec (for Claude Code)

Goal: a real engine and a simple front end where one human (seat 0 by default) plays against five LLM bot seats, replacing the hand-run moderator used for playtests. Rules version: v14 (games 29-30 in progress; v15 changes will follow from the review loop, so keep rules data-driven).

## 0. What is in the handoff folder

| File | Role |
|---|---|
| `PLAYER_BRIEF_v14.md` | Complete player-facing rules and card list. Use verbatim as the bot system prompt. Human-readable rules reference for the UI. |
| `moderator14.py` | Reference implementation of resolution (`resolve`, `apply_calls`, `finalize`, `offers`, `pick_fates`, dealing, view text). It is a hand-run helper, not an engine: it reads/writes a JSON state file and writes prompt text files. Port the logic, do not extend it. Match its behaviour. |
| `ss_data*.py` | Layered card and Fate data (v14 -> v13 -> v12/v11 -> v8 -> v7/v3 ...). The whole chain is included so `import ss_data_v14` works. Flatten into one `data.json` (cards, pairs, Fates, families). |
| `run14.py`, `lib.py`, `dry.py` | How a round is driven today, plus a random-play dry run (5 seeds pass) to use as a smoke test. |
| `RULES_v14.md` | v14 change list and 4 known deviations from the reviewer spec. |
| `table.template.html` | Draft client page (single file, theme-aware). It renders a `VIEW` object and produces the reply JSON. Reuse its layout. |
| `ss_engine.py` | An earlier abandoned engine. Do NOT reuse it; rules have diverged. |

`moderator14.py` is the source of truth for any rule question. The brief is the source of truth for wording.

## 1. Game summary

6 players, seats 0-5 in a circle (neighbours are seat±1 mod 6). 7 rounds. Start 2 VP. Each round has a public theme pair (a Sin and a Virtue); pairs are `Pride/Humility, Greed/Charity, Lust/Chastity, Envy/Kindness, Wrath/Patience, Gluttony/Temperance, Sloth/Diligence`; theme order is a per-game shuffle of the 7 pairs (round r uses `themes[r-1]`).

Round: TALK (public line, up to 3 whispers, optional Call, optional Pledge, Fate pick when an offer exists) then ACT (play one card, optional target, optionally stash one other dealt card, optional Accusation from R4, Final Strike in R7), then RESOLVE and send each player a private report.

Hidden information (design constraint, do not weaken): a player sees own exact VP, others only as bands of 5, public MOMENTUM tokens (HALOED / HOT / none, streak length never shown), public Fate FAMILIES per player (LIGHT / SHADOW, no names or counts), and only what happened to themselves. Exact scores are revealed to all at the start of R7 only. Plays, targets, Favours, Betrayals, Wards, Tithes and hit sources are private. Public lines: Accusations, Calls, BROKEN Pledges, momentum, and in R7 the full card and Final Strike reveal.

## 2. Data model

Card (from `ss_data`): `id, name, kind(sin|virtue), pair, self, target, nbr, others, steal, hit_leader, recoil, ward, ward_target, expose, rumour, others_geq, needs_target, text`. 42 cards `c00..c41`, 3 per pair; the full list with text is in the brief. `others_geq` is the v13 flag on Hubris/Hoard; v14 makes it STRICTLY greater (see 5.1).

Fate: `name -> {reward, desc, family}`. Families: LIGHT = saint, peacemaker, bulwark, survivor, redeemed, late_bloomer; SHADOW = glutton, wolf, heretic, backstabber, fallen, inquisitor. AGGRESSIVE (used by offers) = glutton, wolf, heretic, backstabber. Rewards v14: saint 6, peacemaker 6, redeemed 7, fallen 8, heretic 6, wolf 6, glutton 4, backstabber 6, inquisitor 6, bulwark 5, late_bloomer 6, survivor 7. Total Fate points cap 8; stack +1 if 2 met, +2 if 3 met; max 3 Fates held ever, max 2 per family.

Game state (names from `moderator14.make_setup`): `score[6], wards[6], stash[6]=[card,round]|null, fates[6], removed[6], offers[6], mom[6]=[kind|null,len], maxv, rounds[] (per round: [card,target,accuse] x6), hist[] (scores after each round), acts[], priv[] (per round per seat report lines), live[]/old[] (Favours [round,giver,receiver]), gave[], settled_pairs, settle_rounds, settles[6], bet_pairs, bet_log, betrayals[6], harm_landed[[r,src,victim,amt]], harm_any, smite[[r,src,victim]], lostr[] (per round per seat VP lost), lost[6], pledges{round:{seat:target}}, pkept[6], favw[6], tithe_recv[6], tithe_log, strips[6], nostash[6], accused[6], inq_correct[6], pubcalls[[r,caller,named,hit]], leaders[]`.

RNG: deterministic from a game seed (themes, hands, Scandal peek, Final Strike start seat, Fate offers). Store the seed.

## 3. Turn pipeline (engine API)

1. `new_game(seed, human_seats)`: shuffle themes, deal, offer 3 Fates to each seat (stage 0).
2. `submit_talk(seat, {say<=500 chars, whisper{seat:text}<=3, call, pledge, fate, note})` for all 6 seats (bots in parallel). Order of processing once all are in: apply Fate picks; store pledges for the NEXT act round; apply Calls against the round just resolved (not in R1); build each seat's ACT view.
3. `submit_act(seat, {play, target, stash, accuse?, final_strike?, note})`. Normalise like `norm_acts`: invalid play falls back to first dealt card; missing or illegal target falls back to seat+1; invalid stash dropped; accuse dropped if round<4, already used, self, or out of range; final_strike dropped unless R7 and valid. Log every fix; show the human a message when theirs was altered.
4. `resolve(round)`: see section 5. Produces per-seat reports and the public lines.
5. Offers: after R2 (stage 1) and R4 (stage 2) each seat gets 3 Fates; after any round where a Fate was stripped by an Accusation the stripped seat gets 2 (stage 3, only if holding <3). Offers ride on the post-round talk.
6. After R7: `finalize` computes Fate hits, final scores and winner. Then a debrief (optional for the human; mandatory for bots when used for tuning).

Phases are simultaneous: a client sees nothing about others' choices until resolution. Bots may be asked concurrently.

## 4. Views (what each seat is allowed to see)

Build views from engine state, never from raw state. Reference: `act_files`, `result_file`, `private_board`, `tally`, `momentum_text`, `families_text`, `score_view`. For the human UI emit a structured `VIEW` object (see `table.template.html`) with these fields:

- header: game id, seat, round, theme pair, stage (`talk` or `act` or `over`)
- `vp` exact own; `seats[]` each with band, momentum token, public family list (own band shown as exact VP)
- `board`: live Favours given and received (with expiry and whether Betrayal is still available), Betrayals x/2, Settles x/2, kept paying Pledges x/3, Ward yes/no, own streak, Accusation status
- `report[]`: private report lines for the last round
- `fates[]`: held Fates with description and reward; `tallies` string
- `feed[]`: public lines from every seat, public Calls/Accusations/BROKEN Pledges, public pledges for the coming round; `whispers[]` addressed to this seat
- `offer[]` with `offer_label` (normal or REPLACEMENT)
- `hand[]` (3 cards with `theme` flag) and `stash` (with the current stash bonus it would pay), `can_call`
- R7: exact scores for all, strike start seat, `final=true`

Bot views are the same data rendered as the text in `act_files`/`result_file` (copy those templates), preceded by `PLAYER_BRIEF_v14.md` as the system prompt. Bots reply with JSON only.

## 5. Resolution rules (precise)

Use `moderator14.resolve` as the oracle. Notes where text is easy to get wrong:

1. START-of-round values: `start = score` snapshot is used for Hubris/Hoard (STRICTLY greater than the user; ties are not hit), take-from-leader (highest other player, lowest seat among ties), Haloed status, and Tithe/leader tests of the previous round. Exact `leaders` list stored each round.
2. Own gains per player: card `self - recoil`, theme +2 if the played card's pair equals the round theme (virtue or sin, stash counts only if its pair matches that round), streak (not in R7), stash bonus, then the ROUND GAIN CAP 11 on those own components. Streak: virtue run +1 on 2nd, +2 on 3rd and 4th, then 0 (token stays); sin run flat +1 per round after the first; kind change restarts at 1; a card from stash counts for streak. Stash bonus = min(2, round - stashed_round - 1), lost once if a Rumour hit them.
3. Gifts from others (target+, neighbour+, everyone-else+) feed a RECEIVING CAP 7 per round (Settle, Pledge, insurance, Wounded, Tithe, Smite, Betrayal, Call rewards excluded).
4. Harm events per victim, processed in attacker seat order: Ward (blocks the first non-Final-Strike event, consumed even if the cap would have ignored it) -> Sanctuary (first harmful event against a HALOED victim, -1, only if the victim's own card is a virtue; not vs Final Strike) -> loss cap 5 (R7: 7, or 12 if the victim is a runaway) -> losses applied. A Ward gained this round only protects from the next round (`new_wards` added after).
5. Targeted harm = `target<0`, `steal`, `hit_leader`. Area (`others<0`), neighbour (`nbr<0`) and Final Strike are untargeted for Smite, Betrayal and Calls. Reports say `[PLAIN HIT]` or `[STEAL]` and whether the attacker's card was the THEME card (v14).
6. Smite: real harm by a targeted card on a victim who was HALOED at round start: +2 (+3 if streak >=4). Once per (attacker,victim) per round. Betrayal and Smite on the same hit: attacker takes the larger.
7. Favour = virtue with a target that gives VP or a Ward (Forgive counts once). Favour Ward: giver gains a Ward (max 3/game). Favour live for rounds N+1..N+3; all Favours count in R7.
8. Betrayal: a targeted card that removes >=1 VP (after Sanctuary, before the round cap; a Ward block does not count) on a player whose live Favour you hold from an earlier round: +3 (+1 if you Settled with them in the last 3 rounds), once per ordered pair, max 2 per player. Victim: private notice naming the betrayer, insurance +2, no Wounded that round. Attacker gets a private reason when a Betrayal did not pay (Ward, already used, 2 already, window, no VP removed, same-round Favour).
9. Hand guarantee: in rounds 2-4, a seat holding a live received Favour is dealt at least one harmful targeted sin. Every hand: at least one virtue, one sin, and one card needing a target.
10. Settle: when you give a Favour to a player who has a live Favour on you (given in an earlier round, within 3 rounds): +2 each, max 2 Settles per player, one per pair, Favours stay live.
11. Pledge (announced in the talk before the round): kept pays +1 to both for the pledger's first 3 kept; broken (legal targeted virtue held, not played on the target) = pledger -2, named +2, announced BROKEN; void if no legal card (private).
12. Call (talk after the round): only if a targeted non-Betrayal card cost you VP that round; stake 1. YES: named -3 and streak -1, caller gets stake +2 (first caller in seat order after the target collects). NO: named +1, caller loses stake.
13. Wounded: lost >=3 VP to other players' cards (Final Strikes count) -> +2, not if insurance paid, not if the player was the SOLE leader at round start.
14. Accusation (R4-R7, once per game, resolved in seat order after cards): fate must belong to a family the accused publicly holds, else rejected free. First accuser per target per round only; max one strip per target per game. Correct: target loses the Fate permanently, accuser +5. Wrong: accuser -2.
15. Tithe (end of rounds 3-6, after accusations): if one player leads second place by >=6, leader -2 and the lowest-VP player (lowest seat on ties, not the leader) +2; each player may receive at most 6 total. Private to the two players.
16. Final Strike (R7): pay 2, target loses 5 (7 if target is 8+ ahead of second place); resolved from a die-rolled start seat; max 3 per target (rest void and refunded); bounty +1 per valid Strike on an exact leader at round start; counts toward the R7 cap (7, or 12 for a runaway); bypasses Wards and Sanctuary.
17. Floors and order: VP floor 0; Wounded after gains; accusations after cards; Tithe last. Bulwark Ward given to holders at the end of round 2.
18. Final ranking: base VP + Fate points (cap 8 incl. stack), ties by most virtue cards played, then lowest seat. Fate conditions are in `finalize.hit` and the brief.

## 6. Fate offers

`offers(stage)`: per seat build the achievable pool (not held or lost, family cap <2, feasibility test per Fate, e.g. saint needs enough rounds left, late_bloomer needs rank >=3 and >=3 rounds left, survivor rank >=4), pick one aggressive Fate if any, one LIGHT Fate if any, then fill randomly to 3 (2 for replacements). Stage 0 is random. Keep this logic, but it should live in data/config.

## 7. Bot runner

- One LLM call per bot per phase (talk, act, debrief); parallel across seats; model configurable; temperature default.
- Prompt = `PLAYER_BRIEF_v14.md` + the seat's text view for that phase (template text in `act_files`/`result_file`). The brief tells the bot not to read other files; in an API setting just never give them other seats' data.
- Parse JSON strictly with a repair pass; on failure use the fallback in `norm_acts` and a neutral talk ({"say":"..."}) and log it.
- Give each bot seat a persona line (the playtests used: Turtle, Gambler, Diplomat, Vendetta, Optimizer, Showman, Predator, Saint-seeker, Contrarian, Merchant, Zealot, Underdog) so the table is varied. Personas live in `ids.json` context, not in the brief.
- Keep bot conversation history per seat across the game (they remember earlier talk and results), as the playtest agents did.
- Timeouts: if a bot is slow, wait; a human game can pause for bots.

## 8. Front end

Single HTML page per seat view, driven by the `VIEW` object, no server state in the browser. Reuse `table.template.html`: status header, six seat cards (band, token, families), private board, private report coloured good/bad/note, public feed + whispers, then a form for the current phase.
- Talk form: say, three whispers, Call (when available), Pledge, Fate picker (when an offer exists). Show Fate descriptions.
- Act form: three dealt cards plus stash as selectable cards (theme badge, stash bonus), target selector when the card needs one, "move a dealt card to stash", Accuse (R4+ if unused) with a Fate name list limited to families that seat holds, Final Strike in R7 with start seat shown.
- Submit posts JSON to the engine (or, if no server, shows a Copy button; the template currently does this).
- Add: rules drawer (brief text), card-effect tooltips, end-of-game summary showing every seat's final score, Fates held/hit, and the round log.
- Keep the hidden-info rules: the page only ever receives the seat's own view. Do not leak other seats' cards, VP exact values (before R7), or Fates.
- Mobile first (16px side gutters, no horizontal scroll), light and dark theme tokens.

## 9. Test plan

1. Port `resolve` and add unit tests per rule bullet in section 5, each with a small hand-built state (e.g. Hubris with equal scores hits nobody; Ward blocks first by seat order and is consumed even when capped; Sanctuary only if the Haloed victim played a virtue; own-gain cap 11; receiving cap 7; Tithe tie-breaks and 6 cap; Final Strike 7 vs a runaway and 3-strike cap; Pledge broken/void; Betrayal reasons; Wounded exceptions).
2. Replay the dry-run harness: for the same seed and the same random plays, new engine scores must equal `moderator14` scores (all 5 seeds).
3. Property tests: scores never negative; VP changes in a round never exceed caps; hidden-info views contain no other seat's exact VP before R7.
4. Full bot game end-to-end with a stub bot, then with real LLM bots.

## 10. Known rough edges to decide on (ask Mark if unclear)

- RULES_v14 deviations: Tithe tie for fewest picks the lowest seat among non-leaders; Favour Ward cap 3 per game was applied from the start; round gain cap applied before the receiving cap; late_bloomer place-after-R4 uses strict greater, ties share the better place.
- Wards are stacking heavily in v14 (4-5 per player in G30 by R3), likely dulling harm; the v15 review may change Favour Wards. Keep the cap and Ward gain as config.
- Inflation remains high (G29 scores 17-25 after R3). Keep all numeric rules (caps, bonuses, rewards) in one config.
- v15 will change rules after games 29-30; engine and bot brief must load rules/config by version.
- A human seat shown exact VP only for itself; bots currently see the same limited view. Do not give bots more than humans.
- The 2 Fates cap per family and the offer feasibility tests were tuned on paper; expect tweaks.
