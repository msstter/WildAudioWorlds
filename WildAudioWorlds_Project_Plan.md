# WildAudioWorlds Project Planning Document

Date: 2026-05-19

## 1. Main Goals and Objectives

- Merge 3DAudioGraphs and AudioOnsetFinder into one maintainable desktop application named WildAudioWorlds.
- Use AudioOnsetFinder's GUI as the default or initial launch surface for editing-heavy and configuration-heavy workflows.
- Keep both the AudioOnsetFinder GUI and the 3DAudioGraphs interface fully launchable as standalone shells, while allowing either shell to open the other when a linked workflow requires it.
- Preserve strong modular boundaries so the two interfaces can share core services without being forced into one menu system too early.
- Preserve the existing Python analysis logic from both repositories instead of rewriting working algorithms up front.
- Consolidate and streamline the algorithm and service layers so the merged app is easier to maintain, test, and extend even when legacy behavior is preserved.
- Create one unified backend command surface so the frontend can trigger both 3D graph operations and onset-analysis operations through the same bridge.
- Add bidirectional synchronization so transport state, playhead position, active audio asset, and edited analysis results stay consistent across the 3D graph view and the onset-editing workflow.
- Introduce strict data ownership so raw source files, downloaded model-generation inputs, edited onset data, and generated graph assets cannot contaminate each other.
- Consolidate setup into one clean Python environment definition and one clean Node/Electron toolchain.
- Preserve legacy behavior during the migration by keeping existing entry points working until the new architecture proves parity.

## 1A. Implementation Status Snapshot

As of 2026-05-19, the project is no longer at planning-only stage. The baseline and the first shared extraction wave are already in place.

