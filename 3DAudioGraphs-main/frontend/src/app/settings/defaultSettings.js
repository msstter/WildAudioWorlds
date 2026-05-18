import * as THREE from 'three';

const DEFAULT_TERRAIN_LOW_COLOR = '#0b3d91';
const DEFAULT_TERRAIN_HIGH_COLOR = '#f8e16c';

export const TERRAIN_AXIS_COLOR_KEYS = ['x', 'y', 'z'];
export const TERRAIN_AXIS_VALUE_MODES = ['Percent', 'Axis Values'];
export const TERRAIN_AXIS_COLOR_META = {
    x: {
        label: 'Frequency (X)',
        enabled: false,
        weight: 1.0,
        intervalCount: 3,
        intervals: [
            { endPct: 33.3, minColor: '#102a83', maxColor: '#1d4ed8' },
            { endPct: 66.7, minColor: '#0f766e', maxColor: '#2dd4bf' },
            { endPct: 100, minColor: '#92400e', maxColor: '#fde047' },
        ],
    },
    y: {
        label: 'Amplitude (Y)',
        enabled: true,
        weight: 1.0,
        intervalCount: 1,
        intervals: [
            { endPct: 100, minColor: DEFAULT_TERRAIN_LOW_COLOR, maxColor: DEFAULT_TERRAIN_HIGH_COLOR },
        ],
    },
    z: {
        label: 'Time (Z)',
        enabled: false,
        weight: 1.0,
        intervalCount: 3,
        intervals: [
            { endPct: 33.3, minColor: '#1f2937', maxColor: '#6366f1' },
            { endPct: 66.7, minColor: '#312e81', maxColor: '#ec4899' },
            { endPct: 100, minColor: '#7c2d12', maxColor: '#fb7185' },
        ],
    },
};

export const TERRAIN_TIME_WINDOW_DEFAULTS = {
    enabled: false,
    regionCount: 2,
    regions: [
        { startPct: 10, endPct: 24, tintColor: '#22c55e', strength: 0.22 },
        { startPct: 58, endPct: 74, tintColor: '#f59e0b', strength: 0.28 },
    ],
};

export const TERRAIN_PLANE_SELECTION_META = {
    xz: {
        label: 'Frequency x Time',
        axis1Key: 'x',
        axis1Label: 'Frequency',
        axis2Key: 'z',
        axis2Label: 'Time',
        tintColor: '#22c55e',
        strength: 0.24,
        axis1MinPct: 0,
        axis1MaxPct: 100,
        axis2MinPct: 14,
        axis2MaxPct: 30,
    },
    yz: {
        label: 'Amplitude x Time',
        axis1Key: 'y',
        axis1Label: 'Amplitude',
        axis2Key: 'z',
        axis2Label: 'Time',
        tintColor: '#f59e0b',
        strength: 0.24,
        axis1MinPct: 18,
        axis1MaxPct: 72,
        axis2MinPct: 38,
        axis2MaxPct: 64,
    },
    xy: {
        label: 'Frequency x Amplitude',
        axis1Key: 'x',
        axis1Label: 'Frequency',
        axis2Key: 'y',
        axis2Label: 'Amplitude',
        tintColor: '#e879f9',
        strength: 0.22,
        axis1MinPct: 22,
        axis1MaxPct: 74,
        axis2MinPct: 16,
        axis2MaxPct: 62,
    },
};

export const TERRAIN_2D_GRAPH_TYPES = ['Plot', 'Spectrogram'];
export const TERRAIN_2D_GRAPH_SURFACES = ['Back', 'Front'];
export const TERRAIN_2D_GRAPH_SHOW_MODES = ['Extended 2D Graphs', '3D Aligned 2D Graphs', 'Both'];
export const TERRAIN_HELPER_PREFERENCES = ['Prefer Precomputed', 'Prefer FFT Fallback'];
export const TERRAIN_SCULPT_OVERVIEW_MODES = ['3D Terrain', '2D Spectrogram Overview', 'Both'];
export const TERRAIN_UNSELECTED_APPEARANCE_MODES = ['Normal Surface', 'Dim Surface', 'Dim + Wiremesh', 'Wiremesh Only'];

export const getDefaultTerrain2DGraphExtension = (timeDepth = 180) => Math.max(1, (Math.round(Number(timeDepth)) - 1) * 2);

