// Copy the browser-facing static files into public/ so the Worker can serve
// them at the edge. Without this every page load waits for the container to
// cold-start before the HTML, CSS, and JS can be returned.
import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "../../..");
const out = resolve(here, "../public");
const skipped = (path) => /(__pycache__|\.py$|\.pyc$|_routes\.json$|\.DS_Store$)/.test(path);

rmSync(out, { recursive: true, force: true });
mkdirSync(join(out, "online-assets"), { recursive: true });

const online = join(repo, "research_avatar/online_studio/static");
cpSync(join(online, "index.html"), join(out, "index.html"));
cpSync(join(online, "app.js"), join(out, "online-assets/app.js"));
cpSync(join(online, "style.css"), join(out, "online-assets/style.css"));

const demo = join(repo, "research_avatar/web/demo");
if (!existsSync(demo)) throw new Error("demo directory not found: " + demo);
cpSync(demo, join(out, "demo"), { recursive: true, filter: (src) => !skipped(src) });
console.log("static assets synced to", out);
