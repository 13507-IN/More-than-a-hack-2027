"""Tunable constants for the possession pipeline.

The defaults are football priors, not values fitted to the public five-minute
window.  The public ground truth is for checking that the pipeline is correct
and the file is valid; EVALUATION.md explains why fitting to it picks the wrong
model.
"""

from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class Config:
    # Pitch, from games.py (measured, not the nominal 105 x 68 in the ATD XML).
    pitch: Tuple[float, float] = (105.3, 68.0)
    fps: int = 25

    # ---- ball reconstruction -------------------------------------------------
    # Linear interpolation is safe across short detection gaps.  Longer gaps get
    # a constant-velocity extrapolation for a moment and then a held position
    # whose confidence decays; the decoder is allowed to keep the previous team.
    max_interp_gap_s: float = 1.2
    max_extrapolate_s: float = 1.0
    confidence_half_life_s: float = 1.5

    # ---- team-control features ----------------------------------------------
    near_radius_m: float = 6.0
    softmin_rank: int = 2          # average this many nearest players
    distance_scale_m: float = 5.0  # metres per unit of control logit
    count_weight: float = 0.35

    # ---- dead-ball features --------------------------------------------------
    dead_prior: float = 0.075
    stationary_speed_mps: float = 0.35
    stationary_window_s: float = 1.0
    lone_ball_min_s: float = 1.0
    lone_ball_radius_m: float = 1.2
    missing_ball_dead_prior: float = 0.22
    tagging_dead_prior: float = 0.94
    goal_dead_prior: float = 0.90

    # ---- Smart Tagging priors ------------------------------------------------
    # A SET PIECES instance is a restart.  The dead ball is the moment before it
    # and the tagged team normally has the first touch.
    setpiece_dead_before_s: float = 2.5
    setpiece_dead_after_s: float = 0.4
    setpiece_team_prior_s: float = 3.5
    setpiece_team_weight: float = 1.2

    # ---- temporal decoder ----------------------------------------------------
    mean_team_spell_s: float = 14.0
    mean_dead_spell_s: float = 11.0
    emission_scale: float = 1.0

    # ---- run post-processing -------------------------------------------------
    min_team_run_s: float = 2.0
    min_dead_run_s: float = 1.0

    # ---- output --------------------------------------------------------------
    # Frames outside the two halves are never scored.  Writing X there costs
    # nothing and keeps the file honest.
    mark_ungraded_x: bool = True

    # Only used by tools that need to map a tag value to a side.
    home_names: Tuple[str, ...] = ("Barcelona", "Barca", "FC Barcelona", "Home")
    away_names: Tuple[str, ...] = ("Atletic Club", "Athletic Club", "Athletic", "Away")


DEFAULT = Config()
