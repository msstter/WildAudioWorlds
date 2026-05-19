# Merged Control Surface Audit And Checklist

Date: 2026-05-19

## Scope

This document now serves two purposes at once:

- a merged control-surface audit for the Electron owner shell, the backend monitor window, and the AudioOnsetFinder Qt companion
- an implementation checklist for promoting important merged actions into more discoverable always-visible controls

## Quick Read

- The Electron shell now exposes five always-visible launchers on the transport strip: playback, recording, live source, camera controls, companion launch, and backend analysis.
- Backend analysis coverage is still centralized in the backend monitor, but the monitor remains a secondary window rather than a main-shell inline surface.
- The AudioOnsetFinder companion does not expose a traditional top-level menu bar; it is driven by a top button row, a step sidebar, the onset editor toolbar, popup menus, and dialogs.
- The main remaining UX gap is not missing access, but depth and discoverability inside modal or secondary-window surfaces.

## Implementation Checklist

| Item | Status | Notes |
| --- | --- | --- |
| Keep backend analysis reachable from the main shell | Done | `Call Backend` button already opens the shared backend monitor. |
| Keep companion launch reachable from the main shell | Done | `AOF` button already opens AudioOnsetFinder. |
| Add an always-visible live-source launcher | Done | Added `LIVE` transport button to open or stop the live-source workflow. |
| Add an always-visible camera-controls launcher | Done | Added `CAM` transport button that opens the recording modal at the camera section. |
| Audit the Qt companion window into this same document | Done | Added second-pass Qt surface map below. |
| Decide whether backend monitor actions need direct main-shell shortcuts | Pending | Backend and Bioacoustics actions are still monitor-first. |
| Decide whether live-source start modes deserve one-click transport buttons | Pending | `Stream`, `Record Live`, and `Record New Asset` still live inside the modal. |
| Decide whether camera keyframe actions need direct inline buttons beyond `CAM` | Pending | The launcher is now always visible, but actual keyframe editing remains modal. |
| Decide whether companion-specific onset-editor shortcuts should surface in Electron | Pending | Current design relies on opening the Qt companion for those detailed actions. |

## Electron Shell Surface Map

### Always-visible shell buttons

| Action | Concrete control | Surface | Notes |
| --- | --- | --- | --- |
| Play or pause playback | `Play` button (`#play-btn`) | Bottom transport strip | Also reachable through hotkeys and FPV play/pause bindings. |
| Restart from the beginning | `Restart` button (`#restart-btn`) | Bottom transport strip | Starts playback if the transport was paused. |
| Change playback speed | `Speed` button (`#speed-btn`) plus preset buttons (`0.25x` to `2x`) | Bottom transport strip | Custom speed and preserve-pitch live in the speed popover. |
| Apply custom speed | `Apply` button (`#apply-custom-speed-btn`) | Speed popover | Uses `#custom-speed-input`. |
| Toggle preserve pitch | `Preserve Pitch` checkbox (`#preserve-pitch-checkbox`) | Speed popover | Renderer-owned transport option. |
| Seek within the asset | Progress bar (`#progress-bar`) | Bottom transport strip | Also updated from canonical transport state. |
| Open the recording workflow | `Record Window` button (`#record-btn`) | Bottom transport strip | Opens the recording and camera modal. |
| Open or stop live-source workflow | `LIVE` button (`#live-source-btn`) | Bottom transport strip | New always-visible launcher for the live-source modal and active live-session stop path. |
| Open camera keyframe and motion controls | `CAM` button (`#camera-controls-btn`) | Bottom transport strip | New always-visible launcher for the recording modal's camera section. |
| Open the AudioOnsetFinder companion | `AOF` button (`#open-companion-btn`) | Bottom transport strip | Electron-only launch surface for the PyQt companion. |
| Open backend analysis tools | `Call Backend` button (`#backend-call-btn`) | Bottom transport strip | Opens the backend call monitor window. |

### Recording modal controls

