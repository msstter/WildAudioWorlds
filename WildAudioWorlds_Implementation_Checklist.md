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
- [ ] Introduce DataManager as the single writer for derived artifacts
- [ ] Introduce AudioManager as the shared session authority

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
- [x] Validate the first DataManager extraction around graph-asset publication, manifest ownership, compatibility helper delegation, and stale manifest-write rejection with focused Python contract tests
- [x] Validate the next DataManager extraction around backend-call export publication, workbook-write delegation, and non-graph derived artifact path authority with focused Python contract tests

## Immediate Next

- [x] Extend the reverse shell edge so AudioOnsetFinder can launch the Electron companion into the same shared session
- [x] Extend the thin bootstrap from explicit attach/open flows into `session/detach`
- [x] Add linked-session acceptance coverage for shell-edge launch failures, companion attach failures, and session reuse
- [x] Start the first DataManager extraction around mutable asset publication, manifest ownership, and revision-safe writes

## Newly Completed DataManager Slice

- [x] Add a shared Python `DataManager` in `packages/wild_audio_worlds/data/` so graph-asset publication and mutable asset-manifest writes move behind one shared owner
- [x] Route `3DAudioGraphs-main/backend/main.py` graph asset publication through DataManager while preserving the renderer-facing `audio_assets_manifest.json` contract
- [x] Publish graph assets into per-asset revision directories and add manifest-level revision metadata so new derived revisions do not overwrite prior artifact paths in place
- [x] Route the legacy shared `audio_asset_store` manifest write helpers through DataManager so compatibility callers still land on the same single-writer path

## Newly Completed DataManager Export Slice

- [x] Extend DataManager with backend-call JSON/WAV export publication helpers so `run_selection_analysis.py` no longer writes those artifacts directly
- [x] Route the bioacoustics workbook writer through DataManager so current non-graph derived artifact writes also flow through the shared filesystem authority
- [x] Move backend-call export path generation under DataManager so fallback XLSX exports and save-result paths stay aligned with the managed export root

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

## Notes

- Root repo path: `/Users/mh295/WildAudioWorlds`
- Default shell target: AudioOnsetFinder PyQt GUI
- Companion shell target: 3DAudioGraphs Electron app
- Root Python environment file: `environment.yml`
- Session attach contract draft now lives in `docs/session_attach_contract.md`
- Thin local integration bootstrap entrypoint now lives in `services/local_integration/bootstrap_service.py`
- Current implementation phase: Step 4 is well underway, and Step 5 now includes explicit attach/open/detach bootstrap commands, real shell edges in both directions, focused linked-session acceptance coverage, and DataManager ownership for the current graph compatibility path's derived-artifact writes
- The highest-leverage next move is to extend DataManager beyond the current graph compatibility path into source-input publication and onset-side derived artifact writes before starting AudioManager