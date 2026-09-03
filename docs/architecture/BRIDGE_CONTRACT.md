# Local bridge contract

## Transport

The Tauri process starts exactly one Python sidecar. Messages use one JSON
object per line on stdin and one JSON object per line on stdout. Logs belong on
stderr. The bridge never writes non-JSON text to stdout.

## Request

```json
{
  "id": "req-123",
  "command": "load_library",
  "payload": {
    "root": "C:/Music",
    "sort": {"field": "name", "direction": "asc"},
    "offset": 0,
    "limit": 200
  }
}
```

## Response

```json
{
  "id": "req-123",
  "ok": true,
  "data": {},
  "error": null
}
```

Errors use the stable `ErrorCode` values in `architecture/errors.py`. A
successful response is never inferred from a timeout, EOF or malformed line.

## Lifecycle

1. Tauri starts Python with stdin/stdout/stderr pipes.
2. Python emits a `ready` response to `ping`.
3. Tauri enables library actions only after that response.
4. Every request has a unique ID and every response echoes it.
5. Tauri sends `shutdown` on close and waits for bounded process termination.
6. EOF, non-zero exit or malformed protocol state disables mutations and shows a
   recoverable bridge error.

## Command ownership

- `set_root`, `load_library`, `get_track_page`: Python read authority.
- `move_track`, `undo_last_move`: Python filesystem authority.
- `set_routes`, `get_config`: Python configuration authority.
- `ping`, `shutdown`: bridge lifecycle only.

React and Rust do not move files, parse audio metadata, infer BPM or maintain a
second library authority.