| Action | Concrete control | Surface | Notes |
| --- | --- | --- | --- |
| Choose capture resolution | `Resolution` select (`#rec-resolution`) | Recording modal | 720p, 1080p, 1440p, 4K. |
| Choose video container | `File Type` select (`#rec-format`) | Recording modal | Video choices are MP4, WebM, MKV, MOV, M4V, M4P. |
| Switch to image-sequence mode | `Record as Animated Image` checkbox (`#rec-gif-toggle`) | Recording modal | Replaces the format options with GIF, WebP, APNG, AVIF. |
| Include or exclude audio | `Include Audio` checkbox (`#rec-audio-toggle`) | Recording modal | Hidden while animated-image mode is active. |
| Start capture | `Start Recording` button (`#rec-start-btn`) | Recording modal | Uses the current recording and camera settings. |
| Close without starting | `Cancel` button (`#rec-cancel-btn`) | Recording modal | Modal close action only. |

### Recording modal camera controls

| Action family | Concrete control | Surface | Notes |
| --- | --- | --- | --- |
| Exit FPV and recenter orbit | `Exit FPV and Recenter Orbit` button | Recording modal camera section | Recenters OrbitControls on the active or base keyframe target. |
| Enable or disable camera keyframe hotkeys | `Enable Keyframe Hotkeys` checkbox | Recording modal camera section | Gates the keyframe hotkey capture rows. |
| Capture a new camera keyframe | `Add Current View` button | Recording modal camera section | Adds the current camera pose as a new keyframe. |
| Update the current keyframe from the current view | `Update Active From Current` button | Recording modal camera section | Disabled until a keyframe is active. |
| Reset the camera view | `Reset View` button | Recording modal camera section | Uses the base keyframe target. |
| Restore the default keyframe set | `Reset Keyframes` button | Recording modal camera section | Rebuilds the default XY/XZ/YZ starting set. |
| Rebind camera-keyframe hotkeys | `Record` buttons next to `Set Keyframe`, `Next Keyframe`, `Previous Keyframe` | Recording modal camera section | Stores the bindings alongside the main hotkey state. |
| Edit keyframe list entries | Keyframe table rows | Recording modal camera section | The table exposes per-keyframe values plus row actions. |

### Live-source modal controls

| Action | Concrete control | Surface | Notes |
| --- | --- | --- | --- |
| Refresh microphone inputs | `Refresh Inputs` button (`#live-source-refresh-btn`) | Live Performance Source modal | Re-enumerates audio inputs. |
| Choose microphone | `Microphone` select (`#live-source-input`) | Live Performance Source modal | Input device selection. |
| Choose FFT size | `FFT Size` select (`#live-source-fft-size`) | Live Performance Source modal | Sets SpectroTerrain bin depth for live sessions. |
| Monitor live output | `Monitor live audio output` checkbox (`#live-source-monitor-toggle`) | Live Performance Source modal | Optional monitor path. |
| Start a live stream session | `Stream` button (`#live-source-stream-btn`) | Live Performance Source modal | Puts the app into live SpectroTerrain streaming mode. |
| Start a live recording session | `Record Live` button (`#live-source-record-btn`) | Live Performance Source modal | Uses microphone capture plus MediaRecorder. |
| Record and import a new asset | `Record New Asset` / `Stop & Import` button (`#live-source-capture-btn`) | Live Performance Source modal | Captures PCM, writes a new asset, and can auto-generate MFCC/Timbre data. |
| Set recorded asset label | `Asset Label` input (`#live-source-asset-label`) | Live Performance Source modal | Used for new imported assets. |
| Include MFCC/Timbre generation | `Also generate MFCC / TimbreCube data` checkbox (`#live-source-include-mfcc-toggle`) | Live Performance Source modal | New merged import path option. |
| Cancel or abort the modal/session | `Cancel` / `Cancel Recording` button (`#live-source-cancel-btn`) | Live Performance Source modal | Label changes while recording a new asset. |

### Sidebar: Mode_Audio/Data folder

