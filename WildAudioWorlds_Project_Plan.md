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
- A thin stdio local integration bootstrap now exists in `services/local_integration/bootstrap_service.py`, publishes the first session manifests under `data/sessions/`, and already hosts the current backend-call and recorded-audio compatibility commands.
- The Electron bridge now routes its backend-call and recorded-audio command execution through that bootstrap instead of directly orchestrating runner scripts in shell-local bridge code.
- The project is effectively late Step 4 / mid-Step 5: shared packaging, compatibility extraction, the first attach/session contract draft, and the first bootstrap path now exist, but linked-session attach flows, DataManager, and AudioManager are still not implemented.
- The most important next move is to add linked-session checks and extend the bootstrap from compatibility command hosting into explicit attach/open-companion flows.

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

### Step 5. Define the dual-shell launch model and shared command surface [In Progress]

- Define the contract for standalone-shell mode versus linked-session mode.
- Add a minimal shell-launch and session-attach contract so either UI can open the other with active asset and session context.
- Introduce a unified backend command schema that covers graph actions, onset actions, audio-edit actions, data queries, and shell-attach operations.
- Initially support the new command schema through compatibility wrappers if needed.

Completed Step 5 prep:

- A first attach/session contract draft now exists in `docs/session_attach_contract.md`.
- The first manifest fields for asset ID, revision ID, originating shell, launch context, playhead, selection window, peer snapshots, and service endpoint discovery are now drafted.
- A thin stdio bootstrap now exists in `services/local_integration/bootstrap_service.py` and publishes session manifests while hosting the current backend-call and recorded-audio compatibility commands.
- The current Electron bridge already routes those compatibility commands through the bootstrap.

Remaining Step 5 targets:

- Add the first linked-session smoke or contract checks around manifest publication and session bootstrap.
- Extend the bootstrap into explicit `session/attach` and `shell/open_companion` flows.
- Keep the first implementation thin and compatibility-oriented so both shells remain independently launchable while the shared service path is introduced.

Exit criteria: either shell can start alone, and one shell can launch the other into the same session without bypassing shared services.

### Step 6. Replace one-off Python runners with a persistent local integration service [Not Started]

- Introduce one long-lived Python service process instead of spawning a new Python process for every analysis request.
- Allow stdio bootstrapping for simple single-shell startup paths, but use multi-client local IPC for linked sessions where both shells must attach to the same service instance.
- Add structured job IDs, progress reporting, and failure payloads.
- Add cancellation, supersession, and duplicate-job suppression for revision-producing work.

Exit criteria: both shells can issue backend commands during one app session without repeatedly booting Python, and a linked session can support both shells at once.

### Step 7. Introduce DataManager as the only filesystem authority [Not Started]

- Implement DataManager in the Python service.
- Move all path resolution, manifest generation, revision tracking, and artifact publication into DataManager.
- Redirect current direct writes to `frontend/public/audio_assets/` into the new managed data roots, keeping temporary compatibility links only if needed.
- Enforce the separation between source files, downloaded model inputs, derived onset outputs, derived graph outputs, and exports.
- Add revision locks or leases plus atomic publish rules before connected-shell workflows are enabled broadly.

Exit criteria: no analysis module writes paths directly outside DataManager-owned roots.

### Step 8. Introduce AudioManager as the authoritative session-sync layer [Not Started]

- Implement AudioManager in the shared local integration service.
- Move ownership of active asset selection, playhead position, selection window, revision switching, and dirty-state broadcasting into AudioManager.
- Wire both shells to publish and consume AudioManager events.
- Add version-aware sync so an onset-side edit that produces a new derived revision triggers one coordinated frontend refresh.

Exit criteria: moving the playhead in either view updates the other in real time, and completed onset-side edits switch both views to the same new asset revision.

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

The original first execution order has already been completed through the baseline, regression, and first shared-package extraction work. The next execution order should now be:

1. Add the first linked-session smoke or contract checks around session bootstrap, manifest publication, and session revision updates.
2. Extend the bootstrap into explicit `session/attach` and `shell/open_companion` flows while keeping standalone mode stable.
3. Start the first DataManager extraction around manifest ownership, mutable asset publication, revision-safe writes, and path authority.
4. Only after those pieces are stable, begin AudioManager session authority for playhead, selection, and revision synchronization.

This updated sequence keeps momentum on the merge while still protecting the current working bridge and preserving both shells as independently usable entry points.