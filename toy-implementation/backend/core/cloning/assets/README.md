# Pre-formatted disk images

Empty, filesystem-formatted container images shipped with the drivers, so a
first run does not have to create one.

    macos-pristine.sparseimage    empty APFS, 1 TB ceiling

## Why ship it

`hdiutil create` costs 1717 ms. Cloning this file instead costs 0.1 ms, and
consumes no disk — the base shares blocks with it until it diverges.

It is stored **uncompressed on purpose.** At 15 MB of mostly zeros git deflates
it to ~36 KB, so compressing first would save 27 KB of history and cost 646x on
every first run (64.6 ms to decompress vs 0.1 ms to clone).

It contains no executables, so **one artifact covers every Mac**, Intel and
Apple Silicon alike. There is no per-architecture variant to maintain.

## What it is not

Not the base image. It holds zero files — `base/` is copied in at runtime by
`ensure_base()`. Baking the app into it would make the artifact
architecture-specific (native binaries in `node_modules`) and stale the moment
a lockfile changes.

## Regenerating

Built and verified by a separate repository — **bakztfuture/rapid-prototyping-image-cloning**
— which holds `.github/workflows/build-base-image.yml`. That workflow creates
the image on the oldest available runner, then proves it mounts, clones,
isolates and grows on macos-14, macos-15 and macos-15-intel.

It lives there rather than here because it needs no checkout of this project,
and because `workflow_dispatch` only works from a repository's default branch.

    gh workflow run "Build base disk image" -R bakztfuture/rapid-prototyping-image-cloning
    gh run download <run-id> -n base-sparseimage -R bakztfuture/rapid-prototyping-image-cloning

The download is named `base.sparseimage`; it goes here as
`macos-pristine.sparseimage`.

Build on the oldest macOS you intend to support: newer macOS reads an older
APFS version, but the reverse is not guaranteed. This artifact was built on
**macOS 14.8.9**, which is therefore the floor — macos-13 runners were retired
on 2025-12-08, so GitHub cannot build older.
