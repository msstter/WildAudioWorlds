import { GUI } from 'lil-gui';
import {
    DEFAULT_INPUT_BINDINGS,
    DEFAULT_KEYBOARD_HOTKEYS,
    DEFAULT_POINTER_BINDINGS,
    POINTER_MOUSE_BUTTON_BINDING_META,
    POINTER_SCROLL_BINDING_META,
} from './inputBindings.js';

const HOTKEY_STORAGE_KEY = '3daudio_hotkeys';

const loadHotkeysFromStorage = (storageObject) => {
    try {
        const stored = storageObject.getItem(HOTKEY_STORAGE_KEY);
        if (!stored) return { ...DEFAULT_INPUT_BINDINGS };
        return { ...DEFAULT_INPUT_BINDINGS, ...JSON.parse(stored) };
    } catch {
        return { ...DEFAULT_INPUT_BINDINGS };
    }
};

const ABOUT_PIPELINE_CONTENT = {
    timbreCube: {
        label: 'TimbreCube',
        activeBorder: '#00ffcc',
        activeBackground: 'rgba(0, 255, 204, 0.12)',
        activeText: '#ccfff4',
        html: `
<p style="margin:0 0 22px 0;color:#666;font-size:12px;">
    TimbreCube maps an audio clip's timbre, volume, and pitch into an abstract 3D trajectory,
    so similar sonic moments cluster together while the playback path still unfolds through time.
</p>

<h3 style="margin:0 0 10px 0;font-size:14px;color:#7af2d9;border-bottom:1px solid #1e3c38;padding-bottom:6px;text-transform:uppercase;letter-spacing:1.5px;">
    Frontend
</h3>
<p style="margin:0 0 10px 0;">
    The interface is a desktop app built with
    <strong style="color:#c8f5ec;">Electron</strong> wrapping a
    <strong style="color:#c8f5ec;">Vite</strong>-bundled web app.
    Every visual element is rendered by
    <strong style="color:#c8f5ec;">Three.js (v0.158)</strong> via WebGL:
    the trajectory of the audio through time is drawn as a continuous
    <em>LineSegments</em> geometry, while each data-point is an instance inside
    an <em>InstancedMesh</em> — a single GPU draw call for all nodes regardless of count.
</p>
<p style="margin:0 0 10px 0;">
    Camera navigation (orbit, pan, zoom) is handled by
    <strong style="color:#c8f5ec;">OrbitControls</strong> with smooth inertia damping,
    and the XYZ axis labels floating in 3D space use Three.js's
    <strong style="color:#c8f5ec;">CSS2DRenderer</strong> so they always face the camera.
</p>
<p style="margin:0 0 10px 0;">
    The settings panel is powered by <strong style="color:#c8f5ec;">lil-gui</strong>,
    which writes directly into a shared <code>settings</code> object that the renderer reads
    every frame — there is no event queue between the UI and the visuals.
</p>
<p style="margin:0 0 10px 0;">
    Lines and nodes are both data-driven and highly configurable. Beyond base visibility and
    decay/dull controls, you can map CSV columns to line/node thickness, brightness, and hue-rotation,
    customize min/max effect ranges, and control render ordering for line, enhancer, nodes, and axes.
</p>
<p style="margin:0 0 10px 0;">
    Audio is played through an HTML <code>&lt;audio&gt;</code> element routed through the
    <strong style="color:#c8f5ec;">Web Audio API</strong>:
    a live <code>AnalyserNode</code> feeds real-time frequency data to the
    <em>Breathing</em> effect, which gently jitters node positions in sync with the sound.
    When screen-recording, the same analyser fans out to a
    <code>MediaStreamDestination</code> so the audio is mixed directly into the
    captured video without any re-encoding.
</p>
<p style="margin:0 0 20px 0;">
    Screen capture uses the browser's built-in
    <strong style="color:#c8f5ec;">MediaRecorder API</strong> (video) or
    <strong style="color:#c8f5ec;">gifenc</strong> (animated images).
    The Three.js canvas is captured via <code>canvas.captureStream()</code>, so what you
    record is exactly what you see — including real-time effects.
</p>

<h3 style="margin:0 0 10px 0;font-size:14px;color:#f2a97a;border-bottom:1px solid #3c2a1e;padding-bottom:6px;text-transform:uppercase;letter-spacing:1.5px;">
    Backend
</h3>
<p style="margin:0 0 10px 0;">
    The Python pipeline uses three core packages:
    <strong style="color:#f5dbc8;">librosa</strong> for audio analysis,
    <strong style="color:#f5dbc8;">NumPy</strong> for numerical processing, and
    <strong style="color:#f5dbc8;">umap-learn</strong> for dimensionality reduction.
</p>

<h4 style="margin:0 0 6px 0;font-size:13px;color:#e8c49a;">Step 1 -- Frequency Spectrum Analysis (librosa)</h4>
<p style="margin:0 0 10px 0;">
    The audio file is analysed frame by frame using a fixed
    <code>hop_length</code> of 512 samples — meaning a new descriptor snapshot is taken
    every ≈ 11 ms (at 44.1 kHz). For each snapshot, <strong>15 descriptors</strong> are extracted
    to characterise the audio's unique <em>timbre</em> and <em>spectral brightness</em>:
</p>
<ul style="margin:0 0 12px 16px;padding:0;list-style:disc;">
    <li style="margin-bottom:5px;">
        <strong style="color:#f5dbc8;">13 MFCCs</strong> (Mel-Frequency Cepstral Coefficients) —
        model how the human ear perceives the tonal texture of sound.
        Each coefficient captures energy at a different perceptual frequency band,
        together forming a compact fingerprint of timbre.
    </li>
    <li style="margin-bottom:5px;">
        <strong style="color:#f5dbc8;">Spectral Centroid</strong> —
        the "centre of mass" of the frequency spectrum.
        A high centroid sounds bright and airy; a low centroid sounds warm and dull.
    </li>
    <li style="margin-bottom:5px;">
        <strong style="color:#f5dbc8;">Spectral Flux</strong> —
        measures how rapidly the spectrum changes between frames.
        Percussive or transient moments produce high flux; sustained tones produce low flux.
    </li>
</ul>
<p style="margin:0 0 14px 0;">
    These 15 values are stacked into one row per frame, producing a matrix of shape
    <code>[n_frames × 15]</code> — a high-dimensional time series of the audio's sonic identity.
</p>

<h4 style="margin:0 0 6px 0;font-size:13px;color:#e8c49a;">Step 2 -- UMAP: 15 Dimensions → 3D</h4>
<p style="margin:0 0 12px 0;">
    <strong style="color:#f5dbc8;">UMAP</strong> (Uniform Manifold Approximation and Projection)
    compresses the <code>[n_frames × 15]</code> matrix into <code>[n_frames × 3]</code>.
    Unlike PCA, UMAP preserves both <em>local structure</em> (similar-sounding moments cluster together)
    and <em>global trajectories</em> (the natural flow of the audio unfolds as a smooth path through
    3D space). The result is an abstract but meaningful coordinate system: you can literally
    <em>see</em> where the audio breathes, jumps, or repeats.
</p>
<p style="margin:0 0 14px 0;">
    Because UMAP produces statistically derived axes with no inherent physical meaning,
    the Python script writes dynamic CSV column headers —
    <code>Audio_UMAP_X</code>, <code>Audio_UMAP_Y</code>, <code>Audio_UMAP_Z</code> —
    so the frontend always knows unambiguously which column maps to which spatial axis,
    regardless of how the projection changes with different audio inputs.
</p>

<h4 style="margin:0 0 6px 0;font-size:13px;color:#e8c49a;">Step 3 -- Volume &amp; Pitch (independent signals)</h4>
<p style="margin:0 0 10px 0;">
    Two additional per-frame values are computed independently and appended to the CSV,
    because they carry meaning that UMAP should <em>not</em> compress away:
</p>
<ul style="margin:0 0 12px 16px;padding:0;list-style:disc;">
    <li style="margin-bottom:5px;">
        <strong style="color:#f5dbc8;">Volume</strong> —
        the RMS (Root Mean Square) energy of each frame.
        This is a direct measure of instantaneous loudness, normalised to [0, 1].
        In the visualiser it drives node <em>scale</em> and, optionally, node
        <em>brightness</em>, so louder moments literally grow and glow.
    </li>
    <li style="margin-bottom:5px;">
        <strong style="color:#f5dbc8;">Pitch</strong> —
        the fundamental frequency (F0) estimated by the
        <strong>YIN algorithm</strong>, bounded between C2 (65 Hz) and C7 (2093 Hz)
        to focus on the musically relevant range and avoid noise artefacts.
        Normalised to [0, 1], pitch is mapped to a <em>hue rotation</em> in the visualiser —
        low pitches are cool (blue/purple) and high pitches are warm (red/orange) —
        giving every node a colour that reflects the note being played at that moment.
    </li>
</ul>
<p style="margin:0 0 0 0;color:#555;font-size:12px;">
    The final CSV therefore contains five columns per frame:
    <code>Audio_UMAP_X</code>, <code>Audio_UMAP_Y</code>, <code>Audio_UMAP_Z</code>,
    <code>Volume</code>, <code>Pitch</code>.
</p>
`,
    },
    spectroTerrain: {
        label: 'SpectroTerrain',
        activeBorder: '#7aa8f2',
        activeBackground: 'rgba(122, 168, 242, 0.12)',
        activeText: '#dbe8ff',
        html: `
<p style="margin:0 0 22px 0;color:#666;font-size:12px;">
    SpectroTerrain keeps the audio in spectral space: instead of reducing descriptors into an abstract
    trajectory, it stacks FFT frames into a 3D terrain where frequency spans the width, amplitude drives
    height, and playback time recedes through depth.
</p>

<h3 style="margin:0 0 10px 0;font-size:14px;color:#87b8ff;border-bottom:1px solid #223b63;padding-bottom:6px;text-transform:uppercase;letter-spacing:1.5px;">
    Frontend
</h3>
<p style="margin:0 0 10px 0;">
    The SpectroTerrain view is still rendered by
    <strong style="color:#dbe8ff;">Three.js</strong> inside the same Electron + Vite desktop shell,
    but its core geometry is a scrolling surface mesh rather than a point-cloud trajectory.
    Each FFT frame becomes one depth slice of the terrain: frequency bins spread across the X axis,
    the amplitude (or magnitude) pushes the mesh upward on Y, and time is stacked backward on Z as playback advances.
</p>
<p style="margin:0 0 10px 0;">
    Because the terrain is built directly from frame rows, controls like
    <strong style="color:#dbe8ff;">Frequency Bins</strong>,
    <strong style="color:#dbe8ff;">Time Depth</strong>,
    manual scaling, and XYZ stretch factors reconfigure the surface itself rather than merely styling it.
    The renderer can switch between solid and wireframe views, accumulate past terrain states,
    and recolor the mesh through axis-based gradient rules, timeline windows, and plane-selection overlays.
</p>
<p style="margin:0 0 10px 0;">
    SpectroTerrain also carries two aligned 2D graph systems: a
    <strong style="color:#dbe8ff;">Frequency × Time</strong> floor graph and an
    <strong style="color:#dbe8ff;">Amplitude × Time</strong> wall graph.
    These can render as plots or spectrograms, extend beyond the current 3D window,
    and stay anchored to the same playback-synchronised frame data that drives the terrain mesh.
</p>
<p style="margin:0 0 10px 0;">
    When an asset includes a precomputed <code>TerrainEnvelope</code> helper, the frontend loads it
    alongside the FFT CSV and uses it to accelerate the Amplitude × Time helper views.
    If the helper is missing or incompatible, the renderer falls back to deriving those views directly
    from the FFT rows at runtime. The terrain helper badge reports which path is active so the user can
    see whether the view is using a precomputed helper or FFT fallback.
</p>
<p style="margin:0 0 20px 0;">
    The plane-selection tools operate differently here than they do in TimbreCube because the axes have
    physical meaning: Frequency × Time, Amplitude × Time, and Frequency × Amplitude slices can be edited
    directly in scene space, letting the terrain act both as a playback surface and as a measurable spectral volume.
</p>

<h3 style="margin:0 0 10px 0;font-size:14px;color:#f2a97a;border-bottom:1px solid #3c2a1e;padding-bottom:6px;text-transform:uppercase;letter-spacing:1.5px;">
    Backend
</h3>
<p style="margin:0 0 10px 0;">
    The Python side of SpectroTerrain stays closer to the raw spectrum.
    It still uses <strong style="color:#f5dbc8;">librosa</strong> and
    <strong style="color:#f5dbc8;">NumPy</strong>, but instead of reducing the data immediately,
    it exports FFT amplitude (or magnitude) frames plus an optional precomputed helper bundle for the terrain projections.
</p>

<h4 style="margin:0 0 6px 0;font-size:13px;color:#e8c49a;">Step 1 -- Short-Time FFT Analysis (librosa)</h4>
<p style="margin:0 0 10px 0;">
    The backend computes a short-time Fourier transform over the audio using the same playback-aligned
    frame cadence as the rest of the app. Each frame captures a frequency snapshot of the clip,
    using an FFT size of <code>1024</code> samples and the shared <code>hop_length</code> of 512 samples.
    The amplitude spectrum is converted to decibels and the first <strong>512 bins</strong> are retained,
    producing one FFT row per frame for the terrain renderer.
</p>
<p style="margin:0 0 14px 0;">
    Unlike TimbreCube, nothing is compressed into an abstract latent space here:
    each exported row still directly represents the energy distribution across the audible spectrum
    at that moment in time.
</p>

<h4 style="margin:0 0 6px 0;font-size:13px;color:#e8c49a;">Step 2 -- TerrainEnvelope Helper Generation</h4>
<p style="margin:0 0 10px 0;">
    After the FFT matrix is built, the backend optionally derives a
    <code>terrain-envelope-v2</code> helper payload.
    This helper resamples each frame to the terrain's target display bin count,
    smooths and reshapes the amplitude profile, and precomputes lookup arrays for the
    Amplitude × Time plot/spectrogram helpers.
</p>
<p style="margin:0 0 14px 0;">
    That means the frontend can reuse pre-baked envelope peaks, wall spectrogram display bins,
    and intensity bytes instead of recomputing those views from scratch every time an asset is loaded.
    If the helper does not match the current mode, the app still has a clean FFT fallback path.
</p>

<h4 style="margin:0 0 6px 0;font-size:13px;color:#e8c49a;">Step 3 -- Playback-Aligned Terrain Exports</h4>
<p style="margin:0 0 10px 0;">
    The final export bundle writes both <code>*_FFTs.csv</code> and
    <code>*_TerrainEnvelope.json</code>, then records timing metadata in the asset manifest:
    frame count, hop size, FFT size, clip duration, and related analysis fields.
    Because those exports stay aligned to the audio timeline, the terrain renderer can scrub and sync
    directly against exact frame data instead of estimating position from duration ratios.
</p>
<p style="margin:0 0 0 0;color:#555;font-size:12px;">
    In practice, the SpectroTerrain pipeline ships two complementary assets per clip:
    a dense FFT time-series for the 3D surface itself, and an optional helper JSON that accelerates
    the secondary wall/floor projections without changing the underlying spectral data.
</p>
`,
    },
    rhythmOnset: {
        label: 'Rhythm / Onset',
        activeBorder: '#f2a97a',
        activeBackground: 'rgba(242, 169, 122, 0.12)',
        activeText: '#ffe1cf',
        html: `
<p style="margin:0 0 22px 0;color:#666;font-size:12px;">
    Rhythm / Onset is the analysis layer that sits on top of the selection system: once a group of nodes
    or windows is isolated, the app turns those playback-aligned frames into contiguous time regions,
    detects onset events, computes inter-onset intervals, and projects the results back into playback,
    transport, flash, and export controls.
</p>

<h3 style="margin:0 0 10px 0;font-size:14px;color:#f2d39b;border-bottom:1px solid #5a3b24;padding-bottom:6px;text-transform:uppercase;letter-spacing:1.5px;">
    Current Controls
</h3>
<p style="margin:0 0 10px 0;">
    The current rhythm controls live across the <strong style="color:#ffe7d3;">Analysis</strong> settings,
    the transport bar, the node flash options, and the Node Selection panel.
    You can switch the onset method between selection-scoped <strong style="color:#ffe7d3;">Spectral Flux</strong>
    and the legacy positive-<code>Volume</code> delta heuristic, adjust onset sensitivity and threshold scale,
    choose whether flashes target only onset frames or the full onset window, and toggle clickable transport markers.
</p>
<p style="margin:0 0 10px 0;">
    At runtime, the analysis layer can pulse selected nodes in sync with detected events,
    seek from transport markers directly into the relevant onset, and generate automatic saved tabs
    from onset-derived segments. Current selections and saved Node Group tabs can already export
    JSON, CSV, concatenated WAV clips, and dedicated <strong style="color:#ffe7d3;">Onsets + IOI</strong>
    CSV files for Audacity cross-checking.
</p>
<p style="margin:0 0 20px 0;">
    Because selection playback masking is already wired into the transport runtime,
    the rhythm layer can audition only the chosen windows while still staying locked to the same
    frame-accurate playback anchor used by the rest of the app.
</p>

<h3 style="margin:0 0 10px 0;font-size:14px;color:#8dd7ff;border-bottom:1px solid #24475a;padding-bottom:6px;text-transform:uppercase;letter-spacing:1.5px;">
    Analysis Engine
</h3>
<p style="margin:0 0 10px 0;">
    The analysis pass runs in the browser over explicit backend timing metadata.
    Selected <code>frameRecords</code> are merged into contiguous windows, onset events are picked inside those
    windows, and inter-onset intervals are calculated directly from event timing instead of rough duration ratios.
</p>
<p style="margin:0 0 20px 0;">
    Spectral Flux is now the main onset path, while the older positive-volume-delta method remains available
    as a fallback and comparison baseline. Because the manifest also carries frame count, hop length,
    frame length, clip duration, and FFT size, the onset layer stays aligned with playback-rate changes,
    selection jumps, and clickable transport seeks.
</p>

<h3 style="margin:0 0 10px 0;font-size:14px;color:#cbb5ff;border-bottom:1px solid #4b3470;padding-bottom:6px;text-transform:uppercase;letter-spacing:1.5px;">
    Planned Next Additions
</h3>
<ul style="margin:0 0 12px 16px;padding:0;list-style:disc;">
    <li style="margin-bottom:5px;">
        <strong style="color:#efe7ff;">Fade-in and fade-out padding</strong> for selection masking,
        so isolated playback can be auditioned without hard edges.
    </li>
    <li style="margin-bottom:5px;">
        <strong style="color:#efe7ff;">Loop playback, solo, and quick-audition controls</strong>
        for the current selection windows or active cluster.
    </li>
    <li style="margin-bottom:5px;">
        <strong style="color:#efe7ff;">Jump-to-first-window controls</strong> so the active selection
        can become a faster rhythm audition target.
    </li>
    <li style="margin-bottom:5px;">
        <strong style="color:#efe7ff;">Audacity-friendly export bundles</strong> that combine onset / IOI CSVs
        with selection-window metadata for easier external checking.
    </li>
    <li style="margin-bottom:5px;">
        Longer-term rhythm additions already scoped in the architecture doc include
        <strong style="color:#efe7ff;">rhythm heatmaps</strong>,
        <strong style="color:#efe7ff;">self-similarity / repetition views</strong>,
        timeline bookmarks, and provenance logs tied to exports.
    </li>
</ul>
<p style="margin:0 0 0 0;color:#555;font-size:12px;">
    This tab is intentionally about the shared rhythm-analysis layer rather than one visual pipeline only:
    the goal is to make onset logic, audition tools, and export flows easier to understand as a system in their own right.
</p>
`,
    },
    bioacousticsBridge: {
        label: 'Bioacoustics Bridge',
        activeBorder: '#9cc8ff',
        activeBackground: 'rgba(156, 200, 255, 0.12)',
        activeText: '#e3f1ff',
        html: `
<p style="margin:0 0 22px 0;color:#666;font-size:12px;">
    The Bioacoustics Bridge is meant to let the two apps stay good at different jobs instead of forcing one app to replace the other:
    <strong style="color:#dbe8ff;">BioacousticsProject</strong> remains the structured workbook and downstream-rhythm-analysis system,
    while <strong style="color:#dbe8ff;">3D Audio Maker</strong> becomes the selection, audition, comparison, and onset-refinement layer.
</p>

<h3 style="margin:0 0 10px 0;font-size:14px;color:#8dd7ff;border-bottom:1px solid #24475a;padding-bottom:6px;text-transform:uppercase;letter-spacing:1.5px;">
    What Connects The Two Apps
</h3>
<p style="margin:0 0 10px 0;">
    The shared key is the workbook row's <strong style="color:#e3f1ff;">File Name</strong> column.
    3D Audio Maker now resolves the currently selected asset's actual audio filename from the manifest-backed <code>audioUrl</code>,
    then uses that basename to find the matching row in the Bioacoustics workbook.
    In practice, that means the safest workflow is to keep the exported audio filename from the Bioacoustics pipeline unchanged when you want the two systems to talk to each other.
</p>
<p style="margin:0 0 20px 0;">
    Once the filename matches, the bridge can do two things: import the workbook's onset list into TimbreCube as an onset source,
    or write a new onset list from TimbreCube back into a Bioacoustics-compatible workbook while regenerating the workbook's summary and dyadic-event sheets.
</p>

<h3 style="margin:0 0 10px 0;font-size:14px;color:#f2d39b;border-bottom:1px solid #5a3b24;padding-bottom:6px;text-transform:uppercase;letter-spacing:1.5px;">
    Recommended Workflow
</h3>
<ol style="margin:0 0 14px 18px;padding:0;">
    <li style="margin-bottom:8px;">
        Load or export your audio into 3D Audio Maker normally so the current asset in the app is the same recording represented by the workbook row.
    </li>
    <li style="margin-bottom:8px;">
        Open <strong style="color:#ffe7d3;">Call Backend</strong>, switch the action to
        <strong style="color:#ffe7d3;">Bioacoustics: Import Workbook Onsets</strong>, choose the workbook,
        and run the import. This pulls the row's <code>Exact Onset Times Used (s)</code> into the app.
    </li>
    <li style="margin-bottom:8px;">
        Back in TimbreCube, switch <strong style="color:#ffe7d3;">Analysis → Onset Method</strong> to
        <strong style="color:#ffe7d3;">Bioacoustics Workbook</strong> if you want to treat the imported workbook onsets as the active onset source.
        This is the cleanest way to compare the original pipeline result against your current selection windows and transport markers.
    </li>
    <li style="margin-bottom:8px;">
        Refine the material in 3D Audio Maker: use node selection, saved Node Group tabs, playback masking, transport markers,
        and the existing onset methods when you want to derive or compare a different onset interpretation.
    </li>
    <li style="margin-bottom:8px;">
        When you are ready to send an edited result back, use <strong style="color:#ffe7d3;">Export Onsets + IOI 2</strong>
        from the current selection or a saved group. That path writes a Bioacoustics-compatible workbook export rather than the older generic CSV.
    </li>
    <li style="margin-bottom:0;">
        Prefer <strong style="color:#ffe7d3;">Duplicate Existing Workbook</strong> when you want to preserve the original workbook,
        and use <strong style="color:#ffe7d3;">Overwrite Existing Workbook</strong> only after you are confident that the current 3D selection is the version you want downstream analyses to use.
    </li>
</ol>

<h3 style="margin:0 0 10px 0;font-size:14px;color:#7af2d9;border-bottom:1px solid #1e3c38;padding-bottom:6px;text-transform:uppercase;letter-spacing:1.5px;">
    When To Use Each Side
</h3>
<p style="margin:0 0 10px 0;">
    Use <strong style="color:#c8f5ec;">BioacousticsProject</strong> when you need the workbook as the canonical dataset,
    or when you want the rest of that pipeline's downstream analyses to consume the updated onset list.
</p>
<p style="margin:0 0 10px 0;">
    Use <strong style="color:#c8f5ec;">3D Audio Maker</strong> when you need to understand where onset events sit inside a timbral or spectral structure,
    isolate sub-groups of nodes, compare alternate onset interpretations, or audition timing changes interactively before committing them back to a workbook.
</p>
<p style="margin:0 0 20px 0;">
    A good mental model is: <em>BioacousticsProject stores and distributes the rhythm dataset; 3D Audio Maker edits and tests rhythm ideas against the 3D representation of the sound.</em>
</p>

<h3 style="margin:0 0 10px 0;font-size:14px;color:#cbb5ff;border-bottom:1px solid #4b3470;padding-bottom:6px;text-transform:uppercase;letter-spacing:1.5px;">
    Current Guardrails
</h3>
<ul style="margin:0 0 12px 16px;padding:0;list-style:disc;">
    <li style="margin-bottom:5px;">
        The bridge matches by audio filename, not by display label. If the filename in the workbook does not match the selected asset's file basename, import will not find the row you expect.
    </li>
    <li style="margin-bottom:5px;">
        The new workbook sync path regenerates <strong style="color:#efe7ff;">File Summaries</strong>,
        <strong style="color:#efe7ff;">Dyadic Events (For Plots)</strong>, and
        <strong style="color:#efe7ff;">Dyadic Events (Stable Rhythms)</strong> for the target file,
        while preserving the workbook's other sheets.
    </li>
    <li style="margin-bottom:5px;">
        The older <strong style="color:#efe7ff;">Export Onsets + IOI</strong> action is still useful as a generic CSV export,
        but it is not the interchange format for the Bioacoustics workbook flow.
    </li>
    <li style="margin-bottom:0;">
        The imported workbook onset source is asset-specific. If you switch to another audio asset, import that asset's workbook row separately instead of assuming one import applies globally.
    </li>
</ul>
<p style="margin:0 0 0 0;color:#555;font-size:12px;">
    The intended long-term workflow is not "which app wins," but a loop: detect and structure in BioacousticsProject,
    inspect and refine in 3D Audio Maker, then write the chosen result back to a workbook for the rest of the rhythm-analysis pipeline.
</p>
`,
    },
};

