# Online Paper Studio

Public deployment: <https://research-avatar-studio.yingtaomj.workers.dev/>

This is the private, deployable entry point for the fixed Paper Studio UI. It
accepts `PROFILE.html` plus researcher-owned supporting HTML files, creates one
isolated writing workspace per browser session, and starts the existing Paper
Studio as a localhost-only worker.

For a local smoke test:

```bash
python3 -m research_avatar.online_studio --port 8876
```

Then open <http://127.0.0.1:8876>. The LLM API key entered on the setup page is
kept in server memory and in the isolated worker environment only. It is never
written to a project file, returned to the browser, placed in browser storage,
or included in an export.

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
export ONLINE_STUDIO_ACCESS_TOKEN="a-long-random-deployment-password"
export ONLINE_STUDIO_SECURE_COOKIE=1
export ONLINE_STUDIO_DATA_ROOT="/srv/online-paper-studio"
export ONLINE_STUDIO_PUBLIC_URL="https://paper-studio.example.org"
python3 -m research_avatar.online_studio --host 0.0.0.0 --port 8876
```

For public registration behind a trusted edge proxy, set
`ONLINE_STUDIO_PUBLIC_REGISTRATION=1` instead of a shared access token. Do not
expose the built-in HTTP server directly; the Cloudflare Worker deployment strips
client-supplied identity headers before adding its own D1-verified identity.

The repository also includes `wrangler.example.jsonc` and
`deploy/cloudflare/` for Cloudflare Workers + Containers. In that deployment,
email accounts, salted password digests, hashed login tokens, and auth throttling
state live in D1. The Container receives only the verified user identity and owns
the temporary Paper Studio process. Copy the example config to the ignored local
`wrangler.jsonc`, create the D1 database, apply its migrations, push the amd64
container image to Cloudflare Registry, and run `npm run deploy`.

To enable Google login on the public deployment, create a Google OAuth 2.0 Web
application with this exact authorized redirect URI:

    https://research-avatar-studio.yingtaomj.workers.dev/auth/google/callback

Then store its credentials without committing them and redeploy:

    npx wrangler secret put GOOGLE_OAUTH_CLIENT_ID
    npx wrangler secret put GOOGLE_OAUTH_CLIENT_SECRET
    npm run deploy

The Worker keeps OAuth state and nonce records in D1, exchanges the authorization
code server-side, verifies the returned Google ID token and its audience, and
requires a verified email before creating the account.

The repository includes a production-oriented container at
`deploy/online-paper-studio/Dockerfile` and an HTTPS proxy starting point at
`deploy/online-paper-studio/nginx.conf.example`. Build and run it with:

    docker build -f deploy/online-paper-studio/Dockerfile -t online-paper-studio .
    docker run --rm -p 127.0.0.1:8876:8876 \
      -e ONLINE_STUDIO_ACCESS_TOKEN="a-long-random-deployment-password" \
      -v online-paper-data:/srv/online-paper-studio \
      online-paper-studio

The container includes `latexmk`, pdfLaTeX, Poppler, and Node so accepting prose
can compile the real manuscript and refresh its PDF.

Account records and project files live in the configured data volume for the
self-hosted version. In the Cloudflare deployment, accounts persist in D1 but
Container files are ephemeral. There is intentionally no password-reset email
service yet; an administrator must remove/reset a local account directly in the
deployment database if recovery is required.

Sessions stop after four idle hours by default (`ONLINE_STUDIO_IDLE_SECONDS`).
Their project files remain under the data root, but the API key is deliberately
lost when the process stops. Download `/api/online/export` before ending a
session to retain a portable project bundle.