| Action family | Concrete control | Notes |
| --- | --- | --- |
| Switch pipeline | `Pipeline` dropdown | Toggles between TimbreCube and SpectroTerrain. |
| Accumulate views | `Accumulate View` toggle | Renderer-side visualization behavior. |
| Mask playback to the current selection | `Mask To Selection` toggle | Shared with selection playback mask behavior. |
| Reset the graph for the current asset | `Reset Graph` button | Mode-level reset action. |
| Select asset source | `Asset Source` read-only field | Status display only. |
| Choose a custom asset folder | `Choose Asset Folder` button | File-system backed asset source control. |
| Switch back to bundled assets | `Use Bundled Assets` button | Reverts asset source to bundled manifest. |
| Inspect live-source status | `Live Status` read-only field | Status display only. |
| Open or stop live-source workflow | `Live Source` button | Opens the live-source modal or stops an active session. |

### Sidebar: Timbre selection actions

These are concrete menu entries under `Mode_Audio/Data > Selection Actions`.

| Action | Concrete control |
| --- | --- |
| Play the current Timbre selection | `Play Selection` |
| Jump transport to the first selected window | `Jump To First Window` |
| Clear the current Timbre selection | `Clear Selection` |
| Invert the current Timbre selection | `Invert Selection` |
| Export selection metadata as JSON | `Export Selection JSON` |
| Export selection metadata as CSV | `Export Selection CSV` |
| Export selected audio as an audio clip | `Export Selection Audio` |
| Export onset plus IOI CSV | `Export Onsets + IOI CSV` |
| Export onset plus IOI workbook-style output | `Export Onsets + IOI 2` |

### Sidebar: Timbre plane selection controls

These are concrete menu entries under `Mode_Audio/Data > Plane Selections` and are visible in TimbreCube mode.

| Action family | Concrete control |
| --- | --- |
| Toggle scene handles | `Show Scene Handles` |
| Toggle 3D box display | `Show 3D Box` |
| Change drag interaction target | `Grab Type` |
| Per-plane activation | `Enabled` |
| Per-plane selection method | `Selection Mode` |
| Per-plane tint and strength | `Tint Color`, `Tint Strength` |
| Start or redraw a lasso | `Start Lasso` / `Redraw Lasso` |
| Complete an in-progress lasso | `Complete Lasso` |
| Clear a plane lasso | `Clear Lasso` |
| Restore default plane bounds | `Reset Bounds` |

### Sidebar: SpectroTerrain and full-mask authoring controls

| Action family | Concrete control | Notes |
| --- | --- | --- |
| Enable full-mask sculpting | `Selection Sculpt (Full Mask) > Selection Model > Enabled` | Terrain-mode only. |
| Choose sculpt workflow | `Workflow` | Includes the full-mask workflow modes. |
| Choose authoring view | `Authoring View` | Terrain-mode only. |
| Reset the full sculpt box | `Reset Full Selection` | Restores the full selection mask. |
| Clear the sculpt selection | `Clear Selection` | Clears plane selections. |
| Inspect live sculpt status | `Live Status` subfolder | Read-only status fields for mask, window, spaces, and ranges. |
| Toggle sculpt overlays | `Show Sculpt Handles`, `Show Sculpt Space Box`, `3D Drag Target` | Terrain-mode only. |
| Tune excluded-region appearance | `Excluded Region Appearance` subfolder | Style, surface fade, wire color, wire opacity, wire step. |
| Author per-plane bounds | `Selection Spaces` subfolder | Per-plane enablement, tint, strength, min/max bounds, reset. |
| Edit terrain onset overlays | `Analysis > Terrain Onsets > Show Onsets in Model` and `Onset Editor` | Enables in-model onset display and editing. |

### Sidebar: Terrain rendering and graph controls

