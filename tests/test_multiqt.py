import ast
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from daqa.cache import DATASETS, QUANTILE_LEVELS, load_cache, load_grid
from daqa.methods.multiqt import ADAPTIVE, IDENTITY, isotonic, lr_candidates, run_multiqt, run_stream
from daqa.timing import CELLS

REF_COMMIT = "3300f75c5cedb7f888af4058032a94940b682ccb"
REF_DIR = Path(os.environ.get("MULTIQT_REF_DIR", Path(__file__).resolve().parents[2] / "_refs" / "multiQT"))
LEVELS3 = [0.1, 0.5, 0.9]


# ---------- (a) hand-worked 5-step toy stream ----------

def test_toy_stream_d0_hand_worked():
    # Levels (0.1, 0.5, 0.9), fixed eta = 1, base b = [0, 0.2, 0.4] every step,
    # D = 0 (h=1, d=0): the record issued at p-1 updates theta before issue p.
    base = np.tile([0.0, 0.2, 0.4], (5, 1))
    y = np.array([0.3, 0.5, 0.2, -1.0, 7.0])  # y[4] never matures inside the stream
    res = run_stream(y, base, range(5), h=1, d=0, lr=1.0, levels=LEVELS3)
    expected_theta = [
        [0.0, 0.0, 0.0],  # p0: start
        # p1: y0=0.3 vs q0=[0,0.2,0.4] -> cov [0,0,1]; theta = 0 - ([0,0,1] - [.1,.5,.9]) = [.1,.5,-.1]
        [0.1, 0.5, -0.1],
        # p2: y1=0.5 vs played q1=[.1,.5,.5] -> cov [0,1,1] (non-strict <=; the unprojected
        #     [.1,.7,.3] would give [0,1,0]); theta = [.1+.1, .5-.5, -.1-.1] = [.2, 0, -.2]
        [0.2, 0.0, -0.2],
        # p3: y2=0.2 vs q2=[.2,.2,.2] -> cov [1,1,1]; theta = [.2-.9, 0-.5, -.2-.1] = [-.7,-.5,-.3]
        [-0.7, -0.5, -0.3],
        # p4: y3=-1 vs q3=[-.7,-.3,.1] -> cov [1,1,1]; theta = [-.7-.9, -.5-.5, -.3-.1] = [-1.6,-1,-.4]
        [-1.6, -1.0, -0.4],
    ]
    expected_q = [
        [0.0, 0.2, 0.4],
        # b + theta = [.1, .7, .3] crosses; isotonic pools (.7 + .3) / 2 = .5
        [0.1, 0.5, 0.5],
        [0.2, 0.2, 0.2],  # b + theta = [.2, .2, .2]
        [-0.7, -0.3, 0.1],  # b + theta = [-.7, -.3, .1]
        [-1.6, -0.8, 0.0],  # b + theta = [-1.6, -.8, 0]
    ]
    np.testing.assert_allclose(res.theta, expected_theta, atol=1e-12)
    np.testing.assert_allclose(res.q, expected_q, atol=1e-12)
    np.testing.assert_array_equal(res.eta, [np.nan, 1, 1, 1, 1])
    assert res.n_nan_skips == 0


def test_toy_stream_d3_waits_for_maturity():
    # D = 3 (h=4, d=0): record 0 matures at issue 0+4+0 = 4; nothing moves before.
    base = np.tile([0.0, 0.2, 0.4], (5, 1))
    y = np.array([0.3, 9.0, 9.0, 9.0, 9.0])
    res = run_stream(y, base, range(5), h=4, d=0, lr=1.0, levels=LEVELS3)
    np.testing.assert_allclose(res.theta[:4], 0.0)
    np.testing.assert_allclose(res.q[:4], base[:4])
    # p4: y0=0.3 vs q0=[0,.2,.4] -> cov [0,0,1]; theta = [.1,.5,-.1]; q = iso([.1,.7,.3]) = [.1,.5,.5]
    np.testing.assert_allclose(res.theta[4], [0.1, 0.5, -0.1], atol=1e-12)
    np.testing.assert_allclose(res.q[4], [0.1, 0.5, 0.5], atol=1e-12)


def test_identity_never_moves():
    rng = np.random.default_rng(1)
    base = np.sort(rng.normal(size=(30, 9)), axis=1)
    res = run_stream(rng.normal(size=30), base, range(30), h=1, d=2, lr=IDENTITY)
    assert (res.theta == 0).all()
    np.testing.assert_array_equal(res.q, base)


def test_lr_candidates_and_validation():
    assert lr_candidates((0.01, 0.1)) == (IDENTITY, 0.01, 0.1, ADAPTIVE)
    for bad in [(0.1, 0.1), (0.0, 0.1), (-1, 0.1)]:
        with pytest.raises(ValueError):
            lr_candidates(bad)
    for lr in [0, -0.5, "adaptive", True, None]:
        with pytest.raises(ValueError):
            run_stream(np.zeros(3), np.zeros((3, 9)), range(3), 1, 0, lr)


def test_isotonic_projection_matches_sklearn_bitwise():
    from sklearn.isotonic import IsotonicRegression

    rng = np.random.default_rng(7)
    x = np.arange(9)
    for n in range(3000):
        v = np.sort(rng.normal(size=9)) + rng.normal(size=9) * rng.choice([0, 0.05, 1, 10])
        if n % 4 == 0:
            v = np.round(v, 1)  # ties
        np.testing.assert_array_equal(isotonic(v), IsotonicRegression().fit(x, v).predict(x))


# ---------- (b) parity with the authors' multiQT() ----------