export const TERRAIN_2D_GRAPH_META = {
    xz: {
        label: 'Frequency x Time',
        enabled: false,
        showGraphsAs: '3D Aligned 2D Graphs',
        graphType: 'Plot',
        surface: 'Back',
        graphOpacity: 0.82,
        backgroundEnabled: true,
        backgroundColor: '#07131f',
        backgroundOpacity: 0.34,
        offset: 0.16,
        heatStrength: 1,
    },
    yz: {
        label: 'Amplitude x Time',
        enabled: false,
        showGraphsAs: '3D Aligned 2D Graphs',
        graphType: 'Plot',
        surface: 'Back',
        graphOpacity: 0.88,
        backgroundEnabled: true,
        backgroundColor: '#180f0a',
        backgroundOpacity: 0.32,
        offset: 0.22,
        heatStrength: 1,
    },
};

export const cloneTerrainAxisInterval = (interval) => ({
    endPct: interval.endPct,
    minColor: interval.minColor,
    maxColor: interval.maxColor,
});

export const cloneTerrainTimeWindow = (region) => ({
    startPct: region.startPct,
    endPct: region.endPct,
    tintColor: region.tintColor,
    strength: region.strength,
});

export const cloneTerrainPlaneSelection = (selection, { timbrePlaneSelectionModes = ['Box'] } = {}) => ({
    enabled: selection.enabled,
    tintColor: selection.tintColor,
    strength: selection.strength,
    axis1MinPct: selection.axis1MinPct,
    axis1MaxPct: selection.axis1MaxPct,
    axis2MinPct: selection.axis2MinPct,
    axis2MaxPct: selection.axis2MaxPct,
    selectionMode: timbrePlaneSelectionModes.includes(selection.selectionMode)
        ? selection.selectionMode
        : 'Box',
    lassoPoints: Array.isArray(selection.lassoPoints)
        ? selection.lassoPoints
            .filter((point) => point && Number.isFinite(Number(point.axis1Pct)) && Number.isFinite(Number(point.axis2Pct)))
            .map((point) => ({
                axis1Pct: Number(point.axis1Pct),
                axis2Pct: Number(point.axis2Pct),
            }))
        : [],
});

export const cloneTerrain2DGraphSettings = (graph, timeDepth = 180) => {
    const defaultExtension = getDefaultTerrain2DGraphExtension(timeDepth);
    return {
        enabled: graph.enabled,
        showGraphsAs: TERRAIN_2D_GRAPH_SHOW_MODES.includes(graph.showGraphsAs)
            ? graph.showGraphsAs
            : '3D Aligned 2D Graphs',
        graphType: TERRAIN_2D_GRAPH_TYPES.includes(graph.graphType)
            ? graph.graphType
            : TERRAIN_2D_GRAPH_TYPES[0],
        surface: TERRAIN_2D_GRAPH_SURFACES.includes(graph.surface)
            ? graph.surface
            : TERRAIN_2D_GRAPH_SURFACES[0],
        graphOpacity: THREE.MathUtils.clamp(
            Number.isFinite(Number(graph.graphOpacity)) ? Number(graph.graphOpacity) : 1,
            0,
            1,
        ),
        backgroundEnabled: graph.backgroundEnabled ?? true,
        backgroundColor: typeof graph.backgroundColor === 'string' && graph.backgroundColor
            ? graph.backgroundColor
            : '#07131f',
        backgroundOpacity: THREE.MathUtils.clamp(
            Number.isFinite(Number(graph.backgroundOpacity)) ? Number(graph.backgroundOpacity) : 0.35,
            0,
            1,
        ),
        offset: Math.max(
            0,
            Number.isFinite(Number(graph.offset)) ? Number(graph.offset) : 0,
        ),
        heatStrength: Math.max(
            0,
            Number.isFinite(Number(graph.heatStrength)) ? Number(graph.heatStrength) : 1,
        ),
        extendBefore: Math.max(
            0,
            Number.isFinite(Number(graph.extendBefore)) ? Number(graph.extendBefore) : defaultExtension,
        ),
        extendAfter: Math.max(
            0,
            Number.isFinite(Number(graph.extendAfter)) ? Number(graph.extendAfter) : defaultExtension,
        ),
    };
};

const getDefaultSelectionGrabType = (selectionGrabTypes = []) => (
    selectionGrabTypes.includes('Selection Surface')
        ? 'Selection Surface'
        : (selectionGrabTypes[0] ?? 'Selection Surface')
);

