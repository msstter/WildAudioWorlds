import * as THREE from 'three';
import { createAnimationLoop } from './app/animationLoop.js';
import { createAppInitialization } from './app/appInitialization.js';
import { createAppInteractionBindings } from './app/appInteractionBindings.js';
import {
    BASE_BACKGROUND_COLOR,
    BASE_FOG_COLOR,
    BASE_FOG_DENSITY,
    createAppSceneShell,
} from './app/appSceneShell.js';
import { createFpvControls } from './app/fpvControls.js';
import { createAppRuntimeBindings } from './app/appRuntimeBindings.js';
import { createAppShell } from './app/appShell.js';
import {
    buildProcessCurrentAssetRequest,
    readStoredProcessCurrentAssetIncludeMfcc,
    writeStoredProcessCurrentAssetIncludeMfcc,
} from './app/processCurrentAssetControl.js';
import { createBaseGuiFolders } from './app/settings/baseGuiFolders.js';
import {
    createLineNodeGuiFolders,
    createModeAudioFolder,
    createModeTerrainGuiFolders,
} from './app/settings/statefulGuiFolders.js';
import {
    TERRAIN_2D_GRAPH_META,
    TERRAIN_2D_GRAPH_SHOW_MODES,
    TERRAIN_2D_GRAPH_SURFACES,
    TERRAIN_2D_GRAPH_TYPES,
    TERRAIN_AXIS_COLOR_KEYS,
    TERRAIN_AXIS_COLOR_META,
    TERRAIN_AXIS_VALUE_MODES,
    TERRAIN_HELPER_PREFERENCES,
    TERRAIN_PLANE_SELECTION_META,
    TERRAIN_SCULPT_OVERVIEW_MODES,
    TERRAIN_TIME_WINDOW_DEFAULTS,
    TERRAIN_UNSELECTED_APPEARANCE_MODES,
    cloneTerrainAxisInterval,
    cloneTerrainTimeWindow,
    createDefaultSettings,
    createDefaultTerrain2DGraphs,
    createDefaultTerrainAxisColors,
    createDefaultTerrainPlaneSelections,
    createDefaultTimbrePlaneSelections,
    createDefaultTerrainTimeWindows,
    getDefaultTerrain2DGraphExtension,
} from './app/settings/defaultSettings.js';
import { createAssetLoadUiSync } from './app/assetLoadUiSync.js';
import { createCameraControlPanel } from './app/cameraControlPanel.js';
import { createLivePerformanceControls } from './app/livePerformanceControls.js';
import { createRecordingControls } from './app/recordingControls.js';
import { createAudioEngine } from './audio/audioEngine.js';
import { createAudioAssetCatalog } from './data/assetManifest.js';
import { createAudioAssetLoader } from './data/assetLoader.js';
import { createSelectedAudioAssetState } from './data/selectedAssetState.js';
import { Visualizer } from './visualizer.js';
import { SpectrogramTerrain } from './spectrogramTerrain.js';
import { buildContiguousSelectionWindows, resolveFrameRecordTimeBounds as resolveSelectionFrameRecordTimeBounds } from './shared/analysis/buildSelectionWindows.js';
import {
    buildConcatenatedAudioDataFromWindows,
    buildSelectionAnalysisCsvMatrix,
    buildSelectionAnalysisIoiCsvMatrix,
    buildSelectionAnalysisPayload,
} from './shared/analysis/exportPayloads.js';
import { createSelectionExportService, buildSelectionExportFileStem } from './shared/analysis/exportService.js';
import { buildSelectionOnsetEvents, dedupeNearbyOnsetEvents } from './shared/analysis/onsetDetection.js';
import { buildInterOnsetIntervals } from './shared/analysis/interOnsetIntervals.js';
import { normalizePlaneSelectionRange, shiftPlaneSelectionWindow } from './shared/selection/planeSelectionMath.js';
import { normalizeSelectionIds as normalizeSharedSelectionIds } from './shared/selection/selectionUtils.js';
import {
    evaluateTimbreSelectionFromPlaneSettings as evaluateTimbrePlaneSelections,
    getRenderableTimbreLassoPoints as getRenderableTimbrePlaneLassoPoints,
    normalizeTimbreLassoPoints as normalizeTimbrePlaneLassoPoints,
    timbrePlaneSelectionUsesLasso,
} from './pipelines/timbre/timbrePlaneSelectionMath.js';
import { createTimbrePlaneSelectionControls } from './pipelines/timbre/timbrePlaneSelectionControls.js';
import { createTimbreSelectionActions } from './pipelines/timbre/timbreSelectionActions.js';
import { createTimbreSelectionPanel } from './pipelines/timbre/timbreSelectionPanel.js';
import { createTimbreSelectionController } from './pipelines/timbre/timbreSelectionController.js';
import { createTimbreController } from './pipelines/timbre/timbreController.js';
import { createTimbreTransportRuntime } from './pipelines/timbre/timbreTransport.js';
import { createTerrainAxes } from './pipelines/terrain/terrainAxes.js';
import { createTerrainController } from './pipelines/terrain/terrainController.js';
import { buildTerrainGraphControls, createTerrainScaleControlRegistry } from './pipelines/terrain/terrainGraphControls.js';
import {
    TERRAIN_FULL_MASK_LABEL,
    TERRAIN_RENDER_WINDOW_LABEL,
    applyTerrainFullSpaceSelection as applyTerrainFullSpaceSelectionInModel,
    buildTerrainCanonicalSelectionModel,
    createTerrainSculptStatusState,
    describeTerrainInteractionTarget as describeTerrainInteractionTargetFromModel,
    deriveTerrainVolumeSelection as deriveTerrainVolumeSelectionInModel,
    getDefaultTerrainSculptTargetLabel as getDefaultTerrainSculptTargetLabelFromModel,
    getTerrainFullClipFrameRange as getTerrainFullClipFrameRangeFromModel,
    getTerrainFullClipTimeRangePct as getTerrainFullClipTimeRangePctFromModel,
    getTerrainPlaneSelectionCoverage as getTerrainPlaneSelectionCoverageFromModel,
    getTerrainVisibleFrameWindowSnapshot as getTerrainVisibleFrameWindowSnapshotFromModel,
    formatTerrainRenderedSliceLabel as formatTerrainRenderedSliceLabelFromModel,
    resolveTerrainSculptTargetLabel,
    syncTerrainDisplayedTimeRangesFromFullClipSelection as syncTerrainDisplayedTimeRangesFromFullClipSelectionInModel,
    syncTerrainFullClipTimeSelectionFromDisplayedPlanes as syncTerrainFullClipTimeSelectionFromDisplayedPlanesInModel,
    terrainFrameIndexToFullClipPct as terrainFrameIndexToFullClipPctFromModel,
    terrainFullClipFrameRangeToVisibleDepthPctRange as terrainFullClipFrameRangeToVisibleDepthPctRangeFromModel,
    terrainSelectionSpaceLabel as terrainSelectionSpaceLabelFromModel,
    terrainVisibleDepthPctToFrameIndex as terrainVisibleDepthPctToFrameIndexFromModel,
} from './pipelines/terrain/selection/terrainSelectionModel.js';
import { createTerrainSculptOverviewController } from './pipelines/terrain/terrainSculptOverview.js';
import { createTerrainSelectionController } from './pipelines/terrain/terrainSelectionController.js';
import { createDialogService } from './shared/ui/dialogService.js';
import { createTransportMarkerLayer } from './shared/ui/transportMarkers.js';
import { CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js';

const desktopBridge = globalThis.desktopBridge ?? null;
const backendCallMonitorIpc = desktopBridge?.backend ?? null;
let suppressBackendCallMonitorSyncDepth = 0;
let awaitingInitialLocalIntegrationState = !!backendCallMonitorIpc;
let localIntegrationApplyChain = Promise.resolve();
let localIntegrationHydrationPromise = null;

const BUNDLED_ASSET_MANIFEST_URL = './audio_assets_manifest.json';
const BUNDLED_ASSET_SOURCE_LABEL = 'Bundled Assets';
const AUDIO_ASSET_FOLDER_STORAGE_KEY = '3d-audio-maker.asset-folder-path';

const timbreSelectionDialogService = createDialogService();
const {
    scene,
    camera,
    renderer,
    labelRenderer,
    fpsMeter,
    controls,
    ambientLight,
    directionalLight,
    floatingPanelDragManager,
    elements: {
        terrainHelperBadge,
        timbreSelectionBadge,
        timbreSelectionTitle,
        timbreSelectionMeta,
        timbreSelectionRange,
        timbreSelectionStats,
        timbreSelectionPanel,
        timbreSelectionPanelSubtitle,
        timbreSelectionPanelTabBar,
        timbreSelectionPanelBody,
        terrainSculptOverviewPanel,
        terrainSculptOverviewMeta,
        terrainSculptOverviewCanvas,
        terrainSculptOverviewStatus,
        terrainSculptOverviewFooter,
    },
} = createAppSceneShell();

const trajectoryVisualizer = new Visualizer(scene);
const terrainVisualizer = new SpectrogramTerrain(scene, {
    binCount: 128,
    timeDepth: 180,
});
terrainVisualizer.setVisible(false);

const terrainOnsetOverlayGroup = new THREE.Group();
terrainOnsetOverlayGroup.name = 'TerrainOnsetOverlay';
terrainOnsetOverlayGroup.visible = false;
terrainVisualizer.group.add(terrainOnsetOverlayGroup);

const timbreSelectionRaycaster = new THREE.Raycaster();
const terrainOnsetRaycaster = new THREE.Raycaster();
const timbreSelectionPointer = new THREE.Vector2();
const terrainOnsetPointer = new THREE.Vector2();
const TIMBRE_SELECTION_CLICK_DISTANCE_PX = 6;
const TIMBRE_ONSET_RESET_MIN_SEC = 0.75;
const TERRAIN_ONSET_SELECTION_MIN_SEC = 0.12;
const BIOACOUSTICS_WORKBOOK_ONSET_METHOD = 'Bioacoustics Workbook';
const BIOACOUSTICS_IMPORT_ACTION = 'bioacoustics-import-workbook';
const BIOACOUSTICS_SYNC_ACTION = 'bioacoustics-sync-workbook';
const TIMBRE_ONSET_DETECTION_MODES = ['Spectral Flux', 'Volume Delta', BIOACOUSTICS_WORKBOOK_ONSET_METHOD];
const TIMBRE_ONSET_FLASH_MODES = ['Onset Frames', 'Full Onset Window'];
const TIMBRE_LASSO_CLOSE_DISTANCE_PCT = 4;
const TIMBRE_LASSO_MAX_POINTS = 96;
const TIMBRE_PLANE_SELECTION_MODES = ['Box', 'Lasso'];
const TERRAIN_SELECTION_GRAB_TYPES = ['Center Node', 'Selection Surface'];
const TERRAIN_SELECTION_WORKFLOW_MODES = ['Sculpt Full Selection', 'Manual Plane Selection'];
const TERRAIN_SELECTION_EDGE_HANDLE_ROLES = ['axis1Min', 'axis1Max', 'axis2Min', 'axis2Max'];
const TERRAIN_SELECTION_CORNER_HANDLE_ROLES = ['cornerMinMin', 'cornerMaxMin', 'cornerMinMax', 'cornerMaxMax'];
const TERRAIN_SELECTION_HANDLE_ROLES = [
    ...TERRAIN_SELECTION_EDGE_HANDLE_ROLES,
    ...TERRAIN_SELECTION_CORNER_HANDLE_ROLES,
    'center',
];
let appInteractionBindings = null;
let selectedTimbreInstanceIds = [];
let manualTimbreInstanceIds = [];
let boxTimbreSelectionInstanceIds = [];
let timbreSelectionUi = null;
const assetSourceUiState = {
    assetSourceLabel: BUNDLED_ASSET_SOURCE_LABEL,
    chooseAssetFolder: async () => {},
    useBundledAssets: async () => {},
    processCurrentAssetIncludeMfcc: readStoredProcessCurrentAssetIncludeMfcc(),
    processCurrentAsset: async () => {},
};
const liveSourceUiState = {
    liveStatus: 'Inactive',
    toggleLiveSource: async () => {},
};
let livePerformanceControls = null;
let liveStatusController = null;
let liveActionController = null;
let processCurrentAssetIncludeMfccController = null;
let processCurrentAssetController = null;
let stopLiveSourceSession = async () => false;
let liveRestoreAsset = null;
let timbreSelectionController = null;
let terrainSelectionController = null;
const progressBar = document.getElementById('progress-bar');
const timbreTransportMarkers = createTransportMarkerLayer({ progressElement: progressBar });

timbreTransportMarkers.ensureLayerElement();

const getActiveTimbreLassoDraw = () => timbreSelectionController?.getActiveLassoDraw?.() ?? null;
const isTimbrePlaneSelectionDragging = () => !!timbreSelectionController?.isDragging?.();
const timbreSelectionAnalysis = {
    contiguousWindows: [],
    onsetEvents: [],
    interOnsetIntervals: [],
    onsetMethod: TIMBRE_ONSET_DETECTION_MODES[0],
    lastPlaybackTimeSec: null,
};
const bioacousticsImportedOnsetState = {
    assetId: '',
    workbookPath: '',
    matchedFileName: '',
    onsetTimes: [],
    importedAt: null,
};
const terrainOnsetEditorState = {
    overlayDirty: true,
    overridesByTargetKey: new Map(),
    selectedTargetKey: '',
    selectedOnsetId: '',
    drag: null,
    nextOnsetId: 1,
};
const buildDefaultSettings = () => createDefaultSettings({
    baseBackgroundColor: BASE_BACKGROUND_COLOR,
    baseFogColor: BASE_FOG_COLOR,
    baseFogDensity: BASE_FOG_DENSITY,
    timbreOnsetDetectionModes: TIMBRE_ONSET_DETECTION_MODES,
    timbreOnsetFlashModes: TIMBRE_ONSET_FLASH_MODES,
    timbrePlaneSelectionModes: TIMBRE_PLANE_SELECTION_MODES,
    selectionGrabTypes: TERRAIN_SELECTION_GRAB_TYPES,
});

const settings = buildDefaultSettings();
const modifierColumnOptions = ['Volume', 'Pitch'];
const appShell = createAppShell({
    settings,
    applyRenderOrderSettings: () => applyRenderOrderSettings(),
    confirmHotkeyReset: () => confirmTimbreDialogAction({
        title: 'Reset Hotkeys',
        message: 'Reset all hotkeys to their default bindings?',
        confirmLabel: 'Reset Hotkeys',
    }),
});
const {
    gui,
    bindGuiFolderTitleShortcuts,
    aboutAction,
    sceneActions,
    hotkeyActions,
    getCurrentHotkeys,
    saveHotkeysToStorage,
    elements: {
        aboutOverlay,
        renderOrderModal,
        hotkeyModal,
    },
} = appShell;
gui.add(aboutAction, 'openAbout').name('About This App');

const selectedAudioAssetState = createSelectedAudioAssetState();
const getSelectedAudioAsset = () => selectedAudioAssetState.getSelectedAsset();
const getSelectedAudioAssetId = (fallback = '') => selectedAudioAssetState.getSelectedAssetId(fallback);
const getSelectedAudioAssetLabel = (fallback = '') => selectedAudioAssetState.getSelectedAssetLabel(fallback);
const getSelectedAudioFileName = (fallback = '') => {
    const audioUrl = String(getSelectedAudioAsset()?.audioUrl || '').split('?', 1)[0].split('#', 1)[0];
    if (!audioUrl) return fallback;
    const pathSegments = audioUrl.split('/').filter(Boolean);
    return pathSegments[pathSegments.length - 1] || fallback;
};

const setGuiSmokeAttribute = (target, attributeName, attributeValue) => {
    if (!target || typeof target.setAttribute !== 'function') return;
    target.setAttribute(attributeName, attributeValue);
};

const syncProcessCurrentAssetSmokeState = (selectedAsset = getSelectedAudioAsset()) => {
    const bodyDataset = document.body?.dataset;
    if (!bodyDataset) return;

    bodyDataset.wawProcessCurrentAssetIncludeMfcc = String(!!assetSourceUiState.processCurrentAssetIncludeMfcc);

    const normalizedAsset = selectedAsset && typeof selectedAsset === 'object' && !Array.isArray(selectedAsset)
        ? selectedAsset
        : null;
    if (!normalizedAsset) {
        bodyDataset.wawSelectedAssetReady = 'false';
        delete bodyDataset.wawSelectedAssetId;
        delete bodyDataset.wawSelectedRevisionId;
        delete bodyDataset.wawSelectedAssetHasMfcc;
        return;
    }

    bodyDataset.wawSelectedAssetReady = 'true';
    bodyDataset.wawSelectedAssetId = String(normalizedAsset.id || '').trim();
    bodyDataset.wawSelectedRevisionId = String(
        normalizedAsset.revisionId || normalizedAsset.activeRevisionId || normalizedAsset.id || '',
    ).trim();
    bodyDataset.wawSelectedAssetHasMfcc = String(!!String(normalizedAsset.mfccCsvUrl || '').trim());
};

const fModeAudio = createModeAudioFolder({ gui });
setGuiSmokeAttribute(fModeAudio?.domElement, 'data-waw-folder', 'mode-audio');
const assetSourceLabelController = fModeAudio.add(assetSourceUiState, 'assetSourceLabel').name('Asset Source');
assetSourceLabelController.listen?.();
const assetSourceLabelInput = assetSourceLabelController.domElement?.querySelector?.('input');
if (assetSourceLabelInput) {
    assetSourceLabelInput.readOnly = true;
    assetSourceLabelInput.style.pointerEvents = 'none';
}
fModeAudio.add(assetSourceUiState, 'chooseAssetFolder').name('Choose Asset Folder');
fModeAudio.add(assetSourceUiState, 'useBundledAssets').name('Use Bundled Assets');
processCurrentAssetIncludeMfccController = fModeAudio.add(assetSourceUiState, 'processCurrentAssetIncludeMfcc').name('Regenerate MFCC');
setGuiSmokeAttribute(processCurrentAssetIncludeMfccController?.domElement, 'data-waw-control', 'process-current-asset-include-mfcc');
processCurrentAssetIncludeMfccController.listen?.();
processCurrentAssetIncludeMfccController.onChange?.((nextValue) => {
    writeStoredProcessCurrentAssetIncludeMfcc(nextValue);
    syncProcessCurrentAssetSmokeState();
});
processCurrentAssetController = fModeAudio.add(assetSourceUiState, 'processCurrentAsset').name('Process Current Asset');
setGuiSmokeAttribute(processCurrentAssetController?.domElement, 'data-waw-control', 'process-current-asset');
syncProcessCurrentAssetSmokeState(null);

const rebuildLiveSourceGuiControllers = () => {
    if (liveStatusController) {
        fModeAudio.remove(liveStatusController);
        liveStatusController = null;
    }
    if (liveActionController) {
        fModeAudio.remove(liveActionController);
        liveActionController = null;
    }

    liveStatusController = fModeAudio.add(liveSourceUiState, 'liveStatus').name('Live Status');
    liveStatusController.listen?.();
    const liveStatusInput = liveStatusController.domElement?.querySelector?.('input');
    if (liveStatusInput) {
        liveStatusInput.readOnly = true;
        liveStatusInput.style.pointerEvents = 'none';
    }

    liveActionController = fModeAudio.add(liveSourceUiState, 'toggleLiveSource').name('Live Source');
};

const audioEngine = createAudioEngine({
    getAnalyserFftSize: () => settings.terrainFrequencyBins * 2,
    getPlaybackMaskGainAttacher: () => attachTimbrePlaybackMaskGain,
    onContextReady: () => {
        resetTrajectoryPlaybackAnchor();
        updateSelectionPlaybackMask();
    },
});
const {
    audio,
    createRecordingDestination,
    decodeAudioData,
    disconnectRecordingDestination,
    ensureAudioContext,
    getAudioContext,
    readFrequencyFrame,
    syncAnalyserBinCount,
} = audioEngine;
const audioAssetCatalog = createAudioAssetCatalog({
    folder: fModeAudio,
    audioSourceState: selectedAudioAssetState.getAudioSourceState(),
    onSelectAsset: async (asset) => {
        await loadAudioAsset(asset);
    },
    onManifestUnavailable: (error) => {
        console.warn('Audio assets manifest unavailable. No bundled audio assets were loaded.', error);
    },
    manifestUrl: BUNDLED_ASSET_MANIFEST_URL,
});
let currentCustomAudioAssetFolderPath = '';

const normalizeAssetFolderPath = (value = '') => String(value || '').trim().replace(/[\\/]+$/, '');

const readStoredAudioAssetFolderPath = () => {
    try {
        return normalizeAssetFolderPath(window.localStorage.getItem(AUDIO_ASSET_FOLDER_STORAGE_KEY) || '');
    } catch (_error) {
        return '';
    }
};

const writeStoredAudioAssetFolderPath = (folderPath) => {
    try {
        const normalizedPath = normalizeAssetFolderPath(folderPath);
        if (normalizedPath) {
            window.localStorage.setItem(AUDIO_ASSET_FOLDER_STORAGE_KEY, normalizedPath);
        } else {
            window.localStorage.removeItem(AUDIO_ASSET_FOLDER_STORAGE_KEY);
        }
    } catch (_error) {
        // Ignore storage failures so asset loading still works in private or restricted sessions.
    }
};

const updateAssetSourceLabel = (label) => {
    assetSourceUiState.assetSourceLabel = typeof label === 'string' && label.trim() !== ''
        ? label.trim()
        : BUNDLED_ASSET_SOURCE_LABEL;
    assetSourceLabelController.updateDisplay?.();
};

const buildAssetManifestUrlFromFolderPath = (folderPath) => {
    const normalizedPath = normalizeAssetFolderPath(folderPath);
    if (!normalizedPath) return null;
    return desktopBridge?.buildAssetManifestUrl?.(normalizedPath) ?? null;
};

const showNativeOpenDialog = async (dialogOptions = {}) => {
    if (!backendCallMonitorIpc) {
        console.warn('Native open dialog is available only inside the Electron app shell.');
        return { canceled: true, filePaths: [] };
    }

    try {
        return await backendCallMonitorIpc.invoke('backend-call:show-open-dialog', dialogOptions);
    } catch (error) {
        console.error('Failed to open native file dialog:', error);
        return { canceled: true, filePaths: [] };
    }
};

const importRecordedAudioAsset = async ({
    assetLabel = 'Recorded Session',
    audioBlob,
    includeMfcc = true,
    suggestedFileStem = 'recorded-audio',
} = {}, reportProgress = () => {}) => {
    if (!backendCallMonitorIpc) {
        throw new Error('Recorded asset import is available only inside the Electron app shell.');
    }
    if (!(audioBlob instanceof Blob)) {
        throw new Error('Recorded asset import is missing an audio blob.');
    }

    reportProgress({ value: 45, label: 'Saving audio file...' });
    const audioBuffer = await audioBlob.arrayBuffer();

    reportProgress({
        value: 65,
        label: includeMfcc
            ? 'Analyzing FFT and MFCC data...'
            : 'Analyzing FFT data...',
    });
    const response = await backendCallMonitorIpc.invoke('recorded-audio:import', {
        assetLabel,
        audioBuffer,
        includeMfcc,
        fileStem: suggestedFileStem,
    });
    if (!response?.ok) {
        throw new Error(response?.error || 'Recorded asset import failed.');
    }

    if (!includeMfcc) {
        settings.visualizationMode = 'SpectroTerrain';
    }
    gui.controllersRecursive().forEach((controller) => controller.updateDisplay());

    reportProgress({ value: 85, label: 'Reloading Audio/Data list...' });
    const manifestResult = await applyAudioAssetManifestSource({
        manifestUrl: BUNDLED_ASSET_MANIFEST_URL,
        sourceLabel: BUNDLED_ASSET_SOURCE_LABEL,
        assetFolderPath: '',
        persistSelection: true,
        preferredAssetId: response?.asset?.id || getSelectedAudioAssetId(''),
    });
    if (!manifestResult?.ok) {
        throw new Error(manifestResult?.error || 'Recorded asset imported, but the manifest could not be reloaded.');
    }

    reportProgress({ value: 95, label: 'Rendering imported asset...' });
    return response;
};

const loadPreferredAudioAssetFromCatalog = async (preferredAssetId = getSelectedAudioAssetId('')) => {
    const availableAssets = audioAssetCatalog.getAvailableAudioAssets();
    const nextAsset = availableAssets.find((asset) => asset.id === preferredAssetId) || availableAssets[0] || null;
    if (nextAsset) {
        await loadAudioAsset(nextAsset, { allowAccumulate: false });
    } else {
        clearLoadedAudioAssetState();
    }
    return nextAsset;
};

const applyAudioAssetManifestSource = async ({
    manifestUrl,
    sourceLabel = BUNDLED_ASSET_SOURCE_LABEL,
    assetFolderPath = '',
    persistSelection = true,
    preferredAssetId = getSelectedAudioAssetId(''),
} = {}) => {
    if (livePerformanceControls?.isActive?.()) {
        await stopLiveSourceSession({ restoreAsset: false, closeModal: true });
    }

    const previousSource = audioAssetCatalog.getManifestSource();
    const previousSourceLabel = assetSourceUiState.assetSourceLabel;
    const previousAssetFolderPath = currentCustomAudioAssetFolderPath;

    audioAssetCatalog.setManifestSource({ manifestUrl, sourceLabel });
    updateAssetSourceLabel(sourceLabel);

    const result = await audioAssetCatalog.loadManifest();
    if (!result.ok) {
        audioAssetCatalog.setManifestSource(previousSource);
        currentCustomAudioAssetFolderPath = previousAssetFolderPath;
        updateAssetSourceLabel(previousSourceLabel);

        await audioAssetCatalog.loadManifest(previousSource);
        rebuildLiveSourceGuiControllers();
        await loadPreferredAudioAssetFromCatalog(preferredAssetId);
        return result;
    }

    currentCustomAudioAssetFolderPath = normalizeAssetFolderPath(assetFolderPath);
    updateAssetSourceLabel(result.sourceLabel);
    rebuildLiveSourceGuiControllers();
    await loadPreferredAudioAssetFromCatalog(preferredAssetId);

    if (persistSelection) {
        writeStoredAudioAssetFolderPath(currentCustomAudioAssetFolderPath);
    }

    return result;
};

const withBackendCallMonitorSyncSuppressed = async (callback) => {
    suppressBackendCallMonitorSyncDepth += 1;
    try {
        return await callback();
    } finally {
        suppressBackendCallMonitorSyncDepth = Math.max(0, suppressBackendCallMonitorSyncDepth - 1);
    }
};

const normalizeLocalIntegrationSourcePath = (sourceAudioPath = '') => {
    const normalizedSourceAudioPath = String(sourceAudioPath || '').trim();
    if (!normalizedSourceAudioPath) return '';

    try {
        const parsed = new URL(normalizedSourceAudioPath, window.location.href);
        if (parsed.protocol === 'file:') {
            let pathname = decodeURIComponent(parsed.pathname || '');
            if (/^\/[A-Za-z]:\//.test(pathname)) {
                pathname = pathname.slice(1);
            }
            return pathname.replace(/\\/g, '/');
        }
    } catch (_error) {
        // Fall back to the raw path-like value below.
    }

    return normalizedSourceAudioPath.replace(/\\/g, '/');
};

const normalizeLocalIntegrationSourceKey = (sourceAudioPath = '') => (
    normalizeLocalIntegrationSourcePath(sourceAudioPath).toLowerCase()
);

const resolveCanonicalSelectionTimeRangeSec = (selectionWindow = null) => {
    const normalizedSelectionWindow = selectionWindow && typeof selectionWindow === 'object' && !Array.isArray(selectionWindow)
        ? selectionWindow
        : {};
    const rawTimeRange = normalizedSelectionWindow.timeRangeSec;
    if (Array.isArray(rawTimeRange) && rawTimeRange.length >= 2) {
        const start = Number(rawTimeRange[0]);
        const end = Number(rawTimeRange[1]);
        if (Number.isFinite(start) && Number.isFinite(end)) {
            return { start, end };
        }
    }
    if (rawTimeRange && typeof rawTimeRange === 'object') {
        const start = Number(rawTimeRange.start);
        const end = Number(rawTimeRange.end);
        if (Number.isFinite(start) && Number.isFinite(end)) {
            return { start, end };
        }
    }
    return null;
};

const resolveCanonicalSelectionTimePctRange = (selectionWindow = null) => {
    const normalizedSelectionWindow = selectionWindow && typeof selectionWindow === 'object' && !Array.isArray(selectionWindow)
        ? selectionWindow
        : {};
    const fullClipTimePctRange = normalizedSelectionWindow.fullClipTimePctRange;
    if (fullClipTimePctRange && typeof fullClipTimePctRange === 'object') {
        const minPct = Number(fullClipTimePctRange.minPct);
        const maxPct = Number(fullClipTimePctRange.maxPct);
        if (Number.isFinite(minPct) && Number.isFinite(maxPct)) {
            return {
                minPct: THREE.MathUtils.clamp(Math.min(minPct, maxPct), 0, 100),
                maxPct: THREE.MathUtils.clamp(Math.max(minPct, maxPct), 0, 100),
            };
        }
    }

    const timeRangeSec = resolveCanonicalSelectionTimeRangeSec(normalizedSelectionWindow);
    const durationSec = Math.max(
        Number(audio.duration) || 0,
        Number(getSelectedAudioAsset()?.analysisClipDurationSec) || 0,
    );
    if (!timeRangeSec || durationSec <= 0) {
        return null;
    }

    return {
        minPct: THREE.MathUtils.clamp((Math.min(timeRangeSec.start, timeRangeSec.end) / durationSec) * 100, 0, 100),
        maxPct: THREE.MathUtils.clamp((Math.max(timeRangeSec.start, timeRangeSec.end) / durationSec) * 100, 0, 100),
    };
};

const resolveCanonicalSelectionFrequencyPctRange = (selectionWindow = null) => {
    const terrainVolumeBoundsPct = selectionWindow?.terrainVolumeBoundsPct;
    if (terrainVolumeBoundsPct && typeof terrainVolumeBoundsPct === 'object') {
        const minPct = Number(terrainVolumeBoundsPct.xMinPct);
        const maxPct = Number(terrainVolumeBoundsPct.xMaxPct);
        if (Number.isFinite(minPct) && Number.isFinite(maxPct)) {
            return {
                minPct: THREE.MathUtils.clamp(Math.min(minPct, maxPct), 0, 100),
                maxPct: THREE.MathUtils.clamp(Math.max(minPct, maxPct), 0, 100),
            };
        }
    }

    return {
        minPct: 0,
        maxPct: 100,
    };
};

const resolveCanonicalAudioAssetFromCatalog = (canonicalAsset = null) => {
    const normalizedCanonicalAsset = canonicalAsset && typeof canonicalAsset === 'object' && !Array.isArray(canonicalAsset)
        ? canonicalAsset
        : {};
    const canonicalAssetId = String(normalizedCanonicalAsset.assetId || '').trim();
    const canonicalSourceKey = normalizeLocalIntegrationSourceKey(normalizedCanonicalAsset.sourceAudioPath);
    const candidateAssets = [
        getSelectedAudioAsset(),
        ...audioAssetCatalog.getAvailableAudioAssets(),
    ].filter(Boolean);

    return candidateAssets.find((asset) => {
        const assetId = String(asset?.id || '').trim();
        const assetSourceKey = normalizeLocalIntegrationSourceKey(asset?.audioUrl || '');
        if (canonicalAssetId && assetId === canonicalAssetId) {
            return true;
        }
        return !!canonicalSourceKey && assetSourceKey === canonicalSourceKey;
    }) || null;
};

const deriveCanonicalAssetFolderPath = (canonicalAsset = null) => {
    const sourcePath = normalizeLocalIntegrationSourcePath(canonicalAsset?.sourceAudioPath || '');
    if (!sourcePath) return '';
    const lastSeparatorIndex = Math.max(sourcePath.lastIndexOf('/'), sourcePath.lastIndexOf('\\'));
    return lastSeparatorIndex >= 0 ? sourcePath.slice(0, lastSeparatorIndex) : '';
};

const reloadCurrentAudioAssetManifest = async (preferredAssetId = getSelectedAudioAssetId('')) => {
    const currentManifestSource = audioAssetCatalog.getManifestSource?.() || {};
    return applyAudioAssetManifestSource({
        manifestUrl: currentManifestSource.manifestUrl || BUNDLED_ASSET_MANIFEST_URL,
        sourceLabel: currentManifestSource.sourceLabel || assetSourceUiState.assetSourceLabel || BUNDLED_ASSET_SOURCE_LABEL,
        assetFolderPath: currentCustomAudioAssetFolderPath,
        persistSelection: false,
        preferredAssetId,
    });
};

const ensureCanonicalAudioAssetAvailable = async (canonicalAsset = null) => {
    const normalizedCanonicalAsset = canonicalAsset && typeof canonicalAsset === 'object' && !Array.isArray(canonicalAsset)
        ? canonicalAsset
        : {};
    const preferredAssetId = String(normalizedCanonicalAsset.assetId || '').trim() || getSelectedAudioAssetId('');
    let resolvedAsset = resolveCanonicalAudioAssetFromCatalog(normalizedCanonicalAsset);
    const currentSelectedAsset = getSelectedAudioAsset();
    const selectedRevisionId = String(currentSelectedAsset?.revisionId || currentSelectedAsset?.activeRevisionId || currentSelectedAsset?.id || '').trim();
    const canonicalRevisionId = String(normalizedCanonicalAsset.activeRevisionId || normalizedCanonicalAsset.assetId || '').trim();
    const needsRevisionRefresh = !!resolvedAsset && !!canonicalRevisionId && selectedRevisionId && canonicalRevisionId !== selectedRevisionId;
    if (resolvedAsset && !needsRevisionRefresh) {
        return resolvedAsset;
    }

    const canonicalAssetFolderPath = deriveCanonicalAssetFolderPath(normalizedCanonicalAsset);
    const manifestUrl = canonicalAssetFolderPath && desktopBridge?.buildAssetManifestUrl
        ? desktopBridge.buildAssetManifestUrl(canonicalAssetFolderPath)
        : null;
    if (manifestUrl) {
        const manifestResult = await applyAudioAssetManifestSource({
            manifestUrl,
            sourceLabel: `Folder: ${canonicalAssetFolderPath}`,
            assetFolderPath: canonicalAssetFolderPath,
            persistSelection: false,
            preferredAssetId,
        });
        if (manifestResult?.ok) {
            resolvedAsset = resolveCanonicalAudioAssetFromCatalog(normalizedCanonicalAsset);
        }
    }

    if (!resolvedAsset || needsRevisionRefresh) {
        const manifestResult = await reloadCurrentAudioAssetManifest(preferredAssetId);
        if (manifestResult?.ok) {
            resolvedAsset = resolveCanonicalAudioAssetFromCatalog(normalizedCanonicalAsset);
        }
    }

    return resolvedAsset;
};

const applyCanonicalLocalIntegrationAsset = async (canonicalAsset = null) => {
    const normalizedCanonicalAsset = canonicalAsset && typeof canonicalAsset === 'object' && !Array.isArray(canonicalAsset)
        ? canonicalAsset
        : {};
    if (!normalizedCanonicalAsset.assetId && !normalizedCanonicalAsset.sourceAudioPath) {
        if (getSelectedAudioAsset()) {
            clearLoadedAudioAssetState();
        }
        return;
    }

    const resolvedAsset = await ensureCanonicalAudioAssetAvailable(normalizedCanonicalAsset);
    if (!resolvedAsset) {
        return;
    }

    const selectedAsset = getSelectedAudioAsset();
    const selectedRevisionId = String(selectedAsset?.revisionId || selectedAsset?.activeRevisionId || selectedAsset?.id || '').trim();
    const resolvedRevisionId = String(resolvedAsset?.revisionId || resolvedAsset?.activeRevisionId || resolvedAsset?.id || '').trim();
    if (selectedAsset?.id === resolvedAsset?.id && selectedRevisionId === resolvedRevisionId) {
        return;
    }

    await loadAudioAsset(resolvedAsset, { allowAccumulate: false });
};

const applyCanonicalLocalIntegrationSelectionWindow = async (selectionWindow = null) => {
    const normalizedSelectionWindow = selectionWindow && typeof selectionWindow === 'object' && !Array.isArray(selectionWindow)
        ? selectionWindow
        : {};
    if (!normalizedSelectionWindow.isReady) {
        clearAllTimbreSelections();
        return;
    }

    const timePctRange = resolveCanonicalSelectionTimePctRange(normalizedSelectionWindow);
    if (!timePctRange) {
        return;
    }
    const frequencyPctRange = resolveCanonicalSelectionFrequencyPctRange(normalizedSelectionWindow);
    applyTerrainOverviewSelection({
        timeMinPct: timePctRange.minPct,
        timeMaxPct: timePctRange.maxPct,
        frequencyMinPct: frequencyPctRange.minPct,
        frequencyMaxPct: frequencyPctRange.maxPct,
    });
};

const applyCanonicalLocalIntegrationPlayhead = (playheadSec) => {
    const normalizedPlayheadSec = Number(playheadSec);
    if (!Number.isFinite(normalizedPlayheadSec)) {
        return;
    }

    const nextPlayheadSec = Math.max(0, normalizedPlayheadSec);
    if (Math.abs((audio.currentTime || 0) - nextPlayheadSec) < 0.05) {
        return;
    }

    audio.currentTime = nextPlayheadSec;
    resetTrajectoryPlaybackAnchor(audio.currentTime);
    syncVisualizerToCurrentTime();
};

const applyCanonicalLocalIntegrationAudioManagerState = async (audioManagerState = null) => {
    const normalizedAudioManagerState = audioManagerState && typeof audioManagerState === 'object' && !Array.isArray(audioManagerState)
        ? audioManagerState
        : {};
    const transportState = normalizedAudioManagerState.transportState && typeof normalizedAudioManagerState.transportState === 'object' && !Array.isArray(normalizedAudioManagerState.transportState)
        ? normalizedAudioManagerState.transportState
        : {};

    await withBackendCallMonitorSyncSuppressed(async () => {
        await applyCanonicalLocalIntegrationAsset(normalizedAudioManagerState.asset || null);
        await applyCanonicalLocalIntegrationSelectionWindow(transportState.selectionWindow || null);
        applyCanonicalLocalIntegrationPlayhead(transportState.playheadSec);
    });
};

const queueCanonicalLocalIntegrationApply = (audioManagerState = null) => {
    localIntegrationApplyChain = localIntegrationApplyChain
        .then(() => applyCanonicalLocalIntegrationAudioManagerState(audioManagerState))
        .catch((error) => {
            console.warn('Failed to apply canonical local-integration state:', error);
        });
    return localIntegrationApplyChain;
};

const hydrateCanonicalLocalIntegrationState = () => {
    if (!backendCallMonitorIpc) {
        awaitingInitialLocalIntegrationState = false;
        return Promise.resolve();
    }
    if (localIntegrationHydrationPromise) {
        return localIntegrationHydrationPromise;
    }

    localIntegrationHydrationPromise = backendCallMonitorIpc.invoke('local-integration:get-state')
        .then((response) => {
            if (response?.ok === false) {
                throw new Error(response?.error || 'Failed to hydrate canonical local-integration state.');
            }
            return queueCanonicalLocalIntegrationApply(response?.audioManager || null);
        })
        .catch((error) => {
            console.warn('Failed to hydrate canonical local-integration state:', error);
        })
        .finally(() => {
            awaitingInitialLocalIntegrationState = false;
            localIntegrationHydrationPromise = null;
            syncBackendCallMonitorState();
        });

    return localIntegrationHydrationPromise;
};

assetSourceUiState.chooseAssetFolder = async () => {
    const response = await showNativeOpenDialog({
        title: 'Choose Asset Folder',
        properties: ['openDirectory'],
        defaultPath: currentCustomAudioAssetFolderPath || readStoredAudioAssetFolderPath() || undefined,
    });

    if (response?.canceled) return;

    const nextFolderPath = normalizeAssetFolderPath(response?.filePaths?.[0] || '');
    const manifestUrl = buildAssetManifestUrlFromFolderPath(nextFolderPath);
    if (!manifestUrl) {
        console.warn('Selected asset folder path is unavailable or could not be converted into a manifest URL.', nextFolderPath);
        return;
    }

    const result = await applyAudioAssetManifestSource({
        manifestUrl,
        sourceLabel: `Folder: ${nextFolderPath}`,
        assetFolderPath: nextFolderPath,
        persistSelection: true,
    });
    if (!result.ok) {
        console.error('Selected asset folder could not be loaded. Expected audio_assets_manifest.json inside the chosen folder.', result.error);
    }
};

assetSourceUiState.useBundledAssets = async () => {
    const result = await applyAudioAssetManifestSource({
        manifestUrl: BUNDLED_ASSET_MANIFEST_URL,
        sourceLabel: BUNDLED_ASSET_SOURCE_LABEL,
        assetFolderPath: '',
        persistSelection: true,
    });
    if (!result.ok) {
        console.error('Bundled audio asset manifest could not be loaded.', result.error);
    }
};

assetSourceUiState.processCurrentAsset = async () => {
    await processCurrentGraphAsset();
};

const isTerrainMode = () => settings.visualizationMode === 'SpectroTerrain';

const formatSelectionTimestamp = (timeSec) => {
    if (!Number.isFinite(timeSec)) return 'n/a';
    return `${timeSec.toFixed(3)}s`;
};

const hasImportedBioacousticsWorkbookOnsets = (assetId = getSelectedAudioAssetId('')) => {
    const normalizedAssetId = String(assetId || '').trim();
    return !!normalizedAssetId
        && bioacousticsImportedOnsetState.assetId === normalizedAssetId
        && Array.isArray(bioacousticsImportedOnsetState.onsetTimes)
        && bioacousticsImportedOnsetState.onsetTimes.length > 0;
};

const getTimbreRecordsForInstanceIds = (instanceIds) => normalizeTimbreSelectionIds(instanceIds)
    .map((instanceId) => ({
        instanceId,
        frameRecord: trajectoryVisualizer.getFrameRecordForInstanceId(instanceId),
    }))
    .filter((entry) => entry.frameRecord);

const getAllTimbreRecords = () => {
    if (Array.isArray(trajectoryVisualizer.frameRecords) && trajectoryVisualizer.frameRecords.length > 0) {
        return trajectoryVisualizer.frameRecords
            .map((frameRecord, instanceId) => ({ instanceId, frameRecord }))
            .filter((entry) => entry.frameRecord);
    }

    return trajectoryVisualizer.points
        .map((_, instanceId) => ({
            instanceId,
            frameRecord: trajectoryVisualizer.getFrameRecordForInstanceId(instanceId),
        }))
        .filter((entry) => entry.frameRecord);
};

const getSelectedTimbreRecords = () => getTimbreRecordsForInstanceIds(selectedTimbreInstanceIds);

const shouldUseImportedBioacousticsFullAssetScope = ({
    onsetMethod = settings.timbreOnsetDetectionMode,
    includeSelectionSources = false,
    assetId = getSelectedAudioAssetId(''),
} = {}) => includeSelectionSources
    && onsetMethod === BIOACOUSTICS_WORKBOOK_ONSET_METHOD
    && hasImportedBioacousticsWorkbookOnsets(assetId);

const normalizeTimbreSelectionIds = (instanceIds, { constrainToCurrentPoints = true } = {}) => normalizeSharedSelectionIds(instanceIds, {
    maxIndexExclusive: constrainToCurrentPoints ? trajectoryVisualizer.points.length : null,
});

const normalizeTimbreLassoPoints = (points) => normalizeTimbrePlaneLassoPoints(points, {
    maxPoints: TIMBRE_LASSO_MAX_POINTS,
    minDistancePct: 0.15,
});

const getRenderableTimbreLassoPoints = (planeKey, selection, activeLassoDraw = getActiveTimbreLassoDraw()) => getRenderableTimbrePlaneLassoPoints(planeKey, selection, {
    activeLassoDraw,
    normalizePoints: normalizeTimbreLassoPoints,
});

const evaluateTimbreSelectionFromPlaneSettings = (planeSelections, bounds = getTimbreSceneBounds()) => evaluateTimbrePlaneSelections(planeSelections, {
    bounds,
    planeSelectionMeta: TERRAIN_PLANE_SELECTION_META,
    points: trajectoryVisualizer.points,
    getPointPcts: getTimbrePlaneSelectionPointPcts,
    normalizePoints: normalizeTimbreLassoPoints,
});

const startTimbreLassoDraw = (planeKey) => {
    appInteractionBindings?.clearTimbreLassoPointerDown();
    timbreSelectionController?.startLassoDraw(planeKey);
};

const cancelActiveTimbreLassoDraw = ({ refresh = true } = {}) => {
    appInteractionBindings?.clearTimbreLassoPointerDown();
    timbreSelectionController?.cancelActiveLassoDraw({ refresh });
};

const completeActiveTimbreLassoDraw = ({ adoptCurrentTimeSec = getTrajectoryPlaybackTimeSec() } = {}) => {
    const completed = timbreSelectionController?.completeActiveLassoDraw({ adoptCurrentTimeSec }) ?? false;
    if (completed) {
        appInteractionBindings?.clearTimbreLassoPointerDown();
    }
    return completed;
};

const clearTimbrePlaneLasso = (planeKey) => {
    appInteractionBindings?.clearTimbreLassoPointerDown();
    timbreSelectionController?.clearPlaneLasso(planeKey);
};

const appendPointToActiveTimbreLasso = (event) => timbreSelectionController?.appendPointToActiveLasso(event) ?? false;

const formatSelectionScalar = (value) => {
    if (!Number.isFinite(value)) return '?';
    const rounded = Math.round(value * 100) / 100;
    if (Math.abs(rounded - Math.round(rounded)) < 1e-6) {
        return String(Math.round(rounded));
    }
    return rounded.toFixed(2).replace(/\.00$/, '').replace(/(\.\d)0$/, '$1');
};

const summarizeTimbreSelectionRecords = (selectedRecords, { includeSelectionSources = false } = {}) => {
    if (selectedRecords.length === 0) return null;

    const frameIndices = [];
    const timeBounds = [];
    const pointBounds = {
        minX: Infinity,
        minY: Infinity,
        minZ: Infinity,
        maxX: -Infinity,
        maxY: -Infinity,
        maxZ: -Infinity,
    };

    for (const entry of selectedRecords) {
        frameIndices.push(entry.frameRecord.frameIndex);
        const bounds = resolveFrameRecordTimeBounds(entry.frameRecord);
        timeBounds.push(bounds);

        const point = trajectoryVisualizer.points[entry.instanceId];
        if (!point) continue;
        pointBounds.minX = Math.min(pointBounds.minX, point.x);
        pointBounds.minY = Math.min(pointBounds.minY, point.y);
        pointBounds.minZ = Math.min(pointBounds.minZ, point.z);
        pointBounds.maxX = Math.max(pointBounds.maxX, point.x);
        pointBounds.maxY = Math.max(pointBounds.maxY, point.y);
        pointBounds.maxZ = Math.max(pointBounds.maxZ, point.z);
    }

    const frameMin = Math.min(...frameIndices);
    const frameMax = Math.max(...frameIndices);
    const timeMin = Math.min(...timeBounds.map((entry) => entry.timeStartSec));
    const timeMax = Math.max(...timeBounds.map((entry) => entry.timeEndSec));

    return {
        selectedRecords,
        frameMin,
        frameMax,
        timeMin,
        timeMax,
        durationSec: Math.max(0, timeMax - timeMin),
        pointBounds,
        manualCount: includeSelectionSources ? manualTimbreInstanceIds.length : 0,
        boxCount: includeSelectionSources ? boxTimbreSelectionInstanceIds.length : 0,
    };
};

const getTimbreSelectionSummaryForIds = (instanceIds, options = {}) => summarizeTimbreSelectionRecords(
    getTimbreRecordsForInstanceIds(instanceIds),
    options,
);

const getCurrentTimbreSelectionSummary = () => summarizeTimbreSelectionRecords(
    shouldUseImportedBioacousticsFullAssetScope({ includeSelectionSources: true })
        ? getAllTimbreRecords()
        : getSelectedTimbreRecords(),
    { includeSelectionSources: true },
);

const confirmTimbreDialogAction = async ({
    title,
    message,
    confirmLabel = 'Confirm',
    cancelLabel = 'Cancel',
    danger = false,
}) => {
    return timbreSelectionDialogService.confirm({
        title,
        message,
        confirmLabel,
        cancelLabel,
        danger,
    });
};

const timbreSelectionActionService = createTimbreSelectionActions({
    normalizeSelectionIds: (instanceIds) => normalizeTimbreSelectionIds(instanceIds, { constrainToCurrentPoints: false }),
    getSelectedAsset: getSelectedAudioAsset,
    getCurrentSelectionSummary: getCurrentTimbreSelectionSummary,
    getSelectedInstanceIds: () => selectedTimbreInstanceIds,
    getCurrentSelectionAnalysisState: () => timbreSelectionAnalysis,
    buildSelectionAnalysisForIds: buildTimbreSelectionAnalysisForIds,
    clearPlaneSelections: () => clearTimbrePlaneSelections(),
    setSelectedInstanceIds: (instanceIds) => setSelectedTimbreInstanceIds(instanceIds),
    jumpToAnalysisTarget: (analysis) => jumpToTimbreAnalysisTarget(analysis),
    confirmDeleteGroup: (groupLabel) => confirmTimbreDialogAction({
        title: 'Delete Node Group',
        message: `Delete node group "${groupLabel}"? This removes the saved tab but keeps the current live selection intact.`,
        confirmLabel: 'Delete Group',
        danger: true,
    }),
    renderSelectionPanel: () => renderTimbreSelectionPanel(),
    onSelectionGroupsCommitted: () => updateTransportOnsetMarkers?.(),
    storage: window.localStorage,
    cryptoObject: window.crypto,
});

const {
    autoSaveGroupsFromOnsets: autoSaveTimbreGroupsFromOnsets,
    autoSaveGroupsFromWindows: autoSaveTimbreGroupsFromWindows,
    deleteGroup: deleteTimbreSelectionGroup,
    ensureActivePanelTab: ensureActiveTimbreSelectionPanelTab,
    formatGroupSource: formatTimbreSelectionGroupSource,
    getActivePanelTabId: getActiveTimbreSelectionPanelTabId,
    getCurrentAssetGroups: getCurrentAssetTimbreSelectionGroups,
    getGroupAnalysis: getTimbreSelectionGroupAnalysis,
    getGroupById: getTimbreSelectionGroupById,
    getInlineLabelValue: getTimbreSelectionInlineLabelValue,
    jumpToGroup: jumpToTimbreSelectionGroup,
    loadGroupIntoCurrent: loadTimbreSelectionGroupIntoCurrent,
    mergeCurrentIntoGroup: mergeCurrentSelectionIntoTimbreGroup,
    moveGroupWithinAsset: moveTimbreSelectionGroupWithinAsset,
    overwriteGroupFromCurrent: overwriteTimbreSelectionGroupFromCurrent,
    removeCurrentFromGroup: removeCurrentSelectionFromTimbreGroup,
    renameGroup: renameTimbreSelectionGroup,
    saveCurrentSelectionAsNewGroup: saveCurrentSelectionAsNewTimbreGroup,
    setActivePanelTabId: setActiveTimbreSelectionPanelTabId,
    setInlineLabel: setTimbreSelectionInlineLabel,
    splitGroupByCurrentSelection: splitTimbreSelectionGroupByCurrentSelection,
    syncInlineLabelState: syncTimbreSelectionInlineLabelState,
} = timbreSelectionActionService;

const shouldShowTimbreSelectionBadge = () => !isTerrainMode() && !!settings.showSelectionMenu;
const shouldShowTimbreSelectionPanel = () => !isTerrainMode() && !!settings.showNodeSelectionMenu;

const renderTimbreSelectionPanel = () => timbreSelectionUi?.renderPanel();

const getAnalysisHopDurationSec = () => {
    const manifestHopDuration = Number(getSelectedAudioAsset()?.analysisHopDurationSec);
    if (Number.isFinite(manifestHopDuration) && manifestHopDuration > 0) return manifestHopDuration;

    const durationSec = getTrajectoryDurationSec();
    const frameCount = trajectoryVisualizer.points.length;
    return frameCount > 0 && durationSec > 0 ? durationSec / frameCount : 0;
};

const resolveFrameRecordTimeBounds = (frameRecord) => resolveSelectionFrameRecordTimeBounds(frameRecord, {
    getAnalysisHopDurationSec,
    getFallbackFrameCenterSec: (pointIndex) => trajectoryVisualizer.getFrameTimeAtIndex(pointIndex, getTrajectoryDurationSec()),
});

const buildContiguousTimbreSelectionWindows = (selectedRecords) => buildContiguousSelectionWindows(selectedRecords, {
    getAnalysisHopDurationSec,
    resolveFrameRecordTimeBounds,
});

const getImportedBioacousticsOnsetTimes = (assetId = getSelectedAudioAssetId('')) => {
    if (!assetId || bioacousticsImportedOnsetState.assetId !== assetId) return [];
    return [...bioacousticsImportedOnsetState.onsetTimes];
};

const buildImportedBioacousticsOnsetEvents = (windows, importedOnsetTimes) => {
    if (!Array.isArray(windows) || windows.length === 0) return [];

    const normalizedOnsetTimes = (importedOnsetTimes || [])
        .map((timeSec) => Number(timeSec))
        .filter((timeSec) => Number.isFinite(timeSec))
        .sort((a, b) => a - b);
    if (normalizedOnsetTimes.length === 0) return [];

    const hopDurationSec = Math.max(0.01, Number(getAnalysisHopDurationSec()) || 0.01);
    const windowPaddingSec = Math.max(0.01, hopDurationSec * 0.5);
    const onsetEvents = [];

    for (const onsetTimeSec of normalizedOnsetTimes) {
        let bestMatch = null;

        for (const window of windows) {
            if (!Array.isArray(window?.pointIndices) || !Array.isArray(window?.frameRecords)) continue;
            if (window.pointIndices.length === 0 || window.frameRecords.length === 0) continue;

            const windowStartSec = Number.isFinite(window.timeStartSec) ? window.timeStartSec : -Infinity;
            const windowEndSec = Number.isFinite(window.timeEndSec) ? window.timeEndSec : Infinity;
            if (onsetTimeSec < (windowStartSec - windowPaddingSec) || onsetTimeSec > (windowEndSec + windowPaddingSec)) {
                continue;
            }

            for (let localIndex = 0; localIndex < window.frameRecords.length; localIndex++) {
                const frameRecord = window.frameRecords[localIndex];
                const timeBounds = resolveFrameRecordTimeBounds(frameRecord);
                const candidateTimeSec = Number.isFinite(timeBounds.timeCenterSec)
                    ? timeBounds.timeCenterSec
                    : onsetTimeSec;
                const distanceSec = Math.abs(candidateTimeSec - onsetTimeSec);
                if (!bestMatch || distanceSec < bestMatch.distanceSec) {
                    bestMatch = {
                        distanceSec,
                        frameRecord,
                        pointIndex: window.pointIndices[localIndex],
                        windowIndex: window.windowIndex,
                    };
                }
            }
        }

        if (!bestMatch) continue;
        onsetEvents.push({
            pointIndex: bestMatch.pointIndex,
            frameIndex: bestMatch.frameRecord.frameIndex,
            timeSec: onsetTimeSec,
            strength: 1,
            threshold: 0,
            windowIndex: bestMatch.windowIndex,
            method: BIOACOUSTICS_WORKBOOK_ONSET_METHOD,
        });
    }

    return dedupeNearbyOnsetEvents(onsetEvents, Math.max(0.01, hopDurationSec * 1.5));
};

const buildTimbreSelectionOnsetEventsFromEditableEntries = (windows, editableOnsets, {
    onsetMethod = settings.timbreOnsetDetectionMode,
} = {}) => {
    if (!Array.isArray(windows) || windows.length === 0) return [];

    const normalizedEntries = (editableOnsets || [])
        .map((entry) => ({
            id: String(entry?.id || '').trim(),
            timeSec: Number(entry?.timeSec),
        }))
        .filter((entry) => entry.id && Number.isFinite(entry.timeSec))
        .sort((a, b) => a.timeSec - b.timeSec);
    if (normalizedEntries.length === 0) return [];

    const hopDurationSec = Math.max(0.01, Number(getAnalysisHopDurationSec()) || 0.01);
    const windowPaddingSec = Math.max(0.01, hopDurationSec * 0.5);
    const onsetEvents = [];

    for (const entry of normalizedEntries) {
        let bestMatch = null;

        for (const window of windows) {
            if (!Array.isArray(window?.pointIndices) || !Array.isArray(window?.frameRecords)) continue;
            if (window.pointIndices.length === 0 || window.frameRecords.length === 0) continue;

            const windowStartSec = Number.isFinite(window.timeStartSec) ? window.timeStartSec : -Infinity;
            const windowEndSec = Number.isFinite(window.timeEndSec) ? window.timeEndSec : Infinity;
            if (entry.timeSec < (windowStartSec - windowPaddingSec) || entry.timeSec > (windowEndSec + windowPaddingSec)) {
                continue;
            }

            for (let localIndex = 0; localIndex < window.frameRecords.length; localIndex++) {
                const frameRecord = window.frameRecords[localIndex];
                const timeBounds = resolveFrameRecordTimeBounds(frameRecord);
                const candidateTimeSec = Number.isFinite(timeBounds.timeCenterSec)
                    ? timeBounds.timeCenterSec
                    : entry.timeSec;
                const distanceSec = Math.abs(candidateTimeSec - entry.timeSec);
                if (!bestMatch || distanceSec < bestMatch.distanceSec) {
                    bestMatch = {
                        distanceSec,
                        frameRecord,
                        pointIndex: window.pointIndices[localIndex],
                        windowIndex: window.windowIndex,
                    };
                }
            }
        }

        if (!bestMatch) continue;
        onsetEvents.push({
            pointIndex: bestMatch.pointIndex,
            frameIndex: bestMatch.frameRecord.frameIndex,
            timeSec: entry.timeSec,
            strength: 1,
            threshold: 0,
            windowIndex: bestMatch.windowIndex,
            method: onsetMethod,
            eventKey: entry.id,
            editId: entry.id,
        });
    }

    return onsetEvents;
};

const buildTimbreSelectionOnsetEvents = (windows, { onsetMethod = settings.timbreOnsetDetectionMode } = {}) => buildSelectionOnsetEvents(windows, {
    onsetMethod,
    supportedMethodLabels: TIMBRE_ONSET_DETECTION_MODES,
    spectralFluxMethodLabel: 'Spectral Flux',
    volumeDeltaMethodLabel: 'Volume Delta',
    volumeColumn: trajectoryVisualizer.dataColumnsRaw.Volume || [],
    hasSpectralFrameData: () => terrainVisualizer.hasFrameData(),
    getSpectralFrameDataRow: (frameIndex) => terrainVisualizer.getFrameDataRowAt(frameIndex),
    resolveFrameRecordTimeBounds,
    analysisHopDurationSec: getAnalysisHopDurationSec(),
    sensitivity: settings.timbreOnsetSensitivity,
    thresholdMultiplier: settings.timbreOnsetThresholdMultiplier,
});

const buildTimbreSelectionOnsetEventsForMethod = (windows, { onsetMethod = settings.timbreOnsetDetectionMode } = {}) => {
    if (onsetMethod === BIOACOUSTICS_WORKBOOK_ONSET_METHOD) {
        return {
            onsetEvents: buildImportedBioacousticsOnsetEvents(windows, getImportedBioacousticsOnsetTimes()),
            onsetMethod: BIOACOUSTICS_WORKBOOK_ONSET_METHOD,
        };
    }

    return buildTimbreSelectionOnsetEvents(windows, { onsetMethod });
};

const buildTimbreInterOnsetIntervals = (onsetEvents) => buildInterOnsetIntervals(onsetEvents);

const buildTerrainOnsetTargetKey = ({ onsetMethod = settings.timbreOnsetDetectionMode, selectedRecords = [] } = {}) => {
    const assetId = getSelectedAudioAssetId('');
    if (!assetId) return '';

    const instanceIds = (selectedRecords || [])
        .map((record) => Number(record?.instanceId))
        .filter((instanceId) => Number.isInteger(instanceId))
        .sort((a, b) => a - b);

    return `${assetId}::${String(onsetMethod || '').trim()}::${instanceIds.join(',')}`;
};

const createTerrainOnsetEntryId = () => `terrain-onset-${terrainOnsetEditorState.nextOnsetId++}`;

const cloneTerrainOnsetEntriesFromAnalysis = (analysis) => (analysis?.onsetEvents || [])
    .map((event) => ({
        id: String(event?.eventKey || event?.editId || createTerrainOnsetEntryId()),
        timeSec: Number(event?.timeSec),
    }))
    .filter((entry) => entry.id && Number.isFinite(entry.timeSec))
    .sort((a, b) => a.timeSec - b.timeSec);

const applyTerrainOnsetOverridesToAnalysis = (analysis) => {
    if (!analysis) return null;

    const onsetTargetKey = buildTerrainOnsetTargetKey({
        onsetMethod: analysis.onsetMethod,
        selectedRecords: analysis.selectedRecords,
    });
    const overrideEntry = onsetTargetKey ? terrainOnsetEditorState.overridesByTargetKey.get(onsetTargetKey) : null;
    const onsetEvents = overrideEntry
        ? buildTimbreSelectionOnsetEventsFromEditableEntries(analysis.contiguousWindows, overrideEntry.onsets, {
            onsetMethod: analysis.onsetMethod,
        })
        : (analysis.onsetEvents || []).map((event, index) => ({
            ...event,
            eventKey: event?.eventKey || `derived-onset-${index}-${Number(event?.timeSec || 0).toFixed(6)}`,
        }));

    return {
        ...analysis,
        onsetTargetKey,
        onsetEvents,
        interOnsetIntervals: buildTimbreInterOnsetIntervals(onsetEvents),
    };
};

function buildTimbreSelectionAnalysisForIds(instanceIds, { onsetMethod = settings.timbreOnsetDetectionMode, includeSelectionSources = false } = {}) {
    const analysisRecords = shouldUseImportedBioacousticsFullAssetScope({ onsetMethod, includeSelectionSources })
        ? getAllTimbreRecords()
        : getTimbreRecordsForInstanceIds(instanceIds);
    const summary = summarizeTimbreSelectionRecords(analysisRecords, { includeSelectionSources });
    const contiguousWindows = buildContiguousTimbreSelectionWindows(analysisRecords);
    const onsetResult = buildTimbreSelectionOnsetEventsForMethod(contiguousWindows, { onsetMethod });

    return applyTerrainOnsetOverridesToAnalysis({
        selectedRecords: analysisRecords,
        summary,
        contiguousWindows,
        onsetEvents: onsetResult.onsetEvents,
        interOnsetIntervals: buildTimbreInterOnsetIntervals(onsetResult.onsetEvents),
        onsetMethod: onsetResult.onsetMethod,
    });
}

const applyEffectiveTimbreSelection = ({ adoptCurrentTimeSec = getTrajectoryPlaybackTimeSec() } = {}) => {
    selectedTimbreInstanceIds = normalizeTimbreSelectionIds([
        ...manualTimbreInstanceIds,
        ...boxTimbreSelectionInstanceIds,
    ]);
    trajectoryVisualizer.setSelectedFrameIndices(selectedTimbreInstanceIds);
    rebuildTimbreSelectionAnalysis({ adoptCurrentTimeSec });
};

const clearTimbrePlaneSelections = () => {
    const planeSelections = ensureTimbrePlaneSelectionSettings();
    cancelActiveTimbreLassoDraw({ refresh: false });
    for (const [planeKey] of Object.entries(TERRAIN_PLANE_SELECTION_META)) {
        planeSelections[planeKey].enabled = false;
        planeSelections[planeKey].lassoPoints = [];
    }
    rebuildTimbrePlaneSelectionControls();
    rebuildTimbrePlaneSelectionVisuals();
};

const clearAllTimbreSelections = ({ clearBox = true } = {}) => {
    manualTimbreInstanceIds = [];
    if (clearBox) {
        boxTimbreSelectionInstanceIds = [];
        clearTimbrePlaneSelections();
        return;
    }
    applyEffectiveTimbreSelection();
};

const invertTimbreSelection = () => {
    const effectiveSelection = new Set(selectedTimbreInstanceIds);
    clearTimbrePlaneSelections();
    manualTimbreInstanceIds = trajectoryVisualizer.points
        .map((_, index) => index)
        .filter((index) => !effectiveSelection.has(index));
    applyEffectiveTimbreSelection();
};

const buildTimbreExportFileStem = (label, fallback = 'selection') => buildSelectionExportFileStem(label, {
    assetLabel: getSelectedAudioAssetLabel(''),
    assetId: getSelectedAudioAssetId(''),
    fallback,
});

const jumpToTimbreAnalysisTarget = (analysis) => {
    const firstWindow = analysis?.contiguousWindows?.[0];
    if (!firstWindow || !Number.isFinite(firstWindow.timeStartSec)) return false;

    audio.currentTime = Math.max(0, firstWindow.timeStartSec);
    resetTrajectoryPlaybackAnchor(audio.currentTime);
    syncVisualizerToCurrentTime();
    return true;
};

const jumpToCurrentTimbreSelection = () => {
    jumpToTimbreAnalysisTarget(timbreSelectionAnalysis);
};

const playCurrentTimbreSelection = async () => {
    if (!jumpToTimbreAnalysisTarget(timbreSelectionAnalysis)) return;

    settings.enableSelectionPlaybackMask = true;
    ensureAudioContext();
    await audio.play();
    if (playBtn) playBtn.innerText = '⏸';
    updateSelectionPlaybackMask();
    updateTimbreSelectionBadge();
};

const buildTimbreAnalysisPayload = (analysis, { label = 'Selection' } = {}) => buildSelectionAnalysisPayload(analysis, {
    label,
    assetId: getSelectedAudioAssetId(null),
    assetLabel: getSelectedAudioAssetLabel(null),
    onsetMethod: settings.timbreOnsetDetectionMode,
    resolveFrameRecordTimeBounds,
});

const buildTimbreAnalysisCsvMatrix = (analysis) => buildSelectionAnalysisCsvMatrix(analysis, {
    resolveFrameRecordTimeBounds,
    getPointForInstanceId: (instanceId) => trajectoryVisualizer.points[instanceId] || { x: '', y: '', z: '' },
});

const buildTimbreAnalysisIoiCsvMatrix = (analysis, { label = 'Selection' } = {}) => buildSelectionAnalysisIoiCsvMatrix(analysis, {
    label,
    assetId: getSelectedAudioAssetId(''),
    assetLabel: getSelectedAudioAssetLabel(''),
    onsetMethod: settings.timbreOnsetDetectionMode,
});

const buildConcatenatedAudioDataForAnalysis = async (analysis) => {
    const audioBuffer = await ensureDecodedAudioBufferForSelectedAsset();
    if (!audioBuffer) return null;
    return buildConcatenatedAudioDataFromWindows(audioBuffer, analysis?.contiguousWindows);
};

const {
    exportAnalysisAsJson: exportTimbreAnalysisAsJson,
    exportAnalysisAsCsv: exportTimbreAnalysisAsCsv,
    exportAnalysisAsIoiCsv: exportTimbreAnalysisAsIoiCsv,
    exportAnalysisAsAudioClip: exportTimbreAnalysisAsAudioClip,
    exportCurrentSelectionAsJson: exportCurrentTimbreSelectionAsJson,
    exportCurrentSelectionAsCsv: exportCurrentTimbreSelectionAsCsv,
    exportCurrentSelectionAsIoiCsv: exportCurrentTimbreSelectionAsIoiCsv,
    exportCurrentSelectionAsAudioClip: exportCurrentTimbreSelectionAsAudioClip,
    exportSelectionGroupAsAudioClip: exportTimbreSelectionGroupAsAudioClip,
    exportSelectionGroupAsIoiCsv: exportTimbreSelectionGroupAsIoiCsv,
} = createSelectionExportService({
    buildExportFileStem: buildTimbreExportFileStem,
    buildAnalysisPayload: buildTimbreAnalysisPayload,
    buildAnalysisCsvMatrix: buildTimbreAnalysisCsvMatrix,
    buildAnalysisIoiCsvMatrix: buildTimbreAnalysisIoiCsvMatrix,
    buildAudioDataForAnalysis: buildConcatenatedAudioDataForAnalysis,
    getCurrentAnalysis: () => getCurrentTimbreAnalysisSnapshot?.(),
    getGroupRecord: getTimbreSelectionGroupById,
    getGroupAnalysis: getTimbreSelectionGroupAnalysis,
});

const buildBackendCallAssetSnapshot = (selectedAsset = getSelectedAudioAsset()) => {
    if (livePerformanceControls?.isActive?.()) return null;
    return selectedAsset ? {
    id: selectedAsset.id,
    label: selectedAsset.label,
    revisionId: selectedAsset.revisionId || selectedAsset.activeRevisionId || selectedAsset.id,
    audioUrl: selectedAsset.audioUrl,
    mfccCsvUrl: selectedAsset.mfccCsvUrl,
    fftCsvUrl: selectedAsset.fftCsvUrl,
    terrainEnvelopeUrl: selectedAsset.terrainEnvelopeUrl,
    analysisSampleRate: selectedAsset.analysisSampleRate,
    analysisHopLength: selectedAsset.analysisHopLength,
    analysisFrameLength: selectedAsset.analysisFrameLength,
    analysisFrameCount: selectedAsset.analysisFrameCount,
    analysisHopDurationSec: selectedAsset.analysisHopDurationSec,
    analysisWindowDurationSec: selectedAsset.analysisWindowDurationSec,
    analysisClipDurationSec: selectedAsset.analysisClipDurationSec,
    analysisFftNfft: selectedAsset.analysisFftNfft,
    } : null;
};

const processCurrentGraphAsset = async () => {
    if (!backendCallMonitorIpc) {
        window.alert('Graph asset processing is available only inside the Electron app shell.');
        return null;
    }

    const selectedAsset = getSelectedAudioAsset();
    const assetSnapshot = buildBackendCallAssetSnapshot(selectedAsset);
    const requestPayload = buildProcessCurrentAssetRequest({
        assetSnapshot,
        includeMfcc: assetSourceUiState.processCurrentAssetIncludeMfcc,
        fallbackLabel: getSelectedAudioFileName('Current Asset'),
    });
    if (!requestPayload) {
        window.alert('Load an audio asset before processing the current graph asset.');
        return null;
    }

    try {
        const response = await backendCallMonitorIpc.invoke('graph:process-asset', requestPayload);
        if (!response?.ok) {
            window.alert(response?.error || 'Graph asset processing failed.');
            return null;
        }

        const promotedAsset = response?.promotedAsset || response?.nextAsset || response?.asset || null;
        if (promotedAsset) {
            await applyCanonicalLocalIntegrationAsset(promotedAsset);
        } else {
            const manifestResult = await reloadCurrentAudioAssetManifest(assetSnapshot.id || getSelectedAudioAssetId(''));
            if (!manifestResult?.ok) {
                console.error('Processed graph asset, but the manifest could not be reloaded.', manifestResult?.error);
            }
        }

        return response;
    } catch (error) {
        console.error('Failed to process the current graph asset:', error);
        window.alert(error?.message || 'Graph asset processing failed.');
        return null;
    }
};

const buildBioacousticsBackendSnapshot = (analysis, {
    targetLabel = 'Current Selection',
    targetKind = 'current',
} = {}) => {
    const selectedAsset = getSelectedAudioAsset();
    const assetAudioFileName = getSelectedAudioFileName('');
    const onsetTimes = (analysis?.onsetEvents || [])
        .map((event) => Number(event?.timeSec))
        .filter((timeSec) => Number.isFinite(timeSec))
        .sort((a, b) => a - b);
    const importedOnsetTimes = getImportedBioacousticsOnsetTimes();
    const hasAsset = !!selectedAsset && !!assetAudioFileName;

    return {
        isAssetReady: hasAsset,
        canImport: hasAsset,
        canSync: hasAsset && onsetTimes.length > 0,
        assetAudioFileName,
        targetLabel,
        targetKind,
        onsetCount: onsetTimes.length,
        onsetTimes,
        importedOnsetCount: importedOnsetTimes.length,
        importedWorkbookPath: bioacousticsImportedOnsetState.assetId === getSelectedAudioAssetId('')
            ? bioacousticsImportedOnsetState.workbookPath
            : '',
        importedMatchedFileName: bioacousticsImportedOnsetState.assetId === getSelectedAudioAssetId('')
            ? bioacousticsImportedOnsetState.matchedFileName
            : '',
        importedAt: bioacousticsImportedOnsetState.assetId === getSelectedAudioAssetId('')
            ? bioacousticsImportedOnsetState.importedAt
            : null,
        statusMessage: !hasAsset
            ? 'Load an audio asset before using the Bioacoustics workbook handler.'
            : onsetTimes.length === 0
                ? 'Current Timbre selection has no onset events to sync yet. Import can still load workbook onsets for this asset.'
                : 'Ready. Import can load workbook onsets for this asset, and sync can write the current Timbre onset list back to a compatible workbook.',
    };
};

const clearImportedBioacousticsWorkbookState = (assetId = getSelectedAudioAssetId('')) => {
    const normalizedAssetId = String(assetId || '').trim();
    if (!normalizedAssetId || bioacousticsImportedOnsetState.assetId !== normalizedAssetId) return;

    bioacousticsImportedOnsetState.assetId = '';
    bioacousticsImportedOnsetState.workbookPath = '';
    bioacousticsImportedOnsetState.matchedFileName = '';
    bioacousticsImportedOnsetState.onsetTimes = [];
    bioacousticsImportedOnsetState.importedAt = null;

    if (
        normalizedAssetId === getSelectedAudioAssetId('')
        && settings.timbreOnsetDetectionMode === BIOACOUSTICS_WORKBOOK_ONSET_METHOD
    ) {
        rebuildTimbreSelectionAnalysis({ adoptCurrentTimeSec: getTrajectoryPlaybackTimeSec() });
        gui.controllersRecursive().forEach((controller) => controller.updateDisplay());
    }

    syncBackendCallMonitorState();
};

const applyImportedBioacousticsWorkbookResult = (response) => {
    if (response?.analysisType !== BIOACOUSTICS_IMPORT_ACTION || response?.ok !== true) return;

    const importedWorkbook = response?.result?.importedWorkbook;
    const onsetTimes = (importedWorkbook?.onsetTimes || [])
        .map((timeSec) => Number(timeSec))
        .filter((timeSec) => Number.isFinite(timeSec))
        .sort((a, b) => a - b);
    const responseAssetId = String(response?.asset?.id || '').trim();
    if (!responseAssetId || onsetTimes.length === 0) return;

    bioacousticsImportedOnsetState.assetId = responseAssetId;
    bioacousticsImportedOnsetState.workbookPath = importedWorkbook?.workbookPath || '';
    bioacousticsImportedOnsetState.matchedFileName = importedWorkbook?.matchedFileName || getSelectedAudioFileName('');
    bioacousticsImportedOnsetState.onsetTimes = onsetTimes;
    bioacousticsImportedOnsetState.importedAt = response?.callMeta?.completedAt || new Date().toISOString();

    if (responseAssetId !== getSelectedAudioAssetId('')) {
        syncBackendCallMonitorState();
        return;
    }

    settings.timbreOnsetDetectionMode = BIOACOUSTICS_WORKBOOK_ONSET_METHOD;
    rebuildTimbreSelectionAnalysis({ adoptCurrentTimeSec: getTrajectoryPlaybackTimeSec() });
    gui.controllersRecursive().forEach((controller) => controller.updateDisplay());
    syncBackendCallMonitorState();
};

const autoImportBioacousticsWorkbookForSelectedAsset = async () => {
    if (!backendCallMonitorIpc) return null;

    const selectedAsset = getSelectedAudioAsset();
    const assetSnapshot = buildBackendCallAssetSnapshot(selectedAsset);
    if (!assetSnapshot?.audioUrl) return null;

    try {
        const response = await backendCallMonitorIpc.invoke('backend-call:run', {
            analysisType: BIOACOUSTICS_IMPORT_ACTION,
            saveMode: 'none',
            bioacousticsOptions: {
                autoDiscover: true,
                targetLabel: 'Current Selection',
                targetKind: 'current',
            },
        });

        const responseAssetId = String(response?.asset?.id || assetSnapshot.id || '').trim();
        const onsetCount = Number(response?.result?.summary?.onsetCount || 0);
        if (responseAssetId && (!response?.ok || onsetCount === 0)) {
            clearImportedBioacousticsWorkbookState(responseAssetId);
        }
        return response;
    } catch (error) {
        console.warn('Automatic Bioacoustics workbook import failed:', error);
        clearImportedBioacousticsWorkbookState(assetSnapshot.id);
        return null;
    }
};

const exportAnalysisAsBioacousticsWorkbook = async (analysis, {
    targetLabel = 'Current Selection',
    targetKind = 'current',
} = {}) => {
    if (!backendCallMonitorIpc) {
        window.alert('Bioacoustics workbook export is available only inside the Electron app shell.');
        return null;
    }

    const onsetEvents = analysis?.onsetEvents || [];
    if (onsetEvents.length === 0) {
        window.alert('No onset events are available for the active Timbre target.');
        return null;
    }

    const importedWorkbookPath = bioacousticsImportedOnsetState.assetId === getSelectedAudioAssetId('')
        ? bioacousticsImportedOnsetState.workbookPath
        : '';

    const response = await backendCallMonitorIpc.invoke('backend-call:run', {
        analysisType: BIOACOUSTICS_SYNC_ACTION,
        saveMode: 'xlsx',
        saveLabel: buildTimbreExportFileStem(`${targetLabel}-bioacoustics`, 'bioacoustics'),
        bioacousticsState: buildBioacousticsBackendSnapshot(analysis, {
            targetLabel,
            targetKind,
        }),
        bioacousticsOptions: {
            workbookPath: importedWorkbookPath,
            outputMode: importedWorkbookPath ? 'duplicate' : 'new-compatible',
        },
    });

    if (!response?.ok) {
        window.alert(response?.error || 'Bioacoustics workbook export failed.');
        return null;
    }

    const savedPath = response?.saveResult?.path || response?.result?.summary?.outputWorkbookPath || 'the output workbook';
    window.alert(`Saved Bioacoustics workbook to ${savedPath}.`);
    return response;
};

const exportCurrentTimbreSelectionAsBioacousticsWorkbook = async () => {
    const analysis = getCurrentTimbreAnalysisSnapshot?.();
    if (!analysis) return null;
    return exportAnalysisAsBioacousticsWorkbook(analysis, {
        targetLabel: 'Current Selection',
        targetKind: 'current',
    });
};

const exportTimbreSelectionGroupAsBioacousticsWorkbook = async (groupId) => {
    const group = getTimbreSelectionGroupById(groupId);
    const analysis = getTimbreSelectionGroupAnalysis(groupId);
    if (!group || !analysis?.summary) return null;
    return exportAnalysisAsBioacousticsWorkbook(analysis, {
        targetLabel: group.label,
        targetKind: 'group',
    });
};

const updateTimbreSelectionBadge = () => timbreSelectionUi?.updateBadge();

const {
    getCurrentAnalysisSnapshot: getCurrentTimbreAnalysisSnapshot,
    getActiveAnalysisSnapshot: getActiveTimbreAnalysisSnapshot,
    invalidateOnsetProgress: invalidateTimbreOnsetProgress,
    rebuildSelectionAnalysis: rebuildTimbreSelectionAnalysis,
    updateTransportOnsetMarkers,
} = createTimbreController({
    analysisState: timbreSelectionAnalysis,
    trajectoryVisualizer,
    transportMarkers: timbreTransportMarkers,
    getCurrentSelectionSummary: getCurrentTimbreSelectionSummary,
    getSelectedInstanceIds: () => selectedTimbreInstanceIds,
    ensureActiveSelectionPanelTab: ensureActiveTimbreSelectionPanelTab,
    getActiveSelectionPanelTabId: getActiveTimbreSelectionPanelTabId,
    getGroupById: getTimbreSelectionGroupById,
    getSelectedAsset: getSelectedAudioAsset,
    buildSelectionAnalysisForIds: buildTimbreSelectionAnalysisForIds,
    updateSelectionBadge: () => updateTimbreSelectionBadge(),
    updateSelectionPlaybackMask: (...args) => updateSelectionPlaybackMask(...args),
    formatTimestamp: formatSelectionTimestamp,
    isTerrainMode,
    getShowTransportOnsetMarkers: () => !!settings.showTransportOnsetMarkers,
    getTrajectoryDurationSec: () => getTrajectoryDurationSec(),
    seekToTimeSec: (timeSec) => {
        audio.currentTime = Math.max(0, timeSec);
        resetTrajectoryPlaybackAnchor(audio.currentTime);
        syncVisualizerToCurrentTime();
    },
    highlightOnset: (analysis, event, options) => triggerTimbreOnsetHighlight(analysis, event, options),
    onAnalysisUpdated: () => {
        markTerrainOnsetOverlayDirty();
        refreshTerrainOnsetOverlay();
    },
});

timbreSelectionUi = createTimbreSelectionPanel({
    elements: {
        badge: timbreSelectionBadge,
        badgeTitle: timbreSelectionTitle,
        badgeMeta: timbreSelectionMeta,
        badgeRange: timbreSelectionRange,
        badgeStats: timbreSelectionStats,
        panel: timbreSelectionPanel,
        panelSubtitle: timbreSelectionPanelSubtitle,
        panelTabBar: timbreSelectionPanelTabBar,
        panelBody: timbreSelectionPanelBody,
    },
    isTerrainMode,
    shouldShowBadge: shouldShowTimbreSelectionBadge,
    shouldShowPanel: shouldShowTimbreSelectionPanel,
    getCurrentSelectionSummary: getCurrentTimbreSelectionSummary,
    getCurrentAssetGroups: getCurrentAssetTimbreSelectionGroups,
    getGroupById: getTimbreSelectionGroupById,
    ensureActiveTab: ensureActiveTimbreSelectionPanelTab,
    getActiveTabId: getActiveTimbreSelectionPanelTabId,
    setActiveTabId: setActiveTimbreSelectionPanelTabId,
    getActiveLassoDraw: getActiveTimbreLassoDraw,
    planeSelectionMeta: TERRAIN_PLANE_SELECTION_META,
    syncInlineLabelState: syncTimbreSelectionInlineLabelState,
    getInlineLabelValue: getTimbreSelectionInlineLabelValue,
    setInlineLabel: setTimbreSelectionInlineLabel,
    formatSelectionTimestamp,
    formatSelectionScalar,
    getCurrentAnalysisState: () => timbreSelectionAnalysis,
    buildSelectionAnalysisForIds: buildTimbreSelectionAnalysisForIds,
    getSelectedAssetLabel: () => getSelectedAudioAssetLabel('Current asset'),
    formatGroupSource: formatTimbreSelectionGroupSource,
    updateTransportOnsetMarkers,
    actions: {
        saveCurrentSelectionAsNewGroup: saveCurrentSelectionAsNewTimbreGroup,
        autoSaveGroupsFromWindows: autoSaveTimbreGroupsFromWindows,
        autoSaveGroupsFromOnsets: autoSaveTimbreGroupsFromOnsets,
        exportCurrentSelectionAsAudioClip: exportCurrentTimbreSelectionAsAudioClip,
        exportCurrentSelectionAsIoiCsv: exportCurrentTimbreSelectionAsIoiCsv,
        exportCurrentSelectionAsBioacousticsWorkbook: exportCurrentTimbreSelectionAsBioacousticsWorkbook,
        renameGroup: renameTimbreSelectionGroup,
        loadGroupIntoCurrent: loadTimbreSelectionGroupIntoCurrent,
        overwriteGroupFromCurrent: overwriteTimbreSelectionGroupFromCurrent,
        jumpToGroup: jumpToTimbreSelectionGroup,
        exportGroupAsAudioClip: exportTimbreSelectionGroupAsAudioClip,
        exportGroupAsIoiCsv: exportTimbreSelectionGroupAsIoiCsv,
        exportGroupAsBioacousticsWorkbook: exportTimbreSelectionGroupAsBioacousticsWorkbook,
        mergeCurrentIntoGroup: mergeCurrentSelectionIntoTimbreGroup,
        removeCurrentFromGroup: removeCurrentSelectionFromTimbreGroup,
        splitGroupByCurrentSelection: splitTimbreSelectionGroupByCurrentSelection,
        moveGroupWithinAsset: moveTimbreSelectionGroupWithinAsset,
        deleteGroup: deleteTimbreSelectionGroup,
        isSelectionPlaybackMaskEnabled: () => !!settings.enableSelectionPlaybackMask,
    },
});

const setSelectedTimbreInstanceIds = (instanceIds, { adoptCurrentTimeSec = getTrajectoryPlaybackTimeSec() } = {}) => {
    manualTimbreInstanceIds = normalizeTimbreSelectionIds(instanceIds);
    applyEffectiveTimbreSelection({ adoptCurrentTimeSec });
};

const setBoxSelectedTimbreInstanceIds = (instanceIds, { adoptCurrentTimeSec = getTrajectoryPlaybackTimeSec() } = {}) => {
    boxTimbreSelectionInstanceIds = normalizeTimbreSelectionIds(instanceIds);
    applyEffectiveTimbreSelection({ adoptCurrentTimeSec });
};

const toggleSelectedTimbreInstanceId = (instanceId) => {
    const nextSelection = new Set(selectedTimbreInstanceIds);
    if (nextSelection.has(instanceId)) {
        nextSelection.delete(instanceId);
    } else {
        nextSelection.add(instanceId);
    }
    setSelectedTimbreInstanceIds(Array.from(nextSelection));
};

const setTimbreSelectionPointerFromEvent = (event) => {
    const rect = renderer.domElement.getBoundingClientRect();
    timbreSelectionPointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    timbreSelectionPointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
};

const setTimbreSelectionPointerToCenter = () => {
    timbreSelectionPointer.x = 0;
    timbreSelectionPointer.y = 0;
};

const pickTimbreSelectionIntersection = (event) => {
    if (isTerrainMode()) return null;
    if (!trajectoryVisualizer.instancedMesh || !trajectoryVisualizer.instancedMesh.visible) return null;

    setTimbreSelectionPointerFromEvent(event);
    timbreSelectionRaycaster.setFromCamera(timbreSelectionPointer, camera);
    const intersections = timbreSelectionRaycaster.intersectObject(trajectoryVisualizer.instancedMesh, false);
    return intersections.find((intersection) => Number.isInteger(intersection.instanceId)) || null;
};

const pickCenteredTimbreSelectionIntersection = () => {
    if (isTerrainMode()) return null;
    if (!trajectoryVisualizer.instancedMesh || !trajectoryVisualizer.instancedMesh.visible) return null;

    setTimbreSelectionPointerToCenter();
    timbreSelectionRaycaster.setFromCamera(timbreSelectionPointer, camera);
    const intersections = timbreSelectionRaycaster.intersectObject(trajectoryVisualizer.instancedMesh, false);
    return intersections.find((intersection) => Number.isInteger(intersection.instanceId)) || null;
};

const getTrajectoryDurationSec = () => {
    if (Number.isFinite(audio.duration) && audio.duration > 0) return audio.duration;
    const manifestDurationSec = Number(getSelectedAudioAsset()?.analysisClipDurationSec);
    return Number.isFinite(manifestDurationSec) && manifestDurationSec > 0 ? manifestDurationSec : 0;
};

const timbreTransportRuntime = createTimbreTransportRuntime({
    audio,
    getAudioContext,
    getTrajectoryDurationSec,
    getAnalysisHopDurationSec,
    getSelectionAnalysisState: () => timbreSelectionAnalysis,
    trajectoryVisualizer,
    isTerrainMode,
    getEnableSelectionPlaybackMask: () => !!settings.enableSelectionPlaybackMask,
    getEnableNodeFlash: () => !!settings.enableNodeFlash,
    highlightOnset: (analysis, event, options) => triggerTimbreOnsetHighlight(analysis, event, options),
    onsetResetMinSec: TIMBRE_ONSET_RESET_MIN_SEC,
});

const {
    advanceOnsetPulses: advanceTimbreSelectionOnsetPulses,
    attachPlaybackMaskGain: attachTimbrePlaybackMaskGain,
    getPlaybackTimeSec: getTrajectoryPlaybackTimeSec,
    resetPlaybackAnchor: resetTrajectoryPlaybackAnchor,
    resetRuntime: resetTimbreTransportRuntime,
    syncVisualizerToCurrentTime,
    updateSelectionPlaybackMask,
} = timbreTransportRuntime;

let academicAxesObject = null;
let academicAxesMaterial = null;
let academicAxisLabelGroup = null;
let academicAxisLabelEntries = [];
let academicAxisHeaders = ['', '', ''];
let academicAxisRanges = {
    x: { min: 0, max: 0 },
    y: { min: 0, max: 0 },
    z: { min: 0, max: 0 },
};

let terrainAxes = null;

const axisTitleFor = (axisIndex) => {
    const custom = [settings.axesTextX, settings.axesTextY, settings.axesTextZ][axisIndex] || '';
    if (settings.editAxesText && custom.trim() !== '') return custom.trim();
    return academicAxisHeaders[axisIndex] || ['X', 'Y', 'Z'][axisIndex];
};

const applyRenderOrderSettings = () => {
    trajectoryVisualizer.setRenderOrders({
        line: settings.renderOrderLine,
        lineEnhancer: settings.renderOrderLineEnhancer,
        nodes: settings.renderOrderNodes,
    });
    if (academicAxesObject) {
        academicAxesObject.renderOrder = settings.renderOrderAxes;
    }
};

const applyGraphSettings = () => {
    const inTimbreMode = !isTerrainMode();
    const showLines = settings.showAxesLines && inTimbreMode;
    const showText = settings.showLabels && settings.showAxesText && inTimbreMode;
    if (academicAxesObject) academicAxesObject.visible = showLines;
    if (academicAxisLabelGroup) academicAxisLabelGroup.visible = showText;
    if (academicAxesMaterial) academicAxesMaterial.color.set(settings.axesColor);

    for (const entry of academicAxisLabelEntries) {
        if (entry.label) entry.label.visible = showText;
        const axisTitle = axisTitleFor(entry.axisIndex);
        entry.div.textContent = `${axisTitle}: ${entry.value.toFixed(2)}`;
    }
};

const applyTerrainGraphSettings = () => {
    terrainAxes?.applyGraphSettings();
};

const buildTerrainAxes = () => {
    terrainAxes?.buildAxes();
};

const shouldRenderAxisLabels = () => settings.showLabels && (
    isTerrainMode() ? settings.terrainShowAxesText : settings.showAxesText
);

const updateLabelRendererVisibility = () => {
    labelRenderer.domElement.style.display = shouldRenderAxisLabels() ? 'block' : 'none';
};

const clearAccumulatedViews = () => {
    trajectoryVisualizer.clearAccumulatedView();
    terrainVisualizer.clearAccumulatedView();
};

const accumulateCurrentPipelineView = () => {
    if (isTerrainMode()) {
        terrainVisualizer.accumulateCurrentView();
        return;
    }
    trajectoryVisualizer.accumulateCurrentView();
};

const terrainStretchSettings = () => ({
    x: Math.max(0.1, settings.terrainStretchFreq ?? 1),
    y: Math.max(0.1, settings.terrainStretchAmp ?? 1),
    z: Math.max(0.1, settings.terrainStretchTime ?? 1),
});

let terrainAxisColorValueModeController;
let fSelectionSculpt;
let fTerrainAxisColors;
let fTerrainTimeWindows;
let fTerrainPlaneSelections;
let fTimbreSelectionActions;
let fSelectionSculptGeneral;
let fSelectionSculptStatus;
let fSelectionSculptDisplay;
let fSelectionSculptAppearance;
let terrainAxisColorFolders = [];
let terrainTimeWindowFolders = [];
let terrainPlaneSelectionFolders = [];
let terrainSculptStatusControllers = [];
let timbrePlaneSelectionControlService = null;
let terrainSculptOverviewController = null;
let lastTerrainVisibleWindowKey = '';
const terrainScaleControlRegistry = createTerrainScaleControlRegistry({ settings });
const terrainSculptStatusState = createTerrainSculptStatusState();

const refreshTerrainSculptStatusControllers = () => {
    for (const controller of terrainSculptStatusControllers) {
        controller.updateDisplay();
    }
};

const terrainSelectionSpaceLabel = (planeKey, { compact = false } = {}) => (
    terrainSelectionSpaceLabelFromModel(planeKey, TERRAIN_PLANE_SELECTION_META, { compact })
);

const getDefaultTerrainSculptTargetLabel = () => getDefaultTerrainSculptTargetLabelFromModel({
    terrainMode: isTerrainMode(),
});

const setTerrainSculptCurrentTarget = (nextTarget) => {
    const resolvedTarget = resolveTerrainSculptTargetLabel({
        nextTarget,
        terrainMode: isTerrainMode(),
    });
    if (terrainSculptStatusState.currentlySelected === resolvedTarget) return;
    terrainSculptStatusState.currentlySelected = resolvedTarget;
    refreshTerrainSculptStatusControllers();
    terrainSculptOverviewController?.render?.();
};

const describeTerrainInteractionTarget = ({ planeKey, source } = {}) => describeTerrainInteractionTargetFromModel({
    planeKey,
    source,
    planeSelectionMeta: TERRAIN_PLANE_SELECTION_META,
});

const handleTerrainInteractionTargetChange = (targetInfo = {}) => {
    setTerrainSculptCurrentTarget(describeTerrainInteractionTarget(targetInfo));
};

const terrainAxisBoundsByKey = (axisKey) => {
    const scaleBounds = terrainScaleBoundsFromSettings();
    const ranges = {
        x: [scaleBounds.frequencyMin, scaleBounds.frequencyMax],
        y: [scaleBounds.amplitudeMin, scaleBounds.amplitudeMax],
        z: [scaleBounds.timeMin, scaleBounds.timeMax],
    };
    const [min, max] = ranges[axisKey] ?? [0, 100];
    return { min, max };
};

const terrainAxisPctToDisplayValue = (axisKey, pctValue) => {
    if (settings.terrainAxisColorValueMode !== 'Axis Values') {
        return pctValue;
    }

    const { min, max } = terrainAxisBoundsByKey(axisKey);
    return min + ((pctValue / 100) * (max - min));
};

const terrainAxisDisplayValueToPct = (axisKey, displayValue) => {
    if (settings.terrainAxisColorValueMode !== 'Axis Values') {
        return displayValue;
    }

    const { min, max } = terrainAxisBoundsByKey(axisKey);
    const range = Math.max(1e-6, max - min);
    return THREE.MathUtils.clamp(((displayValue - min) / range) * 100, 0, 100);
};

const terrainAxisBreakpointControlBounds = (axisKey, minPct, maxPct) => {
    if (settings.terrainAxisColorValueMode !== 'Axis Values') {
        return { min: minPct, max: maxPct, step: 0.1 };
    }

    const minValue = terrainAxisPctToDisplayValue(axisKey, minPct);
    const maxValue = terrainAxisPctToDisplayValue(axisKey, maxPct);
    return {
        min: minValue,
        max: maxValue,
        step: Math.max(Math.abs(maxValue - minValue) / 500, 1e-3),
    };
};

const formatTerrainPercent = (value) => {
    if (!Number.isFinite(value)) return '?';
    const rounded = Math.round(value * 10) / 10;
    if (Math.abs(rounded - Math.round(rounded)) < 1e-6) {
        return String(Math.round(rounded));
    }
    return rounded.toFixed(1).replace(/\.0$/, '');
};

const terrainAxisIntervalLabel = (axisKey, intervalIndex, intervals) => {
    const startPercent = intervalIndex === 0 ? 0 : intervals[intervalIndex - 1].endPct;
    const endPercent = intervals[intervalIndex].endPct;

    if (settings.terrainAxisColorValueMode === 'Axis Values') {
        return `Interval ${intervalIndex + 1} (${formatTerrainAxisValue(terrainAxisPctToDisplayValue(axisKey, startPercent))}-${formatTerrainAxisValue(terrainAxisPctToDisplayValue(axisKey, endPercent))})`;
    }

    return `Interval ${intervalIndex + 1} (${formatTerrainPercent(startPercent)}-${formatTerrainPercent(endPercent)}%)`;
};

const terrainTimeWindowLabel = (regionIndex, region) => (
    `Window ${regionIndex + 1} (${formatTerrainPercent(region.startPct)}-${formatTerrainPercent(region.endPct)}%)`
);

const markTerrainStatusControllerReadOnly = (controller) => {
    if (!controller?.domElement) return controller;
    controller.domElement.style.pointerEvents = 'none';
    controller.domElement.style.opacity = '0.82';
    const input = controller.domElement.querySelector('input');
    if (input) input.setAttribute('readonly', 'readonly');
    return controller;
};

const formatTerrainPctRangeLabel = (minPct, maxPct) => (
    `${formatTerrainPercent(minPct)}-${formatTerrainPercent(maxPct)}%`
);

const getTerrainVisibleFrameWindowSnapshot = () => getTerrainVisibleFrameWindowSnapshotFromModel(terrainVisualizer);

const terrainFrameIndexToFullClipPct = (frameIndex, frameCount = terrainVisualizer.getFrameDataCount?.() ?? 0) => (
    terrainFrameIndexToFullClipPctFromModel(frameIndex, frameCount)
);

const formatTerrainRenderedSliceLabel = (
    visibleWindow = getTerrainVisibleFrameWindowSnapshot(),
    frameCount = terrainVisualizer.getFrameDataCount?.() ?? 0,
) => formatTerrainRenderedSliceLabelFromModel(visibleWindow, frameCount);

const getTerrainFullClipTimeRangePct = (planeSelections = settings.terrainPlaneSelections) => (
    getTerrainFullClipTimeRangePctFromModel(planeSelections)
);

const getTerrainFullClipFrameRange = (planeSelections = settings.terrainPlaneSelections, frameCount = terrainVisualizer.getFrameDataCount?.() ?? 0) => (
    getTerrainFullClipFrameRangeFromModel(planeSelections, frameCount)
);

const terrainVisibleDepthPctToFrameIndex = (depthPct, visibleWindow = getTerrainVisibleFrameWindowSnapshot()) => (
    terrainVisibleDepthPctToFrameIndexFromModel(depthPct, visibleWindow)
);

const terrainFullClipFrameRangeToVisibleDepthPctRange = (startFrame, endFrame, visibleWindow = getTerrainVisibleFrameWindowSnapshot()) => (
    terrainFullClipFrameRangeToVisibleDepthPctRangeFromModel(startFrame, endFrame, visibleWindow)
);

const syncTerrainDisplayedTimeRangesFromFullClipSelection = (planeSelections = settings.terrainPlaneSelections) => (
    syncTerrainDisplayedTimeRangesFromFullClipSelectionInModel({
        planeSelections,
        visibleWindow: getTerrainVisibleFrameWindowSnapshot(),
        normalizePlaneSelectionRange: normalizeTerrainPlaneSelectionRange,
    })
);

const syncTerrainFullClipTimeSelectionFromDisplayedPlanes = (planeSelections = settings.terrainPlaneSelections) => (
    syncTerrainFullClipTimeSelectionFromDisplayedPlanesInModel({
        planeSelections,
        visibleWindow: getTerrainVisibleFrameWindowSnapshot(),
        volumeSelection: deriveTerrainVolumeSelection(planeSelections),
        frameCount: terrainVisualizer.getFrameDataCount?.() ?? 0,
    })
);

const syncTerrainSculptStatusDisplay = () => {
    const planeSelections = ensureTerrainPlaneSelectionSettings();
    const terrainSelectionModel = buildTerrainCanonicalSelectionModel({
        planeSelections,
        planeSelectionMeta: TERRAIN_PLANE_SELECTION_META,
        terrainMode: isTerrainMode(),
        currentTarget: terrainSculptStatusState.currentlySelected,
        frameCount: terrainVisualizer.getFrameDataCount?.() ?? 0,
        visibleWindow: getTerrainVisibleFrameWindowSnapshot(),
    });

    Object.assign(terrainSculptStatusState, terrainSelectionModel.status);
    refreshTerrainSculptStatusControllers();
};

const rebuildTerrainTimeWindowControls = () => {
    const timeWindows = ensureTerrainTimeWindowSettings();

    if (fTerrainTimeWindows) {
        fTerrainTimeWindows.destroy();
    }
    terrainTimeWindowFolders = [];
    fTerrainTimeWindows = fTerrainAxisColors.addFolder('Timeline Windows');

    fTerrainTimeWindows.add(timeWindows, 'enabled').name('Enabled').onChange(applyTerrainAxisColorSettings);
    fTerrainTimeWindows.add(timeWindows, 'regionCount', 0, 8, 1).name('Window Count').onChange((value) => {
        timeWindows.regionCount = Math.round(value);
        ensureTerrainTimeWindowSettings();
        rebuildTerrainTimeWindowControls();
        applyTerrainAxisColorSettings();
    });

    for (let regionIndex = 0; regionIndex < timeWindows.regionCount; regionIndex++) {
        const region = timeWindows.regions[regionIndex];
        const regionFolder = fTerrainTimeWindows.addFolder(terrainTimeWindowLabel(regionIndex, region));
        terrainTimeWindowFolders.push(regionFolder);

        regionFolder.add(region, 'startPct', 0, 100, 0.1).name('Start %')
            .onChange(applyTerrainAxisColorSettings)
            .onFinishChange(() => {
                ensureTerrainTimeWindowSettings();
                rebuildTerrainTimeWindowControls();
                applyTerrainAxisColorSettings();
            });
        regionFolder.add(region, 'endPct', 0, 100, 0.1).name('End %')
            .onChange(applyTerrainAxisColorSettings)
            .onFinishChange(() => {
                ensureTerrainTimeWindowSettings();
                rebuildTerrainTimeWindowControls();
                applyTerrainAxisColorSettings();
            });
        regionFolder.addColor(region, 'tintColor').name('Tint Color').onChange(applyTerrainAxisColorSettings);
        regionFolder.add(region, 'strength', 0, 1, 0.01).name('Tint Strength').onChange(applyTerrainAxisColorSettings);
    }

    bindGuiFolderTitleShortcuts();
};

const rebuildTerrainPlaneSelectionControls = () => {
    const planeSelections = ensureTerrainPlaneSelectionSettings();

    if (fSelectionSculptGeneral) fSelectionSculptGeneral.destroy();
    if (fSelectionSculptStatus) fSelectionSculptStatus.destroy();
    if (fSelectionSculptDisplay) fSelectionSculptDisplay.destroy();
    if (fSelectionSculptAppearance) fSelectionSculptAppearance.destroy();
    if (fTerrainPlaneSelections) {
        fTerrainPlaneSelections.destroy();
    }
    terrainPlaneSelectionFolders = [];
    terrainSculptStatusControllers = [];

    if (!fSelectionSculpt) return;

    const sculptActions = {
        resetFullBox: () => {
            applyTerrainFullSpaceSelection(planeSelections);
            rebuildTerrainPlaneSelectionControls();
            applyTerrainPlaneSelectionSettings();
        },
        clearBox: () => {
            setTerrainSculptCurrentTarget(TERRAIN_FULL_MASK_LABEL);
            planeSelections.workflowMode = 'Manual Plane Selection';
            for (const [planeKey, planeMeta] of Object.entries(TERRAIN_PLANE_SELECTION_META)) {
                const selection = planeSelections[planeKey];
                if (!selection) continue;
                selection.enabled = false;
                selection.axis1MinPct = planeMeta.axis1MinPct;
                selection.axis1MaxPct = planeMeta.axis1MaxPct;
                selection.axis2MinPct = planeMeta.axis2MinPct;
                selection.axis2MaxPct = planeMeta.axis2MaxPct;
            }
            rebuildTerrainPlaneSelectionControls();
            applyTerrainPlaneSelectionSettings();
        },
    };

    fSelectionSculptGeneral = fSelectionSculpt.addFolder('Selection Model');
    terrainSculptStatusControllers.push(
        markTerrainStatusControllerReadOnly(fSelectionSculptGeneral.add(terrainSculptStatusState, 'currentlySelected').name('Current Target')),
    );
    fSelectionSculptGeneral.add(planeSelections, 'enabled').name('Enabled').onChange((nextEnabled) => {
        if (nextEnabled && planeSelections.workflowMode === 'Sculpt Full Selection') {
            applyTerrainFullSpaceSelection(planeSelections);
        }
        applyTerrainPlaneSelectionSettings();
    });
    fSelectionSculptGeneral.add(planeSelections, 'workflowMode', TERRAIN_SELECTION_WORKFLOW_MODES).name('Workflow').onChange((nextMode) => {
        if (nextMode === 'Sculpt Full Selection') {
            planeSelections.enabled = true;
            applyTerrainFullSpaceSelection(planeSelections);
        }
        rebuildTerrainPlaneSelectionControls();
        applyTerrainPlaneSelectionSettings();
    });
    fSelectionSculptGeneral.add(planeSelections, 'overviewMode', TERRAIN_SCULPT_OVERVIEW_MODES).name('Authoring View').onChange(() => {
        terrainSculptOverviewController?.syncVisibility?.();
        applyTerrainPlaneSelectionSettings({ preserveFullClip: true });
    });
    fSelectionSculptGeneral.add(sculptActions, 'resetFullBox').name('Reset Full Selection');
    fSelectionSculptGeneral.add(sculptActions, 'clearBox').name('Clear Selection');

    fSelectionSculptStatus = fSelectionSculpt.addFolder('Live Status');
    terrainSculptStatusControllers.push(
        markTerrainStatusControllerReadOnly(fSelectionSculptStatus.add(terrainSculptStatusState, 'selectionModel').name('Final Mask')),
        markTerrainStatusControllerReadOnly(fSelectionSculptStatus.add(terrainSculptStatusState, 'renderWindow').name('3D Window')),
        markTerrainStatusControllerReadOnly(fSelectionSculptStatus.add(terrainSculptStatusState, 'state').name('Mask')),
        markTerrainStatusControllerReadOnly(fSelectionSculptStatus.add(terrainSculptStatusState, 'activePlanes').name('Active Spaces')),
        markTerrainStatusControllerReadOnly(fSelectionSculptStatus.add(terrainSculptStatusState, 'frequency').name('Freq')),
        markTerrainStatusControllerReadOnly(fSelectionSculptStatus.add(terrainSculptStatusState, 'amplitude').name('Amp')),
        markTerrainStatusControllerReadOnly(fSelectionSculptStatus.add(terrainSculptStatusState, 'time').name('Time')),
    );

    fSelectionSculptDisplay = fSelectionSculpt.addFolder('3D Scene Overlay');
    fSelectionSculptDisplay.add(planeSelections, 'showSceneHandles').name('Show Sculpt Handles').onChange(() => {
        rebuildTerrainPlaneSelectionVisuals();
    });
    fSelectionSculptDisplay.add(planeSelections, 'showVolumeBox').name('Show Sculpt Space Box').onChange(() => {
        rebuildTerrainPlaneSelectionVisuals();
    });
    fSelectionSculptDisplay.add(planeSelections, 'grabType', TERRAIN_SELECTION_GRAB_TYPES).name('3D Drag Target').onChange(() => {
        rebuildTerrainPlaneSelectionVisuals();
    });

    fSelectionSculptAppearance = fSelectionSculpt.addFolder('Excluded Region Appearance');
    const unselectedModeController = fSelectionSculptAppearance.add(planeSelections, 'unselectedRegionMode', TERRAIN_UNSELECTED_APPEARANCE_MODES).name('Style');
    const unselectedSurfaceColorController = fSelectionSculptAppearance.addColor(planeSelections, 'unselectedRegionColor').name('Surface Color').onChange(applyTerrainPlaneSelectionSettings);
    const unselectedSurfaceStrengthController = fSelectionSculptAppearance.add(planeSelections, 'unselectedRegionStrength', 0, 1, 0.01).name('Surface Fade').onChange(applyTerrainPlaneSelectionSettings);
    const unselectedWireColorController = fSelectionSculptAppearance.addColor(planeSelections, 'unselectedWireColor').name('Wire Color').onChange(applyTerrainPlaneSelectionSettings);
    const unselectedWireOpacityController = fSelectionSculptAppearance.add(planeSelections, 'unselectedWireOpacity', 0, 1, 0.01).name('Wire Opacity').onChange(applyTerrainPlaneSelectionSettings);
    const unselectedWireStepController = fSelectionSculptAppearance.add(planeSelections, 'unselectedWireStep', 2, 12, 1).name('Wiremesh Step').onChange(applyTerrainPlaneSelectionSettings);
    const syncUnselectedAppearanceVisibility = () => {
        const showSurfaceControls = planeSelections.unselectedRegionMode !== 'Normal Surface';
        const showWireControls = planeSelections.unselectedRegionMode === 'Dim + Wiremesh' || planeSelections.unselectedRegionMode === 'Wiremesh Only';
        unselectedSurfaceColorController.domElement.style.display = showSurfaceControls ? '' : 'none';
        unselectedSurfaceStrengthController.domElement.style.display = showSurfaceControls ? '' : 'none';
        unselectedWireColorController.domElement.style.display = showWireControls ? '' : 'none';
        unselectedWireOpacityController.domElement.style.display = showWireControls ? '' : 'none';
        unselectedWireStepController.domElement.style.display = showWireControls ? '' : 'none';
    };
    unselectedModeController.onChange(() => {
        syncUnselectedAppearanceVisibility();
        applyTerrainPlaneSelectionSettings();
    });
    syncUnselectedAppearanceVisibility();

    fTerrainPlaneSelections = fSelectionSculpt.addFolder('Selection Spaces');

    for (const [planeKey, planeMeta] of Object.entries(TERRAIN_PLANE_SELECTION_META)) {
        const selection = planeSelections[planeKey];
        const planeFolder = fTerrainPlaneSelections.addFolder(planeMeta.label);
        terrainPlaneSelectionFolders.push(planeFolder);

        if (planeSelections.workflowMode === 'Manual Plane Selection') {
            planeFolder.add(selection, 'enabled').name('Enabled').onChange(applyTerrainPlaneSelectionSettings);
        }
        planeFolder.addColor(selection, 'tintColor').name('Tint Color').onChange(applyTerrainPlaneSelectionSettings);
        planeFolder.add(selection, 'strength', 0, 1, 0.01).name('Tint Strength').onChange(applyTerrainPlaneSelectionSettings);

        const addBoundController = (key, label) => {
            planeFolder.add(selection, key, 0, 100, 0.1).name(label)
                .onChange(applyTerrainPlaneSelectionSettings)
                .onFinishChange(() => {
                    normalizeTerrainPlaneSelectionRange(selection, 'axis1MinPct', 'axis1MaxPct');
                    normalizeTerrainPlaneSelectionRange(selection, 'axis2MinPct', 'axis2MaxPct');
                    applyTerrainPlaneSelectionSettings();
                });
        };

        addBoundController('axis1MinPct', `${planeMeta.axis1Label} Min %`);
        addBoundController('axis1MaxPct', `${planeMeta.axis1Label} Max %`);
        addBoundController('axis2MinPct', `${planeMeta.axis2Label} Min %`);
        addBoundController('axis2MaxPct', `${planeMeta.axis2Label} Max %`);

        const planeActions = {
            resetBounds: () => {
                if (planeSelections.workflowMode === 'Sculpt Full Selection') {
                    selection.enabled = true;
                    selection.axis1MinPct = 0;
                    selection.axis1MaxPct = 100;
                    selection.axis2MinPct = 0;
                    selection.axis2MaxPct = 100;
                } else {
                    selection.axis1MinPct = planeMeta.axis1MinPct;
                    selection.axis1MaxPct = planeMeta.axis1MaxPct;
                    selection.axis2MinPct = planeMeta.axis2MinPct;
                    selection.axis2MaxPct = planeMeta.axis2MaxPct;
                }
                applyTerrainPlaneSelectionSettings();
            },
        };
        planeFolder.add(planeActions, 'resetBounds').name('Reset Bounds');
    }

    syncTerrainSculptStatusDisplay();
    bindGuiFolderTitleShortcuts();
};

const ensureTerrainAxisColorSettings = () => {
    if (!settings.terrainAxisColors || typeof settings.terrainAxisColors !== 'object') {
        settings.terrainAxisColors = createDefaultTerrainAxisColors();
    }

    for (const axisKey of TERRAIN_AXIS_COLOR_KEYS) {
        const axisDefaults = TERRAIN_AXIS_COLOR_META[axisKey];
        const axisSettings = settings.terrainAxisColors[axisKey] && typeof settings.terrainAxisColors[axisKey] === 'object'
            ? settings.terrainAxisColors[axisKey]
            : {};

        settings.terrainAxisColors[axisKey] = axisSettings;
        axisSettings.enabled = axisSettings.enabled ?? axisDefaults.enabled;
        axisSettings.weight = Math.max(0, Number(axisSettings.weight ?? axisDefaults.weight ?? 1));
        axisSettings.intervalCount = THREE.MathUtils.clamp(
            Math.round(axisSettings.intervalCount ?? axisDefaults.intervalCount),
            1,
            8,
        );

        const existingIntervals = Array.isArray(axisSettings.intervals) ? axisSettings.intervals : [];
        let previousEndPct = 0;
        axisSettings.intervals = Array.from({ length: axisSettings.intervalCount }, (_, index) => {
            const existingInterval = existingIntervals[index];
            const fallbackInterval = axisDefaults.intervals[Math.min(index, axisDefaults.intervals.length - 1)];
            const defaultEndPct = ((index + 1) / axisSettings.intervalCount) * 100;

            const interval = existingInterval && typeof existingInterval === 'object'
                ? existingInterval
                : cloneTerrainAxisInterval(fallbackInterval);

            interval.minColor = interval.minColor ?? fallbackInterval.minColor;
            interval.maxColor = interval.maxColor ?? fallbackInterval.maxColor;

            if (index === axisSettings.intervalCount - 1) {
                interval.endPct = 100;
            } else {
                const remainingIntervals = axisSettings.intervalCount - index - 1;
                const maxEndPct = 100 - (remainingIntervals * 0.1);
                const requestedEndPct = Number.isFinite(Number(interval.endPct))
                    ? Number(interval.endPct)
                    : (fallbackInterval.endPct ?? defaultEndPct);
                interval.endPct = THREE.MathUtils.clamp(requestedEndPct, previousEndPct + 0.1, maxEndPct);
            }
            previousEndPct = interval.endPct;

            return interval;
        });
    }

    return settings.terrainAxisColors;
};

const ensureTerrainTimeWindowSettings = () => {
    if (!settings.terrainTimeWindows || typeof settings.terrainTimeWindows !== 'object') {
        settings.terrainTimeWindows = createDefaultTerrainTimeWindows();
    }

    const timeWindows = settings.terrainTimeWindows;
    timeWindows.enabled = timeWindows.enabled ?? TERRAIN_TIME_WINDOW_DEFAULTS.enabled;
    timeWindows.regionCount = THREE.MathUtils.clamp(
        Math.round(timeWindows.regionCount ?? TERRAIN_TIME_WINDOW_DEFAULTS.regionCount),
        0,
        8,
    );

    const existingRegions = Array.isArray(timeWindows.regions) ? timeWindows.regions : [];
    timeWindows.regions = Array.from({ length: timeWindows.regionCount }, (_, index) => {
        const fallbackRegion = TERRAIN_TIME_WINDOW_DEFAULTS.regions[
            Math.min(index, TERRAIN_TIME_WINDOW_DEFAULTS.regions.length - 1)
        ] ?? { startPct: 0, endPct: 100, tintColor: '#ffffff', strength: 0.25 };
        const region = existingRegions[index] && typeof existingRegions[index] === 'object'
            ? existingRegions[index]
            : cloneTerrainTimeWindow(fallbackRegion);

        const requestedStart = Number.isFinite(Number(region.startPct)) ? Number(region.startPct) : fallbackRegion.startPct;
        const requestedEnd = Number.isFinite(Number(region.endPct)) ? Number(region.endPct) : fallbackRegion.endPct;
        region.startPct = THREE.MathUtils.clamp(Math.min(requestedStart, requestedEnd), 0, 100);
        region.endPct = THREE.MathUtils.clamp(Math.max(requestedStart, requestedEnd), 0, 100);
        region.tintColor = region.tintColor ?? fallbackRegion.tintColor;
        region.strength = THREE.MathUtils.clamp(
            Number.isFinite(Number(region.strength)) ? Number(region.strength) : fallbackRegion.strength,
            0,
            1,
        );
        return region;
    });

    return timeWindows;
};

const normalizeTerrainPlaneSelectionRange = (selection, minKey, maxKey) => normalizePlaneSelectionRange(selection, minKey, maxKey);

const ensureTimbrePlaneSelectionSettings = () => {
    if (!settings.timbrePlaneSelections || typeof settings.timbrePlaneSelections !== 'object') {
        settings.timbrePlaneSelections = createDefaultTimbrePlaneSelections({
            timbrePlaneSelectionModes: TIMBRE_PLANE_SELECTION_MODES,
            selectionGrabTypes: TERRAIN_SELECTION_GRAB_TYPES,
        });
    }

    const planeSelections = settings.timbrePlaneSelections;
    planeSelections.showSceneHandles = planeSelections.showSceneHandles ?? true;
    planeSelections.showVolumeBox = planeSelections.showVolumeBox ?? true;
    planeSelections.grabType = TERRAIN_SELECTION_GRAB_TYPES.includes(planeSelections.grabType)
        ? planeSelections.grabType
        : 'Selection Surface';

    for (const [planeKey, planeMeta] of Object.entries(TERRAIN_PLANE_SELECTION_META)) {
        const existingSelection = planeSelections[planeKey] && typeof planeSelections[planeKey] === 'object'
            ? planeSelections[planeKey]
            : {};
        planeSelections[planeKey] = existingSelection;

        existingSelection.enabled = existingSelection.enabled ?? false;
        existingSelection.tintColor = existingSelection.tintColor ?? planeMeta.tintColor;
        existingSelection.strength = THREE.MathUtils.clamp(
            Number.isFinite(Number(existingSelection.strength)) ? Number(existingSelection.strength) : planeMeta.strength,
            0,
            1,
        );
        existingSelection.selectionMode = TIMBRE_PLANE_SELECTION_MODES.includes(existingSelection.selectionMode)
            ? existingSelection.selectionMode
            : 'Box';
        existingSelection.axis1MinPct = existingSelection.axis1MinPct ?? planeMeta.axis1MinPct;
        existingSelection.axis1MaxPct = existingSelection.axis1MaxPct ?? planeMeta.axis1MaxPct;
        existingSelection.axis2MinPct = existingSelection.axis2MinPct ?? planeMeta.axis2MinPct;
        existingSelection.axis2MaxPct = existingSelection.axis2MaxPct ?? planeMeta.axis2MaxPct;
        existingSelection.lassoPoints = normalizeTimbreLassoPoints(existingSelection.lassoPoints);

        normalizeTerrainPlaneSelectionRange(existingSelection, 'axis1MinPct', 'axis1MaxPct');
        normalizeTerrainPlaneSelectionRange(existingSelection, 'axis2MinPct', 'axis2MaxPct');
    }

    return planeSelections;
};

const ensureTerrainPlaneSelectionSettings = () => {
    if (!settings.terrainPlaneSelections || typeof settings.terrainPlaneSelections !== 'object') {
        settings.terrainPlaneSelections = createDefaultTerrainPlaneSelections();
    }

    const planeSelections = settings.terrainPlaneSelections;
    planeSelections.enabled = planeSelections.enabled ?? true;
    planeSelections.workflowMode = TERRAIN_SELECTION_WORKFLOW_MODES.includes(planeSelections.workflowMode)
        ? planeSelections.workflowMode
        : 'Sculpt Full Selection';
    planeSelections.overviewMode = TERRAIN_SCULPT_OVERVIEW_MODES.includes(planeSelections.overviewMode)
        ? planeSelections.overviewMode
        : '3D Terrain';
    planeSelections.showSceneHandles = planeSelections.showSceneHandles ?? true;
    planeSelections.showVolumeBox = planeSelections.showVolumeBox ?? true;
    planeSelections.grabType = TERRAIN_SELECTION_GRAB_TYPES.includes(planeSelections.grabType)
        ? planeSelections.grabType
        : 'Selection Surface';
    planeSelections.fullClipTimeMinPct = Number.isFinite(Number(planeSelections.fullClipTimeMinPct))
        ? THREE.MathUtils.clamp(Number(planeSelections.fullClipTimeMinPct), 0, 100)
        : 0;
    planeSelections.fullClipTimeMaxPct = Number.isFinite(Number(planeSelections.fullClipTimeMaxPct))
        ? THREE.MathUtils.clamp(Number(planeSelections.fullClipTimeMaxPct), 0, 100)
        : 100;
    planeSelections.unselectedRegionMode = TERRAIN_UNSELECTED_APPEARANCE_MODES.includes(planeSelections.unselectedRegionMode)
        ? planeSelections.unselectedRegionMode
        : 'Dim + Wiremesh';
    planeSelections.unselectedRegionColor = typeof planeSelections.unselectedRegionColor === 'string' && planeSelections.unselectedRegionColor
        ? planeSelections.unselectedRegionColor
        : '#09131d';
    planeSelections.unselectedRegionStrength = THREE.MathUtils.clamp(
        Number.isFinite(Number(planeSelections.unselectedRegionStrength)) ? Number(planeSelections.unselectedRegionStrength) : 0.76,
        0,
        1,
    );
    planeSelections.unselectedWireColor = typeof planeSelections.unselectedWireColor === 'string' && planeSelections.unselectedWireColor
        ? planeSelections.unselectedWireColor
        : '#8de2ff';
    planeSelections.unselectedWireOpacity = THREE.MathUtils.clamp(
        Number.isFinite(Number(planeSelections.unselectedWireOpacity)) ? Number(planeSelections.unselectedWireOpacity) : 0.42,
        0,
        1,
    );
    planeSelections.unselectedWireStep = THREE.MathUtils.clamp(
        Math.round(Number.isFinite(Number(planeSelections.unselectedWireStep)) ? Number(planeSelections.unselectedWireStep) : 4),
        2,
        12,
    );

    for (const [planeKey, planeMeta] of Object.entries(TERRAIN_PLANE_SELECTION_META)) {
        const existingSelection = planeSelections[planeKey] && typeof planeSelections[planeKey] === 'object'
            ? planeSelections[planeKey]
            : {};
        planeSelections[planeKey] = existingSelection;

        existingSelection.enabled = existingSelection.enabled ?? false;
        existingSelection.tintColor = existingSelection.tintColor ?? planeMeta.tintColor;
        existingSelection.strength = THREE.MathUtils.clamp(
            Number.isFinite(Number(existingSelection.strength)) ? Number(existingSelection.strength) : planeMeta.strength,
            0,
            1,
        );
        existingSelection.selectionMode = TIMBRE_PLANE_SELECTION_MODES.includes(existingSelection.selectionMode)
            ? existingSelection.selectionMode
            : 'Box';
        existingSelection.axis1MinPct = existingSelection.axis1MinPct ?? planeMeta.axis1MinPct;
        existingSelection.axis1MaxPct = existingSelection.axis1MaxPct ?? planeMeta.axis1MaxPct;
        existingSelection.axis2MinPct = existingSelection.axis2MinPct ?? planeMeta.axis2MinPct;
        existingSelection.axis2MaxPct = existingSelection.axis2MaxPct ?? planeMeta.axis2MaxPct;
        existingSelection.lassoPoints = normalizeTimbreLassoPoints(existingSelection.lassoPoints);

        normalizeTerrainPlaneSelectionRange(existingSelection, 'axis1MinPct', 'axis1MaxPct');
        normalizeTerrainPlaneSelectionRange(existingSelection, 'axis2MinPct', 'axis2MaxPct');
    }

    if (
        planeSelections.workflowMode === 'Sculpt Full Selection' &&
        !Object.keys(TERRAIN_PLANE_SELECTION_META).some((planeKey) => planeSelections[planeKey]?.enabled)
    ) {
        applyTerrainFullSpaceSelection(planeSelections);
    }

    if (planeSelections.workflowMode === 'Sculpt Full Selection') {
        syncTerrainDisplayedTimeRangesFromFullClipSelection(planeSelections);
    }

    return planeSelections;
};

const ensureTerrain2DGraphSettings = () => {
    if (!settings.terrain2DGraphs || typeof settings.terrain2DGraphs !== 'object') {
        settings.terrain2DGraphs = createDefaultTerrain2DGraphs(settings.terrainTimeDepth);
    }

    for (const [graphKey, graphMeta] of Object.entries(TERRAIN_2D_GRAPH_META)) {
        const defaultExtension = getDefaultTerrain2DGraphExtension(settings.terrainTimeDepth);
        const existingGraph = settings.terrain2DGraphs[graphKey] && typeof settings.terrain2DGraphs[graphKey] === 'object'
            ? settings.terrain2DGraphs[graphKey]
            : {};
        settings.terrain2DGraphs[graphKey] = existingGraph;

        existingGraph.enabled = existingGraph.enabled ?? graphMeta.enabled;
        existingGraph.showGraphsAs = TERRAIN_2D_GRAPH_SHOW_MODES.includes(existingGraph.showGraphsAs)
            ? existingGraph.showGraphsAs
            : graphMeta.showGraphsAs;
        existingGraph.graphType = TERRAIN_2D_GRAPH_TYPES.includes(existingGraph.graphType)
            ? existingGraph.graphType
            : graphMeta.graphType;
        existingGraph.surface = TERRAIN_2D_GRAPH_SURFACES.includes(existingGraph.surface)
            ? existingGraph.surface
            : graphMeta.surface;
        existingGraph.graphOpacity = THREE.MathUtils.clamp(
            Number.isFinite(Number(existingGraph.graphOpacity)) ? Number(existingGraph.graphOpacity) : graphMeta.graphOpacity,
            0,
            1,
        );
        existingGraph.backgroundEnabled = existingGraph.backgroundEnabled ?? graphMeta.backgroundEnabled;
        existingGraph.backgroundColor = existingGraph.backgroundColor ?? graphMeta.backgroundColor;
        existingGraph.backgroundOpacity = THREE.MathUtils.clamp(
            Number.isFinite(Number(existingGraph.backgroundOpacity)) ? Number(existingGraph.backgroundOpacity) : graphMeta.backgroundOpacity,
            0,
            1,
        );
        existingGraph.offset = Math.max(
            0,
            Number.isFinite(Number(existingGraph.offset)) ? Number(existingGraph.offset) : graphMeta.offset,
        );
        existingGraph.heatStrength = Math.max(
            0,
            Number.isFinite(Number(existingGraph.heatStrength)) ? Number(existingGraph.heatStrength) : graphMeta.heatStrength,
        );
        existingGraph.extendBefore = Math.max(
            0,
            Number.isFinite(Number(existingGraph.extendBefore)) ? Number(existingGraph.extendBefore) : defaultExtension,
        );
        existingGraph.extendAfter = Math.max(
            0,
            Number.isFinite(Number(existingGraph.extendAfter)) ? Number(existingGraph.extendAfter) : defaultExtension,
        );
    }

    return settings.terrain2DGraphs;
};

const deriveTerrainVolumeSelection = (planeSelections) => deriveTerrainVolumeSelectionInModel(planeSelections);

const applyTerrainFullSpaceSelection = (planeSelections = settings.terrainPlaneSelections) => {
    setTerrainSculptCurrentTarget(TERRAIN_FULL_MASK_LABEL);
    return applyTerrainFullSpaceSelectionInModel(planeSelections, {
        planeSelectionMeta: TERRAIN_PLANE_SELECTION_META,
        normalizePlaneSelectionRange: normalizeTerrainPlaneSelectionRange,
    });
};

const getTerrainPlaneSelectionCoverage = (planeSelections) => (
    getTerrainPlaneSelectionCoverageFromModel(planeSelections, TERRAIN_PLANE_SELECTION_META)
);

const scalePctRangeToDiscreteRange = (minPct, maxPct, totalCount) => {
    const safeTotal = Math.max(1, Math.round(totalCount || 1));
    const maxIndex = Math.max(0, safeTotal - 1);
    const minIndex = Math.round((THREE.MathUtils.clamp(minPct, 0, 100) / 100) * maxIndex);
    const maxRangeIndex = Math.round((THREE.MathUtils.clamp(maxPct, 0, 100) / 100) * maxIndex);

    return {
        startBin: Math.max(0, Math.min(minIndex, maxRangeIndex)),
        endBin: Math.max(0, Math.max(minIndex, maxRangeIndex)),
        totalBins: safeTotal,
    };
};

const resolveTerrainFrameTimeRange = (frameIndex, asset) => {
    const safeFrameIndex = Math.max(0, Math.round(frameIndex || 0));
    const clipDurationSec = Math.max(0, Number(asset?.analysisClipDurationSec) || 0);
    const hopDurationSec = Math.max(
        Number(asset?.analysisHopDurationSec) || 0,
        (clipDurationSec > 0 && Number(asset?.analysisFrameCount) > 1)
            ? clipDurationSec / (Number(asset.analysisFrameCount) - 1)
            : 0,
    );
    const windowDurationSec = Math.max(Number(asset?.analysisWindowDurationSec) || 0, hopDurationSec, 0.01);
    const centerTimeSec = safeFrameIndex * hopDurationSec;
    const startSec = Math.max(0, centerTimeSec - (windowDurationSec * 0.5));
    const unclampedEndSec = centerTimeSec + (windowDurationSec * 0.5);

    return {
        startSec,
        endSec: clipDurationSec > 0
            ? Math.min(clipDurationSec, Math.max(startSec + 0.001, unclampedEndSec))
            : Math.max(startSec + 0.001, unclampedEndSec),
    };
};

const getTerrainVisibleFrameWindow = () => {
    return getTerrainVisibleFrameWindowSnapshot();
};

const buildBackendCallMonitorState = () => {
    const selectedAsset = getSelectedAudioAsset();
    const terrainMode = isTerrainMode();
    const planeSelections = ensureTerrainPlaneSelectionSettings();
    const visibleFrameWindow = getTerrainVisibleFrameWindow();
    const frameDataCount = terrainVisualizer.getFrameDataCount?.() ?? 0;
    const terrainSelectionModel = buildTerrainCanonicalSelectionModel({
        planeSelections,
        planeSelectionMeta: TERRAIN_PLANE_SELECTION_META,
        terrainMode,
        currentTarget: terrainSculptStatusState.currentlySelected,
        frameCount: frameDataCount,
        visibleWindow: visibleFrameWindow,
    });
    const coverage = terrainSelectionModel.coverage;
    const volumeSelection = terrainSelectionModel.volumeSelection;
    const visibleFrameCount = Math.max(0, visibleFrameWindow.endExclusive - visibleFrameWindow.start);
    const displayBinCount = Math.max(1, Math.round(settings.terrainFrequencyBins || terrainVisualizer.binCount || 128));
    const fullClipTimeRangePct = terrainSelectionModel.fullClipTimeRangePct;
    const currentTargetLabel = terrainSelectionModel.currentTargetLabel;
    const activeSelectionSpaces = terrainSelectionModel.activeSelectionSpaces;
    const renderedSliceLabel = terrainSelectionModel.renderedSliceLabel;
    const currentTimbreAnalysis = getCurrentTimbreAnalysisSnapshot?.();

    const state = {
        asset: buildBackendCallAssetSnapshot(selectedAsset),
        uiContext: {
            visualizationMode: settings.visualizationMode,
            playbackTimeSec: getTrajectoryPlaybackTimeSec(),
            terrainTimeDepth: settings.terrainTimeDepth,
            terrainFrequencyBins: displayBinCount,
            visibleFrameWindow: {
                startFrame: visibleFrameWindow.start,
                endFrame: Math.max(visibleFrameWindow.start, visibleFrameWindow.endExclusive - 1),
                frameCount: visibleFrameCount,
            },
        },
        bioacoustics: buildBioacousticsBackendSnapshot(currentTimbreAnalysis, {
            targetLabel: 'Current Selection',
            targetKind: 'current',
        }),
        selection: {
            isReady: false,
            source: 'spectroterrain-sculpt-selection',
            selectionModel: terrainSelectionModel.status.selectionModel,
            currentTarget: currentTargetLabel,
            enabled: !!planeSelections.enabled,
            workflowMode: planeSelections.workflowMode,
            overviewMode: planeSelections.overviewMode,
            activePlanes: planeSelections.enabled ? coverage.activePlanes : [],
            activeSelectionSpaces,
            missingAxes: planeSelections.enabled ? coverage.missingAxes : [],
            statusMessage: 'Build the Full Sculpt Mask before calling the backend. The rendered slice is only the current view window.',
            fullClipTimePctRange: fullClipTimeRangePct,
            renderWindowLabel: renderedSliceLabel,
            terrainVolumeBoundsPct: planeSelections.enabled && volumeSelection.enabled
                ? {
                    xMinPct: volumeSelection.xMinPct,
                    xMaxPct: volumeSelection.xMaxPct,
                    yMinPct: volumeSelection.yMinPct,
                    yMaxPct: volumeSelection.yMaxPct,
                    zMinPct: volumeSelection.zMinPct,
                    zMaxPct: volumeSelection.zMaxPct,
                    tintColor: `#${volumeSelection.tintColor.getHexString()}`,
                    strength: volumeSelection.strength,
                }
                : null,
            visibleFrameWindow: {
                startFrame: visibleFrameWindow.start,
                endFrame: Math.max(visibleFrameWindow.start, visibleFrameWindow.endExclusive - 1),
                frameCount: visibleFrameCount,
            },
        },
    };

    if (!terrainMode) {
        state.selection.statusMessage = 'Switch to SpectroTerrain mode to inspect the rendered slice and edit the Full Sculpt Mask.';
        return state;
    }

    if (!planeSelections.enabled) {
        state.selection.statusMessage = 'Selection Sculpt is off. Turn it on to define the Full Sculpt Mask used by backend calls and exports.';
        return state;
    }

    if (!selectedAsset) {
        state.selection.statusMessage = 'Load an audio asset before calling the backend.';
        return state;
    }

    if (!terrainVisualizer.hasFrameData?.() || frameDataCount <= 0) {
        state.selection.statusMessage = 'Terrain frame data is not loaded yet for the current asset.';
        return state;
    }

    if (coverage.activePlanes.length === 0) {
        state.selection.statusMessage = 'No sculpt Selection Space is active. Use Reset Full Selection to start from the whole audio file, or enable spaces manually.';
        return state;
    }

    if (coverage.missingAxes.length > 0) {
        state.selection.statusMessage = `Complete the Full Sculpt Mask by covering: ${coverage.missingAxes.join(', ')}.`;
        return state;
    }

    if (!volumeSelection.enabled || visibleFrameCount <= 0) {
        state.selection.statusMessage = 'The current terrain plane bounds collapse to an empty 3D volume.';
        return state;
    }

    const fullClipFrameRange = terrainSelectionModel.fullClipFrameRange;
    if (!fullClipFrameRange) {
        state.selection.statusMessage = 'The current sculpt selection does not yet resolve to a valid full-clip time range.';
        return state;
    }

    const { startFrame, endFrame } = fullClipFrameRange;
    const startFrameTime = resolveTerrainFrameTimeRange(startFrame, selectedAsset);
    const endFrameTime = resolveTerrainFrameTimeRange(endFrame, selectedAsset);
    const fallbackDurationSec = Math.max(
        Number(selectedAsset.analysisWindowDurationSec) || Number(selectedAsset.analysisHopDurationSec) || 0.05,
        0.01,
    );
    const clipDurationSec = Math.max(0, Number(selectedAsset.analysisClipDurationSec) || 0);
    const timeStartSec = startFrameTime.startSec;
    const unclampedTimeEndSec = Math.max(startFrameTime.startSec + fallbackDurationSec, endFrameTime.endSec);
    const timeEndSec = clipDurationSec > 0
        ? Math.min(clipDurationSec, unclampedTimeEndSec)
        : unclampedTimeEndSec;
    const sampleRate = Math.max(1, Number(selectedAsset.analysisSampleRate) || 22050);

    state.selection = {
        ...state.selection,
        isReady: true,
        missingAxes: [],
        statusMessage: 'Ready. Backend actions will use the Full Sculpt Mask, not only the current rendered slice.',
        frameRange: {
            startFrame,
            endFrame,
            frameCount: Math.max(1, endFrame - startFrame + 1),
        },
        timeRangeSec: {
            start: timeStartSec,
            end: timeEndSec,
            duration: Math.max(0.001, timeEndSec - timeStartSec),
        },
        sampleRange: {
            start: Math.max(0, Math.floor(timeStartSec * sampleRate)),
            end: Math.max(Math.floor(timeStartSec * sampleRate) + 1, Math.ceil(timeEndSec * sampleRate)),
        },
        frequencyBinRange: scalePctRangeToDiscreteRange(volumeSelection.xMinPct, volumeSelection.xMaxPct, displayBinCount),
        amplitudePctRange: {
            min: volumeSelection.yMinPct,
            max: volumeSelection.yMaxPct,
        },
    };

    return state;
};

const syncBackendCallMonitorState = () => {
    if (!backendCallMonitorIpc || awaitingInitialLocalIntegrationState || suppressBackendCallMonitorSyncDepth > 0) return;
    try {
        backendCallMonitorIpc.send('backend-call-monitor:update-state', buildBackendCallMonitorState());
    } catch (error) {
        console.warn('Failed to sync backend call monitor state:', error);
    }
};

const openBackendCallMonitor = async () => {
    if (!backendCallMonitorIpc) return false;
    syncBackendCallMonitorState();
    try {
        await backendCallMonitorIpc.invoke('backend-call-monitor:open');
        return true;
    } catch (error) {
        console.error('Failed to open backend call monitor:', error);
        return false;
    }
};

const openAudioOnsetFinderCompanion = async () => {
    if (!backendCallMonitorIpc) return false;
    syncBackendCallMonitorState();
    try {
        const response = await backendCallMonitorIpc.invoke('shell:open-companion', {
            targetShell: 'audio-onset-finder',
        });
        if (response?.ok === false) {
            throw new Error(response?.error || 'Failed to open the AudioOnsetFinder companion shell.');
        }
        return true;
    } catch (error) {
        console.error('Failed to open AudioOnsetFinder companion shell:', error);
        window.alert(error?.message || 'Failed to open the AudioOnsetFinder companion shell.');
        return false;
    }
};

if (backendCallMonitorIpc?.on) {
    backendCallMonitorIpc.on('backend-call:completed', (_event, response) => {
        applyImportedBioacousticsWorkbookResult(response);
    });
    backendCallMonitorIpc.on('local-integration:event', (_event, eventPayload) => {
        void queueCanonicalLocalIntegrationApply(eventPayload?.audioManager || null);
    });
}

const applyTerrainPlaneSelectionSettings = () => {
    const planeSelections = ensureTerrainPlaneSelectionSettings();
    if (planeSelections.enabled && planeSelections.workflowMode === 'Sculpt Full Selection') {
        syncTerrainFullClipTimeSelectionFromDisplayedPlanes(planeSelections);
        syncTerrainDisplayedTimeRangesFromFullClipSelection(planeSelections);
    }
    terrainSelectionController?.applySettings();
    terrainSculptOverviewController?.render?.();
    syncTerrainSculptStatusDisplay();
    syncBackendCallMonitorState();
};

const applyTerrain2DGraphSettings = () => terrainController.apply2DGraphSettings();

const applyTerrainHelperPreference = () => terrainController.applyHelperPreference();

const applyTerrainOverviewSelection = ({ timeMinPct, timeMaxPct, frequencyMinPct, frequencyMaxPct } = {}) => {
    const planeSelections = ensureTerrainPlaneSelectionSettings();
    if (planeSelections.workflowMode !== 'Sculpt Full Selection') {
        applyTerrainFullSpaceSelection(planeSelections);
    }

    setTerrainSculptCurrentTarget(describeTerrainInteractionTarget({ source: '2d-overview' }));
    planeSelections.enabled = true;
    planeSelections.fullClipTimeMinPct = THREE.MathUtils.clamp(Math.min(timeMinPct, timeMaxPct), 0, 100);
    planeSelections.fullClipTimeMaxPct = THREE.MathUtils.clamp(Math.max(timeMinPct, timeMaxPct), 0, 100);
    planeSelections.xz.enabled = true;
    planeSelections.xz.axis1MinPct = THREE.MathUtils.clamp(Math.min(frequencyMinPct, frequencyMaxPct), 0, 100);
    planeSelections.xz.axis1MaxPct = THREE.MathUtils.clamp(Math.max(frequencyMinPct, frequencyMaxPct), 0, 100);
    normalizeTerrainPlaneSelectionRange(planeSelections.xz, 'axis1MinPct', 'axis1MaxPct');
    syncTerrainDisplayedTimeRangesFromFullClipSelection(planeSelections);
    applyTerrainPlaneSelectionSettings();
};

terrainSculptOverviewController = createTerrainSculptOverviewController({
    panel: terrainSculptOverviewPanel,
    canvas: terrainSculptOverviewCanvas,
    meta: terrainSculptOverviewMeta,
    status: terrainSculptOverviewStatus,
    footer: terrainSculptOverviewFooter,
    terrainVisualizer,
    settings,
    isTerrainMode,
    getSelectedAsset: getSelectedAudioAsset,
    getPlaybackTimeSec: getTrajectoryPlaybackTimeSec,
    getDurationSec: getTrajectoryDurationSec,
    ensureTerrainPlaneSelectionSettings,
    getCurrentSelectionTargetLabel: () => terrainSculptStatusState.currentlySelected,
    getRenderedSliceLabel: () => formatTerrainRenderedSliceLabel(),
    applyOverviewSelection: applyTerrainOverviewSelection,
    onInteractionTargetChange: handleTerrainInteractionTargetChange,
});

const disposeTerrainSelectionObject = (object) => {
    object.traverse((child) => {
        if (child.geometry?.dispose) child.geometry.dispose();
        if (Array.isArray(child.material)) {
            child.material.forEach((material) => material?.dispose?.());
        } else if (child.material?.dispose) {
            child.material.dispose();
        }
    });
};

const getTerrainSceneBounds = () => {
    const { width: terrainWidth, height: terrainHeight, zDepth } = terrainVisualizer.getTerrainWorldBounds();
    const stretch = terrainStretchSettings();
    const width = terrainWidth * stretch.x;
    const height = terrainHeight * stretch.y;
    const depth = zDepth * stretch.z;

    return {
        width,
        height,
        depth,
        minX: -width * 0.5,
        maxX: width * 0.5,
        minY: 0,
        maxY: height,
        minZ: -depth,
        maxZ: 0,
    };
};

const terrainPctToSceneCoord = (axisKey, pctValue, bounds = getTerrainSceneBounds()) => {
    const pct = THREE.MathUtils.clamp(pctValue, 0, 100) / 100;
    if (axisKey === 'x') return bounds.minX + (bounds.width * pct);
    if (axisKey === 'y') return bounds.minY + (bounds.height * pct);
    return bounds.maxZ - (bounds.depth * pct);
};

const sceneCoordToTerrainPct = (axisKey, coordValue, bounds = getTerrainSceneBounds()) => {
    if (axisKey === 'x') return THREE.MathUtils.clamp(((coordValue - bounds.minX) / Math.max(bounds.width, 1e-6)) * 100, 0, 100);
    if (axisKey === 'y') return THREE.MathUtils.clamp(((coordValue - bounds.minY) / Math.max(bounds.height, 1e-6)) * 100, 0, 100);
    return THREE.MathUtils.clamp(((bounds.maxZ - coordValue) / Math.max(bounds.depth, 1e-6)) * 100, 0, 100);
};

const terrainSelectionAxisCoordFromPoint = (axisKey, point) => {
    if (axisKey === 'x') return point.x;
    if (axisKey === 'y') return point.y;
    return point.z;
};

const getTerrainPlaneSelectionPointPcts = (planeKey, point, bounds) => {
    const meta = TERRAIN_PLANE_SELECTION_META[planeKey];
    return {
        axis1Pct: sceneCoordToTerrainPct(meta.axis1Key, terrainSelectionAxisCoordFromPoint(meta.axis1Key, point), bounds),
        axis2Pct: sceneCoordToTerrainPct(meta.axis2Key, terrainSelectionAxisCoordFromPoint(meta.axis2Key, point), bounds),
    };
};

const shiftTerrainPlaneSelectionWindow = (startMinPct, startMaxPct, deltaPct) => shiftPlaneSelectionWindow(startMinPct, startMaxPct, deltaPct);

const getTerrainSelectionVisualOffset = (bounds) => Math.max(Math.min(bounds.width, bounds.height, bounds.depth) * 0.008, 0.35);
const getTerrainSelectionHandleOffset = (bounds) => getTerrainSelectionVisualOffset(bounds) * 1.8;

const createTerrainSelectionVolumeMesh = (volumeSelection, bounds) => {
    const minX = terrainPctToSceneCoord('x', volumeSelection.xMinPct, bounds);
    const maxX = terrainPctToSceneCoord('x', volumeSelection.xMaxPct, bounds);
    const minY = terrainPctToSceneCoord('y', volumeSelection.yMinPct, bounds);
    const maxY = terrainPctToSceneCoord('y', volumeSelection.yMaxPct, bounds);
    const minZ = terrainPctToSceneCoord('z', volumeSelection.zMinPct, bounds);
    const maxZ = terrainPctToSceneCoord('z', volumeSelection.zMaxPct, bounds);
    const geometry = new THREE.BoxGeometry(
        Math.max(0.2, Math.abs(maxX - minX)),
        Math.max(0.2, Math.abs(maxY - minY)),
        Math.max(0.2, Math.abs(maxZ - minZ)),
    );
    const color = volumeSelection.tintColor.clone();
    const root = new THREE.Group();

    const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: Math.max(0.05, volumeSelection.strength * 0.22),
        depthWrite: false,
        depthTest: false,
    }));
    const outline = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), new THREE.LineBasicMaterial({
        color,
        transparent: true,
        opacity: Math.max(0.2, volumeSelection.strength * 0.95),
        depthWrite: false,
        depthTest: false,
    }));

    root.position.set((minX + maxX) * 0.5, (minY + maxY) * 0.5, (minZ + maxZ) * 0.5);
    root.add(mesh);
    root.add(outline);
    return root;
};

