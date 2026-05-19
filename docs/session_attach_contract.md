# WildAudioWorlds Session Attach Contract Draft

Date: 2026-05-19
Status: Draft v0.1

## Implementation Status

The first thin bootstrap implementation now exists in `services/local_integration/bootstrap_service.py`.

Current implemented scope:

- `service/bootstrap`
- `backend-call/run`
- `recorded-audio/import`
- `session/attach`
- `shell/open_companion`

Current non-implemented scope from this draft:

- explicit `session/detach`
- linked-session multi-peer attach behavior
- reverse-direction shell-edge launch from AudioOnsetFinder into Electron

That means this document is now partly implemented: the manifest draft, bootstrap path, first open-companion launch-intent flow, first attach flow, and the first Electron-to-AudioOnsetFinder shell edge are live, but detach behavior and reverse-direction shell-edge launch are still the next Step 5 extension.

## Purpose

This document defines the first concrete contract for standalone-shell and linked-session operation in WildAudioWorlds.

It is intended to do three things:

1. Define what a session is and what it means for a shell to attach to one.
2. Define the first session manifest fields that both shells and the future local integration service can rely on.
3. Provide the initial launch and attach payload draft that the next service bootstrap slice can implement without reopening basic vocabulary decisions.

This draft is intentionally narrow. It does not attempt to finalize the entire long-lived service protocol, DataManager behavior, or AudioManager internals.

## Terms

- Session: the canonical shared context for one active asset, one active derived revision, and one authoritative transport state.
- Standalone shell: a shell running against its own local session with no companion attached.
- Linked session: two shells attached to the same service-owned session state.
- Host shell: the shell that originally opened or currently owns the session launch context.
- Companion shell: the second shell attached to the same session.
- Integration service: the local process that owns canonical session state and brokers commands/events between shells.

## Goals

- Keep AudioOnsetFinder and 3DAudioGraphs independently launchable.
- Allow either shell to launch the other into the same session without direct shell-to-shell synchronization.
- Ensure both shells can identify the same asset, revision, playhead, and selection state.
- Keep the first implementation compatible with the current Electron bridge and Python compatibility wrappers.
- Provide a manifest shape that the later service bootstrap, DataManager, and AudioManager can extend rather than replace.

## Non-Goals For Draft v0.1

- Final transport security or authentication.
- Final multi-user or remote-network behavior.
- Full job-control schema.
- Final DataManager artifact manifest shape.
- Full bidirectional editor/graph sync semantics beyond the initial handoff state.

## Operating Modes

### Standalone Mode

- A shell starts by itself and creates or opens a local session.
- No companion shell is required.
- The same session manifest schema is still used, even if the session is never shared.
- The shell may bootstrap the local integration service through a simple local launch path.
- If no companion is ever requested, the session remains valid and fully usable.

### Linked-Session Mode

- One shell launches or attaches the other using a shared `sessionId` plus discovered service endpoint information.
- The integration service becomes the single authority for session state.
- Both shells must attach through the service rather than talking to each other directly.
- The host shell remains usable even if companion launch or attach fails.
- Session state updates are versioned so later manager work can reject stale writes.

## Ownership Rules

- The integration service owns canonical session state.
- Shells publish user intent and consume canonical updates.
- The session manifest is the published handshake artifact for attach/bootstrap, not the long-term live source of truth.
- Until DataManager exists, the thin integration bootstrap is allowed to write the session manifest.
- When DataManager is introduced, manifest publication authority moves there without changing the shell-facing contract shape.

## Canonical Session Manifest Draft

### Location

Draft path:

```text
data/sessions/<sessionId>/session_manifest.json
```

### Write Rules

- Publish atomically.
- Update `stateRevision` whenever the canonical manifest snapshot changes.
- Preserve the same `sessionId` across standalone-to-linked promotion if a companion shell is later opened.
- Never let shells mutate the manifest directly.

### Required Top-Level Fields

- `schemaVersion`: contract schema version, starting at `0.1`.
- `sessionId`: stable session identifier.
- `mode`: `standalone` or `linked`.
- `stateRevision`: monotonic revision for manifest/state publication.
- `createdAt`: ISO timestamp.
- `updatedAt`: ISO timestamp.
- `service`: the current integration-service bootstrap endpoint and protocol descriptor.
- `hostShell`: the shell that originated the session context.
- `asset`: the currently active asset and revision pointer.
- `transportState`: the canonical playhead and selection snapshot used for initial attach.
- `launchContext`: the reason and origin of the current shell attach/open flow.
- `peers`: attached shell snapshots.

