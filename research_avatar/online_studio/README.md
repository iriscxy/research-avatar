# Online Paper Studio

Public deployment: <https://research-avatar-studio.yingtaomj.workers.dev/>

This is the deployable login, onboarding, and session gateway for the fixed Paper
Studio UI. There is no deployment access-code field. A researcher signs in with
an email/password account or optional Google OAuth, then uses one public setup
form. The form requires exactly four material groups: one Google Scholar profile
HTML, one complete project overview, one or more experiment-result files, and one
complete structural reference paper. Project materials accept DOC, DOCX, TXT,
PDF, Markdown, JSON, or HTML as appropriate.

The server acquires 3--4 author-owned papers strictly from the uploaded Scholar
list, reads their public full text, and summarizes only observed writing
characteristics into the standard `PROFILE.html` writing-style section. The
separately uploaded reference paper is structural authority for the target section
and paragraph architecture; it is never silently treated as evidence for project
claims or inserted into the citation bank. Result JSON drives one deterministic
editable table and one Python-rendered data figure. A model-improvement project
also receives a labeled model/mechanism figure placeholder. If required materials
or readable style evidence are missing, onboarding fails explicitly instead of
inventing them.

The backend retains the validated project-package importer for internal migration
and compatibility testing, but it is not a second public onboarding entry.

## Product modes

- **Paper writing inside Research Studio (`http://127.0.0.1:8780`)** is the only
  local user-facing entry and has the complete feature set: prose, editable
  tables, Python data figures, GPT Image mechanism figures, and editable native
  PPTX/PDF reconstruction. The underlying writer process is an implementation
  detail, not a separate product page.
- **Online Paper Studio** intentionally exposes only prose/title writing,
  deterministic editable tables, and deterministic Python-rendered data figures.
  Mechanism/model/conceptual and every other non-data figure remains in the paper
  plan as a compact placeholder with its real Caption and label. Export the project
  from inside Paper Studio to finish those figures locally.
- **Online citations** use a bounded, project-verified BibTeX bank. Introduction,
  Related Work, and paragraphs that name an external dataset, benchmark, or
  baseline receive an additional citation audit. Verified keys are preserved;
  unknown keys and unresolved `\\cite{}` placeholders are rejected at Accept.
- **Demo** is read-only but shows the completed local/full-capability project,
  including real figures rather than online placeholders. Its inputs cannot be
  edited and it never redirects into a real writing session.

Build the evidence ZIP from the original Research Avatar project root:

```bash
python3 -m research_avatar.online_studio.package
```

The package command includes `PROFILE.html`, `publications.json`, reports `01`–`05`,
`results/`, and only the one author-owned logic-reference text selected by approved
`03`. It deliberately excludes the rest of `researcher-profile/fulltext/`; those
unused papers would increase upload size without contributing to the approved target
architecture. When present it also includes `figures/` and
`code/RESULTS_LEDGER.csv`. The server rejects path traversal, symlinks, unknown
paths, more than 2,000 files, more than 32 MB compressed, or more than 128 MB
expanded. Before creating Paper Studio data it runs the repository's expplan,
report-structure, and result-conformance validators and requires every 03 result
target to be present in 05. Missing result rows are rejected instead of replaced
with placeholders.

For the standard local online-debug pass used before a Cloudflare deployment:

```bash
python3 -m research_avatar.online_studio --host 127.0.0.1 --port 8899
```

Then open <http://127.0.0.1:8899>. Use this gateway for browser-visible or headless
regression testing of login, Demo/免费纯文字 PaperWrite 版 navigation, upload, online-only controls,
project export, and unauthenticated `/studio` redirects. Debug here first; deploy
only after the whole browser path passes.

Online sessions use one server-held DeepSeek key and currently default to
`deepseek-v4-flash`. The browser has no provider/key form. The key is read only
from `DEEPSEEK_API_KEY`, stays in the gateway and child-process environment, and
is never written to project files, returned to the browser, placed in browser
storage, or included in an export. A cumulative per-user shared-key cap defaults
to RMB 200 (`ONLINE_STUDIO_SPEND_CAP_RMB`).

The first screen supports local email/password registration and login. Passwords
are stored as salted PBKDF2-HMAC-SHA256 digests; opaque login tokens are stored
only as hashes in `auth.sqlite3`. Projects and live Paper Studio sessions are
owned by the authenticated user, so a session cookie from another account is
rejected.

Google login is optional. Create a Google OAuth 2.0 **Web application**, register
the exact callback `https://your-host/auth/google/callback`, and configure:

```bash
export ONLINE_STUDIO_PUBLIC_URL="https://paper-studio.example.org"
export GOOGLE_OAUTH_CLIENT_ID="...apps.googleusercontent.com"
export GOOGLE_OAUTH_CLIENT_SECRET="..."
```

The backend uses the Authorization Code flow, checks browser-bound `state`,
checks the ID-token `nonce`, verifies the token with Google's official Python
library, and requires a verified email. Local and Google identities with the
same displayed email remain separate accounts; there is no implicit linking.