- Repository bootstrap is complete, with both legacy codebases present in one root repo and the initial root environment/build flow validated.
- Both legacy applications have been smoke-tested independently: AudioOnsetFinder through the PyQt shell path and 3DAudioGraphs through its backend import/analysis path.
- A shared `packages/wild_audio_worlds/` surface now exists and already carries live `data/`, `graph/`, and `session/` code used by the Electron/Python bridge.
- The `session/` package now owns the first shared request contracts, selection normalization, analysis metadata, readiness metadata, result metadata, backend failure metadata, backend failure formatting, log metadata, log event templates, recorded-audio log events, and recorded-audio error metadata.
- The backend-call monitor now renders shared failure and log view-models produced in Electron main rather than inventing those monitor-facing structures locally.
- A first standalone-shell versus linked-session attach contract draft now exists in `docs/session_attach_contract.md`, including the first session manifest, launch payload, and attach payload draft.
- A persistent local integration service now exists across `services/local_integration/bootstrap_service.py` and `services/local_integration/service_runtime.py`: the thin stdio bootstrap publishes session manifests, starts a reusable per-session Unix-domain-socket daemon, and still hosts compatibility command entrypoints for simple bootstrap paths.
- The Electron and PyQt shell bridges now reuse the advertised persistent service endpoint for non-bootstrap local-integration commands instead of repeatedly orchestrating one-off Python startup for linked-session work.
- The first linked-session contract checks now cover `service/bootstrap`, `shell/open_companion`, and `session/attach` manifest revision updates, including standalone-to-linked promotion when a second peer attaches.
- The first real shell edge now exists from Electron into AudioOnsetFinder: the 3DAudioGraphs toolbar requests `shell/open_companion`, launches `pipeline_gui.py` with shared attach args, and AudioOnsetFinder startup joins the shared session through `session/attach` before the GUI shows.
- The reverse shell edge now also exists from AudioOnsetFinder into Electron: the PyQt main window requests `shell/open_companion`, launches `3DAudioGraphs-main/frontend` with shared attach args, and Electron startup joins the shared session through `session/attach` before the BrowserWindow shows.
- The thin bootstrap now also accepts explicit `session/detach`, and the shared manifest helper can remove peers and downgrade linked sessions back to standalone without losing the session identity or host-shell context.
- Focused acceptance coverage now also exercises shell-edge launch failure, companion attach failure, `session/detach`, and linked-session reuse/re-attach behavior using narrow Python contract tests.
- The persistent service layer now issues structured job IDs and status summaries for compatibility runner work, exposes `job/status` and `job/cancel`, and supports superseding older jobs when a new request declares `supersedesJobId`.
- A first DataManager slice now exists in the shared `data/` package: graph-asset publication, asset-manifest ownership, manifest revision metadata, compatibility helper delegation, and per-asset revision directories are now routed through a shared Python DataManager instead of shell-local file writes.
- A second DataManager slice now covers backend-call JSON/WAV export publication, bioacoustics workbook-write delegation, and fallback non-graph export path generation, so the current 3DAudioGraphs compatibility path no longer writes derived artifacts directly outside DataManager.
- A third DataManager slice now covers recorded-audio source-input publication plus the shared onset writer layers, so `recorded-audio/import`, onset workbook persistence, label/transcript/TextGrid export, selection-export artifacts, and onset-editor persistence writes now route through DataManager-compatible helpers when the shared package tree is available.
- A fourth DataManager closure slice now routes the remaining standalone AudioOnsetFinder batch, workbook, report, plot, analyzer, selector, and noise-profile artifact writes through shared DataManager-compatible bridges, leaving only preset/config persistence and explicit standalone-fallback internals on direct local writes.
- Focused validation now passes for the DataManager contract slice plus the headless-safe AudioOnsetFinder writer/Excel/pipeline bundle; pytest startup seeds PyQt6's bundled plugin paths and non-viewer onset-editor helper imports no longer require `pyqtgraph`.
- The persistent service now also emits canonical AudioManager event traffic through `events/poll`, and both shells now consume service-owned asset, transport, and revision state instead of relying only on shell-local caches.
- Electron backend analysis requests now build from canonical `session/get_state` snapshots through the shared session contracts, while the backend monitor's readiness gating now queries Electron main for canonical readiness instead of treating the pushed monitor snapshot as the source of truth.
- The merged control-surface audit is now documented in `docs/merged_control_surface_audit.md`, including the Electron shell, backend monitor, and AudioOnsetFinder companion; the Electron transport strip now also exposes always-visible `LIVE` and `CAM` launchers for the live-source and camera-control workflows.
- The project is now past the first AudioManager publish, read-side, and canonical backend-request slices; the main remaining cross-app integration work is coordinated dirty-state and revision-ready ownership so both shells switch revisions through one canonical service path.

## 2. Current Baseline

The current codebase already contains several useful seams that reduce integration risk.

- 3DAudioGraphs already uses an Electron main process as a bridge between the renderer and Python scripts. The current bridge launches Python runners over JSON stdin/stdout and already handles asset import and backend analysis requests.
- 3DAudioGraphs already distinguishes between exported data and frontend-facing audio assets. Today that split lives mostly in `data/exports/` and `frontend/public/audio_assets/`, with a manifest at `frontend/public/audio_assets_manifest.json`.
- 3DAudioGraphs frontend already owns transport interactions, audio asset loading, terrain/onset overlay behavior, and backend-call UI feedback.
- AudioOnsetFinder already separates much of its business logic from the PyQt GUI. The processing steps live in standalone Python scripts, while the onset editor has explicit state helpers and audio-viewer playback APIs.
- AudioOnsetFinder already has a dedicated onset editor state layer, onset-layer management, file-routing logic, and a playhead-capable waveform/spectrogram viewer that emits playback position changes.

These facts imply an important architectural decision: WildAudioWorlds should not force both experiences into a single UI yet. The lower-risk path is to keep two first-class shells, reuse Python analysis code from both projects, and consolidate the shared service and algorithm layers underneath them.

## 3. Recommended High-Level Architecture

### 3.1 Primary Design Choice

Adopt a dual-shell architecture. AudioOnsetFinder's PyQt GUI becomes the default or initial launch surface and the primary workflow hub for editing and configuration-heavy sessions. 3DAudioGraphs remains a fully contained specialized spatial-analysis shell that can run by itself or be launched into a linked session. Both shells sit on top of shared integration services and shared data ownership rules.

