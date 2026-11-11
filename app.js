"use strict";

const EXPECTED_FRAME_COUNT = 199319;
const EXPECTED_LAST_FRAME = EXPECTED_FRAME_COUNT - 1;
const LABELS = {
  H: { name: "Home possession", css: "home", color: "#1b6c80" },
  A: { name: "Away possession", css: "away", color: "#2f70bb" },
  D: { name: "Dead ball", css: "dead", color: "#a86f0c" },
  X: { name: "Uncertain / abstain", css: "uncertain", color: "#a9b2ad" }
};
const LABEL_TO_CODE = { H: 0, A: 1, D: 2, X: 3 };
const CODE_TO_LABEL = ["H", "A", "D", "X"];
const COUNT_FORMAT = new Intl.NumberFormat("en-US");

function parseCandidateCsv(csvText) {
  const source = String(csvText).replace(/^\uFEFF/, "");
  const lines = source.split(/\r\n|\n|\r/);
  while (lines.length > 0 && lines[lines.length - 1].trim() === "") {
    lines.pop();
  }

  const issues = [];
  let issueCount = 0;
  const addIssue = (message) => {
    issueCount += 1;
    if (issues.length < 8) issues.push(message);
  };

  if (lines.length === 0 || lines[0].trim() === "") {
    addIssue("The CSV is empty; the first row must be frame,label.");
    return { valid: false, issues, issueCount, dataRows: 0 };
  }

  const header = lines[0].split(",").map((value) => value.trim());
  if (header.length !== 2 || header[0] !== "frame" || header[1] !== "label") {
    addIssue("The first row must contain exactly these columns: frame,label.");
    return { valid: false, issues, issueCount, dataRows: Math.max(0, lines.length - 1) };
  }

  const labels = new Uint8Array(EXPECTED_FRAME_COUNT);
  const labelCounts = [0, 0, 0, 0];
  const dataRows = lines.length - 1;

  for (let rowIndex = 0; rowIndex < dataRows; rowIndex += 1) {
    const lineNumber = rowIndex + 2;
    const line = lines[rowIndex + 1];
    if (line.trim() === "") {
      addIssue(`Line ${COUNT_FORMAT.format(lineNumber)} is blank; each frame needs a row.`);
      continue;
    }

    const fields = line.split(",");
    if (fields.length !== 2) {
      addIssue(`Line ${COUNT_FORMAT.format(lineNumber)} must have exactly two columns.`);
      continue;
    }

    const frameText = fields[0].trim();
    const label = fields[1].trim();
    if (!/^\d+$/.test(frameText)) {
      addIssue(`Line ${COUNT_FORMAT.format(lineNumber)} has a non-integer frame value.`);
      continue;
    }

    const frame = Number(frameText);
    if (!Number.isSafeInteger(frame) || frame < 0 || frame > EXPECTED_LAST_FRAME) {
      addIssue(`Line ${COUNT_FORMAT.format(lineNumber)} has a frame outside 0–${COUNT_FORMAT.format(EXPECTED_LAST_FRAME)}.`);
      continue;
    }
    if (frame !== rowIndex) {
      addIssue(`Line ${COUNT_FORMAT.format(lineNumber)} should be frame ${COUNT_FORMAT.format(rowIndex)}, not ${COUNT_FORMAT.format(frame)}.`);
      continue;
    }

    if (!Object.hasOwn(LABEL_TO_CODE, label)) {
      addIssue(`Line ${COUNT_FORMAT.format(lineNumber)} has an unsupported label; use H, A, D, or X.`);
      continue;
    }

    const code = LABEL_TO_CODE[label];
    labels[frame] = code;
    labelCounts[code] += 1;
  }

  if (dataRows !== EXPECTED_FRAME_COUNT) {
    addIssue(`Expected ${COUNT_FORMAT.format(EXPECTED_FRAME_COUNT)} frame rows; found ${COUNT_FORMAT.format(dataRows)}.`);
  }

  if (issueCount > 0) {
    return { valid: false, issues, issueCount, dataRows };
  }

  const runs = [];
  let start = 0;
  for (let frame = 1; frame <= EXPECTED_FRAME_COUNT; frame += 1) {
    if (frame === EXPECTED_FRAME_COUNT || labels[frame] !== labels[start]) {
      runs.push({ code: labels[start], start, end: frame - 1 });
      start = frame;
    }
  }

  return { valid: true, labels, labelCounts, runs, dataRows, issues, issueCount };
}

function formatCount(value) {
  return COUNT_FORMAT.format(value);
}