const createAboutOverlay = (documentObject) => {
    const aboutOverlay = documentObject.createElement('div');
    aboutOverlay.style.cssText = [
        'position:fixed',
        'inset:0',
        'background:rgba(0,0,0,0.78)',
        'display:none',
        'align-items:center',
        'justify-content:center',
        'z-index:3000',
    ].join(';');

    const aboutBox = documentObject.createElement('div');
    aboutBox.style.cssText = [
        'background:#0d0d0d',
        'border:1px solid #2a2a2a',
        'border-radius:12px',
        'padding:32px 36px',
        'color:#c8c8c8',
        'max-width:760px',
        'width:92%',
        'max-height:82vh',
        'overflow-y:auto',
        'box-shadow:0 12px 48px rgba(0,0,0,0.8)',
        'font-size:13.5px',
        'line-height:1.7',
    ].join(';');

    const title = documentObject.createElement('h2');
    title.textContent = '3D Audio Maker -- How It Works';
    title.style.cssText = 'margin:0 0 6px 0;font-size:18px;color:#00ffcc;letter-spacing:1px;';

    const subtitle = documentObject.createElement('p');
    subtitle.textContent = 'Switch between the visual pipelines, the rhythm-analysis layer, and the Bioacoustics integration guide to compare how each part of the app handles audio, timing, 3D structure, and workbook exchange.';
    subtitle.style.cssText = 'margin:0 0 18px 0;color:#666;font-size:12px;';

    const tabLabel = documentObject.createElement('div');
    tabLabel.textContent = 'Pipelines, Analysis, and Integration';
    tabLabel.style.cssText = 'margin:0 0 8px 0;color:#8a8a8a;font-size:11px;letter-spacing:0.12em;text-transform:uppercase;';

    const tabRow = documentObject.createElement('div');
    tabRow.style.cssText = [
        'display:flex',
        'gap:8px',
        'flex-wrap:wrap',
        'margin:0 0 18px 0',
    ].join(';');

    const contentContainer = documentObject.createElement('div');
    const tabButtons = new Map();
    let activePipelineKey = 'timbreCube';

    const syncTabStyles = () => {
        for (const [pipelineKey, button] of tabButtons.entries()) {
            const pipeline = ABOUT_PIPELINE_CONTENT[pipelineKey];
            const isActive = pipelineKey === activePipelineKey;
            button.style.borderColor = isActive ? pipeline.activeBorder : '#333';
            button.style.background = isActive ? pipeline.activeBackground : '#121212';
            button.style.color = isActive ? pipeline.activeText : '#9ca3af';
            button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        }
    };

    const renderActivePipeline = () => {
        contentContainer.innerHTML = ABOUT_PIPELINE_CONTENT[activePipelineKey].html;
        syncTabStyles();
    };

    for (const [pipelineKey, pipeline] of Object.entries(ABOUT_PIPELINE_CONTENT)) {
        const button = documentObject.createElement('button');
        button.type = 'button';
        button.textContent = pipeline.label;
        button.style.cssText = [
            'padding:8px 14px',
            'border:1px solid #333',
            'border-radius:999px',
            'background:#121212',
            'color:#9ca3af',
            'font-size:12px',
            'font-weight:bold',
            'letter-spacing:0.04em',
            'cursor:pointer',
        ].join(';');
        button.addEventListener('click', () => {
            activePipelineKey = pipelineKey;
            renderActivePipeline();
        });
        tabButtons.set(pipelineKey, button);
        tabRow.appendChild(button);
    }

    const closeButton = documentObject.createElement('button');
    closeButton.textContent = 'Close';
    closeButton.style.cssText = [
        'display:block',
        'margin:24px 0 0 auto',
        'padding:9px 28px',
        'background:#00ffcc',
        'color:#010f0c',
        'border:none',
        'border-radius:6px',
        'font-size:13px',
        'font-weight:bold',
        'cursor:pointer',
        'letter-spacing:0.5px',
    ].join(';');
    closeButton.addEventListener('click', () => {
        aboutOverlay.style.display = 'none';
    });
    aboutOverlay.addEventListener('click', (event) => {
        if (event.target === aboutOverlay) {
            aboutOverlay.style.display = 'none';
        }
    });

    aboutBox.appendChild(title);
    aboutBox.appendChild(subtitle);
    aboutBox.appendChild(tabLabel);
    aboutBox.appendChild(tabRow);
    aboutBox.appendChild(contentContainer);
    aboutBox.appendChild(closeButton);
    renderActivePipeline();

    aboutOverlay.appendChild(aboutBox);
    documentObject.body.appendChild(aboutOverlay);

    return aboutOverlay;
};

