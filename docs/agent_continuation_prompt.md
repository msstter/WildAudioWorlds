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

- A thin local integration bootstrap in `services/local_integration/bootstrap_service.py`
- Shared session manifest helpers and shared session metadata under `packages/wild_audio_worlds/session/`
- Explicit `service/bootstrap`, `backend-call/run`, `recorded-audio/import`, `session/attach`, and `shell/open_companion` bootstrap coverage
- Focused linked-session contract tests for bootstrap/open-companion/attach revision updates
- The first real shell edge from Electron into AudioOnsetFinder:
  - Electron requests `shell/open_companion`
  - Electron launches `AudioOnsetFinder-main/GUI/pipeline_gui.py` with shared WildAudioWorlds session args
  - AudioOnsetFinder startup consumes those args and calls `session/attach` before the GUI shows

## Highest-Priority Next Work

Unless the docs have changed by the time you read them, the next logical implementation order is:

1. Extend the reverse shell edge so AudioOnsetFinder can launch or reopen the Electron companion into the same shared session.
2. Extend the bootstrap into explicit `session/detach` flow.
3. Add the next linked-session acceptance checks around shell-edge launch failures, companion attach failures, and session reuse.
4. Start the first DataManager extraction around manifest ownership, mutable asset publication, revision-safe writes, and path authority.

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