### 3.2 Runtime Topology

```text
PyQt AudioOnsetFinder Shell (default entry shell)
  - pipeline setup
  - onset editor
  - per-file configuration
          |
          | local IPC / session attach
          |
Electron 3DAudioGraphs Shell (standalone or companion shell)
  - 3D audio graph exploration
  - terrain/timbre interaction
  - spatial transport controls
          |
          | local IPC / session attach
          v
Local Integration Service
  - shell launcher / session attach
  - AudioManager
  - DataManager
  - backend command router
  - graph analysis service
  - onset analysis service
  - audio edit service
          |
          v
Workspace Data Roots
  - source audio
  - downloaded graph/model inputs
  - derived onset data
  - derived graph data
  - exports
  - session manifests
```

### 3.3 Component Responsibilities

#### UI Shell Strategy

- Keep both UI shells independently launchable.
- Use the AudioOnsetFinder PyQt shell as the default entry experience for setup, editing, and configuration-heavy work.
- Preserve 3DAudioGraphs as a fully contained spatial-analysis UI rather than forcing it into the PyQt menu system immediately.
- Allow one shell to launch or attach the other using a shared session ID when a linked workflow needs both views at once.
- Keep filesystem writes and heavy analysis work out of both shells and inside shared services.

#### Shared Integration Core

- Replace the current pattern of one-off Python runner scripts with shared service modules and one long-lived local integration service.
- Keep thin compatibility wrappers for existing scripts during migration so current behavior does not break while the service layer is introduced.
- Expose a single backend command surface for both graph and onset workflows.
- Support both standalone-shell mode and linked-session mode without duplicating business logic.

#### AudioManager

AudioManager should live in the shared local integration service, not in a shell-specific process, because both PyQt and Electron must be able to attach to the same session.

- Own the authoritative active session state: active audio asset ID, current asset revision, playhead time, selection window, playback lock state, and dirty flags.
- Accept transport updates from either shell and broadcast the canonical session update back to all attached views.
- Prevent feedback loops by tagging updates with source IDs and monotonic revision counters.
- Trigger backend jobs when edits require regenerated features, then atomically switch both views to the new asset revision when the job completes.
- Remain lightweight and event-driven. It should not perform signal processing itself.

#### DataManager

DataManager should live in the Python backend because it owns path resolution, artifact creation, versioning, and file isolation.

- Be the only component allowed to create, move, rename, or publish analysis artifacts.
- Assign canonical asset IDs and derived-data revision IDs.
- Track the relationship between one source audio file and all derived onset, workbook, label, MFCC, FFT, and terrain-envelope outputs.
- Separate immutable source inputs from mutable derived data.
- Publish explicit manifests so the renderer never guesses paths.
- Support cleanup rules for stale derived artifacts without touching source inputs.

#### Shell Orchestration

- Support two modes: standalone mode and linked-session mode.
- In standalone mode, each shell can run independently against its own local session.
- In linked-session mode, one shell launches or attaches the other using a shared session ID and a discovered service endpoint.
- If the companion shell is unavailable, the originating shell must stay fully usable instead of hard-failing.
- Keep shell orchestration thin. It should launch, attach, and hand off context, but not own business rules.

#### Job Control and Concurrency

- Treat DataManager as the single writer for derived artifacts and revision manifests.
- Allow parallel read-only analysis where safe, but serialize write-producing operations per asset or revision.
- Require cancel, supersede, and retry semantics for long-running jobs so a newer edit can invalidate stale work cleanly.
- Surface job state, progress, and failure details to both shells through the shared integration service.
- Never let either shell consume a partially written revision or partially published manifest.

### 3.4 Communication Model

The integration should standardize on command and event messages. The two shells should not synchronize directly with each other. Both should communicate only with the shared integration service, which fans out canonical session state.

Transport guidance:

- Standalone mode can bootstrap the service through stdio if that is the simplest launch path.
- Linked-session mode requires multi-client local IPC so both shells can attach to the same service instance.
- On macOS and Linux, prefer Unix domain sockets.
- On Windows, prefer named pipes.

