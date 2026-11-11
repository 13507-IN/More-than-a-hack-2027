"use strict";

const assert = require("node:assert/strict");
const {
  EXPECTED_FRAME_COUNT,
  EXPECTED_LAST_FRAME,
  parseCandidateCsv,
  runIndexAtFrame
} = require("./app.js");

const rows = ["frame,label"];
for (let frame = 0; frame < EXPECTED_FRAME_COUNT; frame += 1) {
  const label = frame < 4 ? "H" : frame < 7 ? "D" : "A";
  rows.push(`${frame},${label}`);
}

const valid = parseCandidateCsv(`\uFEFF${rows.join("\r\n")}\r\n`);
assert.equal(valid.valid, true);
assert.equal(valid.dataRows, EXPECTED_FRAME_COUNT);
assert.deepEqual(valid.labelCounts, [4, EXPECTED_FRAME_COUNT - 7, 3, 0]);
assert.deepEqual(
  valid.runs.map(({ code, start, end }) => ({ code, start, end })),
  [
    { code: 0, start: 0, end: 3 },
    { code: 2, start: 4, end: 6 },
    { code: 1, start: 7, end: EXPECTED_LAST_FRAME }
  ]
);
assert.equal(runIndexAtFrame(valid.runs, 0), 0);
assert.equal(runIndexAtFrame(valid.runs, 5), 1);
assert.equal(runIndexAtFrame(valid.runs, EXPECTED_LAST_FRAME), 2);

const wrongHeader = parseCandidateCsv("index,team\n0,H\n");
assert.equal(wrongHeader.valid, false);
assert.match(wrongHeader.issues[0], /frame,label/);

const wrongOrder = parseCandidateCsv("frame,label\n1,H\n");
assert.equal(wrongOrder.valid, false);
assert.ok(wrongOrder.issues.some((issue) => /should be frame 0/.test(issue)));

const invalidLabel = parseCandidateCsv("frame,label\n0,Z\n");
assert.equal(invalidLabel.valid, false);
assert.ok(invalidLabel.issues.some((issue) => /unsupported label/.test(issue)));

const extraColumn = parseCandidateCsv("frame,label\n0,H,extra\n");
assert.equal(extraColumn.valid, false);
assert.ok(extraColumn.issues.some((issue) => /exactly two columns/.test(issue)));

console.log("CSV parser tests passed.");
