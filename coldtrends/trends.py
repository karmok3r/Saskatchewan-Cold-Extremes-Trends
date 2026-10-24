"""Mann-Kendall trend test, Sen's slope and Benjamini-Hochberg FDR."""
import numpy as np
from scipy.stats import norm

from .config import EDGE_WINDOW, MIN_EDGE_YEARS, MIN_VALID_YEARS


def mann_kendall_sen(years, values):
    """Return n, Sen slope (units/yr), intercept, Kendall tau, two-sided p-value."""
    t = np.asarray(years, float)
    y = np.asarray(values, float)
    ok = ~np.isnan(y)
    t, y = t[ok], y[ok]
    n = len(y)
    if n < 3:
        return n, np.nan, np.nan, np.nan, np.nan

    i, j = np.triu_indices(n, 1)
    dy, dt = y[j] - y[i], t[j] - t[i]
    s = np.sign(dy).sum()

    # Variance with tie correction (matters for count indices with many zeros).
    _, counts = np.unique(y, return_counts=True)
    var = (n * (n - 1) * (2 * n + 5) - np.sum(counts * (counts - 1) * (2 * counts + 5))) / 18
    if var <= 0:
        p = 1.0
    else:
        z = (s - np.sign(s)) / np.sqrt(var)
        p = 2 * (1 - norm.cdf(abs(z)))

    slope = np.median(dy / dt)
    intercept = np.median(y - slope * t)
    tau = s / (0.5 * n * (n - 1))
    return n, slope, intercept, tau, p


def has_coverage(years, values, start, end):
    """Enough valid years overall and near both ends of the study period."""
    years = np.asarray(years)
    ok = ~np.isnan(np.asarray(values, float))
    early = ok & (years < start + EDGE_WINDOW)
    late = ok & (years > end - EDGE_WINDOW)
    return ok.sum() >= MIN_VALID_YEARS and early.sum() >= MIN_EDGE_YEARS and late.sum() >= MIN_EDGE_YEARS


def fdr_bh(pvalues):
    """Benjamini-Hochberg adjusted p-values (q-values); NaNs pass through."""
    p = np.asarray(pvalues, float)
    q = np.full_like(p, np.nan)
    ok = ~np.isnan(p)
    pv = p[ok]
    m = len(pv)
    if m == 0:
        return q
    order = np.argsort(pv)
    ranked = pv[order] * m / np.arange(1, m + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(ranked, 1.0)
    q[ok] = out
    return q
