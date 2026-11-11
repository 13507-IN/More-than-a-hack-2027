"""Temporal decoder: sticky three-state Viterbi plus run repair.

Per-frame nearest-player labels flicker, and flicker is fatal for spellF1: each
flicker is a spurious possession.  The decoder therefore treats possession as a
state that persists, switches only on sustained evidence, and then removes any
remaining very short runs.
"""

import numpy as np

from .config import Config, DEFAULT
from .tracking import rolling_mean, sigmoid


def transition_matrix(config=DEFAULT):
    """3x3 transition probabilities for states [H, A, D]."""
    fps = float(config.fps)
    stay_team = 1.0 - 1.0 / (config.mean_team_spell_s * fps)
    stay_dead = 1.0 - 1.0 / (config.mean_dead_spell_s * fps)
    exit_team = 1.0 - stay_team
    exit_dead = 1.0 - stay_dead
    return np.array([
        [stay_team, exit_team * 0.5, exit_team * 0.5],
        [exit_team * 0.5, stay_team, exit_team * 0.5],
        [exit_dead * 0.5, exit_dead * 0.5, stay_dead],
    ], dtype=np.float64)


def emissions(team_logit, dead_probability, config=DEFAULT):
    """Log emission probabilities for H, A and D at every frame."""
    eps = 1e-6
    p_home = sigmoid(team_logit)
    p_dead = np.clip(dead_probability, eps, 1.0 - eps)
    p_alive = 1.0 - p_dead
    return np.column_stack([
        np.log(np.clip(p_alive * p_home, eps, 1.0)),
        np.log(np.clip(p_alive * (1.0 - p_home), eps, 1.0)),
        np.log(p_dead),
    ]).astype(np.float64)


def viterbi(emission, transitions):
    """Most likely state sequence under a first-order Markov model."""
    n, n_states = emission.shape
    log_transition = np.log(np.clip(transitions, 1e-12, 1.0))
    score = emission[0].copy()
    back = np.zeros((n, n_states), dtype=np.int8)

    for index in range(1, n):
        candidate = score[:, None] + log_transition  # (prev, current)
        back[index] = np.argmax(candidate, axis=0)
        score = candidate[back[index], np.arange(n_states)] + emission[index]

    states = np.empty(n, dtype=np.int8)
    states[-1] = int(np.argmax(score))
    for index in range(n - 1, 0, -1):
        states[index - 1] = back[index, states[index]]
    return states


def _runs(codes):
    """(starts, ends, values) for maximal runs.  End is inclusive."""
    if len(codes) == 0:
        return (np.array([], dtype=np.int64), np.array([], dtype=np.int64),
                np.array([], dtype=np.int8))
    change = np.flatnonzero(codes[1:] != codes[:-1]) + 1
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change - 1, [len(codes) - 1]))
    return starts, ends, codes[starts]


def repair_short_runs(codes, config=DEFAULT):
    """Merge runs shorter than a minimum into the longer neighbouring run.

    A two-frame flash of the away team inside a home possession is a tracking
    error, not a possession.  Removing it is worth far more on spellF1 than the
    few frames of macroF1 it might cost.
    """
    min_team = max(1, int(round(config.min_team_run_s * config.fps)))
    min_dead = max(1, int(round(config.min_dead_run_s * config.fps)))
    codes = codes.copy()

    for _ in range(100):
        starts, ends, values = _runs(codes)
        lengths = ends - starts + 1
        threshold = np.where(values == 2, min_dead, min_team)
        short = np.flatnonzero(lengths < threshold)
        if short.size == 0:
            return codes

        updated = codes.copy()
        n_runs = len(starts)
        for position in short:
            left = values[position - 1] if position > 0 else None
            right = values[position + 1] if position + 1 < n_runs else None
            if left is None:
                target = right
            elif right is None:
                target = left
            elif left == right:
                target = left
            else:
                target = left if lengths[position - 1] >= lengths[position + 1] else right
            if target is not None:
                updated[starts[position]:ends[position] + 1] = target
        if np.array_equal(updated, codes):
            return codes
        codes = updated
    return codes


def decode(tracking, features, dead_probability, tag_team, tag_weight, config=DEFAULT):
    """Return per-frame state codes: 0=H, 1=A, 2=D."""
    logit = features["logit"].astype(np.float64)
    if tag_team is not None:
        weight = tag_weight.astype(np.float64)
        prior = np.where(np.isfinite(tag_team), tag_team * 2.0 - 1.0, 0.0)
        logit = logit + weight * prior

    # Average a fraction of a second of evidence before deciding.  This is not
    # the old majority-vote window: it only removes sampling noise, while the
    # HMM below supplies the possession-length persistence.
    logit = rolling_mean(logit, max(1, int(round(0.12 * config.fps)))).astype(np.float64)
    logit = logit * config.emission_scale

    emission = emissions(logit, dead_probability, config)
    codes = viterbi(emission, transition_matrix(config))
    return repair_short_runs(codes, config)


def to_labels(codes, n_frames, graded_mask, config=DEFAULT):
    """Map state codes to submission letters, marking ungraded frames X."""
    letters = np.array(["H", "A", "D"], dtype="<U1")
    labels = letters[codes]
    if config.mark_ungraded_x and graded_mask is not None:
        labels = labels.copy()
        labels[~graded_mask] = "X"
    return labels