const createTerrainSelectionPlaneMesh = (planeKey, selection, bounds, color) => {
    const meta = TERRAIN_PLANE_SELECTION_META[planeKey];
    const axis1Min = terrainPctToSceneCoord(meta.axis1Key, selection.axis1MinPct, bounds);
    const axis1Max = terrainPctToSceneCoord(meta.axis1Key, selection.axis1MaxPct, bounds);
    const axis2Min = terrainPctToSceneCoord(meta.axis2Key, selection.axis2MinPct, bounds);
    const axis2Max = terrainPctToSceneCoord(meta.axis2Key, selection.axis2MaxPct, bounds);
    const offset = getTerrainSelectionVisualOffset(bounds);

    let geometry;
    const meshMaterial = new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: Math.max(0.08, selection.strength * 0.65),
        depthWrite: false,
        side: THREE.DoubleSide,
    });
    const lineMaterial = new THREE.LineBasicMaterial({
        color,
        transparent: true,
        opacity: Math.max(0.18, selection.strength * 1.15),
        depthWrite: false,
    });

    const root = new THREE.Group();

    if (planeKey === 'xz') {
        geometry = new THREE.PlaneGeometry(Math.abs(axis1Max - axis1Min), Math.abs(axis2Max - axis2Min));
        geometry.rotateX(-Math.PI / 2);
        root.position.set((axis1Min + axis1Max) * 0.5, bounds.minY + offset, (axis2Min + axis2Max) * 0.5);
    } else if (planeKey === 'yz') {
        geometry = new THREE.PlaneGeometry(Math.abs(axis2Max - axis2Min), Math.abs(axis1Max - axis1Min));
        geometry.rotateY(Math.PI / 2);
        root.position.set(bounds.minX + offset, (axis1Min + axis1Max) * 0.5, (axis2Min + axis2Max) * 0.5);
    } else {
        geometry = new THREE.PlaneGeometry(Math.abs(axis1Max - axis1Min), Math.abs(axis2Max - axis2Min));
        root.position.set((axis1Min + axis1Max) * 0.5, (axis2Min + axis2Max) * 0.5, bounds.maxZ - offset);
    }

    const mesh = new THREE.Mesh(geometry, meshMaterial);
    const outline = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), lineMaterial);
    mesh.renderOrder = 20;
    outline.renderOrder = 21;
    mesh.userData = { planeKey, role: 'surface' };
    root.add(mesh);
    root.add(outline);
    return root;
};

