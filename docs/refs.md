# External references (not vendored)

## MultiQT — authors' reference implementation

- Repository: https://github.com/tiffanyding/multiQT (Ding, Gibbs and Tibshirani, 2025,
  "Calibrated Multi-Level Quantile Forecasting", arXiv:2512.23671)
- Pinned commit: `3300f75c5cedb7f888af4058032a94940b682ccb`
  (2026-08-01 10:14:47 -0400, "correcting axes typos in initialization")
- Cloned 2026-10-16 to `..\_refs\multiQT` (outside this repository).
- The repository has **no LICENSE**, so none of its code is copied here. `src/daqa/methods/multiqt.py`
  is an independent implementation. `tests/test_multiqt.py` loads only the `isotonic_regression`
  and `multiQT` definitions from `example.py` in the clone at test time (to avoid the file's
  plotting imports) and skips the parity test if the clone is missing or at another commit.
  Override the location with the `MULTIQT_REF_DIR` environment variable.

To reproduce the parity test:

```
git clone https://github.com/tiffanyding/multiQT "..\_refs\multiQT"
git -C "..\_refs\multiQT" checkout 3300f75c5cedb7f888af4058032a94940b682ccb
```
