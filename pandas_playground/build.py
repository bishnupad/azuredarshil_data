"""Build the browser playground (dist/) and the Jupyter notebook from exercises.py.

    python build.py --pyodide /path/to/pyodide-files --out /path/to/dist

The Pyodide runtime (~22 MB) is not stored in the repo. The folder passed with
--pyodide needs pyodide.js, pyodide.asm.js, pyodide.asm.wasm, python_stdlib.zip,
pyodide-lock.json and the numpy, pandas, python-dateutil, pytz and six wheels.
"""
import argparse, json, os, shutil
import pandas as pd
from exercises import SETUP, LEVELS, EXERCISES

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
FILES = ['athletes.csv', 'coaches.csv', 'entriesgender.csv', 'medals.csv', 'teams.csv', 'sales.csv', 'messy.csv']
ABOUT = {
    'athletes': 'Every Tokyo 2020 athlete with country and discipline.',
    'coaches': 'Coaches by country and discipline. Event is often missing.',
    'entries': 'Female and male entries per discipline (from EntriesGender.csv).',
    'medals': 'The medal table: one row per country that won a medal.',
    'teams': 'Team entries by discipline, country and event.',
    'sales': 'Practice table: daily units sold per store and product, Jan to Jun 2024. date is text until you convert it.',
    'messy': 'Practice table full of problems: stray spaces, mixed case, text numbers, gaps and a duplicate row.',
}


def datasets():
    ns = {}
    exec(SETUP, ns)
    out = []
    for name in ['athletes', 'coaches', 'entries', 'medals', 'teams', 'sales', 'messy']:
        df = ns[name]
        out.append({'name': name, 'rows': len(df), 'about': ABOUT[name],
                    'cols': [[c, str(t)] for c, t in df.dtypes.items()],
                    'preview': df.head(4).to_html(border=0, classes='frame')})
    return out


def build_html(out_dir, pyodide_dir):
    data = {
        'levels': LEVELS,
        'exercises': [{k: v for k, v in e.items()} for e in EXERCISES],
        'setup': SETUP,
        'checker': open('checker.py').read(),
        'runtime': open('runtime.py').read(),
        'datasets': datasets(),
        'files': FILES,
        'wheels': sorted(f for f in os.listdir(pyodide_dir) if f.endswith('.whl')) if pyodide_dir else [],
    }
    blob = json.dumps(data).replace('</', '<\\/')
    html = open('template.html').read().replace('__DATA__', blob).replace('__COUNT__', str(len(EXERCISES)))
    os.makedirs(os.path.join(out_dir, 'data'), exist_ok=True)
    os.makedirs(os.path.join(out_dir, 'py'), exist_ok=True)
    open(os.path.join(out_dir, 'index.html'), 'w').write(html)
    shutil.copy('worker.js', out_dir)
    for f in FILES:
        shutil.copy(os.path.join('data', f), os.path.join(out_dir, 'data', f))
    if pyodide_dir:
        import base64
        for f in os.listdir(pyodide_dir):
            src = os.path.join(pyodide_dir, f)
            if f.endswith(('.js', '.wasm', 'pyodide-lock.json')):
                shutil.copy(src, os.path.join(out_dir, 'py', f))
            elif f.endswith(('.zip', '.whl')):  # host serves web types only, so ship as base64 text
                open(os.path.join(out_dir, 'py', f + '.txt'), 'w').write(base64.b64encode(open(src, 'rb').read()).decode())


def build_notebook(path):
    def md(s): return {'cell_type': 'markdown', 'metadata': {}, 'source': s}
    def code(s): return {'cell_type': 'code', 'metadata': {}, 'execution_count': None, 'outputs': [], 'source': s}
    cells = [md("# Pandas Dojo\n\nDrills from basic to advanced on the Tokyo 2020 Olympics data in this repo.\n\n"
                "For each drill, write your code in the cell and store the answer in `result`, then run the `check` cell. "
                "Run the setup cell first. Solutions are in `exercises.py` if you get stuck."),
             code("import os, sys\nsys.path.insert(0, os.getcwd())\nfrom exercises import SETUP, EXERCISES\nfrom checker import check as _check\nexec(SETUP)\n"
                  "_EX = {e['id']: e for e in EXERCISES}\n\n"
                  "def check(ex_id, result):\n    e = _EX[ex_id]\n    ns = {}\n    exec(SETUP, ns)\n    exec(e['solution'], ns)\n"
                  "    ok, msg = _check(result, ns['result'], ignore_index=e.get('ignore_index', False), unordered=e.get('unordered', False))\n"
                  "    print(('PASS  ' if ok else 'TRY AGAIN  ') + msg)\n")]
    for li, lv in enumerate(LEVELS, 1):
        cells.append(md(f"## Level {li}: {lv['name']} ({lv['tag']})\n\n{lv['intro']}\n\n**Cheat sheet**\n\n" + "\n".join(f"- `{c}`" for c in lv['cheats'])))
        for i, e in enumerate([x for x in EXERCISES if x['level'] == lv['id']], 1):
            cells.append(md(f"### {li}.{i} {e['title']}\n\n{e['task']}\n\n<details><summary>Hint</summary>{e['hint']}</details>"))
            cells.append(code(e['starter'] + f"\n\ncheck('{e['id']}', result)"))
    nb = {'cells': cells, 'metadata': {'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'}},
          'nbformat': 4, 'nbformat_minor': 5}
    json.dump(nb, open(path, 'w'), indent=1)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='dist')
    ap.add_argument('--pyodide', default=None)
    a = ap.parse_args()
    build_html(a.out, a.pyodide)
    build_notebook('pandas_dojo.ipynb')
    print('built', a.out, 'and pandas_dojo.ipynb')