const createTerrainSelectionHandlePosition = (planeKey, role, selection, bounds) => {
    const meta = TERRAIN_PLANE_SELECTION_META[planeKey];
    const axis1Min = terrainPctToSceneCoord(meta.axis1Key, selection.axis1MinPct, bounds);
    const axis1Max = terrainPctToSceneCoord(meta.axis1Key, selection.axis1MaxPct, bounds);
    const axis2Min = terrainPctToSceneCoord(meta.axis2Key, selection.axis2MinPct, bounds);
    const axis2Max = terrainPctToSceneCoord(meta.axis2Key, selection.axis2MaxPct, bounds);
    const axis1Mid = (axis1Min + axis1Max) * 0.5;
    const axis2Mid = (axis2Min + axis2Max) * 0.5;
    const offset = getTerrainSelectionHandleOffset(bounds);

    let axis1Coord = axis1Mid;
    let axis2Coord = axis2Mid;

    if (role === 'axis1Min') {
        axis1Coord = axis1Min;
    } else if (role === 'axis1Max') {
        axis1Coord = axis1Max;
    } else if (role === 'axis2Min') {
        axis2Coord = axis2Min;
    } else if (role === 'axis2Max') {
        axis2Coord = axis2Max;
    } else if (role === 'cornerMinMin') {
        axis1Coord = axis1Min;
        axis2Coord = axis2Min;
    } else if (role === 'cornerMaxMin') {
        axis1Coord = axis1Max;
        axis2Coord = axis2Min;
    } else if (role === 'cornerMinMax') {
        axis1Coord = axis1Min;
        axis2Coord = axis2Max;
    } else if (role === 'cornerMaxMax') {
        axis1Coord = axis1Max;
        axis2Coord = axis2Max;
    }

    if (planeKey === 'xz') {
        return new THREE.Vector3(axis1Coord, bounds.minY + offset, axis2Coord);
    }
    if (planeKey === 'yz') {
        return new THREE.Vector3(bounds.minX + offset, axis1Coord, axis2Coord);
    }
    return new THREE.Vector3(axis1Coord, axis2Coord, bounds.maxZ - offset);
};

