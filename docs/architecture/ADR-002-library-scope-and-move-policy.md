# ADR-002 — Library scope and move policy

## Status

Proposed MVP contract; implementation must stop if Product/Mono changes these
semantics during P0.

## Decision

The user-selected folder is the library root. Direct audio files are the
unsorted intake queue. A configured `UNSORTED` child folder may also be an
explicit intake pool. Generated destination folders are excluded from intake.

Classification moves the source file into a validated destination under the
selected root. It does not copy. The backend must reject root escapes,
unsupported cross-volume moves, missing sources and existing destinations. A
conflict leaves the source untouched and returns `DESTINATION_EXISTS`.

The default route surface has nine configurable slots. `Numpad1` through
`Numpad9` invoke those routes. The hot path has no confirmation modal; it uses a
visible result and a bounded undo receipt.

BPM is read from metadata first and analyzed locally with Librosa only when
needed. If no BPM can be obtained, the backend uses an explicit `BPM UNKNOWN`
bucket and never fabricates a value. Genre is metadata display data unless a
route explicitly declares a destination folder.

## Rejected alternatives

- Copying by default: conflicts with the intended unsorted queue semantics.
- Scanning every descendant indiscriminately: reintroduces already classified
  tracks into the queue.
- Overwriting destination files: risks silent data loss.
- Inferring genre/BPM from filenames or guesses: creates untraceable placement.
