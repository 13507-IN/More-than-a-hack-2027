"""Stream the FIFA/EPTS tracking export into arrays and build control features.

The raw ATD is one line per video frame::

    <frame_id>:<player>;<player>;...:<ball>

where every group is ``x,y,speed`` or ``NaN,NaN,NaN``.  Coordinates are
normalised to 0-1, frame ids count from 1, and a submission row is frame_id - 1.
"""

from dataclasses import dataclass
import os
import xml.etree.ElementTree as ET

import numpy as np

from .config import Config, DEFAULT


HOME, AWAY = 0, 1


@dataclass
class Tracking:
    ball_xy: np.ndarray        # (n, 2) reconstructed, metres
    ball_observed: np.ndarray  # (n,) bool
    ball_confidence: np.ndarray  # (n,) 0..1
    ball_speed: np.ndarray     # (n,) m/s, reconstructed
    player_xy: np.ndarray      # (n, slots, 2) metres, NaN where missing
    player_present: np.ndarray  # (n, slots) bool
    player_speed: np.ndarray   # (n, slots) m/s, NaN where missing
    team: np.ndarray           # (slots,) HOME/AWAY
    team_names: tuple


def read_metadata(meta_path):
    """(team_of_slot, (home_name, away_name)) from the EPTS XML."""
    root = ET.parse(meta_path).getroot()
    teams = list(root.iter("Team"))
    if len(teams) != 2:
        raise ValueError("{}: expected 2 teams, found {}".format(meta_path, len(teams)))
    home_id = teams[0].get("id")
    names = tuple(team.findtext("Name") for team in teams)
    team = np.array(
        [HOME if player.get("teamId") == home_id else AWAY for player in root.iter("Player")],
        dtype=np.int8,
    )
    if team.size == 0:
        raise ValueError("{}: no Player entries".format(meta_path))
    return team, names


