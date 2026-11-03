"""Runs learner code inside the browser (Pyodide). Loaded after checker.py and SETUP."""
import ast, io, json, traceback, contextlib

pd.set_option('display.max_columns', 12)
_BASE = {k: v for k, v in globals().items() if isinstance(v, pd.DataFrame)}


def _ns():
    ns = {'pd': pd, 'np': np, '__name__': '__main__'}
    for k, v in _BASE.items():
        ns[k] = v.copy()
    return ns


def _show(v, label=None):
    if isinstance(v, pd.DataFrame):
        out = {'html': v.to_html(max_rows=16, max_cols=10, border=0, classes='frame'),
               'meta': f'DataFrame · {v.shape[0]:,} rows × {v.shape[1]} columns'}
    elif isinstance(v, pd.Series):
        out = {'html': v.to_frame().to_html(max_rows=16, border=0, classes='frame'),
               'meta': f'Series · {len(v):,} values · dtype {v.dtype}'}
    else:
        text = repr(v)
        out = {'text': text[:6000], 'meta': type(v).__name__}
    if label:
        out['label'] = label
    return out


def _exec(code, ns):
    tree = ast.parse(code, '<your code>')
    last = None
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        last = ast.Expression(tree.body.pop().value)
    exec(compile(tree, '<your code>', 'exec'), ns)
    if last is not None:
        return eval(compile(last, '<your code>', 'eval'), ns), True
    return None, False


def _err(e):
    if isinstance(e, SyntaxError):
        if e.text and e.text.rstrip().endswith('='):
            return f'line {e.lineno} is unfinished: write your answer after the = sign.'
        where = f'line {e.lineno}: ' if e.lineno else ''
        return f'SyntaxError: {where}{e.msg}'
    frames = [f for f in traceback.extract_tb(e.__traceback__) if f.filename == '<your code>']
    where = f'line {frames[-1].lineno}' if frames else ''
    msg = f'{type(e).__name__}: {e}'
    return (where + ' · ' if where else '') + msg[:1500]


def _pg_run(code, solution, opts_json, mode):
    res = {'stdout': '', 'shown': None, 'error': None, 'check': None}
    out = io.StringIO()
    if mode == 'expected':
        code = solution
    ns = _ns()
    try:
        with contextlib.redirect_stdout(out):
            v, has = _exec(code, ns)
        if has and v is not None and mode != 'expected':
            res['shown'] = _show(v)
        elif 'result' in ns:
            res['shown'] = _show(ns['result'], 'result')
    except Exception as e:
        res['error'] = _err(e)
    res['stdout'] = out.getvalue()[:20000]
    if mode == 'check' and solution:
        if res['error']:
            res['check'] = {'ok': False, 'msg': 'Your code raised an error. Fix it, then check again.'}
        else:
            ens = _ns()
            with contextlib.redirect_stdout(io.StringIO()):
                exec(solution, ens)
            ok, msg = check(ns.get('result'), ens.get('result'), **json.loads(opts_json))
            res['check'] = {'ok': ok, 'msg': msg}
    return json.dumps(res, default=str)