For a private internet-facing deployment, terminate TLS in a reverse proxy and set:

```bash
export ONLINE_STUDIO_SECURE_COOKIE=1
export ONLINE_STUDIO_DATA_ROOT="/srv/online-paper-studio"
export ONLINE_STUDIO_PUBLIC_URL="https://paper-studio.example.org"
python3 -m research_avatar.online_studio --host 0.0.0.0 --port 8876
```

For public registration behind a trusted edge proxy, set
`ONLINE_STUDIO_PUBLIC_REGISTRATION=1`. Do not
expose the built-in HTTP server directly; the Cloudflare Worker deployment strips
client-supplied identity headers before adding its own D1-verified identity.

The repository also includes `deploy/cloudflare/` (Worker source, package.json,
wrangler config, D1 migrations) for Cloudflare Workers + Containers. In that
deployment, email accounts, salted password digests, hashed login tokens, and
auth throttling state live in D1. The Container receives only the verified
user identity and owns the temporary Paper Studio process. Copy
`deploy/cloudflare/wrangler.example.jsonc` to the ignored local
`deploy/cloudflare/wrangler.jsonc`, create the D1 database, apply its
migrations, push the amd64 container image to Cloudflare Registry, and run
`make deploy` (or `npm run deploy` from inside `deploy/cloudflare/`).

The container config pins `constraints.regions` to `WNAM`/`ENAM`/`WEUR`. Every
OpenAI (and DeepSeek) call is made from inside the Container's own network
egress, not the researcher's browser, so Cloudflare's default nearest-to-requester
placement can schedule the Container in a region whose egress IP OpenAI
classifies as an unsupported country/region/territory (HTTP 403,
`unsupported_country_region_territory`) — every request then fails immediately,
independent of the researcher's own account or location, and retrying or
resuming the batch job cannot help until placement changes. Keep the regions
list restricted to geographies OpenAI reliably serves; do not add `APAC` or `ME`
without confirming the actual Cloudflare Container point of presence in that
constraint is not itself in an embargoed/unsupported territory.

`instance_type` is pinned to `standard-1` (1/2 vCPU, 4 GiB memory). The
Container runs this gateway process, the spawned per-session
`research_avatar.paper_studio.server` writer subprocess, `latexmk`/`pdflatex`,
Poppler, and the bundled Codex CLI all inside the same instance; a live
end-to-end "直接生成全文初稿" batch run against `basic` (1 GiB) killed the
writer subprocess mid-job (the gateway stayed up and reported "会话不存在或已
过期"), losing the researcher's in-progress session even though completed
paragraphs were already saved to disk under the now-unreachable session root.
Do not downgrade the tier without re-running a full real batch-writing job
against it first.

To enable Google login on the public deployment, create a Google OAuth 2.0 Web
application with this exact authorized redirect URI:

    https://research-avatar-studio.yingtaomj.workers.dev/auth/google/callback

Then store its credentials without committing them and redeploy (run from
`deploy/cloudflare/`):

    npx wrangler secret put GOOGLE_OAUTH_CLIENT_ID
    npx wrangler secret put GOOGLE_OAUTH_CLIENT_SECRET
    npm run deploy

The hosted writing flow uses one encrypted DeepSeek secret for both PDF text
ordering and drafting. Store it through Wrangler; do not place its value in
`wrangler.jsonc` or a tracked environment file:

    npx wrangler secret put DEEPSEEK_API_KEY

The Worker keeps OAuth state and nonce records in D1, exchanges the authorization
code server-side, verifies the returned Google ID token and its audience, and
requires a verified email before creating the account.

The repository includes a production-oriented container at
`deploy/online-paper-studio/Dockerfile` and an HTTPS proxy starting point at
`deploy/online-paper-studio/nginx.conf.example`. Build and run it with:

    docker build -f deploy/online-paper-studio/Dockerfile -t online-paper-studio .
    docker run --rm -p 127.0.0.1:8876:8876 \
      -v online-paper-data:/srv/online-paper-studio \
      online-paper-studio

The container includes `latexmk`, pdfLaTeX, Poppler, and Node so accepting prose
can compile the real manuscript and refresh its PDF.

Account records and project files live in the configured data volume for the
self-hosted version. In the Cloudflare deployment, accounts persist in D1 but
Container files are ephemeral. There is intentionally no password-reset email
service yet; an administrator must remove/reset a local account directly in the
deployment database if recovery is required.

The Python service defaults to 16 active writing sessions and four idle hours.
The Cloudflare container overrides these values to 10 active writing sessions and
90 idle minutes (`ONLINE_STUDIO_MAX_SESSIONS=10`,
`ONLINE_STUDIO_IDLE_SECONDS=14400`). The current Worker routes one immutable
version-scoped public container name, so `max_instances: 6` is a platform ceiling,
not `6 × 10` user capacity. Login records persist in D1, but Container writing
workspaces are ephemeral. Download the project ZIP from inside an active Paper
Studio session before it expires; the outer 免费纯文字 PaperWrite 版 page intentionally has no
export control.
