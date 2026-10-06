# Releases

This project uses **Semantic Versioning** — `Major.Minor.Patch`.

| Bump | When |
|---|---|
| **Major** (`vX.0.0`) | Breaking changes (CLI args, `.env` variable names, config schema, state format). |
| **Minor** (`v0.Y.0`) | New features, additive changes, new docs — backward compatible. |
| **Patch** (`v0.1.Z`) | Bug fixes, dependency/security bumps — backward compatible. |

The current line is `v0.1.x` (early 0.x: treat Minor as "feature", Patch as "fix"; no stability
guarantees yet).

## Creating a release

```bash
git checkout main
git pull
git tag v0.1.1                       # choose the next version
git push origin v0.1.1
```

Pushing the `v*` tag triggers CI to run the hermetic test job against the exact tagged commit
(both the GitLab and GitHub pipelines run on tags). A green tag = a releasable version.

On GitLab you can then create a formal **Release** (UI → Releases → New → select the tag, add
release notes). On GitHub, `gh release create v0.1.1 --notes "..."`.

## Version source of truth

The **git tag** is the canonical version (what CI and consumers use). The package version in
`pyproject.toml` is informational; bump it to match when convenient but the tag is authoritative.

## Release checklist

- [ ] On `main`, up to date with the latest.
- [ ] CI green on the commit (hermetic tests pass).
- [ ] No secrets in the tree (`.env`, `storage/`, logs excluded — see `.gitignore`).
- [ ] `docs/DEPLOYMENT.md` still accurate for a fresh server.
- [ ] Tag created and pushed (`vA.B.C`).