terrainSelectionController = createTerrainSelectionController({
    scene,
    camera,
    controls,
    renderer,
    terrainVisualizer,
    settings,
    isTerrainMode,
    ensureTerrainPlaneSelectionSettings,
    terrainPlaneSelectionMeta: TERRAIN_PLANE_SELECTION_META,
    terrainSelectionHandleRoles: TERRAIN_SELECTION_HANDLE_ROLES,
    getTerrainSceneBounds,
    deriveTerrainVolumeSelection,
    createTerrainSelectionVolumeMesh,
    createTerrainSelectionPlaneMesh,
    createTerrainSelectionHandlePosition,
    disposeTerrainSelectionObject,
    getTerrainPlaneSelectionPointPcts,
    normalizeTerrainPlaneSelectionRange,
    shiftTerrainPlaneSelectionWindow,
    getTerrainSelectionVisualOffset,
    onInteractionTargetChange: handleTerrainInteractionTargetChange,
});

const rebuildTerrainPlaneSelectionVisuals = () => terrainSelectionController?.rebuildVisuals();
const startTerrainPlaneSelectionDrag = (event) => terrainSelectionController?.startDrag(event) ?? false;
const updateTerrainPlaneSelectionDrag = (event) => terrainSelectionController?.updateDrag(event);
const finishTerrainPlaneSelectionDrag = (event) => terrainSelectionController?.finishDrag(event);
const updateTerrainPlaneSelectionHover = (event) => terrainSelectionController?.updateHover(event);
const handleTerrainPlaneSelectionPointerLeave = () => terrainSelectionController?.handlePointerLeave();