Suggested command families:

- `session/open_asset`
- `session/attach`
- `session/detach`
- `transport/set_time`
- `transport/set_selection`
- `shell/open_companion`
- `graph/process_asset`
- `graph/load_asset_manifest`
- `onset/load_session`
- `onset/detect_region`
- `onset/save_labels`
- `onset/sync_workbook`
- `audio/edit_region`
- `audio/rebuild_graph_features`
- `data/get_asset_state`
- `data/list_revisions`

Suggested event families:

- `session/asset_changed`
- `session/peer_attached`
- `session/peer_detached`
- `transport/time_changed`
- `transport/selection_changed`
- `job/status_changed`
- `asset/revision_ready`
- `asset/revision_failed`
- `data/manifest_changed`

### 3.5 Playhead Synchronization Strategy

- In standalone mode, the active shell publishes user-initiated playhead changes to AudioManager and receives the canonical result back.
- In linked-session mode, both the 3D graph view and the onset editor workflow publish user-initiated playhead changes to AudioManager.
- AudioManager becomes the only authority allowed to announce the canonical playhead position.
- Both views subscribe to AudioManager updates and render that position immediately.
- During drag or scrubbing, transport updates should be throttled enough to avoid IPC flooding but fast enough to feel real-time.
- Backend analysis should not run on every playhead move. Transport sync and analysis jobs must be separate concerns.

### 3.6 Audio File and Feature Synchronization Strategy

- Any onset-side audio edit must create a new derived revision rather than mutating the current graph asset in place.
- DataManager records that revision and its artifact set.
- The backend rebuilds only the affected derived graph artifacts for that revision: MFCC coordinates, FFT bins, terrain envelope, onset metadata, and any workbook or label outputs that belong to the same edited revision.
- When the rebuild completes, AudioManager switches the active session to the new revision and broadcasts one canonical `asset/revision_ready` event.
- Both the graph view and the onset editor then reload from the same revision manifest.

This avoids race conditions and guarantees that both views are always looking at the same version of the same audio-derived state.

### 3.7 Algorithm Consolidation Strategy

WildAudioWorlds should preserve proven algorithms while still consolidating and streamlining their structure.

- Extract reusable logic from both repositories into shared domain modules instead of leaving it scattered across GUI handlers and script entry points.
- Organize those modules by responsibility, such as audio conditioning, onset detection, feature extraction, spatial projection, workbook and export synchronization, and session or revision models.
- Keep legacy scripts and UI actions as thin adapters over the shared modules during migration.
- Standardize input and output payloads so the same onset, graph, and audio-edit operations can be called from either shell.
- Consolidate duplicate config parsing, path handling, manifest generation, and file-routing helpers early.
- Defer true algorithm replacement or tuning changes until parity checks prove the reorganized structure behaves the same as the legacy paths.

### 3.8 Target Repository Layout

The merged repository should separate shell-specific code from shared logic from the start.

```text
apps/
  audio_onset_finder_shell/
  audio_graphs_shell/
services/
  local_integration/
packages/
  wild_audio_worlds/
    audio/
    onset/
    graph/
    data/
    session/
    config/
tests/
  fixtures/
  contract/
  integration/
  smoke/
docs/
```

Repository rules:

- Keep PyQt-specific code inside its shell area.
- Keep Electron-specific code inside its shell area.
- Put shared algorithms, manifests, config models, and revision logic only in the shared package.
- Keep bootstrap, IPC wiring, session attach, and process supervision in the integration-service area.
- Do not let new shared code continue accumulating inside legacy GUI or script folders once the shared package exists.

## 4. Strict Data Boundaries

The current 3DAudioGraphs layout places mutable runtime assets under `frontend/public/`. That is workable for a prototype, but it is the wrong long-term home for user-generated or session-generated data in a merged desktop app.

WildAudioWorlds should adopt explicit data roots such as:

```text
data/
  source/
    raw_audio/
    downloaded_model_inputs/
  derived/
    graph/
    onset/
  sessions/
  exports/
  manifests/
```

Boundary rules:

- `data/source/raw_audio/` contains imported or recorded source audio and is immutable after ingest.
- `data/source/downloaded_model_inputs/` contains externally downloaded files used to generate 3D models and is never mixed with edited onset data.
- `data/derived/onset/` contains editable onset outputs such as label files, workbook updates, onset layers, and transient analysis results.
- `data/derived/graph/` contains graph-ready artifacts such as MFCC coordinates, FFT bins, terrain envelopes, and graph manifests.
- `data/sessions/` contains session-scoped metadata describing which asset revision is currently active.
- `data/exports/` contains user-requested exports only.
- `frontend/public/` should be reserved for bundled demo assets and static app resources, not mutable working data.

### 4.1 Revision and Write Safety Rules

- Any edit that changes analysis-bearing data should create a new derived revision or a clearly versioned metadata update.
- Session manifests should include a schema version, active revision ID, and source-asset identifier.
- DataManager should publish a revision only after all required artifacts for that revision are complete and validated.
- Revisions should be promoted atomically so neither shell can open half-written outputs.
- Write locks or leases should prevent two shells from mutating the same asset revision concurrently.

## 5. Dependency Consolidation Strategy

### 5.1 Recommended Environment Authority

Use one root `environment.yml` as the authoritative Python environment definition for WildAudioWorlds.

Reasoning:

- AudioOnsetFinder already depends on Conda-friendly scientific and GUI packages such as PyQt6, pyqtgraph, and compiled audio libraries.
- 3DAudioGraphs adds Python analysis dependencies such as `umap-learn` and `scikit-learn` that fit naturally into the same Conda environment.
- A plain `requirements.txt` is possible later, but Conda is the lower-risk choice for the first unified environment because it reduces platform-specific wheel and compiled-library problems.

Keep Node and Electron dependencies in the frontend `package.json`, with Node 24 and npm 11 as the explicit frontend toolchain baseline.

### 5.2 Consolidation Rules

- Start from Python 3.11 because AudioOnsetFinder already pins to it and it is compatible with the current scientific stack.
- Keep shared analysis libraries once: `numpy`, `pandas`, `scipy`, `librosa`, `pysoundfile`, `openpyxl`.
- Add 3DAudioGraphs-specific analysis libraries: `umap-learn`, `scikit-learn`.
- Keep plotting and desktop-transition libraries during migration: `matplotlib`, `pyqt6`, `pyqtgraph`.
- Keep onset-processing and audio-cleaning libraries required for current behavior: `noisereduce` and related direct dependencies.
- Treat heavy or specialized packages as optional until they are proven necessary for the first integrated release: `openai-whisper`, `whisperx`, `torchcrepe`, `thebeat`, `praat-parselmouth`, `plotly`, `statsmodels`.
- Do not carry `websockets` into the first consolidated environment unless the new persistent backend protocol actually requires it. There is no current code reference to it in 3DAudioGraphs.

### 5.3 Recommended Dependency Outcome

Phase 1 should produce:

- One canonical root `environment.yml` for the integrated Python runtime.
- The existing frontend `package.json` retained as the Node/Electron source of truth.
- A short dependency audit note listing deferred optional packages and why they were excluded from the first integrated environment.

## 6. Step-by-Step Implementation Plan

This plan is ordered to minimize breakage and ends with the introduction of the new manager classes, not with an immediate rewrite.

### Delivery Gates Across All Steps

- Keep one shared fixture set that is used by both shells and by the shared backend services.
- Add contract tests for the shared command schema before the two shells depend on it heavily.
- Maintain smoke tests for three modes: standalone AudioOnsetFinder, standalone 3DAudioGraphs, and linked-session mode.
- Record parity baselines for key derived outputs, accepting only clearly documented and intentional differences.
- Treat playhead sync, revision switching, companion-shell launch, and manifest publication as explicit acceptance checks, not informal manual assumptions.

### Step 1. Create the WildAudioWorlds repository and freeze the current baseline [Completed]