def read_raw(raw_path, n_frames, pitch, team=None, config=DEFAULT):
    """Read the raw ATD once.

    Returns a :class:`Tracking` with positions in metres and a reconstructed
    ball track.  Player x/y stay NaN where the tracker had no observation; the
    team vector is supplied by :func:`read_metadata`.
    """
    n_slots = int(team.size) if team is not None else 0
    raw_x = np.full((n_frames, n_slots), np.nan, dtype=np.float32)
    raw_y = np.full((n_frames, n_slots), np.nan, dtype=np.float32)
    raw_s = np.full((n_frames, n_slots), np.nan, dtype=np.float32)
    ball_x = np.full(n_frames, np.nan, dtype=np.float32)
    ball_y = np.full(n_frames, np.nan, dtype=np.float32)
    ball_s = np.full(n_frames, np.nan, dtype=np.float32)

    with open(raw_path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.rstrip("\r\n")
            if not line:
                continue
            parts = line.split(":")
            if len(parts) != 3:
                continue
            try:
                frame = int(parts[0]) - 1
            except ValueError:
                continue
            if frame < 0 or frame >= n_frames:
                continue

            groups = parts[1].split(";")
            for slot, group in enumerate(groups[:n_slots]):
                if not group or group[0] == "N" or group[0] == "n":
                    continue
                comma = group.find(",")
                if comma < 0:
                    continue
                second = group.find(",", comma + 1)
                try:
                    raw_x[frame, slot] = float(group[:comma])
                    raw_y[frame, slot] = float(group[comma + 1:second if second >= 0 else None])
                    if second >= 0:
                        raw_s[frame, slot] = float(group[second + 1:])
                except ValueError:
                    continue

            ball = parts[2]
            if not ball or ball[0] == "N" or ball[0] == "n":
                continue
            comma = ball.find(",")
            if comma < 0:
                continue
            second = ball.find(",", comma + 1)
            try:
                ball_x[frame] = float(ball[:comma])
                ball_y[frame] = float(ball[comma + 1:second if second >= 0 else None])
                if second >= 0:
                    ball_s[frame] = float(ball[second + 1:])
            except ValueError:
                continue

    length, width = pitch
    player_xy = np.stack((raw_x * length, raw_y * width), axis=-1).astype(np.float32)
    present = np.isfinite(raw_x) & np.isfinite(raw_y)
    team = team if team is not None else np.zeros(n_slots, dtype=np.int8)

    observed = np.isfinite(ball_x) & np.isfinite(ball_y)
    ball = np.stack((ball_x * length, ball_y * width), axis=-1).astype(np.float32)
    ball_xy, confidence = reconstruct_ball(ball, observed, config)
    ball_speed = _speed_from_positions(ball_xy, config.fps)

    return Tracking(
        ball_xy=ball_xy,
        ball_observed=observed,
        ball_confidence=confidence,
        ball_speed=ball_speed,
        player_xy=player_xy,
        player_present=present,
        player_speed=raw_s,
        team=team,
        team_names=(),
    )


def _speed_from_positions(xy, fps):
    """Centred finite-difference speed, tolerant of a masked/reconstructed track."""
    out = np.zeros(len(xy), dtype=np.float32)
    if len(xy) < 2:
        return out
    delta = np.diff(xy, axis=0) * fps
    speed = np.sqrt(np.sum(delta * delta, axis=1))
    out[1:] = speed
    out[0] = speed[0]
    return np.clip(out, 0.0, 45.0)


def reconstruct_ball(ball_xy, observed, config=DEFAULT):
    """Fill missing ball frames and return (positions, confidence).

    Short gaps are interpolated.  Long gaps use the last observed velocity for
    up to ``max_extrapolate_s`` and then hold the last position while confidence
    decays.  A held position is better than NaN because relative distances to
    players still say which team is around the ball; the confidence tells the
    decoder how much to trust it.
    """
    n = len(ball_xy)
    xy = np.array(ball_xy, dtype=np.float64, copy=True)
    confidence = np.zeros(n, dtype=np.float32)
    known = np.flatnonzero(observed & np.isfinite(ball_xy).all(axis=1))
    if known.size == 0:
        xy[:] = np.nan
        return xy.astype(np.float32), confidence

    confidence[known] = 1.0
    interp_frames = int(round(config.max_interp_gap_s * config.fps))
    extrap_frames = int(round(config.max_extrapolate_s * config.fps))

    if known.size > 1:
        for left, right in zip(known[:-1], known[1:]):
            gap = right - left - 1
            if gap <= 0:
                continue
            if gap <= interp_frames:
                t = (np.arange(left + 1, right) - left) / float(right - left)
                xy[left + 1:right] = (
                    (1.0 - t)[:, None] * xy[left] + t[:, None] * xy[right]
                )
                confidence[left + 1:right] = 1.0

    # Frames before the first observation: hold the first point, no confidence.
    xy[:known[0]] = xy[known[0]]
    confidence[:known[0]] = 0.0

    # Long internal gaps and frames after the last observation: constant
    # velocity from the previous span, then hold while confidence decays.
    interp_mask = np.zeros(n, dtype=bool)
    interp_mask[known] = True
    if known.size > 1:
        for left, right in zip(known[:-1], known[1:]):
            if right - left - 1 <= interp_frames:
                interp_mask[left + 1:right] = True

    frames = np.arange(n)
    slot = np.searchsorted(known, frames, side="left") - 1
    for index in frames[known[0]:]:
        if interp_mask[index]:
            continue
        position = slot[index]
        b = known[position]
        age = index - b
        xy[index] = xy[b]
        if position >= 1 and age <= extrap_frames:
            a = known[position - 1]
            span = b - a
            if span > 0 and span <= interp_frames + extrap_frames:
                velocity = (xy[b] - xy[a]) / float(span)
                speed = float(np.hypot(*velocity))
                if speed > 12.0:  # ~43 km/h, a plausible upper bound for a rolling ball
                    velocity *= 12.0 / speed
                xy[index] = xy[b] + velocity * age
        confidence[index] = float(np.exp(-age / (config.confidence_half_life_s * config.fps)))
        if age <= 1:
            confidence[index] = 1.0

    return xy.astype(np.float32), np.clip(confidence, 0.0, 1.0)


def rolling_mean(values, window):
    """Centred moving average that keeps the input length."""
    window = max(1, int(window))
    if window == 1:
        return values.astype(np.float32)
    kernel = np.ones(window, dtype=np.float64) / window
    padded = np.pad(values.astype(np.float64), (window // 2, window - 1 - window // 2), mode="edge")
    return np.convolve(padded, kernel, mode="valid").astype(np.float32)


def control_features(tracking, config=DEFAULT):
    """Per-frame team logit and distance summaries.

    The score compares each team's nearest few players to the reconstructed
    ball.  Averaging the two or three nearest players rather than taking the
    single nearest is deliberate: one bad track slot should not decide a frame.
    """
    xy = tracking.ball_xy.astype(np.float64)
    players = tracking.player_xy.astype(np.float64)
    present = tracking.player_present
    team = tracking.team
    length, width = config.pitch

    dx = players[..., 0] - xy[:, None, 0]
    dy = players[..., 1] - xy[:, None, 1]
    distance = np.sqrt(dx * dx + dy * dy)
    distance[~present] = np.inf

    home = distance[:, team == HOME]
    away = distance[:, team == AWAY]
    rank = max(1, int(config.softmin_rank))

    def nearest_mean(block):
        if block.shape[1] == 0:
            return np.full(len(block), np.inf, dtype=np.float64)
        k = min(rank, block.shape[1])
        part = np.partition(block, k - 1, axis=1)[:, :k]
        finite = np.isfinite(part)
        total = np.where(finite, part, 0.0).sum(axis=1)
        count = finite.sum(axis=1)
        out = np.full(len(block), np.inf, dtype=np.float64)
        np.divide(total, count, out=out, where=count > 0)
        return out

    s_home = nearest_mean(home)
    s_away = nearest_mean(away)
    near_home = np.sum(home < config.near_radius_m, axis=1)
    near_away = np.sum(away < config.near_radius_m, axis=1)

    # A large gap in softmin distance is real evidence; the count term rewards
    # a team that surrounds the ball over one lonely defender.
    with np.errstate(invalid="ignore", divide="ignore"):
        logit = (s_away - s_home) / config.distance_scale_m
    logit = np.nan_to_num(logit, nan=0.0, posinf=0.0, neginf=0.0)
    logit += config.count_weight * np.tanh((near_home - near_away) / 2.0)
    # A missing ball leaves the positions stale; shrink the evidence.
    logit *= 0.35 + 0.65 * tracking.ball_confidence

    return {
        "logit": logit.astype(np.float32),
        "min_distance": np.minimum(s_home, s_away).astype(np.float32),
        "s_home": s_home.astype(np.float32),
        "s_away": s_away.astype(np.float32),
        "near_home": near_home.astype(np.int16),
        "near_away": near_away.astype(np.int16),
        "player_distance": distance.astype(np.float32),
    }


def sigmoid(value):
    value = np.clip(value, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-value))