def _authors_multiqt():
    path = REF_DIR / "example.py"
    if not path.exists():
        pytest.skip(f"authors' MultiQT clone not found at {REF_DIR}; clone https://github.com/tiffanyding/multiQT "
                    f"there at {REF_COMMIT} (see docs/refs.md) or set MULTIQT_REF_DIR")
    head = subprocess.run(["git", "-C", str(REF_DIR), "rev-parse", "HEAD"], capture_output=True, text=True)
    if head.stdout.strip() != REF_COMMIT:
        pytest.skip(f"clone at {REF_DIR} is at {head.stdout.strip() or '?'}, parity is pinned to {REF_COMMIT}")
    from sklearn.isotonic import IsotonicRegression

    # Load only the two algorithm definitions; example.py's top-level plotting imports are not needed.
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    defs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in {"isotonic_regression", "multiQT"}]
    assert sorted(n.name for n in defs) == ["isotonic_regression", "multiQT"]
    ns = {"np": np, "IsotonicRegression": IsotonicRegression}
    exec(compile(ast.Module(body=defs, type_ignores=[]), str(path), "exec"), ns)
    return ns["multiQT"]


def _random_stream(seed, T=160):
    rng = np.random.default_rng(seed)
    t = np.arange(T)
    y = 2 + np.sin(t / 8) + rng.normal(scale=0.4 + 0.3 * (t > T // 2), size=T)
    centre = np.r_[2.0, y[:-1]] * 0.7 + 0.6
    base = np.sort(centre[:, None] + rng.normal(scale=0.5, size=(T, 9)), axis=1)
    return y, base


@pytest.mark.parametrize("D, h, d, seed", [(0, 1, 0, 11), (3, 4, 0, 12), (7, 4, 4, 13)])
@pytest.mark.parametrize("lr", [0.05, 0.5, ADAPTIVE])
def test_parity_with_authors_multiqt(D, h, d, seed, lr):
    multiQT = _authors_multiqt()
    y, base = _random_stream(seed)
    T = len(y)
    delay = [[t - D] if t >= D else [] for t in range(T)]  # proposal 5.1: delay[t] = [t - D]
    theirs = multiQT(y, QUANTILE_LEVELS, base_forecasts=base.T, lr=lr, delay=delay)
    ours = run_stream(y, base, range(T), h=h, d=d, lr=lr)
    assert h - 1 + d == D
    np.testing.assert_array_equal(ours.q, theirs.T)  # exactly identical
    assert not np.array_equal(ours.q, base)  # the stream actually adapted


def test_identity_matches_authors_projection():
    # The authors' multiQT() rejects lr = 0; identity is their projection of the base alone.
    multiQT = _authors_multiqt()
    y, base = _random_stream(5)
    ours = run_stream(y, base, range(len(y)), h=1, d=0, lr=IDENTITY)
    tiny = multiQT(y, QUANTILE_LEVELS, base_forecasts=base.T, lr=1e-300, delay=[[]] * len(y))
    np.testing.assert_array_equal(ours.q, tiny.T)


# ---------- (c) NaN targets ----------

@pytest.mark.parametrize("lr", [0.3, ADAPTIVE])
def test_nan_label_leaves_theta_unchanged(lr):
    y, base = _random_stream(21, T=80)
    y[[10, 40]] = np.nan
    h, d = 1, 2  # record r matures at issue r + 3
    res = run_stream(y, base, range(80), h=h, d=d, lr=lr)
    assert res.n_nan_skips == 2
    for r in (10, 40):
        p = r + h + d
        np.testing.assert_array_equal(res.theta[p], res.theta[p - 1])
        assert np.isnan(res.eta[p])
    assert np.isfinite(res.eta[[13 - 1, 13 + 1, 60]]).all()  # neighbours still update; NaN never enters eta
    assert not np.isnan(res.q).any()


@pytest.fixture(scope="module")
def sl():
    return load_grid("srilanka"), load_cache("srilanka")


@pytest.mark.parametrize("h, d", CELLS)
def test_srilanka_nan_skip_counts(h, d, sl):
    grid, cache = sl
    res = run_multiqt("srilanka", h, d, ADAPTIVE, cache=cache, grid=grid)
    assert res.nan_skips == {a: int(a == "Puttalam") for a in grid.columns}
    # Puttalam's NaN week (row 998) is the target of the record issued at 998 - h; it matures at 998 + d.
    j = list(grid.columns).index("Puttalam")
    p = int(np.flatnonzero(res.issue_idx == grid.index.get_loc(pd.Timestamp("2026-02-09")) + d)[0])
    np.testing.assert_array_equal(res.theta[p, j], res.theta[p - 1, j])


# ---------- (d) issued vectors ----------

@pytest.mark.parametrize("ds", DATASETS)
@pytest.mark.parametrize("lr", [IDENTITY, 0.1, ADAPTIVE])
def test_issued_non_decreasing_and_non_negative(ds, lr):
    grid, cache = load_grid(ds), load_cache(ds)
    for h, d in CELLS:
        res = run_multiqt(ds, h, d, lr, cache=cache, grid=grid)
        assert res.issued.shape == (208, grid.shape[1], 9)
        assert not np.isnan(res.issued).any()
        assert (np.diff(res.issued, axis=-1) >= 0).all()
        assert (res.issued >= 0).all()
        assert (np.diff(res.q_scaled, axis=-1) >= 0).all()
        np.testing.assert_array_equal(res.issued, np.maximum(0, res.q_scaled * res.scale[None, :, None]))
        if lr == IDENTITY:  # identity reproduces the clipped frozen base exactly (up to float32 -> float64)
            k = list(cache.delays).index(d)
            b = cache.sorted[:, :, k, h + d - 1].astype(np.float64)
            np.testing.assert_allclose(res.issued, np.maximum(0, b), rtol=1e-12, atol=1e-9)
