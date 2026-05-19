# WildAudioWorlds Implementation Checklist

Last updated: 2026-05-19

## Current Phase

- [x] Freeze and validate both legacy applications inside one root repository
- [x] Establish the first shared `packages/wild_audio_worlds/` extraction surface
- [x] Consolidate the first shared Electron/Python session vocabulary around backend-call and recorded-audio paths
- [x] Define the standalone-shell and linked-session attach contract
- [x] Stand up the local integration service bootstrap path
- [x] Route the current Electron bridge through the local integration bootstrap for backend-call and recorded-audio commands
- [x] Add the first linked-session bootstrap and manifest-revision contract checks
- [x] Extend the bootstrap into explicit `session/attach` and `shell/open_companion` flows
- [x] Wire the first shell-edge caller through the new `session/attach` and `shell/open_companion` bootstrap commands
- [x] Replace the thin bootstrap with a persistent multi-client local integration service
- [x] Introduce DataManager as the single writer for derived artifacts
- [x] Introduce AudioManager as the shared session authority
- [x] Add canonical shell consumption and event delivery for AudioManager asset, transport, and revision state
- [x] Build backend analysis requests and readiness checks from canonical service-owned session state
- [x] Audit the merged Electron and Qt control surface and add the first always-visible cross-app launchers
- [ ] Add dirty-state, revision-ready, and revision-failure coordination on top of the shared session authority

## Completed Foundations

- [x] Finalize the architecture and planning baseline in `WildAudioWorlds_Project_Plan.md`
- [x] Initialize the WildAudioWorlds root git repository
- [x] Set the root repository default branch to `main`
- [x] Add the `origin` remote for `git@github.com:msstter/WildAudioWorlds.git`
- [x] Create the first root `environment.yml`
- [x] Add a root `.gitignore` that covers both legacy projects and future shared data roots
- [x] Create a live implementation checklist with checkboxes for progress tracking
- [x] Create the initial shared scaffold directories for apps, services, packages, tests, and docs
- [x] Add the initial root packaging config for `packages/wild_audio_worlds/`
- [x] Validate root environment imports and the 3DAudioGraphs frontend production build
- [x] Install and validate the root `wild_audio_worlds` Conda environment
- [x] Install frontend dependencies for `3DAudioGraphs-main/frontend`
- [x] Smoke-test standalone AudioOnsetFinder shell startup
- [x] Smoke-test 3DAudioGraphs backend import and asset-processing path
- [x] Begin extracting shared Python code into `packages/wild_audio_worlds/`

## Completed Shared Package Extractions

- [x] Extract shared asset-store path and manifest helpers into `packages/wild_audio_worlds/data/`
- [x] Extract shared graph runtime path helpers into `packages/wild_audio_worlds/graph/`
- [x] Extract shared Python backend request contracts into `packages/wild_audio_worlds/session/command_contracts.py`
- [x] Extract shared analysis-type and readiness metadata into `packages/wild_audio_worlds/session/analysis_types.*`
- [x] Extract shared selection payload normalization into `packages/wild_audio_worlds/session/selection_contracts.*`
- [x] Extract shared save/result metadata into `packages/wild_audio_worlds/session/result_metadata.*`
- [x] Extract shared backend failure/error metadata into `packages/wild_audio_worlds/session/error_metadata.*`
- [x] Extract shared backend failure formatting into `packages/wild_audio_worlds/session/failure_formatter.cjs`
- [x] Extract shared backend-call log metadata and formatted monitor view-models into `packages/wild_audio_worlds/session/log_metadata.*`
- [x] Extract shared backend-call and recorded-audio log event/message templates into `packages/wild_audio_worlds/session/log_events.*`
- [x] Extract shared recorded-audio failure metadata into `packages/wild_audio_worlds/session/recorded_audio_errors.*`

## Validated Current Baseline