- Create or initialize the new root repository and attach the remote `git@github.com:msstter/WildAudioWorlds.git`.
- Bring both codebases into the new repo without deleting or flattening them immediately.
- Prefer preserving history if practical. If not, keep the current folder layout intact for the first integration branch.
- Add a root `.gitignore` that excludes all mutable data roots and generated artifacts.
- Define a small set of representative audio fixtures for repeatable smoke tests.

Exit criteria: both legacy applications still exist in the repo and can be launched independently.

### Step 2. Consolidate the environment before touching application logic [Completed]

- Create one root `environment.yml` that can run the current 3DAudioGraphs backend and the current AudioOnsetFinder scripts.
- Keep frontend dependencies separate in the current Electron app.
- Install and validate the unified environment before modifying backend routing.

Exit criteria: the 3DAudioGraphs Python backend scripts run in the new environment, and AudioOnsetFinder's main processing scripts import cleanly.

### Step 3. Establish regression checks for both legacy paths [Completed]

- Verify the current 3DAudioGraphs import and analysis flow with at least one sample asset.
- Verify the current AudioOnsetFinder pipeline and onset-editor file loading with at least one sample asset.
- Save outputs that can act as comparison baselines during migration.

Exit criteria: you can prove later changes did not silently alter the core outputs.

### Step 4. Extract a unified Python backend package without changing behavior [In Progress]

- Create a new backend package namespace such as `wild_audio_worlds`.
- Move or wrap reusable logic from both repositories into shared domain modules and service modules under that package.
- Consolidate repeated config parsing, manifest handling, file-routing, and analysis helper code while preserving behavior.
- Start moving new shared code into the target repository layout instead of extending legacy folders further.
- Keep the existing script entry points as compatibility shims that call the new package functions.
- Do not redesign algorithms in this step. The goal is relocation and packaging, not behavioral change.

Current progress inside Step 4:

- Shared `data/`, `graph/`, and `session/` helpers already live under `packages/wild_audio_worlds/` and are in active use by the Electron/Python bridge.
- The backend-call and recorded-audio paths already consume shared contracts and metadata instead of duplicating request, result, error, and log vocabulary in multiple places.
- The remaining Step 4 work is to keep moving compatibility logic away from shell-local bridge code and toward the shared service/bootstrap boundary.

Exit criteria: old script entry points still work, but their logic now resolves through the new shared package.

### Step 5. Define the dual-shell launch model and shared command surface [Complete]

- Define the contract for standalone-shell mode versus linked-session mode.
- Add a minimal shell-launch and session-attach contract so either UI can open the other with active asset and session context.
- Introduce a unified backend command schema that covers graph actions, onset actions, audio-edit actions, data queries, and shell-attach operations.
- Initially support the new command schema through compatibility wrappers if needed.

Completed Step 5 prep:

- A first attach/session contract draft now exists in `docs/session_attach_contract.md`.
- The first manifest fields for asset ID, revision ID, originating shell, launch context, playhead, selection window, peer snapshots, and service endpoint discovery are now drafted.
- A thin stdio bootstrap now exists in `services/local_integration/bootstrap_service.py` and publishes session manifests while hosting the current backend-call and recorded-audio compatibility commands.
- The current Electron bridge already routes those compatibility commands through the bootstrap.
- The bootstrap now also accepts explicit `shell/open_companion` and `session/attach` requests and has focused contract coverage for manifest revision updates across bootstrap, open-companion, and attach flows.
- The first real shell edge now uses those commands: Electron can request companion launch through the bootstrap, spawn AudioOnsetFinder with shared session attach args, and AudioOnsetFinder startup attaches back into the linked session before Qt finishes booting.

Step 5 closure additions:

- The reverse shell edge now also exists from AudioOnsetFinder into Electron: the PyQt shell can request `shell/open_companion`, launch the Electron companion with shared attach args, and Electron startup calls `session/attach` before the BrowserWindow shows.
- The bootstrap now also supports explicit `session/detach`, and the shared manifest helper can remove peers and downgrade linked sessions back to standalone without losing the session identity or host-shell context.
- Focused acceptance coverage now exercises shell-edge launch failure, companion attach failure, `session/detach`, and linked-session reuse or re-attach behavior while both shells remain independently launchable.

