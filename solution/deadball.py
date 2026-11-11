"""Dead-ball evidence.

A dead ball is not "the tracker lost the ball": the ball is invisible on 41% of
graded frames and most of those are live play.  The usable evidence is a ball
that stays still with nobody around it, plus a restart tagged by Smart Tagging.
"""

import numpy as np

from .config import Config, DEFAULT
from .tracking import rolling_mean


def _sustained(mask, min_frames):
    """True where a boolean mask has been true for at least ``min_frames``."""
    if min_frames <= 1:
        return mask
    out = np.zeros(len(mask), dtype=bool)
    run = 0
    for index, value in enumerate(mask):
        run = run + 1 if value else 0
        out[index] = run >= min_frames
    # A frame near the start of a true run should count too; a centred view is
    # better for a symmetric decoder.  Keep it causal and cheap: the HMM and the
    # run merge below remove the latency this introduces.
    return out


def missing_ball_age(observed, fps):
    """Seconds since the ball was last actually observed."""
    age = np.empty(len(observed), dtype=np.float32)
    current = 0
    for index, seen in enumerate(observed):
        current = 0 if seen else current + 1
        age[index] = current / float(fps)
    return age


def dead_probability(tracking, features, tag_dead, config=DEFAULT):
    """Per-frame P(dead ball), combining tracking, distance and tag priors."""
    fps = config.fps
    speed = rolling_mean(tracking.ball_speed, max(1, int(round(0.24 * fps))))
    stationary = speed < config.stationary_speed_mps
    stationary = _sustained(stationary, max(1, int(round(config.stationary_window_s * fps))))

    min_distance = features["min_distance"]
    lone = stationary & (min_distance > config.lone_ball_radius_m)
    lone = _sustained(lone, max(1, int(round(config.lone_ball_min_s * fps))))

    age = missing_ball_age(tracking.ball_observed, fps)
    missing_long = (age > 2.0) & (min_distance > 8.0)

    p = np.full(len(speed), config.dead_prior, dtype=np.float32)
    p = np.where(stationary & (min_distance < 1.5), 0.42, p)
    p = np.where(lone, 0.78, p)
    p = np.where(missing_long, np.maximum(p, config.missing_ball_dead_prior), p)
    if tag_dead is not None:
        p = np.where(np.isfinite(tag_dead), np.maximum(p, tag_dead), p)

    return np.clip(rolling_mean(p, max(1, int(round(0.20 * fps)))), 0.0, 0.995).astype(np.float32)