- [x] Add the first shared command-schema contract tests
- [x] Validate the root Conda environment with the environment Python executable
- [x] Validate the 3DAudioGraphs frontend production build with `npm run build`
- [x] Validate AudioOnsetFinder shell startup offscreen through `pipeline_gui.main()`
- [x] Validate the 3DAudioGraphs backend import runner end to end with generated outputs
- [x] Validate shared Python and CJS session slices iteratively with smoke tests and syntax checks
- [x] Validate backend-call monitor rendering against shared failure and log view-models supplied by Electron main
- [x] Remove remaining recorded-audio failure wording from `frontend/main.cjs` in favor of shared session metadata
- [x] Validate the first Electron-to-AudioOnsetFinder shared-session shell-edge path with focused Python/CJS tests, Electron syntax checks, and a frontend production build
- [x] Validate the reverse AudioOnsetFinder-to-Electron shared-session shell-edge path with focused Python contract tests plus Electron CJS smoke and syntax checks
- [x] Validate `session/detach` plus linked-session launch-failure, attach-failure, and session-reuse behavior with focused Python contract tests
- [x] Validate the persistent local integration service bootstrap, shell attach reuse, backend-call job metadata, and job cancellation flow with focused Python contract tests plus an Electron main-process syntax check
- [x] Validate the first AudioManager slice around service-owned asset, revision, playhead, and selection state with focused local-integration Python contract tests
- [x] Validate the first DataManager extraction around graph-asset publication, manifest ownership, compatibility helper delegation, and stale manifest-write rejection with focused Python contract tests
- [x] Validate the next DataManager extraction around backend-call export publication, workbook-write delegation, and non-graph derived artifact path authority with focused Python contract tests
- [x] Validate the next DataManager extraction around recorded-audio source-input publication plus shared onset writer routing with focused Python tests and Electron syntax checks
- [x] Validate the completed DataManager standalone-writer closure plus headless-safe AudioOnsetFinder writer and Excel compatibility paths with focused Python tests and contract coverage
- [x] Validate AudioManager canonical read-side polling and remote apply across the service, PyQt shell, and Electron shell with focused contract and widget tests plus Electron syntax checks
- [x] Validate canonical backend request building and backend-monitor readiness against `session/get_state`-backed Electron paths
- [x] Validate the refreshed frontend production bundle after the new always-visible `LIVE` and `CAM` transport launchers

## Immediate Next

- [ ] Add service-owned dirty-state broadcasting plus `asset/revision_ready` / `asset/revision_failed` coordination so both shells switch revisions through one canonical event path
- [ ] Route onset-editor save or edit completion and backend job completion onto that coordinated revision lifecycle instead of shell-local completion handling
- [ ] Expand contract and integration coverage around canonical event delivery, live-source transitions, revision switching, companion attach or detach reuse, and superseded jobs
- [ ] Decide which backend-monitor and companion-only actions should be promoted into direct main-shell shortcuts after the merged control-surface audit

## Newly Completed DataManager Slice

- [x] Add a shared Python `DataManager` in `packages/wild_audio_worlds/data/` so graph-asset publication and mutable asset-manifest writes move behind one shared owner
- [x] Route `3DAudioGraphs-main/backend/main.py` graph asset publication through DataManager while preserving the renderer-facing `audio_assets_manifest.json` contract
- [x] Publish graph assets into per-asset revision directories and add manifest-level revision metadata so new derived revisions do not overwrite prior artifact paths in place
- [x] Route the legacy shared `audio_asset_store` manifest write helpers through DataManager so compatibility callers still land on the same single-writer path

## Newly Completed DataManager Export Slice

- [x] Extend DataManager with backend-call JSON/WAV export publication helpers so `run_selection_analysis.py` no longer writes those artifacts directly
- [x] Route the bioacoustics workbook writer through DataManager so current non-graph derived artifact writes also flow through the shared filesystem authority
- [x] Move backend-call export path generation under DataManager so fallback XLSX exports and save-result paths stay aligned with the managed export root

## Newly Completed DataManager Source And Onset Writer Slice

- [x] Move `recorded-audio/import` source-input publication behind the Python/DataManager boundary so Electron no longer writes recorded source bytes directly before import
- [x] Route the shared onset writer layers through DataManager-compatible write helpers so onset workbook, label, transcript, TextGrid, selection-export, and onset-editor persistence writes no longer publish directly when the shared package tree is available
- [x] Preserve standalone AudioOnsetFinder compatibility by falling back to the legacy local writer behavior when the shared WildAudioWorlds packages are not present

## Newly Completed DataManager Standalone Writer Closure Slice

- [x] Extend the shared DataManager/write-helper surface with binary-file publication plus indexed CSV support so standalone workbook, figure, and report artifacts can republish through the managed output roots
- [x] Route the remaining standalone AudioOnsetFinder batch, workbook, report, plot, analyzer, selector, and noise-profile artifact writers through shared DataManager-compatible bridges while preserving standalone fallback behavior
- [x] Reduce the remaining direct local writes in `AudioOnsetFinder-main/scripts/` to preset/config persistence and explicit bridge-fallback internals rather than derived analysis artifact publication

## Newly Completed Step 5 Prep

- [x] Write the standalone-shell versus linked-session attach contract as a concrete document plus first payload/schema draft
- [x] Define the first session manifest fields for asset ID, revision ID, originating shell, launch context, playhead, and selection window

