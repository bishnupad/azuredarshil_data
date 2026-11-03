"""Compares a learner's `result` with the reference answer and explains differences."""
import numpy as np
import pandas as pd


def _prep(obj, ignore_index, unordered):
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        if unordered:
            obj = obj.sort_index()
        if ignore_index:
            obj = obj.reset_index(drop=True)
    return obj


def check(got, expected, ignore_index=False, unordered=False):
    """Return (ok, message)."""
    if got is None:
        return False, "`result` is not set. Assign your answer to a variable called result."
    got = _prep(got, ignore_index, unordered)
    exp = _prep(expected, ignore_index, unordered)
    kind = type(exp).__name__
    if isinstance(exp, pd.DataFrame):
        if not isinstance(got, pd.DataFrame):
            return False, f"Expected a DataFrame but got {type(got).__name__}."
        if got.shape != exp.shape:
            return False, f"Shape is {got.shape}; expected {exp.shape}."
        if [str(c) for c in got.columns] != [str(c) for c in exp.columns]:
            return False, f"Columns are {list(got.columns)}; expected {list(exp.columns)}."
        try:
            pd.testing.assert_frame_equal(got, exp, check_dtype=False, check_names=False,
                                          check_index_type=False, check_column_type=False,
                                          check_categorical=False, check_freq=False)
        except AssertionError as e:
            return False, "Values differ: " + _short(e)
        return True, "Correct!"
    if isinstance(exp, pd.Series):
        if isinstance(got, pd.DataFrame) and got.shape[1] == 1:
            got = got.iloc[:, 0]
        if not isinstance(got, pd.Series):
            return False, f"Expected a Series but got {type(got).__name__}."
        if len(got) != len(exp):
            return False, f"Length is {len(got)}; expected {len(exp)}."
        try:
            pd.testing.assert_series_equal(got, exp, check_dtype=False, check_names=False,
                                           check_index_type=False, check_categorical=False,
                                           check_freq=False)
        except AssertionError as e:
            return False, "Values differ: " + _short(e)
        return True, "Correct!"
    if isinstance(exp, (float, np.floating)):
        try:
            ok = bool(np.isclose(float(got), float(exp)))
        except Exception:
            ok = False
        return (True, "Correct!") if ok else (False, f"Got {got!r}; expected a different number.")
    if isinstance(exp, (np.integer, int, np.bool_, bool)):
        try:
            ok = got == exp and not isinstance(got, (pd.Series, pd.DataFrame))
            ok = bool(ok)
        except Exception:
            ok = False
        return (True, "Correct!") if ok else (False, f"Got {got!r}; expected a different value.")
    if isinstance(exp, (list, tuple)):
        if not isinstance(got, (list, tuple)):
            return False, f"Expected a {kind} but got {type(got).__name__}."
        return (True, "Correct!") if list(got) == list(exp) else (False, f"Got {list(got)[:8]}...; not quite.")
    try:
        ok = bool(got == exp)
    except Exception:
        ok = False
    return (True, "Correct!") if ok else (False, "Not quite.")


def _short(e):
    lines = [l for l in str(e).splitlines() if l.strip()]
    return " ".join(lines[:4])[:400]
