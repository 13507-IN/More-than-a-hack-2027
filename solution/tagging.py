"""Turn Smart Tagging phases into soft priors for dead ball and team ownership.

The XML is on the tactical video clock: ``video_frame = round(seconds * 25)``.
It is automatic annotation, not ground truth, so everything here is a prior with
a weight, never a label copied across an interval.
"""

import xml.etree.ElementTree as ET

import numpy as np

from .config import Config, DEFAULT


def _side_from_name(value, config):
    if value is None:
        return None
    text = value.strip().lower()
    if not text or text in ("n/a", "na", "none"):
        return None
    for name in config.home_names:
        if name.lower() in text:
            return 1
    for name in config.away_names:
        if name.lower() in text:
            return 0
    return None


def load_events(path, fps):
    """Smart Tagging instances as dicts with frame intervals and tag values."""
    out = []
    for instance in ET.parse(path).iter("instance"):
        try:
            start_s = float(instance.findtext("start"))
            end_s = float(instance.findtext("end"))
        except (TypeError, ValueError):
            continue
        tags = {}
        for label in instance.findall("label"):
            group = label.findtext("group")
            if group:
                tags[group.strip()] = (label.findtext("text") or "").strip()
        out.append({
            "code": (instance.findtext("code") or "").strip(),
            "start_frame": int(round(start_s * fps)),
            "end_frame": int(round(end_s * fps)),
            "start_s": start_s,
            "end_s": end_s,
            "tags": tags,
        })
    return out


def build_priors(events, n_frames, config=DEFAULT):
    """(dead_prior, team_prior, team_weight) arrays for the whole video.

    ``dead_prior`` is a probability in [0, 1], ``team_prior`` is P(home) where a
    restart tells us who takes it, and ``team_weight`` says how much that prior
    should move the team logit.
    """
    dead = np.zeros(n_frames, dtype=np.float32)
    team_prior = np.full(n_frames, np.nan, dtype=np.float32)
    team_weight = np.zeros(n_frames, dtype=np.float32)
    fps = config.fps

    def paint(array, first, last, value):
        first = max(0, int(first))
        last = min(n_frames - 1, int(last))
        if last >= first:
            array[first:last + 1] = np.maximum(array[first:last + 1], value)

    for event in events:
        code = event["code"].upper()
        start, end = event["start_frame"], event["end_frame"]
        if "SET PIECES" in code:
            before = int(round(config.setpiece_dead_before_s * fps))
            after = int(round(config.setpiece_dead_after_s * fps))
            paint(dead, start - before, start + after, config.tagging_dead_prior)
            side = _side_from_name(event["tags"].get("Team"), config)
            if side is not None:
                length = int(round(config.setpiece_team_prior_s * fps))
                first, last = max(0, start), min(n_frames - 1, start + length)
                if last >= first:
                    # The restart team prior is evidence, not certainty.
                    team_prior[first:last + 1] = side
                    team_weight[first:last + 1] = config.setpiece_team_weight
        elif "GOAL" in code and "OWN" not in code:
            paint(dead, end - int(0.5 * fps), end + int(3.0 * fps), config.goal_dead_prior)

    return dead, team_prior, team_weight
