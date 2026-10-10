import { test } from "node:test";
import assert from "node:assert/strict";
import { labelCells } from "../table.js";

// the smallest DOM that labelCells touches: a table with header texts and body rows of cells
const cell = (text, colSpan = 1) => ({ textContent: text, colSpan, label: undefined, setAttribute(k, v) { if (k === "data-label") this.label = v; } });
const table = (heads, rows) => ({
  querySelectorAll: (sel) => (sel === "thead th" ? heads : sel === "tbody tr" ? rows : []),
});
const labels = (rows) => rows.map((r) => r.cells.map((c) => c.label));

test("every body cell is labelled with its column's header text", () => {
  const heads = [cell("City"), cell("  2019 \n"), cell("2024")];
  const rows = [{ cells: [cell("Berlin"), cell("1"), cell("2")] }, { cells: [cell("Paris"), cell("3"), cell("4")] }];
  labelCells(table(heads, rows));
  assert.deepEqual(labels(rows), [["City", "2019", "2024"], ["City", "2019", "2024"]]);
});

test("labels follow a re-sort: rows moved or replaced are relabelled from the header", () => {
  const heads = [cell("City"), cell("Value")];
  const a = { cells: [cell("A"), cell("1")] };
  const b = { cells: [cell("B"), cell("2")] };
  const rows = [a, b];
  labelCells(table(heads, rows));
  rows.reverse();
  rows.push({ cells: [cell("C"), cell("3")] }); // a row built after the first pass
  heads[1] = cell("Value ↓"); // sorting appends an arrow to the header
  labelCells(table(heads, rows));
  assert.deepEqual(labels(rows), [["City", "Value"], ["City", "Value"], ["City", "Value"]]);
});

test("a colspan cell is named by the column it starts in, and the next cell skips the span", () => {
  const heads = [cell("A"), cell("B"), cell("C")];
  const rows = [{ cells: [cell("x"), cell("n/a", 2)] }, { cells: [cell("y", 2), cell("z")] }];
  labelCells(table(heads, rows));
  assert.deepEqual(labels(rows), [["A", "B"], ["A", "C"]]);
});