const getTimbreSceneBounds = () => {
    if (trajectoryVisualizer.points.length === 0) {
        return {
            width: 1,
            height: 1,
            depth: 1,
            minX: -0.5,
            maxX: 0.5,
            minY: -0.5,
            maxY: 0.5,
            minZ: -0.5,
            maxZ: 0.5,
        };
    }

    let minX = Infinity;
    let minY = Infinity;
    let minZ = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    let maxZ = -Infinity;

    for (const point of trajectoryVisualizer.points) {
        minX = Math.min(minX, point.x);
        minY = Math.min(minY, point.y);
        minZ = Math.min(minZ, point.z);
        maxX = Math.max(maxX, point.x);
        maxY = Math.max(maxY, point.y);
        maxZ = Math.max(maxZ, point.z);
    }

    const ensureRange = (minValue, maxValue) => {
        if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) return [-50, 50];
        if (Math.abs(maxValue - minValue) < 1e-3) {
            const pad = Math.max(Math.abs(minValue) * 0.05, 1);
            return [minValue - pad, maxValue + pad];
        }
        return [minValue, maxValue];
    };

    [minX, maxX] = ensureRange(minX, maxX);
    [minY, maxY] = ensureRange(minY, maxY);
    [minZ, maxZ] = ensureRange(minZ, maxZ);

    return {
        width: Math.max(1e-3, maxX - minX),
        height: Math.max(1e-3, maxY - minY),
        depth: Math.max(1e-3, maxZ - minZ),
        minX,
        maxX,
        minY,
        maxY,
        minZ,
        maxZ,
    };
};