const createRenderOrderModal = ({ documentObject, settings, applyRenderOrderSettings }) => {
    const renderOrderModal = documentObject.createElement('div');
    renderOrderModal.id = 'render-order-modal';
    renderOrderModal.style.cssText = [
        'position:fixed',
        'top:0',
        'left:0',
        'width:100%',
        'height:100%',
        'background:rgba(0,0,0,0.78)',
        'display:none',
        'z-index:1100',
        'align-items:center',
        'justify-content:center',
    ].join(';');
    renderOrderModal.innerHTML = `
        <div style="background:#161616;border:1px solid #333;border-radius:10px;padding:20px;color:#d8d8d8;min-width:340px;">
            <h3 style="margin:0 0 14px 0;color:#7af2d9;">Render Order</h3>
            <div style="display:grid;grid-template-columns:1fr 100px;gap:8px;align-items:center;">
                <label for="ro-line">Line</label>
                <input id="ro-line" type="number" step="1" style="padding:6px;background:#0f0f0f;border:1px solid #333;color:#ddd;border-radius:4px;">

                <label for="ro-line-enhancer">Line Enhancer</label>
                <input id="ro-line-enhancer" type="number" step="1" style="padding:6px;background:#0f0f0f;border:1px solid #333;color:#ddd;border-radius:4px;">

                <label for="ro-nodes">Nodes</label>
                <input id="ro-nodes" type="number" step="1" style="padding:6px;background:#0f0f0f;border:1px solid #333;color:#ddd;border-radius:4px;">

                <label for="ro-axes">Axes Box</label>
                <input id="ro-axes" type="number" step="1" style="padding:6px;background:#0f0f0f;border:1px solid #333;color:#ddd;border-radius:4px;">
            </div>
            <div style="display:flex; gap:8px; margin-top:14px;">
                <button id="ro-apply" style="flex:1; padding:8px; border:none; border-radius:6px; cursor:pointer; background:#00ffcc; color:#021311; font-weight:bold;">Apply</button>
                <button id="ro-reset" style="flex:1; padding:8px; border:1px solid #555; border-radius:6px; cursor:pointer; background:#1f1f1f; color:#ccc;">Reset</button>
                <button id="ro-close" style="flex:1; padding:8px; border:1px solid #555; border-radius:6px; cursor:pointer; background:#1f1f1f; color:#ccc;">Close</button>
            </div>
        </div>
    `;
    documentObject.body.appendChild(renderOrderModal);

    const roLineInput = renderOrderModal.querySelector('#ro-line');
    const roLineEnhancerInput = renderOrderModal.querySelector('#ro-line-enhancer');
    const roNodesInput = renderOrderModal.querySelector('#ro-nodes');
    const roAxesInput = renderOrderModal.querySelector('#ro-axes');
    const closeRenderOrderModal = () => {
        renderOrderModal.style.display = 'none';
    };

    renderOrderModal.querySelector('#ro-apply').addEventListener('click', () => {
        settings.renderOrderLine = Number.parseInt(roLineInput.value || '0', 10);
        settings.renderOrderLineEnhancer = Number.parseInt(roLineEnhancerInput.value || '-1', 10);
        settings.renderOrderNodes = Number.parseInt(roNodesInput.value || '0', 10);
        settings.renderOrderAxes = Number.parseInt(roAxesInput.value || '-1', 10);
        applyRenderOrderSettings?.();
        closeRenderOrderModal();
    });

    renderOrderModal.querySelector('#ro-reset').addEventListener('click', () => {
        settings.renderOrderLine = 0;
        settings.renderOrderLineEnhancer = -1;
        settings.renderOrderNodes = 0;
        settings.renderOrderAxes = -1;
        roLineInput.value = '0';
        roLineEnhancerInput.value = '-1';
        roNodesInput.value = '0';
        roAxesInput.value = '-1';
        applyRenderOrderSettings?.();
    });

    renderOrderModal.querySelector('#ro-close').addEventListener('click', () => {
        closeRenderOrderModal();
    });

    renderOrderModal.addEventListener('click', (event) => {
        if (event.target === renderOrderModal) {
            closeRenderOrderModal();
        }
    });

    return {
        renderOrderModal,
        openRenderOrderEditor: () => {
            roLineInput.value = `${settings.renderOrderLine}`;
            roLineEnhancerInput.value = `${settings.renderOrderLineEnhancer}`;
            roNodesInput.value = `${settings.renderOrderNodes}`;
            roAxesInput.value = `${settings.renderOrderAxes}`;
            renderOrderModal.style.display = 'flex';
        },
    };
};

