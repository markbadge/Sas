"""Command line: `python -m ssengine serve` (play client + API) and `python -m ssengine sim` (all-bot game)."""
import argparse
import json
import sys

from .engine import N
from .session import Session


def sim(args):
    """Run a full game with every seat a bot (no human). Prints the final table; --debrief asks the LLM bots for feedback."""
    sess = Session.create(args.seed, human_seats=(), bots=args.bots, model=args.model, store_dir=args.store, debrief=args.debrief, rules_version=args.rules)
    sess.start()
    ok = sess.wait(lambda g: g.s['phase'] == 'over' and (not args.debrief or sess.debriefs.get('done') or args.bots == 'stub'), timeout=args.timeout)
    if not ok:
        print('timed out', file=sys.stderr)
        return 1
    f = sess.g.s['final']
    for r in f['results']:
        print(f"S{r['seat']} base {r['base']:3d} +{r['bonus']} = {r['final']:3d}  held={','.join(r['held']) or '-'} met={','.join(r['hits']) or '-'}")
    print('winner: S%d' % f['winner'])
    if sess.botlog:
        print(f'{len(sess.botlog)} bot log entries (parse failures, corrections, errors); first: {sess.botlog[0]}', file=sys.stderr)
    if args.debrief:
        print(json.dumps(sess.debriefs, indent=1))
    sess.close()
    return 0


def serve(args):
    from .server import run
    run(args.host, args.port, args.store, args.bots, args.model)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog='ssengine')
    sub = p.add_subparsers(dest='cmd', required=True)
    for name, fn in (('serve', serve), ('sim', sim)):
        sp = sub.add_parser(name)
        sp.set_defaults(fn=fn)
        sp.add_argument('--bots', choices=['llm', 'stub'], default='llm')
        sp.add_argument('--model', default=None, help='bot model id (default: $SS_MODEL or claude-sonnet-5-5)')
        sp.add_argument('--store', default='games', help='directory for saved games')
        if name == 'serve':
            sp.add_argument('--host', default='127.0.0.1')
            sp.add_argument('--port', type=int, default=8000)
        else:
            sp.add_argument('--seed', type=int, default=1)
            sp.add_argument('--rules', default='v14')
            sp.add_argument('--debrief', action='store_true')
            sp.add_argument('--timeout', type=float, default=3600)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == '__main__':
    sys.exit(main())
