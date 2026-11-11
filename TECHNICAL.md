# Technical report: tracking-only ball possession

## Approach

The submission is a deterministic state estimator, not a trained classifier. It
reads the tactical ATD stream, reconstructs a usable ball track, estimates which
team is controlling the ball, estimates whether the ball is dead, and decodes a
persistent `H` / `A` / `D` sequence with a sticky Viterbi decoder. Frames outside
the two playing halves are written as `X` because they are ungraded.

The design target is the `spellF1` metric: whole possessions must be aligned in
time, not just per-frame labels. That pushes the model toward long, stable
states and away from frame-by-frame flickering.

### 1. ATD ingestion

`solution/tracking.py` streams the raw ATD text and keeps the ball, all player
track slots, and the team assigned to each slot. The metadata XML supplies the
team names and slot-to-team mapping. The parser is row-oriented and does not
load the whole file as a table, so the 186 MB tactical export is processed in
about half a minute.

The ball is detected on roughly 57% of frames in this match. Missing frames are
not treated as automatically dead: the ball is interpolated across short gaps,
then extrapolated with a capped constant velocity, then held with a decaying
confidence. The decoder receives that confidence so a long invisible stretch is
weak evidence rather than certain evidence.

### 2. Team-control features

For each frame the ball position is compared with the nearest players in metres.
The main score is the distance from the ball to the second-nearest player of
each team, which is less sensitive to a single bad track slot than the nearest
player alone. Counts of players within a radius, and the relative distance
advantage, are added as secondary evidence. The result is a smooth per-frame
home/away control score rather than a hard nearest-player label.

### 3. Dead-ball evidence

`solution/deadball.py` combines:

- a ball that is stationary while no player is close to it,
- a long invisible ball far from the nearest players,
- Smart Tagging `SET PIECES` and `GOALS` windows when that XML is available.

A restart's `Team` tag is used only as a short soft prior after the restart. It
is never copied directly into the output, and the pipeline still requires the
tracking evidence to support it.

### 4. Sequence decoding

`solution/decoder.py` runs a three-state Viterbi decoder with transition
probabilities expressed as football durations: a mean possession of about 18
seconds and a mean dead-ball spell of about 11 seconds. After decoding, runs
shorter than the configured minimum are merged into their longer neighbour.
This removes camera-cut and tracking-noise flickers, which are the main cause of
over-segmentation.

The decoded output is validated with the official validator and written as
`frame,label` for all 199,319 frames.

## Assets used and dropped

| asset | use |
|---|---|
| `BAR-ATH_tactical_atd.txt` | Primary input: ball and player positions. |
| `BAR-ATH_tactical_atd.xml` | Team names and slot-to-team metadata. |
| `BAR-ATH_tactical_homography.csv` | Inspected; not needed by the current pipeline because the tactical ATD coordinates are already in the pitch frame used by the features. |
| `BAR-ATH_tactical_smart_tagging.xml` | Supported by `tagging.py`, but not present in the local data bundle used for the current generated file. The pipeline prints a message and continues tracking-only. |
| `BAR-ATH_tactical.mp4` | Dropped. The ATD and frame count already define the timeline; the 4.86 GB video adds no information needed by this pipeline. |
| broadcast homography | Dropped. The broadcast camera is not used. |

## Training data

None. No labelled dataset was used to fit, train, or calibrate the model. The
transition durations and feature weights are hand-set football priors, not
values selected by searching the public five-minute window. The public ground
truth was used only to confirm that the generated file is valid and that the
pipeline behaves sensibly on real tracking data; it was not used as a training
signal.

## Possession rules implemented

- **Controlled ball**: the team whose players are closest to the reconstructed
  ball, with the second-nearest player reducing the effect of one bad track.
- **Loose ball / challenge**: no immediate team switch just because the nearest
  player changes. The Viterbi persistence prior keeps the current team until the
  evidence is strong enough to switch, which approximates "the ball is still
  being contested".
- **Dead ball**: stationary ball with no nearby player, long invisible ball away
  from play, or a tagged set piece / goal. Dead-ball runs separate possessions.
- **Restarts**: the tagged team gets a short soft prior after the restart, but
  only while the tracking evidence remains consistent with that team.
- **Halftime and edges**: frames outside the two playing halves are `X`.

## Current check on the public window

The generated file `submissions/BAR-ATH_submission.csv` passes the official
validator (199,319 ordered rows, labels `H/A/D/X`). On the public five-minute
window it scores:

```
macroF1          0.6233
spellF1 (mean)   0.3667
possessions      19 (truth 17)
mean duration    14.6s (truth 14.2s)
alive/dead F1    0.8981
H/A share error  0.0551
```

This is a sanity check, not a tuning target. The published full-match baseline
floor is `spellF1` 0.2433; the public-window numbers are not directly comparable
to full-match numbers because the window is short and unrepresentative.

## Limitations

- Tracking-only dead-ball detection is weaker at restarts and stoppages than a
  complete Smart Tagging pass. Adding the 255 KB Smart Tagging XML is the first
  improvement to try.
- The pipeline does not identify individual players, so a quick one-touch
  exchange between teammates can look like a possession change if the ball
  track jumps.
- Camera cuts and long occlusions can still create short false dead-ball runs.
  The run-repair step removes most, not all, of them.
- The public window is five minutes. It cannot validate full-match behavior such
  as halftime handling, second-half tracking quality, or substitutions.
- Goalkeeper distribution and aerial duels are handled only through the generic
  nearest-player features.

## Reproduction

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Put the licensed tactical files under data/tactical/ (see data/README.md).
python -m solution.pipeline

python evaluation/validate_submission.py submissions/BAR-ATH_submission.csv
python -m solution.evaluate_public submissions/BAR-ATH_submission.csv
```

The pipeline is deterministic: the same ATD and metadata produce the same CSV.