| Action family | Concrete control | Notes |
| --- | --- | --- |
| Adjust FFT terrain resolution | `Terrain (FFT Spectrogram)` root folder controls | Frequency bins, time depth, amplitude scale, smoothing, opacity, wireframe. |
| Select helper source | `Precomputed Helpers > Helper Preference` | Chooses which helper data the terrain uses. |
| Configure axis tinting | `Axis Colors` folder | Per-axis enabled state, blend weight, interval counts, interval colors, and timeline windows. |
| Configure timeline windows | `Axis Colors > Timeline Windows` | Includes window count plus per-window start/end, tint color, strength. |
| Configure 2D graph overlays | `2D Graphs` folder | Per-graph enablement, type, surface, opacity, heat, offset, extension, background. |
| Configure terrain graph labeling | `Graph` folder inside Terrain | Axes line/text toggles, axis colors, axis labels. |
| Configure terrain manual scaling | `Graph > Axis Scaling` | Manual scaling toggle plus min/max bounds. |
| Configure terrain auto padding | `Graph > Axis Scaling > Auto Padding` | Frequency and amplitude auto-padding percentages. |
| Configure terrain axis stretch | `Graph > Axis Stretch` | Frequency, amplitude, and time stretch factors. |

### Sidebar: global visualization and editing controls

| Action family | Concrete control | Notes |
| --- | --- | --- |
| Graph appearance | `Graph` folder | Axes visibility, axes color, editable axis text. |
| Render-order editing | `Scene > Render Order` | Opens the render-order modal. |
| Scene background and fog | `Scene` folder | Background color, fog color, fog density. |
| Lighting | `Lighting` folder | Lighting enablement, shading mode, ambient/directional controls. |
| Performance | `Performance` folder | FPS cap, render scale, label visibility, FPS meter. |
| Hotkey editor | `Hotkeys > Edit Hotkeys / Controls` | Opens the hotkey and pointer-control modal. |
| Onset-analysis settings | `Analysis` folder | Onset method, sensitivity, threshold scale, flash scope, transport markers. |
| Node-onset display | `Analysis > Node: Onsets` | Flash, flash color, duration, brightness, selection menu toggles. |
| Terrain-onset display | `Analysis > Terrain Onsets` | In-model onset visibility plus onset editor toggle. |
| Line styling | `Lines` folder | Line visibility, deconstructive mode, color, thickness, brightness, hue, decay, dulling, breathing. |
| Node styling | `Nodes` folder | Node visibility, deconstructive mode, scale, brightness, hue, decay, dulling, breathing. |
| Restore the full default settings state | `Reset To Defaults` | Global reset action at the root GUI level. |
| Open app about content | `About This App` | Root GUI action. |

### Modals launched from the sidebar

| Action family | Concrete control | Notes |
| --- | --- | --- |
| Edit render order values | `Scene > Render Order` -> modal fields and `Apply` / `Reset` / `Close` buttons | Modal-only surface. |
| Edit keyboard hotkeys | `Hotkeys > Edit Hotkeys / Controls` -> `Record` buttons per action | Includes transport, fullscreen, seek, record, speed menu, and camera keyframe hotkeys. |
| Edit pointer bindings | Same hotkey modal | Includes mouse buttons, scroll gestures, and folder-click shortcuts. |

### Backend call monitor controls

| Action | Concrete control | Notes |
| --- | --- | --- |
| Choose backend action | `Backend Action` dropdown (`#analysis-type`) | Fully populated from the shared analysis action catalog. |
| Choose save mode | `Save Output` dropdown (`#save-mode`) | JSON, WAV, XLSX, or no-save depending on the action. |
| Set an output label | `Save Label` input (`#save-label`) | Optional output label. |
| Run the selected backend action | `Run Backend Call` button (`#run-call-btn`) | Gated by canonical readiness from Electron main. |
| Clear log output | `Clear Logs` button (`#clear-logs-btn`) | Monitor-local log clear action. |
| Browse for a workbook or folder | `Browse` button (`#bio-workbook-browse-btn`) | Visible for Bioacoustics actions. |
| Set workbook output mode | `Workbook Output` dropdown (`#bio-output-mode`) | Visible for workbook sync. |

### Backend actions already mapped to concrete monitor controls

These actions are all surfaced through `Call Backend` -> `Backend Action` dropdown.