const createHotkeyModal = ({
    documentObject,
    storageObject,
    settings,
    confirmHotkeyReset,
} = {}) => {
    const hotkeyModal = documentObject.createElement('div');
    hotkeyModal.id = 'hotkey-modal';
    hotkeyModal.style.cssText = [
        'position:fixed',
        'top:0',
        'left:0',
        'width:100%',
        'height:100%',
        'background:rgba(0,0,0,0.8)',
        'display:none',
        'z-index:1000',
        'align-items:center',
        'justify-content:center',
    ].join(';');
    hotkeyModal.innerHTML = `
        <div style="background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 20px; color: #ccc; width: min(560px, calc(100vw - 32px)); max-height: 82vh; overflow: hidden; box-sizing: border-box;">
            <h3 style="margin: 0 0 6px 0; color: #0ff;">Edit Hotkeys &amp; Pointer Controls</h3>
            <div style="margin: 0 0 15px 0; color: #8c8c8c; font-size: 12px; line-height: 1.45;">
                Keyboard shortcuts and canvas pointer controls are stored together here. Scroll controls only apply over the 3D canvas, not over the GUI panels.
            </div>
            <label style="display:flex; align-items:center; gap:8px; margin:0 0 12px 0; font-size:13px; color:#9adad0;">
                <input id="hotkey-enable-checkbox" type="checkbox" checked>
                Enable Keyboard Hotkeys
            </label>
            <div id="hotkey-bindings" style="margin-bottom: 15px; max-height: min(56vh, 520px); overflow-y: auto; padding-right: 4px;"></div>
            <div style="display: flex; gap: 10px;">
                <button id="hotkey-reset-btn" style="flex: 1; padding: 8px; background: #444; border: 1px solid #666; color: #ccc; cursor: pointer; border-radius: 4px;">Reset to Default</button>
                <button id="hotkey-close-btn" style="flex: 1; padding: 8px; background: #0ff; border: none; color: #000; cursor: pointer; border-radius: 4px; font-weight: bold;">Close</button>
            </div>
        </div>
    `;
    documentObject.body.appendChild(hotkeyModal);

    let currentHotkeys = loadHotkeysFromStorage(storageObject);
    const hotkeyEnableCheckbox = hotkeyModal.querySelector('#hotkey-enable-checkbox');
    hotkeyEnableCheckbox.checked = !!settings.enableHotkeys;
    hotkeyEnableCheckbox.addEventListener('change', () => {
        settings.enableHotkeys = hotkeyEnableCheckbox.checked;
    });

    const saveHotkeysToStorage = (hotkeys = currentHotkeys) => {
        storageObject.setItem(HOTKEY_STORAGE_KEY, JSON.stringify(hotkeys));
    };

    const renderHotkeyEditor = () => {
        const container = hotkeyModal.querySelector('#hotkey-bindings');
        container.replaceChildren();

        const appendSectionHeader = (titleText, { topMargin = 0, color = '#7af2d9' } = {}) => {
            const header = documentObject.createElement('div');
            header.style.cssText = [
                `margin:${topMargin}px 0 6px 0`,
                'padding-top:10px',
                'border-top:1px solid #2f2f2f',
                'font-size:12px',
                'letter-spacing:0.08em',
                'text-transform:uppercase',
                `color:${color}`,
            ].join(';');
            header.textContent = titleText;
            container.appendChild(header);
        };

        const appendSectionNote = (text) => {
            const note = documentObject.createElement('div');
            note.style.cssText = 'margin:0 0 10px 0;font-size:12px;line-height:1.45;color:#8c8c8c;';
            note.textContent = text;
            container.appendChild(note);
        };

        const createLabelBlock = (labelText, detailText) => {
            const wrap = documentObject.createElement('div');
            wrap.style.cssText = 'min-width:0;';

            const label = documentObject.createElement('div');
            label.style.cssText = 'color:#d8e6e4;line-height:1.35;';
            label.textContent = labelText;

            const detail = documentObject.createElement('div');
            detail.style.cssText = 'margin-top:2px;color:#70807d;font-size:11px;line-height:1.35;';
            detail.textContent = detailText;

            wrap.appendChild(label);
            wrap.appendChild(detail);
            return wrap;
        };

        const labels = {
            togglePlayPause: 'Play/Pause',
            toggleFullscreen: 'Fullscreen Toggle',
            seekForward: 'Seek Forward',
            seekBackward: 'Seek Backward',
            toggleRecordControl: 'Record Control',
            playFromBeginning: 'Play From Beginning',
            toggleSpeedMenu: 'Speed Menu Control',
            captureCameraKeyframe: 'Set Camera Keyframe',
            nextCameraKeyframe: 'Next Camera Keyframe',
            previousCameraKeyframe: 'Previous Camera Keyframe',
            toggleSidebarOrCloseMenus: 'Close Menus / Toggle Sidebar',
        };

        const fpvLabels = {
            toggleFpvMode: 'Toggle FPV Mode',
            fpvMoveForward: 'FPV Move Forward',
            fpvMoveBackward: 'FPV Move Backward',
            fpvMoveLeft: 'FPV Move Left',
            fpvMoveRight: 'FPV Move Right',
            fpvMoveUp: 'FPV Move Up',
            fpvMoveDown: 'FPV Move Down',
            fpvSprint: 'FPV Sprint / Double Speed',
            fpvPlayPause: 'FPV Play/Pause',
        };

        const appendKeyboardHotkeyRows = (labelMap) => {
            for (const [key, labelText] of Object.entries(labelMap)) {
                const row = documentObject.createElement('div');
                row.style.cssText = 'display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:8px;';

                const input = documentObject.createElement('input');
                input.type = 'text';
                input.readOnly = true;
                input.value = currentHotkeys[key] || DEFAULT_KEYBOARD_HOTKEYS[key];
                input.style.cssText = 'background:#222;border:1px solid #444;color:#0ff;padding:4px;width:120px;text-align:center;border-radius:4px;';

                const recordButton = documentObject.createElement('button');
                recordButton.textContent = 'Record';
                recordButton.style.cssText = 'background:#0ff;color:#000;border:none;padding:4px 12px;cursor:pointer;border-radius:4px;font-weight:bold;';
                recordButton.addEventListener('click', () => {
                    recordButton.textContent = 'Listening...';
                    recordButton.disabled = true;

                    const handler = (event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        event.stopImmediatePropagation();
                        currentHotkeys[key] = event.code;
                        input.value = event.code;
                        recordButton.textContent = 'Record';
                        recordButton.disabled = false;
                        documentObject.removeEventListener('keydown', handler, true);
                    };

                    documentObject.addEventListener('keydown', handler, true);
                });

                const rowLabel = documentObject.createElement('span');
                rowLabel.style.cssText = 'width:220px;line-height:1.35;';
                rowLabel.textContent = labelText;

                row.appendChild(rowLabel);
                row.appendChild(input);
                row.appendChild(recordButton);
                container.appendChild(row);
            }
        };

        appendSectionHeader('Keyboard Hotkeys', { color: '#7af2d9' });
        appendSectionNote('Keyboard shortcuts can be rebound here without changing the pointer controls below.');
        appendKeyboardHotkeyRows(labels);

        appendSectionHeader('FPV Controls', { topMargin: 14, color: '#f4a7ff' });
        appendSectionNote('These bindings are used only while first-person mode is enabled. Mouse look is handled by raw mouse movement after you click the 3D canvas.');
        appendKeyboardHotkeyRows(fpvLabels);

        appendSectionHeader('Mouse Buttons', { topMargin: 14, color: '#9bbcff' });
        appendSectionNote('These map the OrbitControls drag behavior used over the 3D canvas. Modifier-assisted left-drag still follows the underlying OrbitControls behavior.');

        for (const { key, label, detail, options } of POINTER_MOUSE_BUTTON_BINDING_META) {
            const row = documentObject.createElement('div');
            row.style.cssText = 'display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;margin-bottom:10px;';

            const select = documentObject.createElement('select');
            select.style.cssText = 'background:#222;border:1px solid #444;color:#d8f8ff;padding:6px 8px;min-width:168px;border-radius:4px;';
            for (const optionLabel of options) {
                const option = documentObject.createElement('option');
                option.value = optionLabel;
                option.textContent = optionLabel;
                select.appendChild(option);
            }
            select.value = currentHotkeys[key] || DEFAULT_POINTER_BINDINGS[key];
            select.addEventListener('change', () => {
                currentHotkeys[key] = select.value;
            });

            row.appendChild(createLabelBlock(label, detail));
            row.appendChild(select);
            container.appendChild(row);
        }

        appendSectionHeader('Scroll Controls', { topMargin: 14, color: '#f2c37a' });
        appendSectionNote('Each scroll action can be changed independently. Flip Scroll Direction reverses the zoom or seek direction for that specific gesture.');

        for (const { key, flipKey, label, detail, options } of POINTER_SCROLL_BINDING_META) {
            const row = documentObject.createElement('div');
            row.style.cssText = 'display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;margin-bottom:10px;';

            const controlWrap = documentObject.createElement('div');
            controlWrap.style.cssText = 'display:flex;align-items:center;gap:10px;flex-wrap:wrap;justify-content:flex-end;';

            const select = documentObject.createElement('select');
            select.style.cssText = 'background:#222;border:1px solid #444;color:#d8f8ff;padding:6px 8px;min-width:168px;border-radius:4px;';
            for (const optionLabel of options) {
                const option = documentObject.createElement('option');
                option.value = optionLabel;
                option.textContent = optionLabel;
                select.appendChild(option);
            }
            select.value = currentHotkeys[key] || DEFAULT_POINTER_BINDINGS[key];

            const flipLabel = documentObject.createElement('label');
            flipLabel.style.cssText = 'display:flex;align-items:center;gap:6px;color:#a7b3b1;font-size:12px;';

            const flipCheckbox = documentObject.createElement('input');
            flipCheckbox.type = 'checkbox';
            flipCheckbox.checked = !!currentHotkeys[flipKey];
            flipCheckbox.addEventListener('change', () => {
                currentHotkeys[flipKey] = flipCheckbox.checked;
            });

            const flipText = documentObject.createElement('span');
            flipText.textContent = 'Flip Scroll Direction';

            const syncFlipState = () => {
                const disabled = select.value === 'Disabled';
                flipCheckbox.disabled = disabled;
                flipLabel.style.opacity = disabled ? '0.55' : '1';
            };

            select.addEventListener('change', () => {
                currentHotkeys[key] = select.value;
                syncFlipState();
            });

            syncFlipState();
            flipLabel.appendChild(flipCheckbox);
            flipLabel.appendChild(flipText);
            controlWrap.appendChild(select);
            controlWrap.appendChild(flipLabel);

            row.appendChild(createLabelBlock(label, detail));
            row.appendChild(controlWrap);
            container.appendChild(row);
        }

        const pointerHeader = documentObject.createElement('div');
        pointerHeader.style.cssText = 'margin:14px 0 6px 0;padding-top:10px;border-top:1px solid #2f2f2f;font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:#7af2d9;';
        pointerHeader.textContent = 'Folder Click Shortcuts';
        container.appendChild(pointerHeader);

        const pointerNote = documentObject.createElement('div');
        pointerNote.style.cssText = 'margin:0 0 10px 0;font-size:12px;line-height:1.45;color:#8c8c8c;';
        pointerNote.textContent = 'Applies when clicking a settings folder arrow or title.';
        container.appendChild(pointerNote);

        const pointerShortcuts = [
            { label: 'Open Current Folder', shortcut: 'Click', detail: 'This folder only' },
            { label: 'Open +1 Subsection', shortcut: 'Shift + Click', detail: 'Open one level deeper' },
            { label: 'Open All Subsections', shortcut: 'Ctrl/Cmd + Click', detail: 'Expand the whole branch' },
        ];

        for (const { label, shortcut, detail } of pointerShortcuts) {
            const row = documentObject.createElement('div');
            row.style.cssText = 'display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px;';

            const rowLabel = documentObject.createElement('span');
            rowLabel.style.cssText = 'width:170px;line-height:1.35;';
            rowLabel.textContent = label;

            const value = documentObject.createElement('input');
            value.type = 'text';
            value.readOnly = true;
            value.value = shortcut;
            value.style.cssText = 'background:#222;border:1px solid #444;color:#d8f8ff;padding:4px;width:120px;text-align:center;border-radius:4px;';

            const badge = documentObject.createElement('span');
            badge.style.cssText = 'width:90px;font-size:11px;line-height:1.25;text-align:right;color:#8fcbc2;';
            badge.textContent = detail;

            row.appendChild(rowLabel);
            row.appendChild(value);
            row.appendChild(badge);
            container.appendChild(row);
        }
    };

    const closeHotkeyModal = () => {
        hotkeyModal.style.display = 'none';
        saveHotkeysToStorage(currentHotkeys);
    };

    hotkeyModal.querySelector('#hotkey-close-btn').addEventListener('click', () => {
        closeHotkeyModal();
    });

    hotkeyModal.addEventListener('click', (event) => {
        if (event.target === hotkeyModal) {
            closeHotkeyModal();
        }
    });

    hotkeyModal.querySelector('#hotkey-reset-btn').addEventListener('click', async () => {
        const shouldReset = confirmHotkeyReset ? await confirmHotkeyReset() : true;
        if (!shouldReset) return;

        currentHotkeys = { ...DEFAULT_INPUT_BINDINGS };
        renderHotkeyEditor();
    });

    return {
        hotkeyModal,
        getCurrentHotkeys: () => currentHotkeys,
        saveHotkeysToStorage,
        openHotkeyEditor: () => {
            hotkeyModal.style.display = 'flex';
            hotkeyEnableCheckbox.checked = !!settings.enableHotkeys;
            renderHotkeyEditor();
        },
    };
};