const createDefaultPlaneSelections = ({
    timbrePlaneSelectionModes = ['Box'],
    selectionGrabTypes = ['Selection Surface'],
} = {}) => ({
    showSceneHandles: true,
    showVolumeBox: true,
    grabType: getDefaultSelectionGrabType(selectionGrabTypes),
    ...Object.fromEntries(Object.entries(TERRAIN_PLANE_SELECTION_META).map(([planeKey, planeMeta]) => [
        planeKey,
        cloneTerrainPlaneSelection({
            enabled: false,
            tintColor: planeMeta.tintColor,
            strength: planeMeta.strength,
            axis1MinPct: planeMeta.axis1MinPct,
            axis1MaxPct: planeMeta.axis1MaxPct,
            axis2MinPct: planeMeta.axis2MinPct,
            axis2MaxPct: planeMeta.axis2MaxPct,
            selectionMode: 'Box',
            lassoPoints: [],
        }, { timbrePlaneSelectionModes }),
    ])),
});

const createDefaultFullTerrainPlaneSelections = ({ timbrePlaneSelectionModes = ['Box'] } = {}) => Object.fromEntries(
    Object.entries(TERRAIN_PLANE_SELECTION_META).map(([planeKey, planeMeta]) => [
        planeKey,
        cloneTerrainPlaneSelection({
            enabled: true,
            tintColor: planeMeta.tintColor,
            strength: planeMeta.strength,
            axis1MinPct: 0,
            axis1MaxPct: 100,
            axis2MinPct: 0,
            axis2MaxPct: 100,
            selectionMode: 'Box',
            lassoPoints: [],
        }, { timbrePlaneSelectionModes }),
    ]),
);

export const createDefaultTerrainAxisColors = () => Object.fromEntries(
    Object.entries(TERRAIN_AXIS_COLOR_META).map(([axisKey, axisMeta]) => [
        axisKey,
        {
            enabled: axisMeta.enabled,
            weight: axisMeta.weight,
            intervalCount: axisMeta.intervalCount,
            intervals: axisMeta.intervals.map(cloneTerrainAxisInterval),
        },
    ]),
);

export const createDefaultTerrainTimeWindows = () => ({
    enabled: TERRAIN_TIME_WINDOW_DEFAULTS.enabled,
    regionCount: TERRAIN_TIME_WINDOW_DEFAULTS.regionCount,
    regions: TERRAIN_TIME_WINDOW_DEFAULTS.regions.map(cloneTerrainTimeWindow),
});

export const createDefaultTerrainPlaneSelections = (options = {}) => ({
    ...createDefaultPlaneSelections(options),
    enabled: true,
    workflowMode: 'Sculpt Full Selection',
    overviewMode: '3D Terrain',
    fullClipTimeMinPct: 0,
    fullClipTimeMaxPct: 100,
    unselectedRegionMode: 'Dim + Wiremesh',
    unselectedRegionColor: '#09131d',
    unselectedRegionStrength: 0.76,
    unselectedWireColor: '#8de2ff',
    unselectedWireOpacity: 0.42,
    unselectedWireStep: 4,
    ...createDefaultFullTerrainPlaneSelections(options),
});

export const createDefaultTimbrePlaneSelections = (options = {}) => createDefaultPlaneSelections(options);

export const createDefaultTerrain2DGraphs = (timeDepth = 180) => Object.fromEntries(
    Object.entries(TERRAIN_2D_GRAPH_META).map(([graphKey, graphMeta]) => [
        graphKey,
        cloneTerrain2DGraphSettings(graphMeta, timeDepth),
    ]),
);

