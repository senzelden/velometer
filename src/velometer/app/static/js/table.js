// Stacked tables: below 600 px each body row is a card whose cells print their column name from
// `data-label` (CSS `td::before`). The server writes the labels; this sets them again on tables
// the page builds or reorders itself, so a card never shows a stale or missing name.
// the sort arrow a sortable header carries is state, not part of the column's name
const words = (s) => (s ?? "").replace(/\s+/g, " ").replace(/\s*[↑↓]$/, "").trim();

// Sets data-label on every body cell (row headers included) from the header row, counting
// colspans: a cell is named by the column it starts in.
export function labelCells(table) {
  const heads = [...table.querySelectorAll("thead th")].map((h) => words(h.textContent));
  for (const row of table.querySelectorAll("tbody tr")) {
    let col = 0;
    for (const cell of row.cells) {
      cell.setAttribute("data-label", heads[col] ?? "");
      col += cell.colSpan || 1;
    }
  }
}