## Newly Completed Bootstrap Slice

- [x] Add the thin stdio local integration bootstrap in `services/local_integration/bootstrap_service.py`
- [x] Add shared Python session manifest helpers in `packages/wild_audio_worlds/session/session_manifest.py`
- [x] Publish session manifests under `data/sessions/<sessionId>/session_manifest.json` during bootstrap command handling
- [x] Route the Electron backend-call and recorded-audio compatibility commands through the bootstrap instead of spawning runner scripts directly in shell-local bridge code
- [x] Validate the bootstrap with Python contract tests, `main.cjs` syntax checks, direct `service/bootstrap` smoke, and direct `backend-call/run` smoke

## Newly Completed Linked-Session Slice

- [x] Add focused Python contract coverage for `bootstrap -> shell/open_companion -> session/attach` manifest revision updates
- [x] Auto-promote manifests from `standalone` to `linked` when a second peer attaches through the shared manifest helper
- [x] Add thin bootstrap handlers for explicit `shell/open_companion` and `session/attach` commands without reopening shell-local orchestration

## Newly Completed Shell-Edge Slice

- [x] Add shared shell-launch CLI arg helpers so companion-launch flags stay aligned between Electron and PyQt startup paths
- [x] Wire the Electron toolbar shell edge through `shell/open_companion` and launch AudioOnsetFinder with shared session attach args
- [x] Wire AudioOnsetFinder startup through `session/attach` so a launched companion joins the existing shared session before the GUI shows
- [x] Validate the new shell-edge path with focused Python contract tests, a CJS smoke test, Electron syntax checks, and a frontend production build

## Newly Completed Reverse Shell-Edge Slice

- [x] Add thin AudioOnsetFinder local-integration bootstrap/open-companion helpers so the PyQt shell can own its companion launch path without reintroducing shell-local session vocabulary
- [x] Add a PyQt main-window companion entry point that requests `shell/open_companion` and launches `3DAudioGraphs-main/frontend` with shared WildAudioWorlds attach args
- [x] Wire Electron startup through `session/attach` so an AudioOnsetFinder-launched companion joins the shared session before the BrowserWindow shows
- [x] Validate the reverse shell-edge path with a focused PyQt contract test plus Electron syntax and shared shell-launch smoke checks

## Newly Completed Detach And Acceptance Slice

- [x] Add thin bootstrap handling for `session/detach` so peer removal lives in the shared local integration service instead of shell-local shutdown code
- [x] Extend the shared session manifest helper so detach can remove peers, downgrade `linked` sessions back to `standalone`, and preserve host-shell context without forcing detached peers back into the manifest
- [x] Add focused contract coverage for detach plus shell-edge launch failure, companion attach failure, and linked-session reuse/re-attach behavior

## Newly Completed Persistent Service Slice

- [x] Add a persistent local integration daemon in `services/local_integration/service_runtime.py` that is bootstrapped from `service/bootstrap`, advertises a reusable Unix-domain-socket endpoint, and keeps one service instance alive per session
- [x] Route both shell clients to prefer the advertised persistent service endpoint for non-bootstrap local-integration commands, falling back to the thin bootstrap only when the reusable endpoint is unavailable
- [x] Add structured local-integration job metadata plus `job/status`, `job/cancel`, and supersession wiring for `backend-call/run` and `recorded-audio/import`, with focused contract coverage around job lifecycle behavior

## Newly Completed AudioManager Foundation Slice

- [x] Add a service-owned `AudioManager` in `services/local_integration/audio_manager.py` so canonical asset, revision, playhead, and selection state live behind the persistent local integration daemon instead of shell-local caches
- [x] Route `session/get_state`, `session/open_asset`, `asset/set_revision`, `transport/set_time`, and `transport/set_selection` through the persistent service and persist those mutations back to the shared session manifest
- [x] Keep the daemon's AudioManager state aligned with bootstrap, attach, detach, and open-companion manifest updates, and validate the new ownership path with focused local-integration contract tests

## Newly Completed AudioManager Shell Publish Slice

- [x] Add `session/clear_asset` so the persistent service can clear stale canonical asset state when the Electron shell unloads the current asset or enters live-source mode
- [x] Wire the Electron shell to publish real asset open, asset clear, playhead, and selection changes from the existing backend-call monitor path into the AudioManager command surface
- [x] Wire the AudioOnsetFinder onset editor to publish loaded assets, manual seek changes, playback position updates, and viewer selection clear/select changes through the shared local-integration session helpers while remaining standalone-safe when the shared package tree is absent
- [x] Validate the shell-publish slice with focused service-runtime and shell-helper contract tests, a focused onset-editor widget test, and Electron syntax checks

