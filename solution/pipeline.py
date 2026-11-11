"""End-to-end possession submission builder.

    python -m solution.pipeline
    python -m solution.pipeline --data-dir D:\\mtah2027 --out submissions/barca_ath.csv

Steps: read the tactical tracking, reconstruct the ball, score team control,
add Smart Tagging restart priors, decode a persistent H/A/D sequence, write the
199,319-row CSV, and print diagnostics that tell you whether the output looks
like football.
"""

import argparse
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from games import GAME, asset_paths, half_video_blocks, require  # noqa: E402
from solution.config import DEFAULT, Config  # noqa: E402
from solution import deadball, decoder, features as feature_mod, tagging  # noqa: E402
from solution.tracking import read_metadata, read_raw  # noqa: E402


def graded_mask(n_frames):
    """Frames that carry real ground truth: the two halves of the match."""
    mask = np.zeros(n_frames, dtype=bool)
    for _, first, last in half_video_blocks(GAME):
        mask[first:last + 1] = True
    return mask


def write_submission(path, labels):
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("frame,label\n")
        for frame, label in enumerate(labels):
            handle.write("{},{}\n".format(frame, label))
    return path


def possession_stats(labels):
    """Count same-team H/A runs, matching the scorer's spell definition."""
    codes = np.full(len(labels), -1, dtype=np.int8)
    for index, letter in enumerate("HAD"):
        codes[labels == letter] = index
    alive = np.isin(codes, (0, 1))
    # A possession is a maximal run of one team, so H->A starts two spells.
    n = 0
    for code in (0, 1):
        mask = codes == code
        n += int(np.sum(mask & ~np.r_[False, mask[:-1]]))
    alive_frames = int(alive.sum())
    return {
        "frames": int(len(labels)),
        "possessions": n,
        "mean_duration_s": round(alive_frames / 25.0 / n, 2) if n else 0.0,
        "frames_H": int(np.sum(labels == "H")),
        "frames_A": int(np.sum(labels == "A")),
        "frames_D": int(np.sum(labels == "D")),
        "frames_X": int(np.sum(labels == "X")),
    }


def run(data_dir=None, out=None, config=Config(), cache=None):
    paths = asset_paths(GAME, data_dir=data_dir)
    require(["atd_meta", "atd_raw"], GAME, data_dir)
    n_frames = 199319

    started = time.time()
    team, names = read_metadata(paths["atd_meta"])
    print("teams: H = {}, A = {}".format(names[0], names[1]))
    print("reading {} ...".format(os.path.basename(paths["atd_raw"])))
    tracking = read_raw(paths["atd_raw"], n_frames, config.pitch, team=team, config=config)
    tracking.team_names = names
    print("  ball tracked on {:.1f}% of frames".format(100.0 * tracking.ball_observed.mean()))

    if cache:
        os.makedirs(os.path.dirname(os.path.abspath(cache)), exist_ok=True)
        np.savez_compressed(
            cache,
            ball_xy=tracking.ball_xy,
            ball_observed=tracking.ball_observed,
            ball_confidence=tracking.ball_confidence,
            ball_speed=tracking.ball_speed,
            player_xy=tracking.player_xy,
            player_present=tracking.player_present,
            team=tracking.team,
        )

    print("building control features ...")
    feats = feature_mod.build(tracking, config)
    print("  median nearest-player distance: {:.2f} m".format(
        float(np.nanmedian(feats["min_distance"]))))

    tag_dead = np.full(n_frames, np.nan, dtype=np.float32)
    tag_team = np.full(n_frames, np.nan, dtype=np.float32)
    tag_weight = np.zeros(n_frames, dtype=np.float32)
    if os.path.isfile(paths.get("smart_tagging", "")):
        events = tagging.load_events(paths["smart_tagging"], config.fps)
        tag_dead, tag_team, tag_weight = tagging.build_priors(events, n_frames, config)
        print("  smart tagging: {} instances, {} with a team prior".format(
            len(events), int(np.isfinite(tag_team).sum())))
    else:
        print("  smart tagging not found; continuing on tracking only")

    print("estimating dead-ball probability ...")
    p_dead = deadball.dead_probability(tracking, feats, tag_dead, config)

    print("decoding persistent possessions ...")
    codes = decoder.decode(tracking, feats, p_dead, tag_team, tag_weight, config)
    mask = graded_mask(n_frames)
    labels = decoder.to_labels(codes, n_frames, mask, config)

    out = out or os.path.join(ROOT, "submissions", "BAR-ATH_submission.csv")
    write_submission(out, labels)
    stats = possession_stats(labels)
    stats.update({
        "frames": n_frames,
        "graded_frames": int(mask.sum()),
        "ball_observed_pct": round(100.0 * float(tracking.ball_observed.mean()), 2),
        "elapsed_s": round(time.time() - started, 1),
        "config": {
            "mean_team_spell_s": config.mean_team_spell_s,
            "mean_dead_spell_s": config.mean_dead_spell_s,
            "min_team_run_s": config.min_team_run_s,
            "min_dead_run_s": config.min_dead_run_s,
            "tagging_dead_prior": config.tagging_dead_prior,
        },
    })
    diagnostics = os.path.splitext(out)[0] + "_diagnostics.json"
    with open(diagnostics, "w", encoding="utf-8") as handle:
        json.dump(stats, handle, indent=2)
        handle.write("\n")

    print("\nwrote {}".format(out))
    print("wrote {}".format(diagnostics))
    print("  {frames} rows, {frames_H} H, {frames_A} A, {frames_D} D, {frames_X} X".format(**stats))
    print("  {possessions} possessions, mean {mean_duration_s}s".format(**stats))
    print("  elapsed {elapsed_s}s".format(**stats))
    return out, stats


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", default=None, help="override MTAH_DATA_DIR / ./data")
    parser.add_argument("--out", default=None, help="output frame,label CSV")
    parser.add_argument("--cache", default=None, help="optional .npz feature cache")
    args = parser.parse_args(argv)
    run(data_dir=args.data_dir, out=args.out, cache=args.cache)


if __name__ == "__main__":
    main()