const timbrePctToSceneCoord = (axisKey, pctValue, bounds = getTimbreSceneBounds()) => {
    const pct = THREE.MathUtils.clamp(pctValue, 0, 100) / 100;
    if (axisKey === 'x') return bounds.minX + (bounds.width * pct);
    if (axisKey === 'y') return bounds.minY + (bounds.height * pct);
    return bounds.minZ + (bounds.depth * pct);
};

const sceneCoordToTimbrePct = (axisKey, coordValue, bounds = getTimbreSceneBounds()) => {
    if (axisKey === 'x') return THREE.MathUtils.clamp(((coordValue - bounds.minX) / Math.max(bounds.width, 1e-6)) * 100, 0, 100);
    if (axisKey === 'y') return THREE.MathUtils.clamp(((coordValue - bounds.minY) / Math.max(bounds.height, 1e-6)) * 100, 0, 100);
    return THREE.MathUtils.clamp(((coordValue - bounds.minZ) / Math.max(bounds.depth, 1e-6)) * 100, 0, 100);
};

const timbreSelectionAxisCoordFromPoint = (axisKey, point) => {
    if (axisKey === 'x') return point.x;
    if (axisKey === 'y') return point.y;
    return point.z;
};

const getTimbrePlaneSelectionPointPcts = (planeKey, point, bounds) => {
    const meta = TERRAIN_PLANE_SELECTION_META[planeKey];
    return {
        axis1Pct: sceneCoordToTimbrePct(meta.axis1Key, timbreSelectionAxisCoordFromPoint(meta.axis1Key, point), bounds),
        axis2Pct: sceneCoordToTimbrePct(meta.axis2Key, timbreSelectionAxisCoordFromPoint(meta.axis2Key, point), bounds),
    };
};

const createTimbreSelectionVolumeMesh = (volumeSelection, bounds) => {
    const minX = volumeSelection.minX;
    const maxX = volumeSelection.maxX;
    const minY = volumeSelection.minY;
    const maxY = volumeSelection.maxY;
    const minZ = volumeSelection.minZ;
    const maxZ = volumeSelection.maxZ;
    const geometry = new THREE.BoxGeometry(
        Math.max(0.2, Math.abs(maxX - minX)),
        Math.max(0.2, Math.abs(maxY - minY)),
        Math.max(0.2, Math.abs(maxZ - minZ)),
    );
    const color = volumeSelection.tintColor.clone();
    const root = new THREE.Group();

    const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: Math.max(0.05, volumeSelection.strength * 0.16),
        depthWrite: false,
        depthTest: false,
    }));
    const outline = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), new THREE.LineBasicMaterial({
        color,
        transparent: true,
        opacity: Math.max(0.24, volumeSelection.strength * 0.95),
        depthWrite: false,
        depthTest: false,
    }));

    root.position.set((minX + maxX) * 0.5, (minY + maxY) * 0.5, (minZ + maxZ) * 0.5);
    root.add(mesh);
    root.add(outline);
    return root;
};

const createTimbreSelectionGuidePlaneMesh = (planeKey, bounds, color) => {
    const guideRoot = createTimbreSelectionPlaneMesh(planeKey, {
        axis1MinPct: 0,
        axis1MaxPct: 100,
        axis2MinPct: 0,
        axis2MaxPct: 100,
        strength: 0.12,
    }, bounds, color);

    const guideMesh = guideRoot.children.find((child) => child.isMesh);
    const guideOutline = guideRoot.children.find((child) => child.isLineSegments);
    if (guideMesh?.material) {
        guideMesh.material.opacity = 0.04;
    }
    if (guideOutline?.material) {
        guideOutline.material.opacity = 0.18;
    }
    return guideRoot;
};

const createTimbreSelectionPlanePointWorldPosition = (planeKey, pointPct, bounds) => {
    const meta = TERRAIN_PLANE_SELECTION_META[planeKey];
    const axis1Coord = timbrePctToSceneCoord(meta.axis1Key, pointPct.axis1Pct, bounds);
    const axis2Coord = timbrePctToSceneCoord(meta.axis2Key, pointPct.axis2Pct, bounds);
    const offset = getTerrainSelectionVisualOffset(bounds);

    if (planeKey === 'xz') {
        return new THREE.Vector3(axis1Coord, bounds.minY + offset, axis2Coord);
    }
    if (planeKey === 'yz') {
        return new THREE.Vector3(bounds.minX + offset, axis1Coord, axis2Coord);
    }
    return new THREE.Vector3(axis1Coord, axis2Coord, bounds.maxZ + offset);
};

const createTimbreSelectionLassoMesh = (planeKey, lassoPoints, bounds, color, { closed = true, showHandles = false } = {}) => {
    const normalizedPoints = normalizeTimbreLassoPoints(lassoPoints);
    const root = new THREE.Group();
    if (normalizedPoints.length === 0) return root;

    const worldPoints = normalizedPoints.map((point) => createTimbreSelectionPlanePointWorldPosition(planeKey, point, bounds));
    const linePoints = closed && worldPoints.length >= 3
        ? [...worldPoints, worldPoints[0]]
        : worldPoints;

    if (linePoints.length >= 2) {
        const line = new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(linePoints),
            new THREE.LineBasicMaterial({
                color,
                transparent: true,
                opacity: 0.95,
                depthWrite: false,
                depthTest: false,
            }),
        );
        line.renderOrder = 23;
        root.add(line);
    }

    if (showHandles) {
        const handleRadius = Math.max(Math.min(bounds.width, bounds.height, bounds.depth) * 0.01, 0.5);
        for (const worldPoint of worldPoints) {
            const handle = new THREE.Mesh(
                new THREE.SphereGeometry(handleRadius, 10, 10),
                new THREE.MeshBasicMaterial({
                    color,
                    transparent: true,
                    opacity: 0.92,
                    depthWrite: false,
                    depthTest: false,
                }),
            );
            handle.position.copy(worldPoint);
            handle.renderOrder = 24;
            root.add(handle);
        }
    }

    return root;
};

const createTimbreSelectionPlaneMesh = (planeKey, selection, bounds, color) => {
    const meta = TERRAIN_PLANE_SELECTION_META[planeKey];
    const axis1Min = timbrePctToSceneCoord(meta.axis1Key, selection.axis1MinPct, bounds);
    const axis1Max = timbrePctToSceneCoord(meta.axis1Key, selection.axis1MaxPct, bounds);
    const axis2Min = timbrePctToSceneCoord(meta.axis2Key, selection.axis2MinPct, bounds);
    const axis2Max = timbrePctToSceneCoord(meta.axis2Key, selection.axis2MaxPct, bounds);
    const offset = getTerrainSelectionVisualOffset(bounds);

    let geometry;
    const meshMaterial = new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: Math.max(0.08, selection.strength * 0.42),
        depthWrite: false,
        side: THREE.DoubleSide,
    });
    const lineMaterial = new THREE.LineBasicMaterial({
        color,
        transparent: true,
        opacity: Math.max(0.18, selection.strength * 1.05),
        depthWrite: false,
    });

    const root = new THREE.Group();

    if (planeKey === 'xz') {
        geometry = new THREE.PlaneGeometry(Math.abs(axis1Max - axis1Min), Math.abs(axis2Max - axis2Min));
        geometry.rotateX(-Math.PI / 2);
        root.position.set((axis1Min + axis1Max) * 0.5, bounds.minY + offset, (axis2Min + axis2Max) * 0.5);
    } else if (planeKey === 'yz') {
        geometry = new THREE.PlaneGeometry(Math.abs(axis2Max - axis2Min), Math.abs(axis1Max - axis1Min));
        geometry.rotateY(Math.PI / 2);
        root.position.set(bounds.minX + offset, (axis1Min + axis1Max) * 0.5, (axis2Min + axis2Max) * 0.5);
    } else {
        geometry = new THREE.PlaneGeometry(Math.abs(axis1Max - axis1Min), Math.abs(axis2Max - axis2Min));
        root.position.set((axis1Min + axis1Max) * 0.5, (axis2Min + axis2Max) * 0.5, bounds.maxZ + offset);
    }

    const mesh = new THREE.Mesh(geometry, meshMaterial);
    const outline = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), lineMaterial);
    mesh.renderOrder = 20;
    outline.renderOrder = 21;
    mesh.userData = { planeKey, role: 'surface' };
    root.add(mesh);
    root.add(outline);
    return root;
};

const createTimbreSelectionHandlePosition = (planeKey, role, selection, bounds) => {
    const meta = TERRAIN_PLANE_SELECTION_META[planeKey];
    const axis1Min = timbrePctToSceneCoord(meta.axis1Key, selection.axis1MinPct, bounds);
    const axis1Max = timbrePctToSceneCoord(meta.axis1Key, selection.axis1MaxPct, bounds);
    const axis2Min = timbrePctToSceneCoord(meta.axis2Key, selection.axis2MinPct, bounds);
    const axis2Max = timbrePctToSceneCoord(meta.axis2Key, selection.axis2MaxPct, bounds);
    const axis1Mid = (axis1Min + axis1Max) * 0.5;
    const axis2Mid = (axis2Min + axis2Max) * 0.5;
    const offset = getTerrainSelectionHandleOffset(bounds);

    let axis1Coord = axis1Mid;
    let axis2Coord = axis2Mid;

    if (role === 'axis1Min') {
        axis1Coord = axis1Min;
    } else if (role === 'axis1Max') {
        axis1Coord = axis1Max;
    } else if (role === 'axis2Min') {
        axis2Coord = axis2Min;
    } else if (role === 'axis2Max') {
        axis2Coord = axis2Max;
    } else if (role === 'cornerMinMin') {
        axis1Coord = axis1Min;
        axis2Coord = axis2Min;
    } else if (role === 'cornerMaxMin') {
        axis1Coord = axis1Max;
        axis2Coord = axis2Min;
    } else if (role === 'cornerMinMax') {
        axis1Coord = axis1Min;
        axis2Coord = axis2Max;
    } else if (role === 'cornerMaxMax') {
        axis1Coord = axis1Max;
        axis2Coord = axis2Max;
    }

    if (planeKey === 'xz') {
        return new THREE.Vector3(axis1Coord, bounds.minY + offset, axis2Coord);
    }
    if (planeKey === 'yz') {
        return new THREE.Vector3(bounds.minX + offset, axis1Coord, axis2Coord);
    }
    return new THREE.Vector3(axis1Coord, axis2Coord, bounds.maxZ - offset);
};

timbreSelectionController = createTimbreSelectionController({
    scene,
    camera,
    controls,
    renderer,
    trajectoryVisualizer,
    settings,
    isTerrainMode,
    ensureTimbrePlaneSelectionSettings,
    timbrePlaneSelectionMeta: TERRAIN_PLANE_SELECTION_META,
    timbreSelectionHandleRoles: TERRAIN_SELECTION_HANDLE_ROLES,
    getTimbreSceneBounds,
    evaluateTimbreSelectionFromPlaneSettings,
    createTimbreSelectionVolumeMesh,
    createTimbreSelectionGuidePlaneMesh,
    createTimbreSelectionLassoMesh,
    createTimbreSelectionPlaneMesh,
    createTimbreSelectionHandlePosition,
    disposeTimbreSelectionObject: disposeTerrainSelectionObject,
    getTimbrePlaneSelectionPointPcts,
    normalizeTimbrePlaneSelectionRange: normalizeTerrainPlaneSelectionRange,
    shiftTimbrePlaneSelectionWindow: shiftTerrainPlaneSelectionWindow,
    getTimbreSelectionVisualOffset: getTerrainSelectionVisualOffset,
    getPlaybackTimeSec: getTrajectoryPlaybackTimeSec,
    setBoxSelectedTimbreInstanceIds,
    timbrePlaneSelectionUsesLasso,
    getRenderableTimbreLassoPoints,
    normalizeTimbreLassoPoints,
    lassoCloseDistancePct: TIMBRE_LASSO_CLOSE_DISTANCE_PCT,
    onRebuildControls: () => rebuildTimbrePlaneSelectionControls(),
});

const rebuildTimbrePlaneSelectionVisuals = (options) => timbreSelectionController?.rebuildVisuals(options);
const startTimbrePlaneSelectionDrag = (event) => {
    const started = timbreSelectionController?.startDrag(event) ?? false;
    if (started) {
        appInteractionBindings?.clearTimbreSelectionPointerDown();
    }
    return started;
};
const updateTimbrePlaneSelectionDrag = (event) => timbreSelectionController?.updateDrag(event);
const finishTimbrePlaneSelectionDrag = (event) => timbreSelectionController?.finishDrag(event);
const updateTimbrePlaneSelectionHover = (event) => timbreSelectionController?.updateHover(event);
const handleTimbrePlaneSelectionPointerLeave = () => timbreSelectionController?.handlePointerLeave();
const applyTimbrePlaneSelectionSettings = () => timbreSelectionController?.applySettings();
if (!timbrePlaneSelectionControlService) {
    timbrePlaneSelectionControlService = createTimbrePlaneSelectionControls({
        modeAudioFolder: fModeAudio,
        ensureTimbrePlaneSelectionSettings,
        planeSelectionMeta: TERRAIN_PLANE_SELECTION_META,
        planeSelectionModes: TIMBRE_PLANE_SELECTION_MODES,
        selectionGrabTypes: TERRAIN_SELECTION_GRAB_TYPES,
        rebuildVisuals: rebuildTimbrePlaneSelectionVisuals,
        applySettings: applyTimbrePlaneSelectionSettings,
        cancelActiveLassoDraw: cancelActiveTimbreLassoDraw,
        startLassoDraw: startTimbreLassoDraw,
        getActiveLassoDraw: getActiveTimbreLassoDraw,
        completeActiveLassoDraw: completeActiveTimbreLassoDraw,
        clearPlaneLasso: clearTimbrePlaneLasso,
        bindGuiFolderTitleShortcuts,
    });
}

const rebuildTimbrePlaneSelectionControls = () => timbrePlaneSelectionControlService?.rebuild();
const setTimbrePlaneSelectionControlsVisible = (visible) => timbrePlaneSelectionControlService?.setVisible(visible);

const applyTerrainAxisColorSettings = () => {
    terrainController.applyAxisColorSettings();
    rebuildTerrainPlaneSelectionVisuals();
};