| Backend action | Concrete control path |
| --- | --- |
| Slice Summary | Backend monitor -> `Backend Action` -> `Slice Summary` |
| MFCC Profile | Backend monitor -> `Backend Action` -> `MFCC Profile` |
| Spectral Shape | Backend monitor -> `Backend Action` -> `Spectral Shape` |
| Export Time Slice Audio | Backend monitor -> `Backend Action` -> `Export Time Slice Audio` |
| Export Sculpted Spectral Mask Audio | Backend monitor -> `Backend Action` -> `Export Sculpted Spectral Mask Audio` |
| Bioacoustics: Import Workbook Onsets | Backend monitor -> `Backend Action` -> `Bioacoustics: Import Workbook Onsets` |
| Bioacoustics: Sync Workbook | Backend monitor -> `Backend Action` -> `Bioacoustics: Sync Workbook` |

## AudioOnsetFinder Qt Companion Surface Map

### Main window menus and top bar

| Surface | Concrete control | Owner | Notes |
| --- | --- | --- | --- |
| Traditional menu bar | None detected | `GUI/main_window_shell.py` | The companion appears to use buttons and sidebars rather than a `QMenuBar`. |
| Preview toggle | `Open Preview` button | `GUI/main_window_shell.py` | Toggles the preview panel. |
| Companion handoff back to Electron | `3D Graphs` button | `GUI/main_window_shell.py` | Opens the 3D Audio Graphs companion shell. |
| Preset management | `Presets` button | `GUI/main_window_shell.py` | Opens the presets dialog. |
| Description or walkthrough level | Description combo box | `GUI/main_window_shell.py` | Options include Off, Brief, Detailed, Novice, Terms, and Walkthrough. |
| Pipeline execution | `Run ▶` button | `GUI/main_window_shell.py` | Runs the pipeline. |

### Step sidebar navigation

| Surface | Concrete control | Owner | Notes |
| --- | --- | --- | --- |
| Main pipeline steps | Checkbox plus step button rows | `GUI/step_sidebar.py` | Each row combines a run-toggle checkbox with a button that selects the central panel. |
| Step families | Onset Editor, Prep, Muter, Extractor, Beat/Tempo, Plot, Histogram, nPVI Group, Analysis, Assoc Rules | `GUI/step_sidebar.py` | These are the visible pipeline destinations in the sidebar. |
| Experimental section | Collapsible `Experimental` header | `GUI/step_sidebar.py` | Expands or hides optional advanced analyses. |

### Onset editor file and source controls

| Action family | Concrete control | Owner | Notes |
| --- | --- | --- | --- |
| Choose audio input | `Browse...` audio button | `GUI/onset_editor.py` | Opens a file picker for the audio file. |
| Choose onset or workbook source | `Browse...` onset button | `GUI/onset_editor.py` | Opens a file picker for onset CSV or Excel input. |
| Undo or redo edits | `Undo`, `Redo` buttons | `GUI/onset_editor.py` | Local onset-edit history controls. |
| Manage onset and workbook sources | `Manage Onset / Excel Files` button | `GUI/onset_editor.py` | Opens the onset manager dialog. |
| Choose onset column | `Choose Column...` button | `GUI/onset_editor.py` | Opens the Excel column selection flow. |
| Move across loaded files | `Prev`, `Next` buttons | `GUI/onset_editor.py` | File navigation controls. |
| Per-file settings | `Settings` button | `GUI/onset_editor.py` | Opens onset-editor settings or per-file configuration. |

### Onset editor review controls

| Action family | Concrete control | Owner | Notes |
| --- | --- | --- | --- |
| Review navigation | `Previous`, `Next` buttons | `GUI/onset_editor.py` | Used in review mode. |
| Revert current review item | `Revert` button | `GUI/onset_editor.py` | Discards current edits. |
| Save both representations | `Save Both` button | `GUI/onset_editor.py` | Saves label and Excel state together. |
| Save and advance | `Save & Next` button | `GUI/onset_editor.py` | Persists and advances to the next item. |
| Exit review mode | `Finish Review` button | `GUI/onset_editor.py` | Closes review mode. |