### First Manifest Field Draft

```json
{
  "schemaVersion": "0.1",
  "sessionId": "waw-session-20260519-001",
  "mode": "linked",
  "stateRevision": 7,
  "createdAt": "2026-05-19T19:30:00.000Z",
  "updatedAt": "2026-05-19T19:31:10.000Z",
  "service": {
    "protocolVersion": "0.1",
    "transport": "unix-domain-socket",
    "endpoint": "/tmp/wild_audio_worlds/session-20260519-001.sock",
    "bootMode": "spawned-by-audio-onset-finder",
    "ownerShellId": "shell-aof-001"
  },
  "hostShell": {
    "shellId": "shell-aof-001",
    "shellType": "audio-onset-finder",
    "startedAt": "2026-05-19T19:30:00.000Z",
    "version": "draft"
  },
  "asset": {
    "assetId": "asset-forest-001",
    "assetLabel": "Forest Dawn",
    "sourceAudioPath": "data/source/raw_audio/forest_dawn.wav",
    "sourceKind": "raw-audio",
    "activeRevisionId": "rev-0007"
  },
  "transportState": {
    "playheadSec": 12.345,
    "selectionWindow": {
      "selectionModel": "spectroterrain-full-sculpt",
      "isReady": true,
      "timeRangeSec": {
        "start": 11.8,
        "end": 13.1
      },
      "frequencyBinRange": {
        "startBin": 10,
        "endBin": 120,
        "totalBins": 256
      },
      "amplitudePctRange": {
        "min": 15,
        "max": 85
      },
      "updatedByShellId": "shell-graph-001"
    }
  },
  "launchContext": {
    "originatingShell": "audio-onset-finder",
    "launchReason": "open-companion",
    "requestedCompanion": "audio-graphs",
    "requestedByShellId": "shell-aof-001"
  },
  "peers": [
    {
      "shellId": "shell-aof-001",
      "shellType": "audio-onset-finder",
      "status": "attached",
      "attachedAt": "2026-05-19T19:30:00.000Z",
      "lastSeenAt": "2026-05-19T19:31:10.000Z"
    },
    {
      "shellId": "shell-graph-001",
      "shellType": "audio-graphs",
      "status": "attached",
      "attachedAt": "2026-05-19T19:30:30.000Z",
      "lastSeenAt": "2026-05-19T19:31:10.000Z"
    }
  ]
}
```

## First Priority Fields

These are the fields the next implementation slice should treat as mandatory because they unblock service bootstrap and companion attach behavior immediately.

- Asset identity: `asset.assetId`
- Active revision identity: `asset.activeRevisionId`
- Originating shell: `hostShell.shellType`
- Launch context: `launchContext.originatingShell`, `launchContext.launchReason`, `launchContext.requestedCompanion`
- Playhead: `transportState.playheadSec`
- Selection window: `transportState.selectionWindow`
- Service endpoint: `service.transport`, `service.endpoint`
- Session revisioning: `stateRevision`

## First Command Payload Draft

### `shell/open_companion`

Purpose: request that the service or host shell launch the companion shell into the current session.

Request draft:

```json
{
  "command": "shell/open_companion",
  "sessionId": "waw-session-20260519-001",
  "originShell": {
    "shellId": "shell-aof-001",
    "shellType": "audio-onset-finder"
  },
  "targetShell": "audio-graphs",
  "asset": {
    "assetId": "asset-forest-001",
    "activeRevisionId": "rev-0007"
  },
  "transportState": {
    "playheadSec": 12.345,
    "selectionWindow": {
      "selectionModel": "spectroterrain-full-sculpt",
      "isReady": true
    }
  },
  "launchContext": {
    "originatingShell": "audio-onset-finder",
    "launchReason": "open-companion"
  }
}
```

Response draft:

```json
{
  "ok": true,
  "sessionId": "waw-session-20260519-001",
  "manifestPath": "data/sessions/waw-session-20260519-001/session_manifest.json",
  "service": {
    "transport": "unix-domain-socket",
    "endpoint": "/tmp/wild_audio_worlds/session-20260519-001.sock"
  },
  "launchedShell": {
    "shellType": "audio-graphs"
  }
}
```

### `session/attach`

Purpose: attach a shell to an already-created session.

Request draft:

```json
{
  "command": "session/attach",
  "sessionId": "waw-session-20260519-001",
  "shell": {
    "shellId": "shell-graph-001",
    "shellType": "audio-graphs"
  },
  "requestedCapabilities": [
    "transport-read",
    "transport-write",
    "asset-read"
  ],
  "lastKnownStateRevision": 6
}
```

Response draft:

```json
{
  "ok": true,
  "sessionId": "waw-session-20260519-001",
  "mode": "linked",
  "stateRevision": 7,
  "manifest": {
    "schemaVersion": "0.1",
    "asset": {
      "assetId": "asset-forest-001",
      "activeRevisionId": "rev-0007"
    },
    "transportState": {
      "playheadSec": 12.345
    }
  },
  "service": {
    "transport": "unix-domain-socket",
    "endpoint": "/tmp/wild_audio_worlds/session-20260519-001.sock"
  }
}
```

### `session/detach`

Purpose: cleanly detach a shell from a shared session without destroying the session unless it is the final peer and shutdown rules allow it.

Request draft:

```json
{
  "command": "session/detach",
  "sessionId": "waw-session-20260519-001",
  "shellId": "shell-graph-001",
  "reason": "window-closed"
}
```

## First Event Draft

These events are the minimum useful set for the next integration slice.

- `session/peer_attached`
- `session/peer_detached`
- `session/asset_changed`
- `transport/time_changed`
- `transport/selection_changed`

The next service bootstrap does not need to implement the full final event family immediately, but it should use these names so later work does not rename basic session vocabulary again.

## Implementation Rules For The Next Slice

- The first integration service bootstrap should accept this draft as the source of truth for attach/open payloads.
- The current Electron bridge should be able to route backend-call and recorded-audio commands through that bootstrap without changing user-visible behavior.
- AudioOnsetFinder now attaches on companion startup in the first shell-edge slice, but reverse-direction Electron launch and broader shell lifecycle behavior still remain outside this draft's implemented scope.

## Current Thin Implementation Notes

- `shell/open_companion` currently records companion-launch intent in the manifest, updates `launchContext.requestedCompanion` and `launchContext.requestedByShellId`, and returns the current service/session descriptor.
- `shell/open_companion` is now also used by the Electron shell edge to launch `AudioOnsetFinder-main/GUI/pipeline_gui.py` with shared WildAudioWorlds session attach args.
- `session/attach` currently attaches a second shell snapshot, increments `stateRevision`, and promotes the manifest from `standalone` to `linked` when peer count grows beyond one.
- AudioOnsetFinder startup now consumes those shared attach args before Qt initialization and calls `session/attach` through the thin bootstrap so the companion joins the linked session during launch.
- Focused Python contract tests now cover `service/bootstrap -> shell/open_companion -> session/attach` and assert manifest revision updates `1 -> 2 -> 3`.
- Focused shell-edge validation now also covers the shared CLI arg vocabulary, the AudioOnsetFinder startup attach helper, Electron syntax checks, and the frontend production build.
- The session manifest should be safe to publish even before DataManager exists, but only the bootstrap/service should write it.
- Companion attach failures must return structured failures while leaving the host shell fully usable.

## Acceptance Checks For This Draft

This draft is good enough for the next implementation slice if it supports the following checks:

1. A standalone shell can create a session manifest that includes asset, revision, playhead, and selection state.
2. The host shell can request companion launch with `shell/open_companion` without inventing new payload fields.
3. A companion shell can attach with `session/attach` and receive the current asset, revision, playhead, and selection snapshot.
4. Session state updates can be versioned with `stateRevision`.
5. Failure to launch or attach a companion shell does not invalidate the host shell session.

## Immediate Follow-On Work

After this draft, the next implementation work should be:

1. Stand up the thin local integration service bootstrap.
2. Route the current Electron bridge through that bootstrap using compatibility wrappers.
3. Add the first linked-session smoke or contract checks against this manifest and payload shape.
4. Use that working service boundary to start DataManager extraction.