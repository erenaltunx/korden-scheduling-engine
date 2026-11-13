# OPTERA security policy

OPTERA is an educational optimization engine, not a hardened multi-user factory management system.

- Never commit `.env`, credentials, tokens, real customer data, private production files or SQLite databases.
- Do not upload proprietary plant data to public demos. The public demo does not persist scenarios, but HTTP hosting is still outside your private environment.
- Run the private history-enabled version on `127.0.0.1`, in Codespaces with private ports, or within a trusted network.
- `OPTERA_PUBLIC_DEMO=1` disables history, rejects expensive scenarios, caps solver concurrency, and limits request size. These are safeguards, **not** full authentication, DDoS prevention or isolation of untrusted workloads.
- Deploy behind an HTTPS ingress with its own request limits, rate limiting and resource limits. No authentication is implemented; keep it a public demonstration, never a real company system.
- Run dependency/security checks on updates. Never auto-merge dependency upgrade PRs without testing.
- If a token ever leaks, revoke and rotate it immediately; removing a file from the latest commit does not erase Git history.
- Report vulnerabilities privately to the repository owner rather than posting secrets or exploits in issues.