### Onset editor detection and editing actions

| Action family | Concrete control | Owner | Notes |
| --- | --- | --- | --- |
| Manual onset creation | `+ Add Onset` | `GUI/onset_editor.py` | Adds an onset at the playhead or waveform selection. |
| Delete selected onset | `- Remove Selected` | `GUI/onset_editor.py` | Removes selected onset rows. |
| Run region detection | `Quick Onset Finder` | `GUI/onset_editor.py` | Opens the onset detection dialog. |
| Run all-layer detection | `Auto-Detect All Layers` | `GUI/onset_editor.py` | Batch onset detection across layers. |
| Analyze focus signals | `Analyze Signals` | `GUI/onset_editor.py` | Opens the signal-analysis dialog. |
| Per-signal onset detection | `Per-Signal Detect` | `GUI/onset_editor.py` | Opens the per-signal configuration dialog. |
| Negative subtraction flow | `Neg. Subtract` | `GUI/onset_editor.py` | Opens negative subtraction configuration. |
| Merge per-signal layers | `Merge Layers` | `GUI/onset_editor.py` | Produces a merged onset layer. |
| Quick audio editing | `Quick Audio Editor` | `GUI/onset_editor.py` | Opens the audio edit dialog. |
| MFCC-driven audio cleanup | `Audio Edits-MFCC` | `GUI/onset_editor.py` | Opens the MFCC audio edit flow. |
| Playback of selected region | `Play Selection` | `GUI/onset_editor.py` | Plays the current selection. |
| Loop selected region | `Loop Selection` | `GUI/onset_editor.py` | Toggle button for loop playback. |
| Toggle drag editing | `Edit Onsets` | `GUI/onset_editor.py` | Enables onset marker dragging. |

### Onset editor focus, layer, and signal controls

| Action family | Concrete control | Owner | Notes |
| --- | --- | --- | --- |
| Toggle focus mode | `Focus Onsets` | `GUI/onset_editor.py` | Enters the focus-region workflow. |
| Set focus polarity | `+ Positive`, `- Negative` | `GUI/onset_editor.py` | Chooses the polarity of the drawn focus regions. |
| Layer visibility popup | Layer dropdown button | `GUI/onset_editor.py`, `GUI/onset_editor_workbench_dialogs.py` | Uses `_LayerCheckboxMenu`, a popup menu with all/select/sort controls and per-layer checkboxes. |
| Merge only checked layers | `Merge Sel.` | `GUI/onset_editor.py` | Merges checked layers from the popup selection state. |
| Add or remove layers | `+ Layer`, `- Layer` | `GUI/onset_editor.py` | Layer management controls. |
| Browse focus signals | `Signals` combo box | `GUI/onset_editor.py` | Selects saved focus regions or signal exemplars. |
| Save focus selections | `Save Selections` | `GUI/onset_editor.py` | Opens the save-selections dialog. |
| Load focus selections | `Load Selections` | `GUI/onset_editor.py` | Opens the load-selections dialog. |

### Qt popup menus and context menus

| Surface | Concrete control | Owner | Notes |
| --- | --- | --- | --- |
| Audio viewer context menu | Right-click menu on focus regions | `GUI/audio_viewer.py` | Contains polarity switch, export, move-to-layer submenu, copy-to-layer submenu, and delete. |
| Move region submenu | `Move to Layer` | `GUI/audio_viewer.py` | Includes existing target layers plus `Add to New Layer`. |
| Copy region submenu | `Copy to Layer` | `GUI/audio_viewer.py` | Includes existing target layers plus `Add to New Layer`. |
| Layer checkbox popup | `Layers` popup menu | `GUI/onset_editor.py`, `GUI/onset_editor_workbench_dialogs.py` | Includes `All`, sort cycling, and per-layer visibility checkboxes. |

### Qt dialogs and their trigger actions