Exit criteria: either shell can start alone, and one shell can launch the other into the same session without bypassing shared services.

### Step 6. Replace one-off Python runners with a persistent local integration service [Complete]

- Introduce one long-lived Python service process instead of spawning a new Python process for every analysis request.
- Allow stdio bootstrapping for simple single-shell startup paths, but use multi-client local IPC for linked sessions where both shells must attach to the same service instance.
- Add structured job IDs, progress reporting, and failure payloads.
- Add cancellation, supersession, and duplicate-job suppression for revision-producing work.

Completed Step 6 additions:

- `service/bootstrap` now promotes linked sessions onto a reusable per-session daemon in `services/local_integration/service_runtime.py`, advertises the Unix-domain-socket endpoint through the session manifest, and preserves stdio bootstrap compatibility for initial launch paths.
- Both shells now prefer the advertised persistent endpoint for non-bootstrap local-integration commands, so attach, open-companion, backend-call, and recorded-audio requests can reuse one live service instance during a shared session.
- Compatibility runner work now executes as structured service jobs with stable job IDs, active-job summaries in `service/ping`, direct `job/status` lookup, `job/cancel`, failure payload propagation, and supersession wiring through `supersedesJobId`.
- Focused validation now passes for the persistent-service contract bundle (`tests/contract/test_local_integration_service_runtime.py`, `tests/contract/test_local_integration_bootstrap.py`, `tests/contract/test_audio_onset_shell_session.py`) plus the Electron main-process syntax check on `3DAudioGraphs-main/frontend/main.cjs`.

Exit criteria: both shells can issue backend commands during one app session without repeatedly booting Python, and a linked session can support both shells at once.

### Step 7. Introduce DataManager as the only filesystem authority [Complete]

- Implement DataManager in the Python service.
- Move all path resolution, manifest generation, revision tracking, and artifact publication into DataManager.
- Redirect current direct writes to `frontend/public/audio_assets/` into the new managed data roots, keeping temporary compatibility links only if needed.
- Enforce the separation between source files, downloaded model inputs, derived onset outputs, derived graph outputs, and exports.
- Add revision locks or leases plus atomic publish rules before connected-shell workflows are enabled broadly.

Current slice status:

- A first shared DataManager now owns graph-asset manifest writes plus graph-asset publication from `3DAudioGraphs-main/backend/main.py`.
- The first extraction preserves the current renderer-facing `audio_assets_manifest.json` contract while publishing new asset revisions into immutable per-revision directories.
- DataManager now also owns backend-call JSON/WAV export publication plus the current bioacoustics workbook writer delegation and fallback XLSX export path generation from `run_selection_analysis.py` and `bioacoustics_workbook.py`.
- DataManager now also owns recorded-audio source-input publication for `recorded-audio/import`, and the shared onset writer layers now route labels, transcripts, TextGrids, workbook writes, selection exports, and onset-editor persistence artifacts through DataManager-compatible helpers with standalone fallback.
- DataManager-compatible bridge helpers now also own the remaining standalone AudioOnsetFinder batch, workbook, report, plot, analyzer, selector, and noise-profile artifact publications while preserving standalone fallback behavior when the shared package tree is absent.
- Focused validation now passes for `tests/contract/test_data_manager.py` and for the headless-safe AudioOnsetFinder writer and Excel bundle (`tests/test_shared_output_writers.py`, `tests/test_onset_exports.py`, `tests/test_excel_onset_io.py`, `tests/test_pipeline_file_selection.py`).

Exit criteria: current analysis modules publish derived artifacts through DataManager-owned roots or DataManager-compatible bridge helpers, with only preset/config persistence and explicit standalone fallback internals remaining local.

### Step 8. Introduce AudioManager as the authoritative session-sync layer [In Progress]

