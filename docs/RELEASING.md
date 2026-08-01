# Releasing BixDot

> Version: 0.6.3 · Last updated: 2026-08-02

This document is the authority on how BixDot ships. It exists because
**v0.6.0 and v0.6.1 were both dead on arrival** — the packaged backend
crashed at import on every machine and nobody noticed, because our tests
run from source and the actual bundle was never executed. Every checklist
item below was paid for by a broken release.

---

## Release channels

| Tag form | Channel | GitHub release | Who gets it |
|---|---|---|---|
| `vX.Y.Z` | Stable | Full release | Everyone, including auto-update |
| `vX.Y.Z-beta.N` | Beta | Prerelease | Only people who download it deliberately |

Tag examples: `v0.6.3` (stable), `v0.7.0-beta.1` (beta).

### Why betas can never reach stable users

The Tauri updater endpoint is:

```
https://github.com/bixdot-app/bixdot/releases/latest/download/latest.json
```

GitHub's `latest` pointer **excludes prereleases by definition**. A tag
containing `-beta` is published with `prerelease: true`
(`.github/workflows/release.yml`), so it never becomes `latest`, so the
updater never offers it to stable users.

**Do not break this invariant.** Specifically, never:

- set `prerelease: false` unconditionally in the release workflow;
- point `plugins.updater.endpoints` at a specific tag or at an endpoint
  that enumerates all releases;
- manually re-tag a beta as a stable release to "promote" it — cut a new
  stable tag from the same commit instead.

### Nightly channel

Out of scope for now.
TODO(v0.7): decide whether a nightly channel is worth the maintenance —
it needs its own signing story and a separate updater endpoint.

---

## Signing (mandatory)

Every release must be signed. The updater public key shipped in v0.6.1, so
installed apps **reject unsigned updates**.

- Repo secrets required: `TAURI_SIGNING_PRIVATE_KEY`,
  `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`
- The private key lives **outside the repo** and must be backed up offline.
  Losing it permanently breaks auto-update for every installed copy.
- If the secrets are absent the build still succeeds but produces no `.sig`
  files and no `latest.json` — check for these on the draft before publishing.

---

## Pre-tag checklist

Run `python scripts/pre_release.py` first — it gates version consistency,
the changelog, tests, ruff, bandit, and pip-audit. It cannot catch anything
that only manifests in a packaged build, which is what the rest of this list
is for.

**Automated (must be green):**

- [ ] `python scripts/pre_release.py` reports READY
- [ ] Bundle smoke test passes in CI for **all four** targets — the release
      workflow boots the packaged backend and requires a healthy `/health`
      before producing installers. Never disable or skip this step.

**Manual (per release, on real machines):**

- [ ] **Clean install** — install on a machine with no prior BixDot; the
      first-run wizard completes end to end
- [ ] **Upgrade from previous stable** — install over the last stable
      release *while BixDot is running*; confirm the version in Settings
      actually changed (this is precisely what silently failed before v0.6.2)
- [ ] **Auto-update** — an installed previous version detects, downloads,
      and applies this release
- [ ] **All four platform bundles launch** — Windows, macOS (both arches),
      Linux; the UI reaches the chat screen, not an error page

If any box cannot be ticked, **do not tag**. Fix it or cut the scope.
Shipping a partial release is how v0.6.0 and v0.6.1 happened.

---

## Release sequence

```bash
python scripts/bump_version.py X.Y.Z --yes    # all version strings, atomically
# write CHANGELOG.md entry + .github/RELEASE_NOTES_vX.Y.Z.md
python scripts/pre_release.py                 # must report READY
git add -A && git commit -m "chore(release): vX.Y.Z"
git push origin main
git tag vX.Y.Z && git push origin vX.Y.Z      # triggers the build (~20 min)
```

Then:

1. Wait for the workflow to finish (it creates a **draft** release).
2. Verify the draft has installers for all platforms, `.sig` files,
   `latest.json`, and `bixdot-sbom.json`.
3. Work the manual checklist above against the draft's artifacts.
4. **Publish** the draft.
5. Update `bixdot-website/index.html` — hero badge + all six download links.

---

## Supply chain

Every release ships `bixdot-sbom.json`, a CycloneDX SBOM of the Python
dependency tree, generated in CI from `requirements.txt`.

- `cyclonedx-bom` is Apache-2.0 and is installed **only in CI** — it must
  never appear in `requirements.txt` or `requirements-dev.txt`.
- Dependencies are declared with `>=` minimums rather than `==` pins, so
  SBOM entries carry ranges rather than exact versions.
- TODO(v0.7): `cargo-cyclonedx` for the Rust dependency tree.

---

© 2026 DigiTech Business Pte. Ltd.
