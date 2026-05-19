# WildAudioWorlds Agent Continuation Prompt

You are an expert continuing implementation work inside the WildAudioWorlds repository.

Your job is to keep moving the combined-app migration forward in small, validated slices without breaking either legacy shell.

## Repository Context

- Workspace root: `/Users/mh295/WildAudioWorlds`
- Combined app goal: merge `AudioOnsetFinder-main` and `3DAudioGraphs-main` into one maintainable desktop application with shared services, shared session/data ownership, and two still-usable shells during migration.
- Default/initial shell target: AudioOnsetFinder PyQt GUI
- Companion shell target: 3DAudioGraphs Electron app

## Read These First

Before making changes, read these files and treat them as the live source of truth for status and sequencing:

1. `WildAudioWorlds_Implementation_Checklist.md`
2. `WildAudioWorlds_Project_Plan.md`
3. `docs/session_attach_contract.md`

Do not treat those docs as optional notes. Use them to decide what is already done, what is currently in progress, and what should happen next.

## Working Expectations

- Continue using the markdown tracking docs as part of the implementation workflow.
- If you complete a meaningful slice, update the tracking docs so they reflect the new real state.
- Prefer small, behavior-preserving slices with immediate validation.
- Preserve both shells as independently launchable while the shared integration path grows.
- Reuse the shared `packages/wild_audio_worlds/` surfaces instead of reintroducing shell-local vocabulary.
- Favor contract tests, smoke tests, syntax checks, and narrow builds over broad unscoped validation.
- Do not reopen already-stabilized areas unless the current task truly requires it.

## Current Status Snapshot

At the start of this prompt, the repo already has:

- A persistent local integration service split across `services/local_integration/bootstrap_service.py` and `services/local_integration/service_runtime.py`
- Shared session manifest helpers and shared session metadata under `packages/wild_audio_worlds/session/`
- Explicit `service/bootstrap`, `backend-call/run`, `recorded-audio/import`, `session/attach`, `session/detach`, and `shell/open_companion` coverage across the bootstrap and persistent-service boundary
- Focused linked-session contract tests for bootstrap/open-companion/attach revision updates
- The first real shell edge from Electron into AudioOnsetFinder:
  - Electron requests `shell/open_companion`
  - Electron launches `AudioOnsetFinder-main/GUI/pipeline_gui.py` with shared WildAudioWorlds session args
  - AudioOnsetFinder startup consumes those args and calls `session/attach` before the GUI shows
- The reverse shell edge from AudioOnsetFinder into Electron:
  - AudioOnsetFinder requests `shell/open_companion`
  - AudioOnsetFinder launches `3DAudioGraphs-main/frontend` with shared WildAudioWorlds session args
  - Electron startup consumes those args and calls `session/attach` before the BrowserWindow shows
- Both shell clients now prefer the advertised persistent Unix-domain-socket endpoint for non-bootstrap local-integration commands, falling back to the stdio bootstrap only when the reusable endpoint is unavailable
- The persistent service now owns structured compatibility-job lifecycle data including job IDs, active-job summaries, `job/status`, `job/cancel`, and supersession wiring through `supersedesJobId`
- A first AudioManager slice now exists in `services/local_integration/audio_manager.py`, and the persistent service now owns canonical asset, revision, playhead, and selection state through `session/get_state`, `session/open_asset`, `session/clear_asset`, `asset/set_revision`, `transport/set_time`, and `transport/set_selection`
- Bootstrap, attach, detach, and open-companion manifest mutations now keep the daemon's AudioManager snapshot in sync instead of leaving service-owned state behind the manifest
- Both shells now publish real asset and transport changes into that AudioManager surface: Electron publishes backend-monitor asset and playhead or selection snapshots from `3DAudioGraphs-main/frontend/main.cjs`, and AudioOnsetFinder publishes onset-editor asset, playhead, and selection changes through `AudioOnsetFinder-main/GUI/local_integration_session.py`
- Step 7 DataManager filesystem authority is complete for the current derived-artifact surfaces, including the remaining standalone AudioOnsetFinder batch, report, analyzer, selector, and noise-profile outputs
- Focused validation currently passes for `tests/contract/test_data_manager.py` and the AudioOnsetFinder writer/Excel/pipeline bundle (`tests/test_shared_output_writers.py`, `tests/test_onset_exports.py`, `tests/test_excel_onset_io.py`, `tests/test_pipeline_file_selection.py`)
- Focused Step 6 validation now also passes for `tests/contract/test_local_integration_service_runtime.py`, `tests/contract/test_local_integration_bootstrap.py`, `tests/contract/test_audio_onset_shell_session.py`, and `node --check 3DAudioGraphs-main/frontend/main.cjs`
- Focused Step 8 validation now also passes for `tests/contract/test_local_integration_service_runtime.py`, `tests/contract/test_local_integration_bootstrap.py`, `tests/contract/test_audio_onset_shell_session.py`, `AudioOnsetFinder-main/GUI/test_onset_editor.py -k local_integration_audio_state`, and Electron syntax checks for both `3DAudioGraphs-main/frontend/main.cjs` and `3DAudioGraphs-main/frontend/src/main.js`
- Headless pytest startup now seeds PyQt6's bundled plugin paths, and non-viewer `onset_editor` helper imports no longer require `pyqtgraph`

## Highest-Priority Next Work

Unless the docs have changed by the time you read them, the next logical implementation order is:

1. Add canonical shell consumption plus event delivery for AudioManager transport, asset, and revision updates without peer-to-peer synchronization.
2. Add dirty-state ownership plus revision-ready switching so onset-side edits move both shells through one canonical service-owned revision transition.
3. Add focused contract and integration coverage around playhead sync, selection sync, revision-ready switching, companion attach or detach reuse, and superseded jobs.
4. Collapse temporary shell-local caches where the service-owned read path is now strong enough to replace them.

If you discover the docs have moved beyond this, follow the docs instead of this snapshot.

## Execution Style

Please work in this style:

- Read the tracking docs first.
- Pick the smallest next meaningful slice.
- Implement it at the controlling abstraction, not as a scattered workaround.
- Validate it immediately with the narrowest useful checks.
- Update the tracking markdown files if the implementation status changes.
- End with a concise summary of what changed, what was validated, and what remains next.

## Required Close-Out Format

At the end of your response, include a very concise commit message suggestion on its own line in this exact form:

`Commit: <very short message>`

Keep that commit message short and practical.