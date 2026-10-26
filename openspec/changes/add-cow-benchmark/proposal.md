# Proposal

> **Parked.** Only the proposal is written. Specs, design and tasks come when this change is picked up, after `harden-db-and-expand-tests`.

## Why

Copy-on-write branching is the core bet of the product: hundreds or thousands of features on one machine, without running out of disk. That claim should be measured, per OS, at realistic app sizes, and re-measured as the drivers change. The 2026-08-28 benchmark (macOS only, up to 10 GB, 27.7x faster than `git worktree`) was a one-off; this makes it repeatable and cross-OS, with results kept in the repo.

## What Changes

- A benchmark that creates **1000 branches** of an app with `node_modules` at **500 MB, 1 GB and 10 GB**, and records per OS:
  - time per branch and total;
  - actual disk used across all branches (shared blocks counted once);
  - file metadata size across the branches;
  - the same measurements for `git worktree`, sampled and extrapolated, since 1000 real worktrees of 10 GB would need about 10 TB.
- Runs on each OS with a working driver: macOS (sparse images) and Linux (btrfs); Windows once its driver exists.
- Its own GitHub Actions workflow, started by hand, on runners with enough disk; the 10 GB tier can't run on the development Mac.
- Results committed under `benchmarks/results/` as JSON, plus a generated markdown summary comparing runs over time.
- Apps come from the R2 test apps (`make testapps`, large tiers on demand).
- `make test-cow-bench` runs it locally on whatever tiers fit.

## Capabilities

### New Capabilities

- `cow-benchmark`: what is measured, at which sizes, how results are recorded and compared.

### Modified Capabilities

None.

## Impact

- New: benchmark script, `benchmarks/results/`, `.github/workflows/cow-bench.yml`, the `make test-cow-bench` target.
- Uses: the copy-on-write drivers in `backend/core/cloning/`, the R2 test apps.
- Needs: large CI runners per OS; R2 keys as CI secrets.
- Prior art: the scripts in `rapid-prototyping-speed-test` and its two cost models (worktree grows with bytes, copy-on-write with file count).
