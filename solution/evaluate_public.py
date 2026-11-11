"""Score a submission on the public five-minute ground truth.

    python -m solution.evaluate_public submissions/BAR-ATH_submission.csv

This uses the competition's own metric library.  The public window is a
correctness check, not a tuning set; see EVALUATION.md.
"""

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.path.insert(0, os.path.join(ROOT, "evaluation"))
import possession_metrics as pm  # noqa: E402

from games import GAME, GAMES  # noqa: E402

GT = os.path.join(ROOT, "evaluation", "gt", "BAR-ATH_possession_gt_public.csv")


def score(submission, gt_path=GT):
    gt_table = pm.read_label_csv(gt_path)
    sub_table = pm.read_label_csv(submission)
    reason = pm.validate_submission(sub_table, GAMES[GAME]["n_video_frames"])
    if reason:
        raise SystemExit("FAIL {}: {}".format(os.path.basename(submission), reason))
    gt_codes = pm.label_codes(gt_table)
    pred_codes = pm.label_codes(sub_table)
    return pm.evaluate(gt_codes, pred_codes)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("submission")
    parser.add_argument("--gt", default=GT)
    parser.add_argument("--bootstrap", type=int, default=0)
    args = parser.parse_args(argv)

    result = score(args.submission, args.gt)
    print("{}".format(os.path.basename(args.submission)))
    print("  macroF1          {:.4f}".format(result["macro_f1"]))
    print("  spellF1 (mean)   {:.4f}".format(result["spell_f1_mean"]))
    print("  spellF1 @0.5     {:.4f}".format(result["spell_f1_at_headline"]))
    print("  possessions      {} (truth {})".format(result["n_pred_spells"], result["n_gt_spells"]))
    print("  mean duration    {:.1f}s (truth {:.1f}s)".format(
        result["mean_spell_duration_s"], result["gt_mean_spell_duration_s"]))
    print("  alive/dead F1    {:.4f}".format(result["alive_dead_f1"]))
    print("  H/A share error  {:.4f}".format(result["share_err"]))
    print("  abstained        {} graded frames".format(result["n_abstain_on_graded"]))
    return result


if __name__ == "__main__":
    main()