export const createAppShell = ({
    documentObject = document,
    storageObject = localStorage,
    settings,
    applyRenderOrderSettings,
    confirmHotkeyReset,
} = {}) => {
    const gui = new GUI({ title: '3D Audio Settings' });
    gui._closeFolders = true;

    const walkGuiFolders = (folder, visitor) => {
        for (const childFolder of folder.folders ?? []) {
            visitor(childFolder);
            walkGuiFolders(childFolder, visitor);
        }
    };

    const closeGuiFolderBranch = (folder) => {
        folder.close();
        for (const childFolder of folder.folders ?? []) {
            closeGuiFolderBranch(childFolder);
        }
    };

    const openGuiFolderBranchToDepth = (folder, depth) => {
        folder.open();

        for (const childFolder of folder.folders ?? []) {
            if (depth === Infinity) {
                openGuiFolderBranchToDepth(childFolder, Infinity);
            } else if (depth > 0) {
                openGuiFolderBranchToDepth(childFolder, depth - 1);
            } else {
                closeGuiFolderBranch(childFolder);
            }
        }
    };

    const bindGuiFolderTitleShortcuts = () => {
        walkGuiFolders(gui, (folder) => {
            if (!folder.$title || folder.$title.dataset.folderDepthShortcutBound === 'true') return;

            folder.$title.dataset.folderDepthShortcutBound = 'true';
            folder.$title.addEventListener('click', (event) => {
                if ('button' in event && event.button !== 0) return;

                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();

                if (event.metaKey || event.ctrlKey) {
                    openGuiFolderBranchToDepth(folder, Infinity);
                    return;
                }

                if (event.shiftKey) {
                    openGuiFolderBranchToDepth(folder, 1);
                    return;
                }

                if (folder._closed) {
                    openGuiFolderBranchToDepth(folder, 0);
                } else {
                    closeGuiFolderBranch(folder);
                }
            }, true);
        });
    };

    const aboutOverlay = createAboutOverlay(documentObject);
    const {
        renderOrderModal,
        openRenderOrderEditor,
    } = createRenderOrderModal({
        documentObject,
        settings,
        applyRenderOrderSettings,
    });
    const {
        hotkeyModal,
        getCurrentHotkeys,
        saveHotkeysToStorage,
        openHotkeyEditor,
    } = createHotkeyModal({
        documentObject,
        storageObject,
        settings,
        confirmHotkeyReset,
    });

    return {
        gui,
        bindGuiFolderTitleShortcuts,
        aboutAction: {
            openAbout: () => {
                aboutOverlay.style.display = 'flex';
            },
        },
        sceneActions: {
            openRenderOrderEditor,
        },
        hotkeyActions: {
            openHotkeyEditor,
        },
        getCurrentHotkeys,
        saveHotkeysToStorage,
        elements: {
            aboutOverlay,
            renderOrderModal,
            hotkeyModal,
        },
    };
};