const rebuildTerrainAxisColorControls = () => {
    const axisColors = ensureTerrainAxisColorSettings();

    for (const folder of terrainAxisColorFolders) {
        folder.destroy();
    }
    terrainAxisColorFolders = [];

    for (const axisKey of TERRAIN_AXIS_COLOR_KEYS) {
        const axisMeta = TERRAIN_AXIS_COLOR_META[axisKey];
        const axisSettings = axisColors[axisKey];
        const axisFolder = fTerrainAxisColors.addFolder(axisMeta.label);
        terrainAxisColorFolders.push(axisFolder);

        axisFolder.add(axisSettings, 'enabled').name('Enabled').onChange(applyTerrainAxisColorSettings);
        axisFolder.add(axisSettings, 'weight', 0, 3, 0.01).name('Blend Weight').onChange(applyTerrainAxisColorSettings);
        axisFolder.add(axisSettings, 'intervalCount', 1, 8, 1).name('Axis Intervals').onChange((value) => {
            axisSettings.intervalCount = Math.round(value);
            ensureTerrainAxisColorSettings();
            rebuildTerrainAxisColorControls();
            applyTerrainAxisColorSettings();
        });

        for (let intervalIndex = 0; intervalIndex < axisSettings.intervalCount; intervalIndex++) {
            const intervalSettings = axisSettings.intervals[intervalIndex];
            const intervalFolder = axisFolder.addFolder(terrainAxisIntervalLabel(axisKey, intervalIndex, axisSettings.intervals));
            if (intervalIndex < axisSettings.intervalCount - 1) {
                const minBreakPct = intervalIndex === 0 ? 0.1 : (axisSettings.intervals[intervalIndex - 1].endPct + 0.1);
                const maxBreakPct = 100 - ((axisSettings.intervalCount - intervalIndex - 1) * 0.1);
                const controlBounds = terrainAxisBreakpointControlBounds(axisKey, minBreakPct, maxBreakPct);
                if (settings.terrainAxisColorValueMode === 'Axis Values') {
                    const breakProxy = {
                        breakValue: terrainAxisPctToDisplayValue(axisKey, intervalSettings.endPct),
                    };
                    intervalFolder.add(breakProxy, 'breakValue', controlBounds.min, controlBounds.max, controlBounds.step).name('Break Value')
                        .onChange((value) => {
                            intervalSettings.endPct = terrainAxisDisplayValueToPct(axisKey, value);
                            applyTerrainAxisColorSettings();
                        })
                        .onFinishChange(() => {
                            ensureTerrainAxisColorSettings();
                            rebuildTerrainAxisColorControls();
                            applyTerrainAxisColorSettings();
                        });
                } else {
                    intervalFolder.add(intervalSettings, 'endPct', controlBounds.min, controlBounds.max, controlBounds.step).name('Break %')
                        .onChange(applyTerrainAxisColorSettings)
                        .onFinishChange(() => {
                            ensureTerrainAxisColorSettings();
                            rebuildTerrainAxisColorControls();
                            applyTerrainAxisColorSettings();
                        });
                }
            }
            intervalFolder.addColor(intervalSettings, 'minColor').name('Min Color').onChange(applyTerrainAxisColorSettings);
            intervalFolder.addColor(intervalSettings, 'maxColor').name('Max Color').onChange(applyTerrainAxisColorSettings);
        }
    }

    bindGuiFolderTitleShortcuts();
};

const normalizeTerrainScaleBounds = (candidate, fallback) => {
    const normalizePair = (minValue, maxValue, fallbackMin, fallbackMax) => {
        const nextMin = Number.isFinite(minValue) ? minValue : fallbackMin;
        let nextMax = Number.isFinite(maxValue) ? maxValue : fallbackMax;
        const minGap = Math.max(1e-3, Math.abs(fallbackMax - fallbackMin) * 0.001 || 1);

        if (nextMax <= nextMin) nextMax = nextMin + minGap;
        return [nextMin, nextMax];
    };

    const [frequencyMin, frequencyMax] = normalizePair(
        candidate.frequencyMin,
        candidate.frequencyMax,
        fallback.frequencyMin,
        fallback.frequencyMax,
    );
    const [amplitudeMin, amplitudeMax] = normalizePair(
        candidate.amplitudeMin,
        candidate.amplitudeMax,
        fallback.amplitudeMin,
        fallback.amplitudeMax,
    );
    const [timeMin, timeMax] = normalizePair(
        candidate.timeMin,
        candidate.timeMax,
        fallback.timeMin,
        fallback.timeMax,
    );

    return {
        frequencyMin,
        frequencyMax,
        amplitudeMin,
        amplitudeMax,
        timeMin,
        timeMax,
    };
};

const syncTerrainScaleSettingDisplays = () => {
    terrainScaleControlRegistry.syncDisplays();
};

const syncTerrainScaleSettings = (bounds) => {
    settings.terrainScaleFreqMin = bounds.frequencyMin;
    settings.terrainScaleFreqMax = bounds.frequencyMax;
    settings.terrainScaleAmpMin = bounds.amplitudeMin;
    settings.terrainScaleAmpMax = bounds.amplitudeMax;
    settings.terrainScaleTimeMin = bounds.timeMin;
    settings.terrainScaleTimeMax = bounds.timeMax;
    syncTerrainScaleSettingDisplays();
};

const terrainScaleBoundsFromSettings = () => {
    const autoBounds = terrainVisualizer.getAutoScaleBounds();

    if (!settings.terrainManualScaling) {
        return autoBounds;
    }

    return normalizeTerrainScaleBounds({
        frequencyMin: Number(settings.terrainScaleFreqMin),
        frequencyMax: Number(settings.terrainScaleFreqMax),
        amplitudeMin: Number(settings.terrainScaleAmpMin),
        amplitudeMax: Number(settings.terrainScaleAmpMax),
        timeMin: Number(settings.terrainScaleTimeMin),
        timeMax: Number(settings.terrainScaleTimeMax),
    }, autoBounds);
};

const formatTerrainAxisValue = (value) => {
    if (!Number.isFinite(value)) return '?';

    const absValue = Math.abs(value);
    if (Number.isInteger(value) || absValue >= 100) {
        return value.toFixed(0);
    }
    if (absValue >= 10) {
        return value.toFixed(1).replace(/\.0$/, '');
    }
    if (absValue >= 1) {
        return value.toFixed(2).replace(/\.?0+$/, '');
    }
    return value.toFixed(4).replace(/\.?0+$/, '');
};

terrainAxes = createTerrainAxes({
    scene,
    labelRenderer,
    terrainVisualizer,
    settings,
    isTerrainMode,
    terrainStretchSettings,
    terrainScaleBoundsFromSettings,
    formatTerrainAxisValue,
});

const applyTerrainAxisScaling = ({ syncFromAuto = false } = {}) => {
    const autoBounds = terrainVisualizer.getAutoScaleBounds();

    if (syncFromAuto || !settings.terrainManualScaling) {
        syncTerrainScaleSettings(autoBounds);
    }

    const nextBounds = terrainScaleBoundsFromSettings();
    if (settings.terrainManualScaling) {
        syncTerrainScaleSettings(nextBounds);
    }

    terrainVisualizer.setScaleBounds(nextBounds);
    applyTerrainStretch();
    markTerrainOnsetOverlayDirty();
    refreshTerrainOnsetOverlay();

    if (settings.terrainAxisColorValueMode === 'Axis Values') {
        rebuildTerrainAxisColorControls();
    }
};

const terrainBoxCenter = () => {
    const stretch = terrainStretchSettings();
    const { height, zDepth } = terrainVisualizer.getTerrainWorldBounds();
    return new THREE.Vector3(
        0,
        (height * stretch.y) * 0.5,
        -(zDepth * stretch.z) * 0.5,
    );
};

const centerCameraOnTerrain = () => {
    const nextTarget = terrainBoxCenter();
    const currentOffset = camera.position.clone().sub(controls.target);
    controls.target.copy(nextTarget);
    camera.position.copy(nextTarget.clone().add(currentOffset));
    controls.update();
};

const terrainController = createTerrainController({
    settings,
    terrainVisualizer,
    terrainHelperBadge,
    isTerrainMode,
    ensureTerrainAxisColorSettings,
    ensureTerrainTimeWindowSettings,
    ensureTerrainPlaneSelectionSettings,
    ensureTerrain2DGraphSettings,
    applyTerrainAxisScaling,
    syncAnalyserBinCount: (binCount) => {
        if (livePerformanceControls?.isActive?.()) {
            livePerformanceControls.syncAnalyserBinCount(binCount);
            return;
        }
        if (!terrainVisualizer.hasFrameData()) {
            syncAnalyserBinCount(binCount);
        }
    },
    centerCameraOnTerrain,
    getPlaybackTimeSec: getTrajectoryPlaybackTimeSec,
    getDurationSec: getTrajectoryDurationSec,
    readLiveFrequencyFrame: () => livePerformanceControls?.readFrequencyFrame?.() || readFrequencyFrame(),
    resetTimbreRuntime: (playbackTimeSec) => resetTimbreTransportRuntime(playbackTimeSec),
});

const applyTerrainStretch = () => {
    terrainVisualizer.setDisplayScale(terrainStretchSettings());
    buildTerrainAxes();
    rebuildTerrainPlaneSelectionVisuals();
    terrainSculptOverviewController?.render?.();
    markTerrainOnsetOverlayDirty();
    refreshTerrainOnsetOverlay();
    if (isTerrainMode()) centerCameraOnTerrain();
};

const applyTerrainAmplitudeScale = () => {
    terrainVisualizer.refreshGeometry();
    markTerrainOnsetOverlayDirty();
    refreshTerrainOnsetOverlay();
    applyTerrainStretch();
};

const applyTerrainAutoPaddingSettings = () => {
    terrainVisualizer.setSettings(settings);
    terrainVisualizer.refreshGeometry();
    markTerrainOnsetOverlayDirty();
    refreshTerrainOnsetOverlay();
    applyTerrainAxisScaling({ syncFromAuto: !settings.terrainManualScaling });
};

const applyPerformanceSettings = () => {
    const pixelRatio = Math.min(2, Math.max(0.5, window.devicePixelRatio * settings.renderScale));
    renderer.setPixelRatio(pixelRatio);
    updateLabelRendererVisibility();
    applyGraphSettings();
    applyTerrainGraphSettings();
    fpsMeter.style.display = settings.showFPSMeter ? 'block' : 'none';
    terrainHelperBadge.style.top = settings.showFPSMeter ? '42px' : '12px';
    scene.background.set(settings.backgroundColor);
    if (scene.fog) scene.fog.density = settings.fogDensity;
    if (scene.fog) scene.fog.color.set(settings.fogColor);
};

const applyLightingSettings = () => {
    ambientLight.visible = settings.enableLighting;
    directionalLight.visible = settings.enableLighting;
    ambientLight.intensity = settings.ambientIntensity;
    directionalLight.intensity = settings.directionalIntensity;
    directionalLight.position.set(settings.directionalX, settings.directionalY, settings.directionalZ);
    trajectoryVisualizer.setNodeShadingMode(settings.nodeShading);
};

const applyVisualizationMode = () => {
    const terrainMode = isTerrainMode();
    if (!terrainMode && livePerformanceControls?.isActive?.()) {
        void stopLiveSourceSession({ restoreAsset: true, closeModal: true });
    }
    setTerrainSculptCurrentTarget(terrainMode ? TERRAIN_FULL_MASK_LABEL : TERRAIN_RENDER_WINDOW_LABEL);
    trajectoryVisualizer.setVisible(!terrainMode);
    terrainVisualizer.setVisible(terrainMode);
    updateLabelRendererVisibility();
    rebuildTerrainPlaneSelectionVisuals();
    rebuildTimbrePlaneSelectionVisuals({ adoptCurrentTimeSec: getTrajectoryPlaybackTimeSec() });
    terrainSculptOverviewController?.syncVisibility?.();

    fLines.domElement.style.display = terrainMode ? 'none' : '';
    fNodes.domElement.style.display = terrainMode ? 'none' : '';
    fGraph.domElement.style.display = terrainMode ? 'none' : '';
    if (fSelectionSculpt) fSelectionSculpt.domElement.style.display = terrainMode ? '' : 'none';
    fTerrain.domElement.style.display = terrainMode ? '' : 'none';
    setTimbrePlaneSelectionControlsVisible(!terrainMode);
    if (fTimbreSelectionActions) fTimbreSelectionActions.domElement.style.display = terrainMode ? 'none' : '';

    if (terrainMode) {
        terrainController.activateMode({
            playbackTimeSec: getTrajectoryPlaybackTimeSec(),
            durationSec: getTrajectoryDurationSec(),
        });
    }

    markTerrainOnsetOverlayDirty();
    refreshTerrainOnsetOverlay();

    applyGraphSettings();
    applyTerrainGraphSettings();
    updateTimbreSelectionBadge();
    syncBackendCallMonitorState();
    if (!terrainMode) {
        syncVisualizerToCurrentTime();
        return;
    }
    ensureAudioContext();
};

const applyTerrainSettings = () => {
    terrainController.applySettings();
    markTerrainOnsetOverlayDirty();
    refreshTerrainOnsetOverlay();
    terrainSculptOverviewController?.refreshData?.();
    syncBackendCallMonitorState();
};
const modeActions = {
    resetGraph: async () => {
        await resetGraphToCurrentAsset();
    },
};

rebuildTimbrePlaneSelectionControls();

const timbreSelectionActions = {
    playSelection: async () => {
        await playCurrentTimbreSelection();
    },
    jumpToSelection: () => {
        jumpToCurrentTimbreSelection();
    },
    clearSelection: () => {
        clearAllTimbreSelections();
    },
    invertSelection: () => {
        invertTimbreSelection();
    },
    exportSelectionJson: async () => {
        await exportCurrentTimbreSelectionAsJson();
    },
    exportSelectionCsv: async () => {
        await exportCurrentTimbreSelectionAsCsv();
    },
    exportSelectionAudio: async () => {
        await exportCurrentTimbreSelectionAsAudioClip();
    },
    exportSelectionIoiCsv: async () => {
        await exportCurrentTimbreSelectionAsIoiCsv();
    },
    exportSelectionIoiCsv2: async () => {
        await exportCurrentTimbreSelectionAsBioacousticsWorkbook();
    },
};
const {
    fSelectionSculpt: nextSelectionSculpt,
    fTerrain,
    fTerrainAxisColors: nextTerrainAxisColors,
    terrainAxisColorValueModeController: nextTerrainAxisColorValueModeController,
    fTimbreSelectionActions: nextTimbreSelectionActions,
} = createModeTerrainGuiFolders({
    gui,
    modeAudioFolder: fModeAudio,
    settings,
    modeActions,
    timbreSelectionActions,
    terrainHelperPreferences: TERRAIN_HELPER_PREFERENCES,
    terrainAxisValueModes: TERRAIN_AXIS_VALUE_MODES,
    terrain2DGraphMeta: TERRAIN_2D_GRAPH_META,
    terrain2DGraphShowModes: TERRAIN_2D_GRAPH_SHOW_MODES,
    terrain2DGraphTypes: TERRAIN_2D_GRAPH_TYPES,
    terrain2DGraphSurfaces: TERRAIN_2D_GRAPH_SURFACES,
    applyVisualizationMode,
    updateSelectionPlaybackMask,
    updateTimbreSelectionBadge,
    applyTerrainSettings,
    applyTerrainAmplitudeScale,
    terrainVisualizer,
    applyTerrainHelperPreference,
    rebuildTerrainAxisColorControls,
    ensureTerrain2DGraphSettings,
    applyTerrain2DGraphSettings,
    buildTerrainGraphControls,
    terrainScaleControlRegistry,
    isTerrainMode,
    buildTerrainAxes,
    applyTerrainGraphSettings,
    updateLabelRendererVisibility,
    applyTerrainAxisScaling,
    applyTerrainAutoPaddingSettings,
    applyTerrainStretch,
});

fSelectionSculpt = nextSelectionSculpt;
fTerrainAxisColors = nextTerrainAxisColors;
terrainAxisColorValueModeController = nextTerrainAxisColorValueModeController;
fTimbreSelectionActions = nextTimbreSelectionActions;
rebuildTerrainAxisColorControls();
rebuildTerrainTimeWindowControls();
rebuildTerrainPlaneSelectionControls();

const {
    fLines,
    fNodes,
    modifierControllers,
} = createLineNodeGuiFolders({
    gui,
    settings,
    modifierColumnOptions,
    syncVisualizerToCurrentTime,
    invalidateTimbreOnsetProgress,
    getTrajectoryPlaybackTimeSec,
});
const {
    fGraph,
    updateAxisTextEditorsVisibility,
} = createBaseGuiFolders({
    gui,
    settings,
    sceneActions,
    hotkeyActions,
    applyGraphSettings,
    applyPerformanceSettings,
    applyLightingSettings,
    rebuildTimbreSelectionAnalysis,
    getTrajectoryPlaybackTimeSec,
    invalidateTimbreOnsetProgress,
    syncVisualizerToCurrentTime,
    updateTimbreSelectionBadge,
    updateTransportOnsetMarkers,
    refreshTerrainOnsetOverlay,
    timbreOnsetDetectionModes: TIMBRE_ONSET_DETECTION_MODES,
    timbreOnsetFlashModes: TIMBRE_ONSET_FLASH_MODES,
});

bindGuiFolderTitleShortcuts();
gui.open();

const actions = {
    resetToDefaults: () => {
        Object.assign(settings, buildDefaultSettings());
        manualTimbreInstanceIds = [];
        boxTimbreSelectionInstanceIds = [];
        rebuildTerrainAxisColorControls();
        rebuildTerrainTimeWindowControls();
        rebuildTerrainPlaneSelectionControls();
        rebuildTimbrePlaneSelectionControls();
        clearAccumulatedViews();
        applyPerformanceSettings();
        applyLightingSettings();
        applyRenderOrderSettings();
        updateAxisTextEditorsVisibility();
        applyGraphSettings();
        applyTerrainSettings();
        applyVisualizationMode();
        syncVisualizerToCurrentTime();
        gui.controllersRecursive().forEach((controller) => controller.updateDisplay());
    }
};
gui.add(actions, 'resetToDefaults').name('Reset To Defaults');

// Pass live settings references once — each visualizer reads it every frame
trajectoryVisualizer.setSettings(settings);
trajectoryVisualizer.setViewportSize(window.innerWidth, window.innerHeight);
terrainVisualizer.setSettings(settings);
applyPerformanceSettings();
applyLightingSettings();

// ==========================================
// NEW: DYNAMIC ACADEMIC AXES
// ==========================================
function buildAcademicAxes(bounds) {
    const cleanupLabelEntries = (entries) => {
        for (const entry of entries) {
            if (entry?.div?.parentNode) {
                entry.div.parentNode.removeChild(entry.div);
            }
        }
    };

    // Remove any stale timbre labels left from prior rebuilds.
    for (const node of labelRenderer.domElement.querySelectorAll('.axis-label[data-axis-pipeline="timbre"]')) {
        node.remove();
    }

    if (academicAxesObject) {
        cleanupLabelEntries(academicAxisLabelEntries);
        academicAxesObject.parent?.remove(academicAxesObject);
        academicAxesObject.traverse((child) => {
            if (child.geometry && typeof child.geometry.dispose === 'function') child.geometry.dispose();
            if (child.material && typeof child.material.dispose === 'function') child.material.dispose();
        });
        academicAxesObject.clear?.();
        academicAxesObject = null;
        academicAxesMaterial = null;
        academicAxisLabelEntries = [];
    }
    if (academicAxisLabelGroup) {
        academicAxisLabelGroup.parent?.remove(academicAxisLabelGroup);
        academicAxisLabelGroup.clear?.();
        academicAxisLabelGroup = null;
    }

    if (!bounds?.visualSize || !bounds?.min || !bounds?.max) {
        academicAxisHeaders = ['X', 'Y', 'Z'];
        academicAxisRanges = {
            x: { min: 0, max: 0 },
            y: { min: 0, max: 0 },
            z: { min: 0, max: 0 },
        };
        return;
    }

    // 1. Create a bounding box that perfectly fits the normalized data
    const geometry = new THREE.BoxGeometry(bounds.visualSize.x, bounds.visualSize.y, bounds.visualSize.z);
    
    // EdgesGeometry creates a wireframe box
    const edges = new THREE.EdgesGeometry(geometry);
    const boxMaterial = new THREE.LineBasicMaterial({ color: 0x444444 });
    academicAxesMaterial = boxMaterial;
    const boundingBox = new THREE.LineSegments(edges, boxMaterial);
    academicAxesObject = boundingBox;
    academicAxisLabelGroup = new THREE.Group();
    applyRenderOrderSettings();
    scene.add(boundingBox);
    scene.add(academicAxisLabelGroup);

    academicAxisLabelEntries = [];
    academicAxisHeaders = [
        bounds.axisLabels[0] || 'X',
        bounds.axisLabels[1] || 'Y',
        bounds.axisLabels[2] || 'Z',
    ];
    academicAxisRanges = {
        x: { min: bounds.min.x, max: bounds.max.x },
        y: { min: bounds.min.y, max: bounds.max.y },
        z: { min: bounds.min.z, max: bounds.max.z },
    };
    if (!settings.axesTextX) settings.axesTextX = academicAxisHeaders[0];
    if (!settings.axesTextY) settings.axesTextY = academicAxisHeaders[1];
    if (!settings.axesTextZ) settings.axesTextZ = academicAxisHeaders[2];

    // 2. Helper function to create an HTML label at a specific 3D coordinate
    const createLabel = (axisIndex, value, x, y, z) => {
        const div = document.createElement('div');
        div.className = 'axis-label';
        div.dataset.axisPipeline = 'timbre';
        div.textContent = `${axisTitleFor(axisIndex)}: ${value.toFixed(2)}`;
        
        const label = new CSS2DObject(div);
        label.position.set(x, y, z);
        academicAxisLabelGroup.add(label);
        academicAxisLabelEntries.push({ axisIndex, value, div, label });
    };

    const halfX = bounds.visualSize.x / 2;
    const halfY = bounds.visualSize.y / 2;
    const halfZ = bounds.visualSize.z / 2;

    // 3. Attach labels dynamically using the CSV headers!
    // X Axis
    createLabel(0, bounds.max.x, halfX, -halfY, halfZ);
    createLabel(0, bounds.min.x, -halfX, -halfY, halfZ);

    // Y Axis
    createLabel(1, bounds.max.y, -halfX, halfY, halfZ);
    createLabel(1, bounds.min.y, -halfX, -halfY, halfZ);

    // Z Axis
    createLabel(2, bounds.max.z, -halfX, -halfY, -halfZ);
    createLabel(2, bounds.min.z, -halfX, -halfY, halfZ);

    applyGraphSettings();
}


// ==========================================
// AUDIO & UI SETUP
// ==========================================
const backendCallBtn = document.getElementById('backend-call-btn');
const cameraControlsBtn = document.getElementById('camera-controls-btn');
const liveSourceBtn = document.getElementById('live-source-btn');
const openCompanionBtn = document.getElementById('open-companion-btn');
const playBtn = document.getElementById('play-btn');
const restartBtn = document.getElementById('restart-btn');
const speedBtn = document.getElementById('speed-btn');
const speedMenu = document.getElementById('speed-menu');
const customSpeedBtn = document.getElementById('custom-speed-btn');
const customSpeedRow = document.getElementById('custom-speed-row');
const customSpeedInput = document.getElementById('custom-speed-input');
const applyCustomSpeedBtn = document.getElementById('apply-custom-speed-btn');
const preservePitchCheckbox = document.getElementById('preserve-pitch-checkbox');
const speedOptionButtons = Array.from(document.querySelectorAll('.speed-option[data-rate]'));
const timeDisplay = document.getElementById('time-display');
const uiContainer = document.getElementById('ui-container');

if (backendCallBtn) {
    if (!backendCallMonitorIpc) {
        backendCallBtn.disabled = true;
        backendCallBtn.title = 'Backend calls are available only inside the Electron app shell.';
    } else {
        backendCallBtn.addEventListener('click', () => {
            openBackendCallMonitor();
        });
    }
}

if (openCompanionBtn) {
    if (!backendCallMonitorIpc) {
        openCompanionBtn.disabled = true;
        openCompanionBtn.title = 'Companion shell launch is available only inside the Electron app shell.';
    } else {
        openCompanionBtn.addEventListener('click', () => {
            void openAudioOnsetFinderCompanion();
        });
    }
}

if (audio && typeof audio.addEventListener === 'function') {
    [
        'play',
        'pause',
        'seeking',
        'seeked',
        'timeupdate',
        'loadedmetadata',
        'ended',
        'ratechange',
    ].forEach((eventName) => {
        audio.addEventListener(eventName, () => {
            syncBackendCallMonitorState();
        });
    });
}

window.setInterval(() => {
    syncBackendCallMonitorState();
}, 1000);
void hydrateCanonicalLocalIntegrationState();
syncBackendCallMonitorState();

const formatTransportTimestamp = (timeSec = 0) => {
    const safeTimeSec = Math.max(0, Number.isFinite(timeSec) ? timeSec : 0);
    return `${Math.floor(safeTimeSec / 60)}:${(`0${Math.floor(safeTimeSec % 60)}`).slice(-2)}`;
};

const syncAlwaysVisibleShellControls = () => {
    if (liveSourceBtn) {
        const liveState = livePerformanceControls?.getState?.() || { active: false, statusLabel: 'Inactive' };
        liveSourceBtn.dataset.liveState = liveState.active ? 'active' : 'idle';
        liveSourceBtn.title = liveState.active
            ? `${liveState.statusLabel || 'Live source active'}. Click to stop the live source session.`
            : 'Open Live Performance Source controls';
    }

    if (cameraControlsBtn) {
        cameraControlsBtn.title = 'Open camera keyframe and motion controls';
    }
};

const syncLiveSourceTransportUi = () => {
    const liveState = livePerformanceControls?.getState?.() || { active: false, mode: 'inactive' };
    const transportLocked = !!liveState.active;

    [playBtn, restartBtn, speedBtn, customSpeedBtn, applyCustomSpeedBtn, progressBar].forEach((element) => {
        if (element) element.disabled = transportLocked;
    });
    if (customSpeedInput) customSpeedInput.disabled = transportLocked;
    if (preservePitchCheckbox) preservePitchCheckbox.disabled = transportLocked;

    if (transportLocked) {
        audio.pause();
        playBtn.innerText = '▶';
        progressBar.value = 0;
        timeDisplay.innerText = liveState.mode === 'recording' ? 'LIVE / REC' : 'LIVE / STREAM';
        speedMenu.classList.remove('open');
        customSpeedRow.classList.remove('open');
        return;
    }

    progressBar.value = (audio.currentTime / (audio.duration || 1)) * 100;
    timeDisplay.innerText = `${formatTransportTimestamp(audio.currentTime)} / ${formatTransportTimestamp(audio.duration || 0)}`;
    syncAlwaysVisibleShellControls();
};

let lastLiveSourceActive = false;

const handleLiveSourceStateChange = async (nextState) => {
    liveSourceUiState.liveStatus = nextState?.statusLabel || 'Inactive';
    liveStatusController?.updateDisplay?.();

    const isActive = !!nextState?.active;
    if (isActive && !lastLiveSourceActive) {
        liveRestoreAsset = getSelectedAudioAsset() ? { ...getSelectedAudioAsset() } : null;

        audio.pause();
        audio.currentTime = 0;
        resetTrajectoryPlaybackAnchor(0);
        terrainVisualizer.loadTerrainEnvelopeData(null);
        terrainVisualizer.loadFrameData('');
        lastTerrainVisibleWindowKey = '';
        clearTerrainOnsetOverlaySelection();
        markTerrainOnsetOverlayDirty();
        refreshTerrainOnsetOverlay();

        settings.visualizationMode = 'SpectroTerrain';
        const requestedTerrainBins = Math.max(128, Math.round((Number(nextState?.fftSize) || 1024) / 2));
        if (settings.terrainFrequencyBins !== requestedTerrainBins) {
            settings.terrainFrequencyBins = requestedTerrainBins;
        }
        gui.controllersRecursive().forEach((controller) => controller.updateDisplay());
        applyTerrainSettings();
        applyVisualizationMode();
    }

    if (!isActive && lastLiveSourceActive) {
        syncBackendCallMonitorState();
    }

    lastLiveSourceActive = isActive;
    syncLiveSourceTransportUi();
    syncBackendCallMonitorState();
    syncAlwaysVisibleShellControls();
};

stopLiveSourceSession = async ({ restoreAsset = true, closeModal = true } = {}) => {
    if (!livePerformanceControls?.isActive?.()) {
        if (closeModal) livePerformanceControls?.closeModal?.();
        syncLiveSourceTransportUi();
        return false;
    }

    const restoreCandidate = restoreAsset && liveRestoreAsset ? { ...liveRestoreAsset } : null;
    const stopped = await livePerformanceControls.stopSession({ saveRecording: true, closeDialog: closeModal });
    if (!stopped) return false;

    liveRestoreAsset = null;
    if (restoreCandidate?.audioUrl) {
        await loadAudioAssetInternal(restoreCandidate, { allowAccumulate: false });
    }
    syncLiveSourceTransportUi();
    syncBackendCallMonitorState();
    return true;
};

