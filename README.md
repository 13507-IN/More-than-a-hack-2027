# Possession Lab — More than a Hack 2027, Phase 1

A complete workspace for the Metrica Sports / FC Barcelona ball-possession
challenge: the official scorer and starter tooling, a possession pipeline that
writes the 199,319-row submission, and a browser-only review screen for checking
a candidate CSV.

The task is one label per tactical-video frame: `H` (home in possession), `A`
(away), `D` (dead ball), or `X` (no answer). The board is ranked on **spellF1**,
which matches whole possessions by temporal IoU. See
[CHALLENGE.md](CHALLENGE.md), [DATA.md](DATA.md) and
[EVALUATION.md](EVALUATION.md) for the official rules.

## Quickstart

```powershell
# 1. Environment (Python 3.9+)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Rebuild the published baselines and score them (no match data needed)
python starter/baseline.py
python evaluation/run_evaluation.py

# 3. Unpack the licensed bundle into .\data (see data/README.md), then:
python -m solution.pipeline

# 4. Validate and score the exact file before submitting
python evaluation/validate_submission.py submissions/BAR-ATH_submission.csv
python -m solution.evaluate_public submissions/BAR-ATH_submission.csv
```

`MTAH_DATA_DIR` overrides the default `data/` location. The scorer itself reads
only CSVs, so it runs on a fresh clone before any match data exists.

## What the pipeline does

`solution/` is a deterministic, numpy-only possession estimator:

1. **Read the tactical ATD** and keep the ball, all 46 track slots and their
   team membership. Ball present on ~57% of all frames is the normal case.
2. **Reconstruct the ball track.** Short detection gaps are interpolated; longer
   gaps use a capped constant-velocity extrapolation and then a held position
   whose confidence decays. The decoder is told how much to trust the position
   instead of treating every invisible ball as dead.
3. **Score team control** from the two or three nearest players to the
   reconstructed ball, in metres, plus how many players each team has around it.
   Averaging several players makes one bad track slot much less dangerous.
4. **Estimate dead-ball probability** from a stationary ball with nobody near
   it, long invisible stretches far from play, and Smart Tagging `SET PIECES`
   and `GOALS` windows. A restart's `Team` tag is used as a soft prior for the
   first seconds after it, never copied across as a label.
5. **Decode a persistent state sequence** with a sticky three-state Viterbi
   (H/A/D). The transition prior is expressed as football durations: a mean
   possession of ~14 s and a mean dead-ball spell of ~11 s. Short flickers are
   merged into their longer neighbour afterwards.
6. **Write and check** `frame,label` for every frame. Frames outside the two
   halves are `X`, which is ungraded and therefore free.

The compiled defaults are football priors, not values fitted to the public
five-minute ground truth. EVALUATION.md explains why tuning against those 17
possessions selects the wrong model.

## Repository layout

```
games.py                      per-match constants, paths and frame alignment
CHALLENGE.md DATA.md ...      official challenge documentation
evaluation/                   official scorer, validator, metrics, public GT, baselines
starter/                      official baseline and loaders
solution/                     this project's submission pipeline
  config.py                   tunable priors
  tracking.py                 ATD reader, ball reconstruction, control features
  tagging.py                  Smart Tagging to dead-ball/team priors
  deadball.py                 dead-ball evidence
  decoder.py                  sticky Viterbi + run repair
  pipeline.py                 end-to-end CSV builder
  evaluate_public.py          score a submission on the public window
tests/                        data-free unit tests
tools/                        data helper scripts
data/                         licensed bundle goes here; gitignored
submissions/                  generated CSVs; gitignored
index.html app.js styles.css  browser-only candidate CSV reviewer
parser.test.cjs               node test for the browser parser
```

## Browser review screen

Open `index.html` in a modern browser and choose a candidate CSV. The file is
read locally and never uploaded. The page checks the local contract (header,
199,319 ordered frames, one of `H/A/D/X` per row), then shows label counts and a
full-match timeline. Select anywhere on the strip, type a frame number, or walk
the nearby runs. This is an inspection aid only: it does not calculate macroF1
or spellF1 and does not replace the official validator.

Run its parser tests with:

```powershell
node parser.test.cjs
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node parser.test.cjs
```

The Python suite builds a synthetic FIFA/EPTS export in a temporary directory,
so it runs without the licensed data.

## Data and licence

The code and documentation are MIT-licensed (see [LICENSE](LICENSE)). The match
data is **not** covered by that licence: it is separately licensed for this
competition only, under the terms accepted at enrolment. Do not commit or
redistribute anything under `data/`.