- Implement AudioManager in the shared local integration service.
- Move ownership of active asset selection, playhead position, selection window, revision switching, and dirty-state broadcasting into AudioManager.
- Wire both shells to publish and consume AudioManager events.
- Add version-aware sync so an onset-side edit that produces a new derived revision triggers one coordinated frontend refresh.

Completed Step 8 additions:

- A first service-owned AudioManager now exists in `services/local_integration/audio_manager.py` and is loaded by the persistent daemon in `services/local_integration/service_runtime.py`.
- The persistent service now owns canonical `asset`, `transportState`, and revision mutations through `session/get_state`, `session/open_asset`, `session/clear_asset`, `asset/set_revision`, `transport/set_time`, and `transport/set_selection`, while persisting those updates back into the shared session manifest.
- Bootstrap-written session manifests now sync their initial state into the live persistent service, and manifest-backed commands like `session/attach`, `session/detach`, and `shell/open_companion` now update the daemon's AudioManager state rather than leaving the in-memory service snapshot behind.
- Both shells now publish real asset and transport mutations into that command surface: Electron publishes backend-monitor asset open or clear plus transport snapshots from the existing renderer bridge, and AudioOnsetFinder publishes onset-editor asset, playhead, and selection changes through the shared session helper.
- The persistent service now also publishes canonical AudioManager event traffic through `events/poll`, and both shells now consume that read side: AudioOnsetFinder polls and applies canonical asset, playhead, and selection updates through its shared session helper and event pump, and Electron hydrates from `local-integration:get-state`, polls canonical events, and applies remote state without republishing loops.
- Backend analysis request building now uses canonical `session/get_state` snapshots rather than monitor-shaped renderer caches, preserving richer canonical asset metadata and treating Bioacoustics overrides as explicit request options rather than replacement request state.
- The backend monitor's readiness gating now queries Electron main for canonical readiness instead of treating the pushed monitor snapshot as the source of truth, and the main Electron transport strip now exposes always-visible `LIVE` and `CAM` launchers for the live-source and camera-control workflows.
- Focused validation now passes for the service-runtime and shell-session contract slices, the canonical onset-editor apply slice, Electron syntax checks across `main.cjs`, `preload.cjs`, `src/main.js`, and `public/backend-call-monitor.js`, and the current frontend production build.

Exit criteria: both shells consume canonical asset and transport state in real time from the service-owned read path, and onset-side or backend-side edits switch both views to the same new asset revision through one coordinated revision-ready path.

## 7. Architectural Rules That Will Keep This Merge Safe

- Do not try to merge the Electron UI and the PyQt UI at the widget level.
- Do not force the two shells into one shared menu system before the service boundaries and launch contract are stable.
- Do not let the renderer own mutable file paths directly.
- Do not let either shell become the long-term owner of shared session state.
- Do not let onset modules overwrite graph assets in place.
- Do not let graph modules discover onset files by scanning arbitrary directories.
- Do not remove legacy entry points until the unified command path is proven.
- Do not design AudioManager or DataManager until the service boundaries and regression fixtures exist.

## 8. Recommended Next Execution Order

The original first execution order has already been completed through the baseline, regression, persistent-service, DataManager, AudioManager publish/read slices, canonical backend-request slice, and first cross-app control-surface pass. The next execution order should now be:

1. Add service-owned dirty-state, revision-ready, and revision-failed coordination so onset-side and backend-side edits move both shells through one canonical revision lifecycle.
2. Route onset-editor save or edit completion and backend job completion onto that coordinated revision path instead of shell-local completion handling.
3. Expand contract and integration coverage around canonical event delivery, live-source transitions, revision switching, companion attach or detach reuse, and superseded jobs.
4. Decide which backend-monitor and companion-only actions should be promoted into clearer main-shell shortcuts after the merged control-surface audit.
5. Retire the remaining temporary monitor-shaped and shell-local caches once the service-owned dirty-state and revision path can replace them safely.

This updated sequence keeps momentum on the merge while still protecting the current working bridge and preserving both shells as independently usable entry points.