# Project plan — More than a Hack 2027: Phase 1

## Objective

Build a reproducible, fully algorithmic pipeline that assigns `H`, `A`, `D`, or `X` to all
199,319 tactical-video frames. Optimize for **spellF1** (whole possessions), while tracking
macroF1 as a secondary metric. The submission must be regenerable from code and the licensed
local data bundle.

## Guardrails

- Keep the provided match data and anything that could reconstruct it out of the public repo.
- Do not hand-label or hand-correct this match, and do not use private ground truth or other
  human-produced labels about this match.
- The public five-minute ground truth is for pipeline/file correctness only. Do not train on it,
  tune thresholds against it, or choose a model because it scores better on it.
- Record all external labelled datasets/models and explain their use in the technical document.
- Make the tactical feed the frame-index reference. Treat broadcast as optional because its
  timeline is not synchronised to tactical.

## Work plan

### 1. Establish a reproducible starting point

- Create an isolated Python environment and install the repository's evaluation requirements.
- Run the official scorer and reproduce the four supplied baselines; save the output as the
  reference result.
- Read the challenge, data, metric, rules, and submission contracts before changing the baseline.
- Confirm the data bundle is available locally through `MTAH_DATA_DIR` or the default `data/`
  location, without copying it into version control.

**Checkpoint:** the repository's scorer and baseline generation run from documented commands.

### 2. Audit inputs and frame alignment

- Load the tactical tracking, Smart Tagging, and homography with the starter utilities.
- Check frame counts, timestamps/index conversion, team mapping, missing values, track gaps,
  identity switches, and ball visibility.
- Plot a few automatically selected intervals to understand failure modes; use viewing only for
  debugging and feature design, never to create labels or frame-specific corrections.
- Keep a data-quality report with counts and examples of algorithmically detected issues.

**Checkpoint:** each input can be joined to the tactical frame index without off-by-one errors.

### 3. Build a stronger possession estimator

Start with the tactical tracking and add signals beyond “nearest player wins”:

- Ball-to-player distance in pitch coordinates, relative motion, and track confidence/availability.
- Per-team proximity and movement summaries, using multiple nearby players to reduce the effect of
  one bad track or identity switch.
- Temporal evidence for control: retain the current team through brief loose-ball periods; switch
  only when opposing-team control is sustained.
- Dead-ball evidence from the supplied tagging/tracking, separated from live-play team ownership.
- A sequence decoder/state machine with transition persistence and duration-aware smoothing, so
  isolated noisy frames do not create extra possessions.

Use `X` only where abstention is genuinely appropriate; remember it is forward-filled for spellF1,
so it does not protect a possession boundary from carrying the previous team label.

**Checkpoint:** a baseline-plus-temporal model generates a complete valid CSV and has explainable
state transitions.

### 4. Evaluate responsibly and iterate

- Use the public evaluation to verify frame alignment, label semantics, and file validity—not to
  fit thresholds or rank competing model variants.
- If learning is useful, prefer unsupervised/self-supervised signals from this match or labelled
  possession data from other matches that can be disclosed and inspected.
- Compare ablations using the permitted independent validation source, if available. Prioritize
  possession-boundary quality and spellF1; inspect macroF1 and predicted possession counts/durations
  as diagnostics rather than optimizing frame accuracy alone.
- Keep a small experiment log: code/config version, signals enabled, validation source, metrics,
  known failure cases, and the reason for accepting/rejecting a change.

**Checkpoint:** improvements have evidence that does not rely on tuning against the public or
private labels for this match.

### 5. Harden, document, and submit

- Run the official validator on the exact final CSV; check 199,319 rows, ordered frames
  `0..199318`, valid labels, and no blank cells.
- Test that a clean environment can reproduce the exact same output.
- Pin dependencies, document the run command, preserve the final config, and keep data ignored.
- Write the required short technical document: approach, assets used/dropped, training data,
  possession rules for loose balls/restarts, limitations, and reproduction steps.
- Freeze and validate the exact team-named CSV and documentation before upload.

**Checkpoint:** code, technical document, and possession CSV agree and are reproducible.

## Suggested schedule

The repository lists **17 November 2026** as the submission deadline. Starting 31 October, use a
short sprint:

| Dates | Focus |
|---|---|
| 31 Oct–1 Nov | Environment, scorer, baseline, rules and data-path check |
| 2–5 Nov | Input/frame audit and visual diagnostics |
| 6–10 Nov | Possession features, temporal model, controlled experiments |
| 11–13 Nov | Robustness, full-file generation, validator and reproducibility |
| 14–16 Nov | Technical document, final freeze, validate exact submission |
| 17 Nov | Submit |

## Initial success criteria

1. Reproduce the supplied baseline locally.
2. Produce a valid, deterministic 199,319-row file from the available data.
3. Improve possession-level behavior over the baseline using a compliant validation strategy.
4. Deliver the public code and technical document without including licensed match data.
