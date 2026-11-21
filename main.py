#!/usr/bin/env python3
"""Deterministic, standard-library forecast for Exophase trophy earn rates."""

import json
import math
import os
from datetime import datetime
from pathlib import Path
from statistics import NormalDist, median

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))


def timestamp(value):
    """Convert an ISO UTC timestamp (including fractional seconds) to epoch seconds."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def logit(rate):
    p = min(99.99, max(0.01, float(rate))) / 100.0
    return math.log(p / (1.0 - p))


def logistic(value):
    # Stable on either tail and bounded for JSON output.
    if value >= 0:
        e = math.exp(-min(value, 745.0))
        return 100.0 / (1.0 + e)
    e = math.exp(max(value, -745.0))
    return 100.0 * e / (1.0 + e)


def weighted_line(points):
    """Weighted least squares; return intercept, slope, residual SD and slope SE."""
    total = sum(w for _, _, w in points)
    if not points or total <= 0:
        return 0.0, 0.0, 0.0, 0.0
    mx = sum(x * w for x, _, w in points) / total
    my = sum(y * w for _, y, w in points) / total
    sxx = sum(w * (x - mx) ** 2 for x, _, w in points)
    sxy = sum(w * (x - mx) * (y - my) for x, y, w in points)
    slope = sxy / sxx if sxx > 1e-14 else 0.0
    intercept = my - slope * mx
    ss = sum(w * (y - intercept - slope * x) ** 2 for x, y, w in points)
    # Weighted residual SD and slope SE use effective degrees of freedom.
    dof = max(1.0, len(points) - 2.0)
    resid = math.sqrt(max(0.0, ss / total))
    se = math.sqrt(max(0.0, (ss / dof) / sxx)) if sxx > 1e-14 and len(points) >= 3 else 0.0
    return intercept, slope, resid, se


def collapse_history(history, count):
    """Keep state transitions and weight each by its capped duration."""
    kept = []
    previous = None
    for read in history:
        state = (read.get("players_tracked"), tuple(read.get("rates", [])))
        if state != previous:
            kept.append(read)
            previous = state
    if not kept:
        return [], [], []
    times = [timestamp(r["at"]) for r in kept]
    gaps = [times[i + 1] - times[i] for i in range(len(times) - 1) if times[i + 1] > times[i]]
    typical = median(gaps) if gaps else 1800.0
    typical = max(1.0, typical)
    weights = []
    for i in range(len(kept)):
        gap = times[i + 1] - times[i] if i + 1 < len(times) else typical
        weights.append(min(max(1.0, gap), 3.0 * typical))
    origin = timestamp(history[0]["at"])
    xs = [math.log1p(max(0.0, (t - origin) / 3600.0)) for t in times]
    return kept, xs, weights


def choose_window(points):
    """Use the recent 72-hour slice only when it retains at least five observations."""
    if len(points) < 5:
        return points
    latest = max(p[0] for p in points)
    latest_hours = math.expm1(latest)
    cutoff = max(0.0, latest_hours - 72.0)
    recent = [p for p in points if math.expm1(p[0]) >= cutoff]
    return recent if len(recent) >= 5 and len(points) > len(recent) else points


def fit_ceiling(points, target_days):
    """Grid-fit a saturating rate curve, scoring in logit space."""
    best = None
    for a in (0.6, 0.8, 1.0, 1.2, 1.5):
        for k in (0.02, 0.05, 0.1, 0.2, 0.4, 0.8, 1.6, 3.2):
            factors = [1.0 - math.exp(-k * days ** a) for days, _, _ in points]
            denom = sum(weight * factor * factor for factor, (_, _, weight) in zip(factors, points))
            if denom <= 0:
                continue
            c = sum(weight * factor * rate for factor, (_, rate, weight) in zip(factors, points)) / denom
            if c <= 0:
                continue
            sse = sum(weight * (logit(min(99.9, max(0.01, c * factor))) - logit(rate)) ** 2
                      for factor, (_, rate, weight) in zip(factors, points))
            if best is None or sse < best[3]:
                best = (c, k, a, sse)
    if best is None:
        return None
    c, k, a, sse = best
    residual = math.sqrt(sse / sum(weight for _, _, weight in points))
    predicted = min(99.9, max(0.01, c * (1.0 - math.exp(-k * target_days ** a))))
    return c, k, a, sse, residual, predicted


def round4(value):
    # Positive values only: floor(x + .5) implements the requested half-up rounding.
    return math.floor(value * 10000.0 + 0.5) / 10000.0


def forecast(case):
    trophies = case.get("trophies", [])
    history = case.get("history", [])
    levels = case.get("levels", [0.05, 0.25, 0.5, 0.75, 0.95])
    horizon_days = max(0.0, float(case.get("horizon_minutes", 0)) / 1440.0)
    base_sigma = 0.45 * math.sqrt(horizon_days)
    normal = NormalDist()

    if not history:
        sig = min(1.7, max(0.5 * math.sqrt(horizon_days), base_sigma, 0.5))
        rows = []
        for trophy in trophies:
            qs = [round4(logistic(logit(1.0) + normal.inv_cdf(level) * sig)) for level in levels]
            rows.append({"id": trophy["id"], "q": qs})
        return {"trophies": rows}

    kept, xs, weights = collapse_history(history, len(trophies))
    target_x = math.log1p(max(0.0, (timestamp(case["target"]) - timestamp(history[0]["at"])) / 3600.0))
    # The last state may have been repeated many times; the forecast anchor is
    # the checkpoint's final read, while its fitting weight remains capped.
    last_x = math.log1p(max(0.0, (timestamp(history[-1]["at"]) - timestamp(history[0]["at"])) / 3600.0))
    last_read = history[-1]
    per_trophy = []
    slopes = []
    linear_slopes = []
    last_logits = []

    # Build time and player-count regressions independently for each trophy.
    player_line_points = [(xs[i], math.log(float(r["players_tracked"])), weights[i])
                          for i, r in enumerate(kept)
                          if isinstance(r.get("players_tracked"), (int, float)) and r["players_tracked"] > 0]
    pl_a, pl_b, _, _ = weighted_line(player_line_points)
    varied_players = len({r.get("players_tracked") for r in kept}) > 1
    last_players = max(1.0, float(last_read.get("players_tracked") or 1))
    predicted_players = math.exp(min(700.0, pl_a + pl_b * target_x)) if player_line_points else last_players
    predicted_players = min(50.0 * last_players, max(last_players, predicted_players))

    for i, trophy in enumerate(trophies):
        pts = []
        ppts = []
        epts = []
        for j, read in enumerate(kept):
            rates = read.get("rates", [])
            rate = rates[i] if i < len(rates) else None
            if rate is None:
                continue
            value = logit(rate)
            pts.append((xs[j], value, weights[j]))
            nplayers = read.get("players_tracked")
            if isinstance(nplayers, (int, float)) and nplayers > 0:
                ppts.append((math.log(float(nplayers)), value, weights[j]))
                epts.append((xs[j], math.log(float(rate) / 100.0 * float(nplayers) + 0.5), weights[j]))
        if pts:
            latest_hours = max(math.expm1(x) for x, _, _ in pts)
            def recency(point):
                x, value, point_weight = point
                factor = 0.5 ** ((latest_hours - math.expm1(x)) / 48.0)
                return x, value, point_weight * factor
            pts = [recency(point) for point in pts]
            epts = [recency(point) for point in epts]
        pts = choose_window(pts)
        window_xs = {x for x, _, _ in pts}
        epts = [point for point in epts if point[0] in window_xs]
        a, b, resid, se = weighted_line(pts)
        linear_pts = [(math.expm1(x), value, weight) for x, value, weight in pts]
        linear_a, linear_b, linear_resid, _ = weighted_line(linear_pts)
        latest_rate = last_read.get("rates", [None] * len(trophies))
        raw_last = latest_rate[i] if i < len(latest_rate) else None
        if raw_last is not None:
            last_value = logit(raw_last)
            last_logits.append(last_value)
        else:
            last_value = None
        per_trophy.append({"points": pts, "a": a, "b": b, "resid": resid, "se": se,
                           "linear_a": linear_a, "linear_b": linear_b, "linear_resid": linear_resid,
                           "last": last_value, "ppts": ppts, "earner_points": epts})
        if len(pts) >= 2:
            slopes.append(b)
            linear_slopes.append(linear_b)

    median_slope = median(slopes) if slopes else 0.0
    median_linear_slope = median(linear_slopes) if linear_slopes else 0.0
    fallback_last = median(last_logits) if last_logits else logit(1.0)
    rows = []
    for i, (trophy, model) in enumerate(zip(trophies, per_trophy)):
        pts = model["points"]
        n = len(pts)
        last = model["last"] if model["last"] is not None else fallback_last
        dx = max(0.0, target_x - last_x)
        sigma = math.sqrt(base_sigma * base_sigma + model["resid"] ** 2 + (dx * model["se"]) ** 2)
        # Calibrated on synthetic scenarios: unscaled spread covered ~100% of outcomes where ~90% is honest.
        sigma = min(1.7, max(0.20, sigma * 0.65))

        if n < 3:
            median_value = last
            sigma = min(1.7, max(sigma, 0.5 * math.sqrt(horizon_days)))
        else:
            weight = n / (n + 4.0)
            shrunk_b = min(3.5, max(-2.0, weight * model["b"] + (1.0 - weight) * median_slope))
            # Express both views as moves from the last observed logit.
            time_move = shrunk_b * dx
            hours_ahead = max(0.0, math.expm1(target_x) - math.expm1(last_x))
            shrunk_linear_b = min(3.5, max(-2.0, weight * model["linear_b"] + (1.0 - weight) * median_linear_slope))
            linear_move = shrunk_linear_b * hours_ahead
            # Log-time fits decelerating growth; linear-time fits a steady per-hour logit climb. Extrapolate with the better-fitting transform.
            use_linear = model["linear_resid"] < model["resid"]
            picked_move = linear_move if use_linear else time_move
            if len(model["earner_points"]) >= 3:
                earner = model["earner_points"]
                _, earner_b, earner_resid, _ = weighted_line(earner)
                earner_linear = [(math.expm1(x), value, point_weight) for x, value, point_weight in earner]
                _, earner_linear_b, earner_linear_resid, _ = weighted_line(earner_linear)
                earner_move = (earner_linear_b * hours_ahead if earner_linear_resid < earner_resid
                               else earner_b * dx)
                earner_move -= math.log(predicted_players) - math.log(last_players)
                picked_move = 0.5 * (picked_move + earner_move)
            blended_move = picked_move
            player_move = 0.0
            if len(model["ppts"]) >= 4 and varied_players:
                _, pb, _, _ = weighted_line(model["ppts"])
                player_move = pb * (math.log(predicted_players) - math.log(last_players))
                blended_move = 0.5 * (picked_move + player_move)
            ceiling_fit_pts = pts
            if n > 48:
                sample_indices = [round(i * (n - 1) / 47) for i in range(48)]
                ceiling_fit_pts = [pts[index] for index in sample_indices]
            ceiling_points = [(math.expm1(x) / 24.0, logistic(value), point_weight)
                              for x, value, point_weight in ceiling_fit_pts]
            ceiling = fit_ceiling(ceiling_points, max(0.0, math.expm1(target_x) / 24.0)) if n >= 4 else None
            ceiling_wins = ceiling is not None and ceiling[4] < (model["linear_resid"] if use_linear else model["resid"])
            if ceiling_wins:
                ceiling_move = logit(ceiling[5]) - last
                if len(model["ppts"]) >= 4 and varied_players:
                    ceiling_move = 0.5 * (ceiling_move + player_move)
                median_value = last + 0.55 * ceiling_move
            else:
                # Chosen for robustness across synthetic scenarios, not fitted to one seed.
                median_value = last + (0.85 if use_linear else 0.35) * blended_move
        median_value = min(logit(99.9), max(logit(0.01), median_value))
        center = logistic(median_value)
        qs = []
        for level in levels:
            z = normal.inv_cdf(float(level))
            if z > 0:
                side_sigma = sigma * (1.0 + 0.30 * math.exp(-center / 8.0))
            elif z < 0:
                side_sigma = sigma * (1.0 + 0.30 * center / 100.0)
            else:
                side_sigma = sigma
            qs.append(round4(min(100.0, max(0.0, logistic(median_value + z * side_sigma)))))
        # The supplied levels are ordered in normal cases; enforce monotonicity regardless.
        for j in range(1, len(qs)):
            qs[j] = max(qs[j], qs[j - 1])
        rows.append({"id": trophy["id"], "q": qs})
    return {"trophies": rows}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in"), key=lambda p: p.name):
        case = json.loads(path.read_text(encoding="utf-8"))
        result = forecast(case)
        payload = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
        (OUTPUT_DIR / (path.stem + ".out")).write_text(payload, encoding="utf-8")


if __name__ == "__main__":
    main()
