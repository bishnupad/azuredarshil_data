"""Run every reference solution and confirm the checker accepts it and rejects the starter."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from exercises import SETUP, EXERCISES
from checker import check

base = {}
exec(SETUP, base)

def run(code):
    ns = {k: (v.copy() if hasattr(v, 'copy') and k in ('athletes','coaches','entries','medals','teams','sales','messy') else v) for k, v in base.items()}
    exec(code, ns)
    return ns.get('result')

bad = 0
for ex in EXERCISES:
    exp = run(ex['solution'])
    opts = dict(ignore_index=ex.get('ignore_index', False), unordered=ex.get('unordered', False))
    ok, msg = check(run(ex['solution']), exp, **opts)
    try:
        sok, _ = check(run(ex['starter']), exp, **opts)
    except Exception:
        sok = False
    size = getattr(exp, 'shape', exp if not hasattr(exp, '__len__') else len(exp))
    flag = '' if ok and not sok else '  <-- PROBLEM'
    if flag: bad += 1
    print(f"{ex['id']:12} {type(exp).__name__:10} {str(size)[:40]:40}{flag} {'' if ok else msg}")
print('problems:', bad)
sys.exit(1 if bad else 0)