function runIndexAtFrame(runs, frame) {
  let low = 0;
  let high = runs.length - 1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    const run = runs[middle];
    if (frame < run.start) high = middle - 1;
    else if (frame > run.end) low = middle + 1;
    else return middle;
  }
  return -1;
}

function initializePossessionLab() {
  const byId = (id) => document.getElementById(id);
  const ui = {
    fileInput: byId("file-input"),
    chooseFile: byId("choose-file"),
    browseFile: byId("browse-file"),
    dropZone: byId("drop-zone"),
    fileStatus: byId("file-status"),
    validationPanel: byId("validation-panel"),
    validationTitle: byId("validation-title"),
    validationSummary: byId("validation-summary"),
    validationState: byId("validation-state"),
    validationIssues: byId("validation-issues"),
    statFrames: byId("stat-frames"),
    statRuns: byId("stat-runs"),
    statFile: byId("stat-file"),
    canvas: byId("timeline-canvas"),
    timelineEmpty: byId("timeline-empty"),
    timelineCaption: byId("timeline-caption"),
    frameInput: byId("frame-input"),
    previousFrame: byId("previous-frame"),
    nextFrame: byId("next-frame"),
    selectedCode: byId("selected-code"),
    selectedName: byId("selected-name"),
    selectedRange: byId("selected-range"),
    nearbyCount: byId("nearby-count"),
    runList: byId("run-list"),
    countHome: byId("count-home"),
    countAway: byId("count-away"),
    countDead: byId("count-dead"),
    countUncertain: byId("count-uncertain")
  };

  const state = { result: null, fileName: "", frame: 0 };
  const canvasContext = ui.canvas.getContext("2d");

  function resetStatistics() {
    ui.statFrames.textContent = "-";
    ui.statRuns.textContent = "-";
    ui.countHome.textContent = "-";
    ui.countAway.textContent = "-";
    ui.countDead.textContent = "-";
    ui.countUncertain.textContent = "-";
  }

  function setValidation(result) {
    ui.validationPanel.hidden = false;
    ui.validationIssues.replaceChildren();
    ui.validationPanel.dataset.state = result.valid ? "pass" : "error";
    ui.validationTitle.textContent = result.valid ? "CSV shape checks" : "CSV needs attention";
    ui.validationState.textContent = result.valid ? "Checks passed" : "Needs attention";
    ui.validationSummary.textContent = result.valid
      ? "The header, frame sequence, row count, and labels match the local file contract."
      : `${formatCount(result.issueCount)} issue${result.issueCount === 1 ? "" : "s"} found. The first ${formatCount(result.issues.length)} are listed below.`;

    for (const issue of result.issues) {
      const item = document.createElement("li");
      item.textContent = issue;
      ui.validationIssues.append(item);
    }
  }

  function updateControls() {
    const hasResult = Boolean(state.result?.valid);
    ui.frameInput.disabled = !hasResult;
    ui.previousFrame.disabled = !hasResult || state.frame === 0;
    ui.nextFrame.disabled = !hasResult || state.frame === EXPECTED_LAST_FRAME;
    ui.frameInput.value = String(state.frame);
  }

  function drawTimeline() {
    const bounds = ui.canvas.getBoundingClientRect();
    const width = Math.max(1, Math.floor(bounds.width));
    const height = Math.max(1, Math.floor(bounds.height));
    const pixelRatio = Math.max(1, window.devicePixelRatio || 1);
    ui.canvas.width = Math.floor(width * pixelRatio);
    ui.canvas.height = Math.floor(height * pixelRatio);
    canvasContext.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    canvasContext.clearRect(0, 0, width, height);
    canvasContext.fillStyle = "#f0f3f1";
    canvasContext.fillRect(0, 0, width, height);

    if (!state.result?.valid) return;

    const labels = state.result.labels;
    const palette = ["#1b6c80", "#2f70bb", "#a86f0c", "#a9b2ad"];
    for (let x = 0; x < width; x += 1) {
      const from = Math.floor((x / width) * EXPECTED_FRAME_COUNT);
      const to = Math.max(from + 1, Math.floor(((x + 1) / width) * EXPECTED_FRAME_COUNT));
      const bucketCounts = [0, 0, 0, 0];
      for (let frame = from; frame < Math.min(to, EXPECTED_FRAME_COUNT); frame += 1) {
        bucketCounts[labels[frame]] += 1;
      }
      let dominantCode = 0;
      for (let code = 1; code < bucketCounts.length; code += 1) {
        if (bucketCounts[code] > bucketCounts[dominantCode]) dominantCode = code;
      }
      canvasContext.fillStyle = palette[dominantCode];
      canvasContext.fillRect(x, 0, 1.2, height);
    }

    const markerX = (state.frame / EXPECTED_LAST_FRAME) * width;
    canvasContext.fillStyle = "#ffffff";
    canvasContext.fillRect(markerX - 2, 0, 5, height);
    canvasContext.fillStyle = "#17211c";
    canvasContext.fillRect(markerX - 1, 0, 2, height);
    ui.canvas.setAttribute("aria-disabled", "false");
    ui.canvas.setAttribute("aria-valuenow", String(state.frame));
    ui.canvas.setAttribute(
      "aria-valuetext",
      `Frame ${formatCount(state.frame)}: ${LABELS[CODE_TO_LABEL[labels[state.frame]]].name}`
    );
  }

  function renderNearbyRuns() {
    const result = state.result;
    const selectedIndex = runIndexAtFrame(result.runs, state.frame);
    const first = Math.max(0, selectedIndex - 2);
    const last = Math.min(result.runs.length, first + 5);
    const adjustedFirst = Math.max(0, last - 5);
    ui.runList.replaceChildren();
    ui.nearbyCount.textContent = `${formatCount(adjustedFirst + 1)}–${formatCount(last)} of ${formatCount(result.runs.length)}`;

    for (let index = adjustedFirst; index < last; index += 1) {
      const run = result.runs[index];
      const label = CODE_TO_LABEL[run.code];
      const meta = LABELS[label];
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.className = "run-button";
      button.type = "button";
      button.setAttribute("aria-current", index === selectedIndex ? "true" : "false");
      button.setAttribute("aria-label", `${meta.name}, frames ${formatCount(run.start)} to ${formatCount(run.end)}, ${formatCount(run.end - run.start + 1)} frames`);

      const mark = document.createElement("span");
      mark.className = `key-mark key-${meta.css}`;
      mark.textContent = label;
      const range = document.createElement("span");
      range.className = "run-range";
      range.textContent = `${formatCount(run.start)}–${formatCount(run.end)}`;
      const length = document.createElement("span");
      length.className = "run-length";
      length.textContent = `${formatCount(run.end - run.start + 1)} frames`;
      button.append(mark, range, length);
      button.addEventListener("click", () => selectFrame(run.start));
      item.append(button);
      ui.runList.append(item);
    }
  }

  function renderSelection() {
    const runIndex = runIndexAtFrame(state.result.runs, state.frame);
    const run = state.result.runs[runIndex];
    const label = CODE_TO_LABEL[run.code];
    const meta = LABELS[label];
    ui.selectedCode.className = `key-mark key-${meta.css}`;
    ui.selectedCode.textContent = label;
    ui.selectedName.textContent = meta.name;
    ui.selectedRange.textContent = `Frames ${formatCount(run.start)}–${formatCount(run.end)} · ${formatCount(run.end - run.start + 1)} frames in this run.`;
    ui.timelineCaption.textContent = `${formatCount(state.result.runs.length)} consecutive label runs across ${formatCount(EXPECTED_FRAME_COUNT)} frames.`;
    ui.timelineEmpty.hidden = true;
    renderNearbyRuns();
    updateControls();
    drawTimeline();
  }

  function selectFrame(frame) {
    if (!state.result?.valid) return;
    state.frame = Math.max(0, Math.min(EXPECTED_LAST_FRAME, Math.trunc(frame)));
    renderSelection();
  }

  function clearCurrentResult() {
    state.result = null;
    state.frame = 0;
    resetStatistics();
    updateControls();
    ui.timelineCaption.textContent = "Load a valid CSV to see how labels run across the match.";
    ui.timelineEmpty.hidden = false;
    ui.canvas.setAttribute("aria-disabled", "true");
    ui.canvas.setAttribute("aria-valuenow", "0");
    ui.canvas.setAttribute("aria-valuetext", "No candidate CSV loaded");
    ui.selectedCode.className = "key-mark key-uncertain";
    ui.selectedCode.textContent = "-";
    ui.selectedName.textContent = "Load a valid file";
    ui.selectedRange.textContent = "A frame and its run details will appear here.";
    ui.nearbyCount.textContent = "-";
    ui.runList.replaceChildren();
    const empty = document.createElement("li");
    empty.className = "empty-run";
    empty.textContent = "A valid file is needed to list label runs.";
    ui.runList.append(empty);
    drawTimeline();
  }

  function renderLoadedResult(result, fileName) {
    if (!result.valid) {
      clearCurrentResult();
      setValidation(result);
      state.fileName = fileName;
      ui.statFile.textContent = fileName;
      ui.statFrames.textContent = formatCount(result.dataRows);
      ui.fileStatus.textContent = `${fileName} · checks failed`;
      return;
    }

    state.fileName = fileName;
    state.result = result;
    state.frame = 0;
    setValidation(result);
    ui.statFile.textContent = fileName;
    ui.fileStatus.textContent = fileName;
    ui.statFrames.textContent = formatCount(result.dataRows);
    ui.statRuns.textContent = formatCount(result.runs.length);
    ui.countHome.textContent = formatCount(result.labelCounts[0]);
    ui.countAway.textContent = formatCount(result.labelCounts[1]);
    ui.countDead.textContent = formatCount(result.labelCounts[2]);
    ui.countUncertain.textContent = formatCount(result.labelCounts[3]);
    ui.fileStatus.textContent = `${fileName} · local checks passed`;
    renderSelection();
  }

  async function loadFile(file) {
    if (!file) return;
    clearCurrentResult();
    ui.validationPanel.hidden = true;
    ui.statFile.textContent = file.name;
    ui.fileStatus.textContent = `Reading ${file.name}…`;

    try {
      const text = await file.text();
      const result = parseCandidateCsv(text);
      renderLoadedResult(result, file.name);
    } catch (error) {
      clearCurrentResult();
      const result = {
        valid: false,
        dataRows: 0,
        issues: ["The selected file could not be read as text."],
        issueCount: 1
      };
      setValidation(result);
      ui.statFile.textContent = file.name;
      ui.fileStatus.textContent = `${file.name} · could not be read`;
      if (error instanceof Error) console.error("Could not read selected CSV:", error.message);
    }
  }

  function openFilePicker() {
    ui.fileInput.click();
  }

  ui.chooseFile.addEventListener("click", openFilePicker);
  ui.browseFile.addEventListener("click", openFilePicker);
  ui.fileInput.addEventListener("change", () => {
    const [file] = ui.fileInput.files || [];
    if (file) loadFile(file);
    ui.fileInput.value = "";
  });

  ui.dropZone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openFilePicker();
    }
  });
  ui.dropZone.addEventListener("dragover", (event) => {
    event.preventDefault();
    ui.dropZone.classList.add("is-dragging");
  });
  ui.dropZone.addEventListener("dragleave", (event) => {
    if (!ui.dropZone.contains(event.relatedTarget)) ui.dropZone.classList.remove("is-dragging");
  });
  ui.dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    ui.dropZone.classList.remove("is-dragging");
    const [file] = event.dataTransfer?.files || [];
    if (file) loadFile(file);
  });

  ui.canvas.addEventListener("click", (event) => {
    if (!state.result?.valid) return;
    const bounds = ui.canvas.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    selectFrame(Math.floor(ratio * EXPECTED_FRAME_COUNT));
  });
  ui.canvas.addEventListener("keydown", (event) => {
    if (!state.result?.valid) return;
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      selectFrame(state.frame - 1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      selectFrame(state.frame + 1);
    } else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
      event.preventDefault();
      const runIndex = runIndexAtFrame(state.result.runs, state.frame);
      const nextIndex = Math.max(0, Math.min(state.result.runs.length - 1, runIndex + (event.key === "ArrowUp" ? -1 : 1)));
      selectFrame(state.result.runs[nextIndex].start);
    } else if (event.key === "Home") {
      event.preventDefault();
      selectFrame(0);
    } else if (event.key === "End") {
      event.preventDefault();
      selectFrame(EXPECTED_LAST_FRAME);
    }
  });
  ui.frameInput.addEventListener("change", () => {
    const value = Number(ui.frameInput.value);
    if (Number.isInteger(value) && value >= 0 && value <= EXPECTED_LAST_FRAME) {
      selectFrame(value);
    } else {
      ui.frameInput.value = String(state.frame);
    }
  });
  ui.previousFrame.addEventListener("click", () => selectFrame(state.frame - 1));
  ui.nextFrame.addEventListener("click", () => selectFrame(state.frame + 1));

  if ("ResizeObserver" in window) {
    new ResizeObserver(drawTimeline).observe(ui.canvas);
  } else {
    window.addEventListener("resize", drawTimeline);
  }

  resetStatistics();
  updateControls();
  drawTimeline();
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    EXPECTED_FRAME_COUNT,
    EXPECTED_LAST_FRAME,
    parseCandidateCsv,
    runIndexAtFrame
  };
}

if (typeof document !== "undefined") {
  initializePossessionLab();
}
