# Powerunits Bundled Docs Freshness Contract v1

## Purpose

Bundled Powerunits markdown in Hermes is a **read-only, build-time snapshot**. The manifest-keyed reader (`read_powerunits_doc`) must not be mistaken for live monorepo or database access. Freshness metadata makes **staleness explicit** without widening the first-safe surface.

---

## Snapshot truth vs live truth

| Concept | Meaning |
|--------|---------|
| **Bundled docs** | Copied at image build / bundle time from an allowlisted set of paths in the Powerunits monorepo. |
| **Manifest** | Authoritative list of keys, hashes, optional `doc_class` / `freshness_tier` / `summary`, and bundle provenance (`generated_at`, optional git fields). |
| **Live truth** | Production DB, Railway runtime, uncommitted code, or HEAD of the monorepo — **not** visible through this tool. |

Hermes should treat bundled text as **documented state at bundle time**, not a guarantee of current operations.

---

## Freshness tiers (allowlist / manifest)

Operators classify each entry in `scripts/powerunits_docs_allowlist.json`:

| Tier | Intended content | Default soft-stale threshold (bundle age) |
|------|------------------|-------------------------------------------|
| **stable** | Slow-moving references (architecture, index) | **90** days |
| **medium** | Roadmaps, gaps, plans that change on cadence | **30** days |
| **volatile** | Implementation state, runbooks, ops notes | **14** days |

Thresholds are **soft warnings** only. They do not block reads.

### Environment overrides (optional)

- `HERMES_POWERUNITS_DOCS_STALE_DAYS_STABLE` (default 90)
- `HERMES_POWERUNITS_DOCS_STALE_DAYS_MEDIUM` (default 30)
- `HERMES_POWERUNITS_DOCS_STALE_DAYS_VOLATILE` (default 14)

**List-keys bundle hint** (not tier-specific):

- `HERMES_POWERUNITS_DOCS_STALE_WARNING_DAYS` (default **30**) — if bundle age exceeds this, `list_keys` may include `stale_warning`.

---

## Manifest shape (bundle_version 2)

Top-level (additive; older bundles may omit new fields):

- `bundle_version` (integer; **2** for provenance + per-entry metadata)
- `allowlist_version`
- `generated_at` (UTC ISO8601 with `Z`)
- `source_root_note` (unchanged)
- `source_repo_name` (optional; from allowlist or checkout folder name)
- `source_repo_commit` (optional; full SHA when `git` works in monorepo)
- `source_repo_branch` (optional; absent on detached HEAD)
- `source_ref` (optional; short human-readable ref, e.g. `branch@abcdef123456`)
- `entries[]`: each entry keeps `key`, `source_relative`, `sha256`, `bytes` and may include `doc_class`, `freshness_tier`, `summary`

If git metadata cannot be resolved, bundling **continues**; commit/branch/ref fields are simply omitted.

---

## Reader behavior (runtime)

- **`list_keys`**: returns keys, count, `bundled_docs_notice`, bundle freshness fields (`generated_at`, `bundle_age_days`, optional git fields, `stale_warning` when applicable). **No** filesystem paths to the bundle directory.
- **`read`**: returns document content plus `bundled_docs_notice`, optional `doc_class` / `freshness_tier` / `summary`, `bundle_generated_at`, `bundle_age_days`, and `stale_warning` when bundle age exceeds the **tier** threshold. Still **no** path beyond existing `source_relative` from the manifest.

**No** live repo reads, **no** new tools, **no** DB access — first-safe posture unchanged.

---

## Operator refresh workflow

1. Update the Powerunits monorepo checkout to the desired commit/branch.
2. Run `python scripts/bundle_powerunits_docs.py --source-root "<path-to-EU-PP-Database>"`.
3. Review diff under `docker/powerunits_docs/` and `MANIFEST.json`.
4. Commit, build Docker image, redeploy Hermes.

---

## Verknuepfungen

- Reader tool: `docs/powerunits_docs_reader_v1.md`
- Bundle build: `docs/powerunits_docs_read_surface_v1.md`
- Allowlist design: `docs/powerunits_docs_allowlist_integration_v1.md`