| Dialog | Trigger control | Owner | Notes |
| --- | --- | --- | --- |
| Presets dialog | `Presets` | `GUI/main_window_shell.py` | Top-level companion dialog. |
| Onset manager dialog | `Manage Onset / Excel Files` | `GUI/onset_editor.py`, `GUI/onset_editor_workbench_dialogs.py` | Manages onset files and workbook sources. |
| Onset detection dialog | `Quick Onset Finder` | `GUI/onset_editor.py`, `GUI/onset_editor_workbench_dialogs.py` | Region or clip detection workflow. |
| Analyze signals dialog | `Analyze Signals` | `GUI/onset_editor.py`, `GUI/onset_editor_dialogs.py` | Signal analysis and recommendation workflow. |
| Per-signal configuration dialog | `Per-Signal Detect` | `GUI/onset_editor.py`, `GUI/onset_editor_workbench_dialogs.py` | Advanced per-signal onset detection setup. |
| Negative subtraction dialog | `Neg. Subtract` | `GUI/onset_editor.py`, `GUI/onset_editor_workbench_dialogs.py` | Removes negative-region matches. |
| Quick audio editor dialog | `Quick Audio Editor` | `GUI/onset_editor.py` | Audio preprocessing and cleanup actions. |
| MFCC audio edit dialog | `Audio Edits-MFCC` | `GUI/onset_editor.py`, `GUI/onset_editor_workbench_dialogs.py` | Template-driven MFCC audio cleanup flow. |
| Save selections dialog | `Save Selections` | `GUI/onset_editor.py`, `GUI/onset_editor_workbench_dialogs.py` | Exports focus regions and onset selections. |
| Load selections dialog | `Load Selections` | `GUI/onset_editor.py`, `GUI/onset_editor_workbench_dialogs.py` | Restores saved focus regions and selections. |
| Onset-editor settings dialog | `Settings` | `GUI/onset_editor.py`, `GUI/onset_editor_dialogs.py` | Per-file or editor settings dialog. |
| Excel column dialog | `Choose Column...` | `GUI/onset_editor.py`, `GUI/onset_editor_dialogs.py` | Selects onset source columns. |
| Excel save dialog | Save flows inside onset management | `GUI/onset_editor_dialogs.py` | Workbook-oriented save configuration. |

## Coverage Notes

- The backend monitor is still the only surface that exposes the full shared backend analysis catalog directly. The main shell now surfaces the monitor launch clearly, but not each analysis action individually.
- The live-source workflow now has an always-visible launcher, but the actual stream, record-live, and record-and-import commands remain modal actions.
- Camera keyframe controls now have an always-visible launcher, but the detailed keyframe editor still lives inside the recording modal.
- The Qt companion is not menu-bar-driven. Its user-facing control surface is mostly a top button row, a pipeline step sidebar, onset-editor toolbars, popup menus, and dialogs.
- Several controls remain mode-gated by pipeline selection. `Plane Selections` is a TimbreCube surface, while `Selection Sculpt (Full Mask)` and most Terrain authoring controls are SpectroTerrain surfaces.

## Current Gaps To Track

1. Backend and Bioacoustics actions are still monitor-first. If the goal is single-surface discoverability, the main shell may need direct shortcuts for the most common monitor actions.
2. The new `LIVE` launcher opens the workflow, but the transport strip still does not expose one-click `Stream`, `Record Live`, or `Record New Asset` actions.
3. The new `CAM` launcher opens the camera controls, but keyframe capture, reset, and auto-motion controls still remain inside the modal.
4. The companion audit is now mapped, but there is still no cross-window design decision on which Qt-only editor actions should remain companion-only versus be mirrored in Electron.

## Suggested Next Implementation Pass

1. Promote the most common backend monitor actions into clearer main-shell affordances or shortcuts.
2. Decide whether `LIVE` should stay a launcher-only control or grow direct start-mode choices.
3. Decide whether `CAM` should stay a launcher-only control or gain direct keyframe actions.
4. Use this map as the checklist for any control-surface redesign so each existing action is either preserved, relocated, or intentionally removed.