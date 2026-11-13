# Data protection & disaster recovery

KORDEN has **two different things to protect**: (A) source code and (B) experiment history. GitHub protects only (A). You must separately back up (B).

## Source code

1. Keep a separate repository: `erenaltunx/korden-scheduling-engine`.
2. Push reviewed branches to GitHub; tag known-good releases: `git tag v0.3.0 && git push origin v0.3.0`.
3. Enable branch protection: require CI, pull request review and forbid force-push on `main`. Prefer commits from PR branches over editing `main` directly.
4. Optional offline code backup after each release: `git bundle create KORDEN-offline-backup.bundle --all`. Keep the bundle outside the project on another drive.
5. Recover source: `git clone https://github.com/erenaltunx/korden-scheduling-engine.git` (or `git clone KORDEN-offline-backup.bundle korden-recovered`).

## Local experiment database

- Default directory: `~/.korden/experiments.sqlite3`. Change with `KORDEN_DATA_DIR`.
- Docker Compose stores it in a **named volume** called `korden-data`. Never run `docker compose down -v` unless you explicitly want to erase that volume.
- The public demo does not save experiments. Export its results as JSON.

**Create a consistent online backup** (safe even while the application is active):

```bash
python backup.py --out ~/korden-backups/experiments-2026-11-13.sqlite3
```

Use a *new filename each time*: an existing backup is never overwritten. Put a copy in a second location (encrypted cloud drive or external drive); keeping the backup beside the original disk is not enough.

**Restore after data loss**:

1. Stop KORDEN before restoring (`Ctrl+C` or `docker compose stop`).
2. Preserve any surviving original DB and WAL files in a separate folder first; never blindly overwrite them.
3. Copy the verified `.sqlite3` backup to the configured data directory as `experiments.sqlite3`.
4. Run `python -c "from korden.storage import connect; c=connect(); print(c.execute('PRAGMA integrity_check').fetchone()[0]); c.close()"` — must print `ok`.
5. Start KORDEN and verify `/api/history`, then open an old experiment to verify the saved result.

**Do not** rely solely on GitHub, Codespaces, Render's ephemeral disk, or the existence of a Docker volume as a disaster recovery plan. Test a restore periodically.

## Releases and compatibility

Keep old `samples/` plus experiment snapshots. An incompatible DB schema must fail safely instead of modifying unknown tables. Every DB migration must come with migration+restore regression tests.