liveSourceUiState.toggleLiveSource = async () => {
    if (livePerformanceControls?.isActive?.()) {
        await stopLiveSourceSession({ restoreAsset: true, closeModal: true });
        return;
    }
    await livePerformanceControls?.openModal?.();
};

const assetLoadUiSync = createAssetLoadUiSync({
    settings,
    modifierColumnOptions,
    modifierControllers,
    terrainVisualizer,
    applyTerrainAxisScaling,
    buildAcademicAxes,
    applyRenderOrderSettings,
    applyLightingSettings,
    applyGraphSettings,
    applyVisualizationMode,
    syncVisualizerToCurrentTime,
    updateTransportOnsetMarkers,
});

const audioAssetLoader = createAudioAssetLoader({
    audio,
    decodeAudioData,
    trajectoryVisualizer,
    terrainVisualizer,
    getSelectedAsset: getSelectedAudioAsset,
    setSelectedAsset: (asset) => {
        selectedAudioAssetState.setSelectedAsset(asset);
    },
    syncSelectedAssetId: (assetId) => {
        audioAssetCatalog.syncSelectedAssetId(assetId);
    },
    shouldAccumulateView: () => !!settings.accumulateView,
    clearAccumulatedViews,
    accumulateCurrentPipelineView,
    clearSelectedTimbreInstances: () => {
        setSelectedTimbreInstanceIds([]);
    },
    onPlaybackReset: () => {
        resetTrajectoryPlaybackAnchor(0);
        playBtn.innerText = '▶';
    },
    onAssetLoaded: (payload) => {
        assetLoadUiSync.handleAssetLoaded(payload);
        lastTerrainVisibleWindowKey = '';
        terrainOnsetEditorState.drag = null;
        clearTerrainOnsetOverlaySelection();
        markTerrainOnsetOverlayDirty();
        terrainSculptOverviewController?.refreshData?.();
        syncProcessCurrentAssetSmokeState(payload?.asset || getSelectedAudioAsset());
        syncBackendCallMonitorState();
        refreshTerrainOnsetOverlay();
        void autoImportBioacousticsWorkbookForSelectedAsset();
    },
    onWarn: (...args) => {
        console.warn(...args);
    },
    onError: (...args) => {
        console.error(...args);
    },
});

const ensureDecodedAudioBufferForSelectedAsset = () => audioAssetLoader.ensureDecodedAudioBufferForSelectedAsset();
const loadAudioAssetInternal = (asset, options) => audioAssetLoader.loadAudioAsset(asset, options);
const loadAudioAsset = async (asset, options) => {
    if (livePerformanceControls?.isActive?.()) {
        await stopLiveSourceSession({ restoreAsset: false, closeModal: true });
    }
    return loadAudioAssetInternal(asset, options);
};

function clearLoadedAudioAssetState() {
    selectedAudioAssetState.setSelectedAsset(null);
    syncProcessCurrentAssetSmokeState(null);
    setSelectedTimbreInstanceIds([]);
    clearAccumulatedViews();

    audio.pause();
    audio.currentTime = 0;
    audio.removeAttribute('src');
    audio.load();

    trajectoryVisualizer.clearData();
    trajectoryVisualizer.setAudioWaveform(null);
    terrainVisualizer.loadFrameData('');
    terrainVisualizer.loadTerrainEnvelopeData(null);

    resetTrajectoryPlaybackAnchor(0);
    playBtn.innerText = '▶';
    buildAcademicAxes(null);
    updateTransportOnsetMarkers();
    terrainSculptOverviewController?.refreshData?.();
    syncBackendCallMonitorState();
}

async function resetGraphToCurrentAsset() {
    if (livePerformanceControls?.isActive?.()) {
        await stopLiveSourceSession({ restoreAsset: true, closeModal: true });
        return;
    }
    await audioAssetLoader.resetGraphToCurrentAsset();
}

function markTerrainOnsetOverlayDirty() {
    terrainOnsetEditorState.overlayDirty = true;
}

function clearTerrainOnsetOverlaySelection() {
    terrainOnsetEditorState.selectedTargetKey = '';
    terrainOnsetEditorState.selectedOnsetId = '';
}

function disposeTerrainOnsetOverlayChildren() {
    const children = [...terrainOnsetOverlayGroup.children];
    for (const child of children) {
        terrainOnsetOverlayGroup.remove(child);
        if (child.geometry?.dispose) child.geometry.dispose();
        if (Array.isArray(child.material)) {
            child.material.forEach((material) => material?.dispose?.());
        } else if (child.material?.dispose) {
            child.material.dispose();
        }
    }
}

function getTerrainOnsetEditorSelectionThresholdSec() {
    return Math.min(0.75, Math.max(TERRAIN_ONSET_SELECTION_MIN_SEC, (getAnalysisHopDurationSec() || 0) * 3));
}

function shouldShowTerrainOnsetOverlay() {
    return isTerrainMode() && (!!settings.showTerrainOnsetsInModel || !!settings.enableTerrainOnsetEditor);
}

function ensureTerrainOnsetOverrideEntryForAnalysis(analysis) {
    const targetKey = String(analysis?.onsetTargetKey || '').trim();
    if (!targetKey) return null;

    let overrideEntry = terrainOnsetEditorState.overridesByTargetKey.get(targetKey) || null;
    if (overrideEntry) {
        return { targetKey, entry: overrideEntry, created: false };
    }

    overrideEntry = {
        onsets: cloneTerrainOnsetEntriesFromAnalysis(analysis),
    };
    terrainOnsetEditorState.overridesByTargetKey.set(targetKey, overrideEntry);
    return { targetKey, entry: overrideEntry, created: true };
}

function findNearestTerrainOnsetEntry(onsets, timeSec) {
    if (!Array.isArray(onsets) || !Number.isFinite(timeSec)) return null;

    let bestMatch = null;
    for (const onset of onsets) {
        const onsetTimeSec = Number(onset?.timeSec);
        if (!Number.isFinite(onsetTimeSec)) continue;

        const distanceSec = Math.abs(onsetTimeSec - timeSec);
        if (!bestMatch || distanceSec < bestMatch.distanceSec) {
            bestMatch = {
                ...onset,
                distanceSec,
            };
        }
    }

    return bestMatch;
}

function setTerrainOnsetPointerFromEvent(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    if (!rect.width || !rect.height) return false;

    terrainOnsetPointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    terrainOnsetPointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    return true;
}

function pickTerrainOnsetFrameFromEvent(event) {
    if (!isTerrainMode() || !terrainVisualizer.hasFrameData?.()) return null;
    if (!setTerrainOnsetPointerFromEvent(event)) return null;

    terrainOnsetRaycaster.setFromCamera(terrainOnsetPointer, camera);
    const intersection = terrainVisualizer.pickSurfaceIntersection?.(terrainOnsetRaycaster);
    if (!intersection?.point) return null;

    const localPoint = terrainVisualizer.group.worldToLocal(intersection.point.clone());
    const frameIndex = terrainVisualizer.getClosestVisibleFrameIndexForLocalZ?.(localPoint.z);
    if (!Number.isFinite(frameIndex)) return null;

    const durationSec = getTrajectoryDurationSec();
    const terrainFrameCount = terrainVisualizer.getFrameDataCount?.() ?? 0;
    let timeSec = 0;
    if (trajectoryVisualizer.points.length > 0 && durationSec > 0 && frameIndex < trajectoryVisualizer.points.length) {
        timeSec = trajectoryVisualizer.getFrameTimeAtIndex(frameIndex, durationSec);
    } else if (getAnalysisHopDurationSec() > 0) {
        timeSec = frameIndex * getAnalysisHopDurationSec();
    } else if (durationSec > 0 && terrainFrameCount > 1) {
        timeSec = (frameIndex / (terrainFrameCount - 1)) * durationSec;
    }

    return {
        intersection,
        localPoint,
        frameIndex,
        timeSec: durationSec > 0 ? THREE.MathUtils.clamp(timeSec, 0, durationSec) : Math.max(0, timeSec),
    };
}

function syncTerrainOnsetAnalysisAfterMutation({ adoptCurrentTimeSec = getTrajectoryPlaybackTimeSec() } = {}) {
    markTerrainOnsetOverlayDirty();

    const activeTarget = getActiveTimbreAnalysisSnapshot?.();
    if (activeTarget?.kind === 'current') {
        rebuildTimbreSelectionAnalysis({ adoptCurrentTimeSec });
    } else {
        updateTransportOnsetMarkers?.();
        updateTimbreSelectionBadge?.();
        renderTimbreSelectionPanel?.();
    }

    refreshTerrainOnsetOverlay();
}

function refreshTerrainOnsetOverlay() {
    terrainOnsetEditorState.overlayDirty = false;
    disposeTerrainOnsetOverlayChildren();
    terrainOnsetOverlayGroup.visible = false;

    if (!shouldShowTerrainOnsetOverlay()) {
        clearTerrainOnsetOverlaySelection();
        return;
    }

    const activeTarget = getActiveTimbreAnalysisSnapshot?.();
    const activeAnalysis = activeTarget?.analysis;
    const activeTargetKey = String(activeAnalysis?.onsetTargetKey || '').trim();
    const onsetEvents = activeAnalysis?.onsetEvents || [];
    if (!activeAnalysis || !activeTargetKey || onsetEvents.length === 0) {
        clearTerrainOnsetOverlaySelection();
        return;
    }

    if (!terrainVisualizer.hasFrameData?.()) return;

    const editorEnabled = !!settings.enableTerrainOnsetEditor;
    const selectedMatchesTarget = terrainOnsetEditorState.selectedTargetKey === activeTargetKey;
    const liftY = Math.max(0.08, terrainVisualizer.getTerrainWorldBounds().height * 0.0025);
    const renderedOnsetIds = new Set();

    for (const onsetEvent of onsetEvents) {
        const frameIndex = Number(onsetEvent?.frameIndex);
        if (!Number.isFinite(frameIndex)) continue;

        const surfaceProfile = terrainVisualizer.getSurfaceProfileForFrame?.(frameIndex);
        if (!surfaceProfile?.xPositions || !surfaceProfile?.yValues || surfaceProfile.xPositions.length === 0) continue;

        const onsetId = String(onsetEvent?.eventKey || onsetEvent?.editId || `rendered-${frameIndex}-${Number(onsetEvent?.timeSec || 0).toFixed(6)}`);
        renderedOnsetIds.add(onsetId);

        const isSelected = editorEnabled
            && selectedMatchesTarget
            && terrainOnsetEditorState.selectedOnsetId === onsetId;
        const positions = new Float32Array(surfaceProfile.xPositions.length * 3);
        for (let index = 0; index < surfaceProfile.xPositions.length; index++) {
            positions[(index * 3) + 0] = surfaceProfile.xPositions[index];
            positions[(index * 3) + 1] = (surfaceProfile.yValues[index] ?? 0) + liftY;
            positions[(index * 3) + 2] = surfaceProfile.z;
        }

        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

        const material = new THREE.LineBasicMaterial({
            color: isSelected ? '#facc15' : '#ef4444',
            transparent: true,
            opacity: isSelected ? 0.98 : 0.86,
            depthWrite: false,
        });
        const onsetLine = new THREE.Line(geometry, material);
        onsetLine.frustumCulled = false;
        onsetLine.renderOrder = isSelected ? 36 : 34;
        onsetLine.userData = {
            onsetId,
            targetKey: activeTargetKey,
            timeSec: onsetEvent.timeSec,
        };
        terrainOnsetOverlayGroup.add(onsetLine);
    }

    terrainOnsetOverlayGroup.visible = terrainOnsetOverlayGroup.children.length > 0;

    if (!editorEnabled) {
        clearTerrainOnsetOverlaySelection();
        return;
    }

    if (!selectedMatchesTarget || !renderedOnsetIds.has(terrainOnsetEditorState.selectedOnsetId)) {
        clearTerrainOnsetOverlaySelection();
    }
}

function handleTerrainOnsetEditorPointerDown(event) {
    if (!settings.enableTerrainOnsetEditor || !isTerrainMode() || event.button !== 0) return false;

    const pickedFrame = pickTerrainOnsetFrameFromEvent(event);
    if (!pickedFrame) return false;

    renderer.domElement.focus();
    const activeTarget = getActiveTimbreAnalysisSnapshot?.();
    const activeAnalysis = activeTarget?.analysis;
    const ensuredEntry = ensureTerrainOnsetOverrideEntryForAnalysis(activeAnalysis);
    if (!ensuredEntry?.entry) {
        clearTerrainOnsetOverlaySelection();
        refreshTerrainOnsetOverlay();
        return true;
    }

    const nearestOnset = findNearestTerrainOnsetEntry(ensuredEntry.entry.onsets, pickedFrame.timeSec);
    if (!nearestOnset || nearestOnset.distanceSec > getTerrainOnsetEditorSelectionThresholdSec()) {
        clearTerrainOnsetOverlaySelection();
        refreshTerrainOnsetOverlay();
        return true;
    }

    terrainOnsetEditorState.selectedTargetKey = ensuredEntry.targetKey;
    terrainOnsetEditorState.selectedOnsetId = nearestOnset.id;
    terrainOnsetEditorState.drag = {
        pointerId: event.pointerId,
        targetKey: ensuredEntry.targetKey,
        onsetId: nearestOnset.id,
    };

    if (ensuredEntry.created && activeTarget?.kind === 'current') {
        syncTerrainOnsetAnalysisAfterMutation({ adoptCurrentTimeSec: getTrajectoryPlaybackTimeSec() });
        return true;
    }

    refreshTerrainOnsetOverlay();
    return true;
}

function handleTerrainOnsetEditorPointerMove(event) {
    if (!settings.enableTerrainOnsetEditor || !terrainOnsetEditorState.drag) return false;
    if (event.pointerId !== terrainOnsetEditorState.drag.pointerId) return false;

    const pickedFrame = pickTerrainOnsetFrameFromEvent(event);
    if (!pickedFrame) return true;

    const overrideEntry = terrainOnsetEditorState.overridesByTargetKey.get(terrainOnsetEditorState.drag.targetKey) || null;
    const onsetEntry = overrideEntry?.onsets?.find((entry) => entry.id === terrainOnsetEditorState.drag.onsetId) || null;
    if (!onsetEntry) return true;

    onsetEntry.timeSec = pickedFrame.timeSec;
    overrideEntry.onsets.sort((a, b) => a.timeSec - b.timeSec);
    terrainOnsetEditorState.selectedTargetKey = terrainOnsetEditorState.drag.targetKey;
    terrainOnsetEditorState.selectedOnsetId = terrainOnsetEditorState.drag.onsetId;
    syncTerrainOnsetAnalysisAfterMutation({ adoptCurrentTimeSec: getTrajectoryPlaybackTimeSec() });
    return true;
}

function handleTerrainOnsetEditorPointerUp(event) {
    if (!terrainOnsetEditorState.drag) return false;
    if (event.pointerId !== terrainOnsetEditorState.drag.pointerId) return false;

    terrainOnsetEditorState.drag = null;
    return true;
}

function handleTerrainOnsetEditorPointerLeave() {
    if (!terrainOnsetEditorState.drag) return;
    terrainOnsetEditorState.drag = null;
}

function handleTerrainOnsetEditorContextMenu(event) {
    if (!settings.enableTerrainOnsetEditor || !isTerrainMode()) return false;

    const pickedFrame = pickTerrainOnsetFrameFromEvent(event);
    if (!pickedFrame) return false;

    const activeTarget = getActiveTimbreAnalysisSnapshot?.();
    const activeAnalysis = activeTarget?.analysis;
    const ensuredEntry = ensureTerrainOnsetOverrideEntryForAnalysis(activeAnalysis);
    if (!ensuredEntry?.entry) return false;

    const nearestOnset = findNearestTerrainOnsetEntry(ensuredEntry.entry.onsets, pickedFrame.timeSec);
    if (nearestOnset && nearestOnset.distanceSec <= getTerrainOnsetEditorSelectionThresholdSec()) {
        terrainOnsetEditorState.selectedTargetKey = ensuredEntry.targetKey;
        terrainOnsetEditorState.selectedOnsetId = nearestOnset.id;
        refreshTerrainOnsetOverlay();
        return true;
    }

    const nextOnset = {
        id: createTerrainOnsetEntryId(),
        timeSec: pickedFrame.timeSec,
    };
    ensuredEntry.entry.onsets.push(nextOnset);
    ensuredEntry.entry.onsets.sort((a, b) => a.timeSec - b.timeSec);
    terrainOnsetEditorState.selectedTargetKey = ensuredEntry.targetKey;
    terrainOnsetEditorState.selectedOnsetId = nextOnset.id;
    syncTerrainOnsetAnalysisAfterMutation({ adoptCurrentTimeSec: getTrajectoryPlaybackTimeSec() });
    return true;
}

function canDeleteSelectedTerrainOnset() {
    return !!settings.enableTerrainOnsetEditor
        && !!terrainOnsetEditorState.selectedTargetKey
        && !!terrainOnsetEditorState.selectedOnsetId;
}

function deleteSelectedTerrainOnset() {
    if (!canDeleteSelectedTerrainOnset()) return false;

    const overrideEntry = terrainOnsetEditorState.overridesByTargetKey.get(terrainOnsetEditorState.selectedTargetKey) || null;
    if (!overrideEntry?.onsets?.length) return false;

    const onsetIndex = overrideEntry.onsets.findIndex((entry) => entry.id === terrainOnsetEditorState.selectedOnsetId);
    if (onsetIndex < 0) return false;

    overrideEntry.onsets.splice(onsetIndex, 1);
    clearTerrainOnsetOverlaySelection();
    syncTerrainOnsetAnalysisAfterMutation({ adoptCurrentTimeSec: getTrajectoryPlaybackTimeSec() });
    return true;
}

async function loadAudioAssetsManifest() {
    const preferredAssetId = getSelectedAudioAssetId('');
    const storedAssetFolderPath = readStoredAudioAssetFolderPath();
    const storedManifestUrl = buildAssetManifestUrlFromFolderPath(storedAssetFolderPath);

    if (storedManifestUrl) {
        const result = await applyAudioAssetManifestSource({
            manifestUrl: storedManifestUrl,
            sourceLabel: `Folder: ${storedAssetFolderPath}`,
            assetFolderPath: storedAssetFolderPath,
            persistSelection: false,
            preferredAssetId,
        });
        if (result.ok) return;

        writeStoredAudioAssetFolderPath('');
        if (audioAssetCatalog.getAvailableAudioAssets().length > 0) {
            return;
        }
    }

    await applyAudioAssetManifestSource({
        manifestUrl: BUNDLED_ASSET_MANIFEST_URL,
        sourceLabel: BUNDLED_ASSET_SOURCE_LABEL,
        assetFolderPath: '',
        persistSelection: false,
        preferredAssetId,
    });
}

let lastFpvEnabledState = false;

const fpvControls = createFpvControls({
    renderer,
    camera,
    controls,
    settings,
    getCurrentHotkeys,
    onTogglePlayPause: () => playBtn.click(),
    onModeChange: (enabled) => {
        const didExitFpv = lastFpvEnabledState && !enabled;
        lastFpvEnabledState = !!enabled;

        if (didExitFpv && cameraControlPanel?.handleFpvDisabled?.()) {
            return;
        }

        cameraControlPanel?.refresh?.();
    },
});

appInteractionBindings = createAppInteractionBindings({
    renderer,
    isTerrainMode,
    isFirstPersonModeEnabled: () => fpvControls.isEnabled(),
    isFirstPersonPointerLocked: () => fpvControls.isPointerLocked(),
    getActiveTimbreLassoDraw,
    isTimbrePlaneSelectionDragging,
    startTerrainPlaneSelectionDrag,
    startTimbrePlaneSelectionDrag,
    updateTerrainPlaneSelectionHover,
    updateTimbrePlaneSelectionHover,
    handleTerrainPlaneSelectionPointerLeave,
    handleTimbrePlaneSelectionPointerLeave,
    updateTerrainPlaneSelectionDrag,
    updateTimbrePlaneSelectionDrag,
    finishTerrainPlaneSelectionDrag,
    finishTimbrePlaneSelectionDrag,
    appendPointToActiveTimbreLasso,
    pickTimbreSelectionIntersection,
    pickCenteredTimbreSelectionIntersection,
    setSelectedTimbreInstanceIds,
    toggleSelectedTimbreInstanceId,
    handleTerrainOnsetEditorPointerDown,
    handleTerrainOnsetEditorPointerMove,
    handleTerrainOnsetEditorPointerUp,
    handleTerrainOnsetEditorPointerLeave,
    handleTerrainOnsetEditorContextMenu,
    selectionClickDistancePx: TIMBRE_SELECTION_CLICK_DISTANCE_PX,
});

const appRuntimeBindings = createAppRuntimeBindings({
    settings,
    gui,
    uiContainer,
    renderer,
    labelRenderer,
    controls,
    camera,
    trajectoryVisualizer,
    floatingPanelDragManager,
    timbreSelectionBadge,
    timbreSelectionPanel,
    aboutOverlay,
    renderOrderModal,
    hotkeyModal,
    playBtn,
    restartBtn,
    speedBtn,
    speedMenu,
    customSpeedBtn,
    customSpeedRow,
    customSpeedInput,
    applyCustomSpeedBtn,
    preservePitchCheckbox,
    speedOptionButtons,
    progressBar,
    timeDisplay,
    audio,
    getCurrentHotkeys,
    saveHotkeysToStorage,
    ensureAudioContext,
    getTrajectoryDurationSec,
    getTrajectoryPlaybackTimeSec,
    resetTrajectoryPlaybackAnchor,
    syncVisualizerToCurrentTime,
    applyTerrainSettings,
    applyVisualizationMode,
    updateTimbreSelectionBadge,
    canDeleteSelectedTerrainOnset,
    deleteSelectedTerrainOnset,
    isTransportPlaybackLocked: () => !!livePerformanceControls?.isActive?.(),
    isFirstPersonModeEnabled: () => fpvControls.isEnabled(),
    isCameraKeyframeHotkeysEnabled: () => cameraControlPanel.isKeyframeHotkeysEnabled(),
    captureCameraKeyframe: () => cameraControlPanel.captureCurrentKeyframe(),
    cycleCameraKeyframe: (direction) => cameraControlPanel.cycleKeyframe(direction),
});

const animationLoop = createAnimationLoop({
    controls,
    settings,
    getPlaybackTimeSec: getTrajectoryPlaybackTimeSec,
    updateSelectionPlaybackMask,
    isTerrainMode,
    terrainController,
    getTrajectoryDurationSec,
    advanceTimbreSelectionOnsetPulses,
    trajectoryVisualizer,
    readFrequencyFrame,
    renderer,
    scene,
    camera,
    shouldRenderAxisLabels,
    labelRenderer,
    fpsMeter,
    updateTerrainHelperIndicator: () => terrainController.updateHelperIndicator(),
    updateTerrainModeRuntime: () => {
        const visibleWindow = getTerrainVisibleFrameWindow();
        const visibleWindowKey = `${visibleWindow.start}:${visibleWindow.endExclusive}`;
        if (visibleWindowKey !== lastTerrainVisibleWindowKey) {
            syncTerrainDisplayedTimeRangesFromFullClipSelection();
            rebuildTerrainPlaneSelectionVisuals();
            syncTerrainSculptStatusDisplay();
            markTerrainOnsetOverlayDirty();
            lastTerrainVisibleWindowKey = visibleWindowKey;
        }
        if (terrainOnsetEditorState.overlayDirty) {
            refreshTerrainOnsetOverlay();
        }
        terrainSculptOverviewController?.render?.();
    },
    updateCameraMotion: (deltaSec) => {
        if (fpvControls.isEnabled()) {
            return fpvControls.update(deltaSec);
        }
        return cameraControlPanel.update(deltaSec);
    },
    shouldUpdateControls: () => !fpvControls.isEnabled(),
});

// ==========================================
// SCREEN RECORDING
// ==========================================
const recordBtn       = document.getElementById('record-btn');
const recModal        = document.getElementById('rec-modal');
const recModalOverlay = document.getElementById('rec-modal-overlay');
const recResolution   = document.getElementById('rec-resolution');
const recFormat       = document.getElementById('rec-format');
const recGifToggle    = document.getElementById('rec-gif-toggle');
const recAudioToggle  = document.getElementById('rec-audio-toggle');
const recStartBtn     = document.getElementById('rec-start-btn');
const recCancelBtn    = document.getElementById('rec-cancel-btn');
const liveSourceModalOverlay = document.getElementById('live-source-modal-overlay');
const liveSourceInput = document.getElementById('live-source-input');
const liveSourceFftSize = document.getElementById('live-source-fft-size');
const liveSourceMonitorToggle = document.getElementById('live-source-monitor-toggle');
const liveSourceRefreshBtn = document.getElementById('live-source-refresh-btn');
const liveSourceStreamBtn = document.getElementById('live-source-stream-btn');
const liveSourceRecordBtn = document.getElementById('live-source-record-btn');
const liveSourceCaptureBtn = document.getElementById('live-source-capture-btn');
const liveSourceCancelBtn = document.getElementById('live-source-cancel-btn');
const liveSourceStatusText = document.getElementById('live-source-status-text');
const liveSourceAssetLabelInput = document.getElementById('live-source-asset-label');
const liveSourceIncludeMfccToggle = document.getElementById('live-source-include-mfcc-toggle');
const liveSourceProgressBlock = document.getElementById('live-source-progress-block');
const liveSourceProgressBar = document.getElementById('live-source-progress-bar');
const liveSourceProgressText = document.getElementById('live-source-progress-text');

const cameraControlPanel = createCameraControlPanel({
    camera,
    controls,
    fpvControls,
    recModalRoot: recModal,
    recStartBtn,
    getCurrentHotkeys,
    saveHotkeysToStorage,
});

const recordingControls = createRecordingControls({
    renderer,
    settings,
    ensureAudioContext,
    createRecordingDestination,
    disconnectRecordingDestination,
    recordBtn,
    recModalOverlay,
    recResolution,
    recFormat,
    recGifToggle,
    recAudioToggle,
    recStartBtn,
    recCancelBtn,
    beforeOpenModal: () => cameraControlPanel.refresh(),
});

if (liveSourceBtn) {
    liveSourceBtn.addEventListener('click', () => {
        void liveSourceUiState.toggleLiveSource();
    });
}

if (cameraControlsBtn) {
    cameraControlsBtn.addEventListener('click', () => {
        recordingControls.openModal({ focusSelector: '#camera-controls-section' });
    });
}

livePerformanceControls = createLivePerformanceControls({
    ensureAudioContext,
    getAudioContext,
    liveModalOverlay: liveSourceModalOverlay,
    liveSourceInput,
    liveSourceFftSize,
    liveSourceMonitorToggle,
    liveSourceRefreshBtn,
    liveSourceStreamBtn,
    liveSourceRecordBtn,
    liveSourceCaptureBtn,
    liveSourceCancelBtn,
    liveSourceStatusText,
    liveSourceAssetLabelInput,
    liveSourceIncludeMfccToggle,
    liveSourceProgressBlock,
    liveSourceProgressBar,
    liveSourceProgressText,
    onSessionStateChange: (nextState) => {
        void handleLiveSourceStateChange(nextState);
    },
    onImportRecordedAsset: async (payload, reportProgress) => {
        return importRecordedAudioAsset(payload, reportProgress);
    },
    onWarn: (...args) => {
        console.warn(...args);
    },
    onError: (...args) => {
        console.error(...args);
    },
});

syncAlwaysVisibleShellControls();

const appInitialization = createAppInitialization({
    applyInitialState: () => {
        appRuntimeBindings.applyInitialState();
        cameraControlPanel.applyInitialState();
        recordingControls.applyInitialState();
        livePerformanceControls.applyInitialState();
    },
    bindRuntimeEvents: () => {
        fpvControls.bind();
        appRuntimeBindings.bind();
        appInteractionBindings?.bind();
        recordingControls.bind();
        livePerformanceControls.bind();
    },
    startAnimationLoop: animationLoop.start,
    loadInitialAudioAssets: loadAudioAssetsManifest,
});

appInitialization.initialize();