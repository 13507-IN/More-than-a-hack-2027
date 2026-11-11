"""Unit tests that run without the licensed match bundle."""

import os
import sys
import tempfile
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "evaluation"))

from solution.config import Config  # noqa: E402
from solution.tracking import (  # noqa: E402
    read_metadata, read_raw, reconstruct_ball, control_features,
)
from solution.decoder import decode, repair_short_runs, viterbi, transition_matrix  # noqa: E402
from solution.deadball import dead_probability  # noqa: E402
from solution.pipeline import graded_mask, possession_stats, write_submission  # noqa: E402
from solution.tagging import load_events, build_priors  # noqa: E402
import possession_metrics as pm  # noqa: E402


META = """<?xml version="1.0" encoding="utf-8"?>
<root>
  <Team id="1"><Name>Barcelona</Name></Team>
  <Team id="2"><Name>Atletic Club</Name></Team>
  <Player teamId="1"/><Player teamId="1"/>
  <Player teamId="2"/><Player teamId="2"/>
</root>
"""


def make_frames(n, config):
    """A synthetic 40-second sequence: home has the ball, then away."""
    rows = []
    for frame in range(n):
        ball_x, ball_y = (0.50, 0.50) if frame < n // 2 else (0.10, 0.10)
        if frame > 20 and frame % 7 == 0:
            ball = "NaN,NaN,NaN"      # regular detection gaps
        else:
            ball = "{:.4f},{:.4f},0.5".format(ball_x, ball_y)
        home = "0.5000,0.5000,1.0;0.5200,0.5100,1.0"
        away = "0.1000,0.1000,1.0;0.1200,0.1100,1.0"
        rows.append("{}:{};{}:{}".format(frame + 1, home, away, ball))
    return "\n".join(rows) + "\n"


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.meta_path = os.path.join(self.temp.name, "atd.xml")
        self.raw_path = os.path.join(self.temp.name, "atd.txt")
        with open(self.meta_path, "w", encoding="utf-8") as handle:
            handle.write(META)
        self.config = Config()
        self.n = 1000
        with open(self.raw_path, "w", encoding="utf-8") as handle:
            handle.write(make_frames(self.n, self.config))

    def tearDown(self):
        self.temp.cleanup()

    def test_metadata_and_raw_alignment(self):
        team, names = read_metadata(self.meta_path)
        self.assertEqual(names, ("Barcelona", "Atletic Club"))
        self.assertEqual(team.tolist(), [0, 0, 1, 1])
        tracking = read_raw(self.raw_path, self.n, self.config.pitch, team=team)
        self.assertEqual(tracking.player_xy.shape, (self.n, 4, 2))
        self.assertGreater(tracking.ball_observed.mean(), 0.7)
        self.assertFalse(np.isnan(tracking.ball_xy).any())

    def test_ball_reconstruction_interpolates_short_gaps(self):
        ball = np.array([[0.0, 0.0], [np.nan, np.nan], [np.nan, np.nan], [30.0, 0.0]])
        observed = np.array([True, False, False, True])
        xy, confidence = reconstruct_ball(ball, observed, self.config)
        self.assertAlmostEqual(xy[1, 0], 10.0)
        self.assertAlmostEqual(xy[2, 0], 20.0)
        self.assertTrue((confidence[:2] > 0.9).all())

    def test_control_prefers_the_team_around_the_ball(self):
        team, _ = read_metadata(self.meta_path)
        tracking = read_raw(self.raw_path, self.n, self.config.pitch, team=team)
        feats = control_features(tracking, self.config)
        self.assertGreater(float(np.mean(feats["logit"][:self.n // 2])), 0.0)
        self.assertLess(float(np.mean(feats["logit"][self.n // 2 + 50:])), 0.0)

    def test_dead_ball_evidence_and_decode(self):
        team, _ = read_metadata(self.meta_path)
        tracking = read_raw(self.raw_path, self.n, self.config.pitch, team=team)
        feats = control_features(tracking, self.config)
        tag_dead = np.full(self.n, np.nan, dtype=np.float32)
        tag_team = np.full(self.n, np.nan, dtype=np.float32)
        tag_weight = np.zeros(self.n, dtype=np.float32)
        p_dead = dead_probability(tracking, feats, tag_dead, self.config)
        codes = decode(tracking, feats, p_dead, tag_team, tag_weight, self.config)
        self.assertEqual(len(codes), self.n)
        self.assertIn(int(codes[100]), (0, 2))
        self.assertIn(int(codes[-100]), (1, 2))
        self.assertLessEqual(len(np.flatnonzero(codes[1:] != codes[:-1])), 6)

    def test_run_repair_removes_flicker(self):
        codes = np.array([0] * 100 + [1] * 5 + [0] * 100, dtype=np.int8)
        repaired = repair_short_runs(codes, Config())
        self.assertTrue(np.all(repaired == 0))

    def test_viterbi_is_sticky(self):
        transitions = transition_matrix(Config())
        emission = np.zeros((50, 3))
        emission[:, 0] = np.log(0.34)
        emission[:, 1] = np.log(0.33)
        emission[:, 2] = np.log(0.33)
        emission[25, 1] = np.log(0.99)
        states = viterbi(emission, transitions)
        self.assertEqual(int(states[0]), int(states[-1]))
        self.assertEqual(int(states[0]), int(states[24]))

    def test_tagging_priors(self):
        xml = """<?xml version="1.0"?><root><ALL_INSTANCES>
        <instance><ID>1</ID><start>10.0</start><end>12.0</end><code>SET PIECES</code>
        <label><group>Team</group><text>Barcelona</text></label>
        <label><group>Type</group><text>Throw-in</text></label></instance>
        </ALL_INSTANCES></root>"""
        path = os.path.join(self.temp.name, "tags.xml")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(xml)
        events = load_events(path, 25)
        dead, team_prior, weight = build_priors(events, 1000, self.config)
        self.assertGreater(float(np.nanmax(dead)), 0.9)
        self.assertEqual(float(team_prior[300]), 1.0)
        self.assertGreater(float(weight[300]), 0.0)

    def test_submission_is_valid_and_stats_exist(self):
        n = 199319
        labels = np.full(n, "X", dtype="<U1")
        mask = graded_mask(n)
        labels[mask] = "H"
        labels[n // 2:n // 2 + 400] = "D"
        path = os.path.join(self.temp.name, "submission.csv")
        write_submission(path, labels)
        table = pm.read_label_csv(path)
        self.assertIsNone(pm.validate_submission(table, n))
        stats = possession_stats(labels)
        self.assertGreaterEqual(stats["possessions"], 1)
        self.assertEqual(stats["frames"], n)


if __name__ == "__main__":
    unittest.main()