const DEFAULT_SETTINGS = {
    // Base line rendering
    showLine: true,
    deconstructiveLine: false,
    lineColor: '#00ffcc',
    enableLineScaleEnhancer: false,
    showLineThickness: true,
    lineThicknessDataColumn: 'Volume',
    lineThicknessMin: 1.0,
    lineThicknessMax: 28.0,
    showLineBrightness: false,
    lineBrightnessDataColumn: 'Volume',
    lineBrightnessMin: 0.3,
    lineBrightnessMax: 0.8,
    showLineHueRotation: true,
    lineHueDataColumn: 'Pitch',
    lineHueLowColor: '#3a4dff',
    lineHueHighColor: '#ff4a3a',
    enableLineDecay: false,
    lineDecayTailLength: 60,
    enableLineDull: false,
    lineDullTailLength: 120,
    lineDullColor: '#111111',
    enableLineBreathing: true,
    lineBreathingAmplitude: 1.0,

    // Base node rendering
    showNodes: true,
    deconstructiveNodes: false,
    showNodeScale: true,
    nodeScaleDataColumn: 'Volume',
    nodeScaleMin: 0.3,
    nodeScaleMax: 4.0,
    showNodeBrightness: false,
    nodeBrightnessDataColumn: 'Volume',
    nodeBrightnessMin: 0.3,
    nodeBrightnessMax: 0.7,
    showNodeHueRotation: true,
    nodeHueDataColumn: 'Pitch',
    hueLowColor: '#3a4dff',
    hueHighColor: '#ff4a3a',
    enableDecay: false,
    decayTailLength: 60,
    enableDull: false,
    dullTailLength: 120,
    dullColor: '#111111',
    enableBreathing: true,
    jitterIntensity: 1.0,
    enableNodeFlash: true,
    nodeFlashColor: '#fff1a8',
    nodeFlashDurationMs: 180,
    nodeFlashBrightness: 1.15,
    showSelectionMenu: false,
    showNodeSelectionMenu: false,

    // Scene
    showAxesLines: true,
    showAxesText: true,
    axesColor: '#444444',
    editAxesText: false,
    axesTextX: '',
    axesTextY: '',
    axesTextZ: '',
    renderOrderLine: 0,
    renderOrderLineEnhancer: -1,
    renderOrderNodes: 0,
    renderOrderAxes: -1,

    // Lighting
    enableLighting: true,
    nodeShading: 'Standard',
    ambientIntensity: 0.4,
    directionalIntensity: 1.5,
    directionalX: 50,
    directionalY: 100,
    directionalZ: 80,

    // Performance
    maxFPS: 60,
    renderScale: 1.0,
    maxBreathingNodes: 120,
    showLabels: true,
    showFPSMeter: false,

    // Hotkeys
    enableHotkeys: true,
    keyWheelStepSeconds: 0.25,
    keySecondStep: 1.0,
    keyFrameStepFrames: 1,
    fpvForwardFollowsLook: true,

    // Visualization mode
    visualizationMode: 'TimbreCube',
    accumulateView: false,
    enableSelectionPlaybackMask: false,

    // Method B: FFT terrain
    terrainFrequencyBins: 128,
    terrainTimeDepth: 180,
    terrainAmplitudeScale: 45,
    terrainSmoothing: 0.65,
    terrainOpacity: 0.95,
    terrainWireframe: false,
    terrainHelperPreference: 'Prefer Precomputed',

    // Terrain graph (axes)
    terrainShowAxesLines: true,
    terrainShowAxesText: true,
    terrainAxesColor: '#444444',
    terrainAxesTextFreq: 'Frequency',
    terrainAxesTextAmp: 'Amplitude',
    terrainAxesTextTime: 'Time',
    terrainAxisColorValueMode: 'Percent',
    terrainManualScaling: false,
    terrainScaleFreqMin: 0,
    terrainScaleFreqMax: 127,
    terrainScaleAmpMin: 0,
    terrainScaleAmpMax: 255,
    terrainScaleTimeMin: 0,
    terrainScaleTimeMax: 179,
    terrainAutoPadFreqPercent: 2,
    terrainAutoPadAmpPercent: 5,
    terrainStretchFreq: 1.0,
    terrainStretchAmp: 1.0,
    terrainStretchTime: 1.0,
};

export const createDefaultSettings = ({
    baseBackgroundColor = '#000000',
    baseFogColor = '#000000',
    baseFogDensity = 0.002,
    timbreOnsetDetectionModes = ['Spectral Flux'],
    timbreOnsetFlashModes = ['Onset Frames'],
    timbrePlaneSelectionModes = ['Box'],
    selectionGrabTypes = ['Selection Surface'],
} = {}) => ({
    ...DEFAULT_SETTINGS,
    timbreOnsetDetectionMode: timbreOnsetDetectionModes[0] ?? 'Spectral Flux',
    timbreOnsetSensitivity: 1.0,
    timbreOnsetThresholdMultiplier: 1.0,
    timbreOnsetFlashMode: timbreOnsetFlashModes[0] ?? 'Onset Frames',
    showTransportOnsetMarkers: true,
    showTerrainOnsetsInModel: false,
    enableTerrainOnsetEditor: false,
    backgroundColor: baseBackgroundColor,
    fogColor: baseFogColor,
    fogDensity: baseFogDensity,
    timbrePlaneSelections: createDefaultTimbrePlaneSelections({
        timbrePlaneSelectionModes,
        selectionGrabTypes,
    }),
    terrainAxisColors: createDefaultTerrainAxisColors(),
    terrainTimeWindows: createDefaultTerrainTimeWindows(),
    terrainPlaneSelections: createDefaultTerrainPlaneSelections({
        timbrePlaneSelectionModes,
        selectionGrabTypes,
    }),
    terrain2DGraphs: createDefaultTerrain2DGraphs(),
});