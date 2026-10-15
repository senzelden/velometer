// The repository root, found from a test file by walking up to the directory that holds
// pyproject.toml, so a node test reads the shared tests/*.json however deep the static tree sits
// (a fixed run of `../` breaks when the tree moves).
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/** The nearest directory at or above `from` (a path) that holds pyproject.toml; throws without one. */
export function repoRoot(from = fileURLToPath(import.meta.url)) {
  for (let dir = from; ; dir = dirname(dir)) {
    if (existsSync(join(dir, "pyproject.toml"))) return dir;
    if (dirname(dir) === dir) throw new Error(`no pyproject.toml at or above ${from}`);
  }
}

/** A file of the repository by its path from the root (`tests/url_cases.json`). */
export const repoFile = (rel) => join(repoRoot(), rel);