## Newly Completed AudioManager Canonical Read Slice

- [x] Add service-owned AudioManager event delivery through `events/poll` so both shells can consume canonical asset, transport, and revision updates without direct peer-to-peer synchronization
- [x] Wire AudioOnsetFinder to poll and apply canonical AudioManager state through the shared local-integration session helper plus a GUI event pump, including remote asset, playhead, and selection updates without republishing loops
- [x] Wire Electron to hydrate from `local-integration:get-state`, poll canonical local-integration events, and apply remote AudioManager asset, transport, and revision updates without treating backend-monitor snapshots as canonical state

## Newly Completed Canonical Backend Request Slice

- [x] Build backend analysis requests from canonical `session/get_state` snapshots through the shared session contracts instead of renderer-local backend-monitor cache state
- [x] Preserve richer canonical asset metadata in the shared AudioManager state so backend analysis requests can reuse those fields without shell-local reconstruction
- [x] Route backend-monitor readiness through an explicit Electron-main canonical readiness query instead of treating the pushed monitor snapshot as the selection-readiness source of truth

## Newly Completed Cross-App Control Surface Slice

- [x] Audit the merged Electron shell, backend monitor, and AudioOnsetFinder companion controls in `docs/merged_control_surface_audit.md`
- [x] Add always-visible `LIVE` and `CAM` transport launchers in the Electron shell so the live-source and camera-control workflows are discoverable without opening the sidebar first
- [x] Complete the second-pass Qt companion audit so the control-surface document now maps the AudioOnsetFinder top action row, step sidebar, onset-editor toolbar, popup menus, and dialogs alongside the Electron shell

## Notes

- Root repo path: `/Users/mh295/WildAudioWorlds`
- Default shell target: AudioOnsetFinder PyQt GUI
- Companion shell target: 3DAudioGraphs Electron app
- Root Python environment file: `environment.yml`
- Session attach contract draft now lives in `docs/session_attach_contract.md`
- Thin local integration bootstrap entrypoint now lives in `services/local_integration/bootstrap_service.py`
- Persistent local integration daemon entrypoint now lives in `services/local_integration/service_runtime.py`
- AudioManager now lives in `services/local_integration/audio_manager.py` and currently owns asset, revision, playhead, and selection state for the persistent service, including explicit asset-clear mutations
- Focused Step 6 validation now passes for `tests/contract/test_local_integration_service_runtime.py`, `tests/contract/test_local_integration_bootstrap.py`, and `tests/contract/test_audio_onset_shell_session.py`, plus `node --check 3DAudioGraphs-main/frontend/main.cjs`
- Focused Step 8 foundation validation now passes for `tests/contract/test_local_integration_service_runtime.py`, `tests/contract/test_local_integration_bootstrap.py`, and `tests/contract/test_audio_onset_shell_session.py`
- Focused Step 8 shell-publish validation now passes for `tests/contract/test_local_integration_service_runtime.py`, `tests/contract/test_audio_onset_shell_session.py`, `AudioOnsetFinder-main/GUI/test_onset_editor.py`, `node --check 3DAudioGraphs-main/frontend/main.cjs`, and `node --check 3DAudioGraphs-main/frontend/src/main.js`
- Focused Step 8 canonical read-side validation now also passes for `tests/contract/test_local_integration_service_runtime.py`, `tests/contract/test_audio_onset_shell_session.py`, `AudioOnsetFinder-main/GUI/test_onset_editor.py`, `node --check 3DAudioGraphs-main/frontend/main.cjs`, `node --check 3DAudioGraphs-main/frontend/preload.cjs`, `node --check 3DAudioGraphs-main/frontend/public/backend-call-monitor.js`, and `node --check 3DAudioGraphs-main/frontend/src/main.js`
- Focused Step 7 close-out validation now passes for `tests/contract/test_data_manager.py` plus the AudioOnsetFinder writer/Excel/pipeline bundle (`tests/test_shared_output_writers.py`, `tests/test_onset_exports.py`, `tests/test_excel_onset_io.py`, `tests/test_pipeline_file_selection.py`)
- Current implementation phase: Step 6 and Step 7 are complete, and Step 8 is now in progress through the service-owned AudioManager publish/read path, canonical backend-request path, and first cross-app control-surface polish
- The highest-leverage next move is to add service-owned dirty-state plus revision-ready/revision-failed coordination, then route edit completion and backend-job completion onto that canonical revision lifecycle