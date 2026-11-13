# GitHub, Codespaces & Web Demo

KORDEN separates **source hosting** (GitHub), **cloud development** (GitHub Codespaces)
and **web deployment** (Render). GitHub Pages alone cannot execute this Python/SciPy
optimization backend.

## Publish source to its own repository

Recommended project repository: `erenaltunx/korden-scheduling-engine`. Avoid
placing this code in NORTHSTAR or the older supply-chain-agent repository.

1. Create a **public** repository named `korden-scheduling-engine` in GitHub.
2. Do **not** add a template `.gitignore`, license, or README (they are here already).
3. If publishing via your own terminal, in the directory containing `README.md`:
   ```bash
   git add .
   git commit -m "Initialize KORDEN production optimization and safety baseline"
   git branch -M main
   git remote add origin https://github.com/erenaltunx/korden-scheduling-engine.git
   git push -u origin main
   ```
   GitHub authentication/authorization is needed for the push. Alternatively, a
   connected GitHub integration may upload the text files into a repo that already exists.

## Run without downloading anything: GitHub Codespaces

After publication, use the repository **Code → Codespaces → Create codespace on main**.
The `.devcontainer` configuration installs the Python dependencies and starts
KORDEN. Open the forwarded port **8000** to use the full web interface. Codespaces
availability and usage limits depend on the account.

## Host a shareable web app with Render

1. In Render, create a web service from this GitHub repository or deploy the
   provided `render.yaml` blueprint.
2. Select the Free plan for an experimental demo when available.
3. Build: `pip install -r requirements.txt`
4. Start: `uvicorn korden.api:app --host 0.0.0.0 --port $PORT --workers 1`
5. Health check: `/api/health`.
6. Set environment variable `KORDEN_PUBLIC_DEMO=1` to bound demo request size,
   maximum production order count and optimization time.

Render free web services may sleep during inactivity; they are not suitable for
production SLAs. This public demo does not require API keys or persistent storage. Local mode uses a separate SQLite archive.
Do not expose confidential company data to a public demo.

## Verify a deployment

- `/api/health` returns `{"status":"ok", ...}`.
- Home page loads and lists both synthetic example factories.
- The Assembly Cell experiment returns EDD weighted tardiness **39** and MILP **15**.
- GitHub Actions has green unit/API tests and a benchmark artifact.

## Security limitations

The demo is public and carries out CPU-intensive mathematical optimization.
`KORDEN_PUBLIC_DEMO=1` reduces but does not eliminate denial-of-service risk. Configure rate limiting, network controls, CPU and memory quotas at the hosting layer.
No authentication, multi-tenancy, persistent database, or upload privacy is
provided. Do not market this research demo as a production SaaS.

## Protect the repository before larger changes

- In Settings → Branches / Rulesets, protect `main`, require passing KORDEN Quality Gate, disallow force pushes and avoid unreviewed direct edits.
- Keep `KORDEN_PUBLIC_DEMO=1` on public hosts. No user accounts, access controls, or persistent experiments are available there.
- Set backup strategy for local/Codespaces SQLite experiments separately. **GitHub is not a database backup.**
- Tag a working release only after tests and live smoke checks. See `docs/RECOVERY.md`.
