import * as THREE from 'three';

const DEFAULT_LOW_COLOR = '#0b3d91';
const DEFAULT_HIGH_COLOR = '#f8e16c';
const DEFAULT_TERRAIN_WIDTH = 180;
const DEFAULT_TERRAIN_TIME_SPACING = 1.4;
const SCALE_EPSILON = 1e-6;
const TERRAIN_ENVELOPE_V1_KIND = 'terrain-envelope-v1';
const TERRAIN_ENVELOPE_V2_KIND = 'terrain-envelope-v2';
const TERRAIN_ENVELOPE_SUPPORTED_VERSIONS = new Set([1, 2]);
const TERRAIN_ENVELOPE_DEFAULT_SMOOTHING = 0.65;
const TERRAIN_ENVELOPE_DEFAULT_POWER = 0.45;
const TERRAIN_ENVELOPE_DEFAULT_AMP_PADDING_PERCENT = 5;
const TERRAIN_ENVELOPE_SPECTROGRAM_INTENSITY_SCALE = 255;
const DEFAULT_SURFACE_COLOR = new THREE.Color(0.1, 0.4, 0.8);
const DEFAULT_AXIS_COLOR_CONFIG = {
    x: {
        enabled: false,
        weight: 1,
        intervalCount: 1,
        intervals: [{ endPct: 100, minColor: '#102a83', maxColor: '#1d4ed8' }],
    },
    y: {
        enabled: true,
        weight: 1,
        intervalCount: 1,
        intervals: [{ endPct: 100, minColor: DEFAULT_LOW_COLOR, maxColor: DEFAULT_HIGH_COLOR }],
    },
    z: {
        enabled: false,
        weight: 1,
        intervalCount: 1,
        intervals: [{ endPct: 100, minColor: '#1f2937', maxColor: '#ec4899' }],
    },
};
const DEFAULT_TIME_WINDOW_CONFIG = {
    enabled: false,
    regions: [],
};
const DEFAULT_PLANE_SELECTION_ENABLED = true;
const DEFAULT_PLANE_SELECTION_CONFIG = {
    xz: { enabled: false, tintColor: '#22c55e', strength: 0.24, axis1MinPct: 0, axis1MaxPct: 100, axis2MinPct: 0, axis2MaxPct: 100 },
    yz: { enabled: false, tintColor: '#f59e0b', strength: 0.24, axis1MinPct: 0, axis1MaxPct: 100, axis2MinPct: 0, axis2MaxPct: 100 },
    xy: { enabled: false, tintColor: '#e879f9', strength: 0.22, axis1MinPct: 0, axis1MaxPct: 100, axis2MinPct: 0, axis2MaxPct: 100 },
};
const DEFAULT_UNSELECTED_REGION_MODE = 'Dim + Wiremesh';
const DEFAULT_UNSELECTED_REGION_COLOR = '#09131d';
const DEFAULT_UNSELECTED_REGION_STRENGTH = 0.76;
const DEFAULT_UNSELECTED_WIRE_COLOR = '#8de2ff';
const DEFAULT_UNSELECTED_WIRE_OPACITY = 0.42;
const DEFAULT_UNSELECTED_WIRE_STEP = 4;
const UNSELECTED_WIRE_REGION_MODES = new Set(['Dim + Wiremesh', 'Wiremesh Only']);
const LIVE_TERRAIN_COLOR_SYNC_INTERVAL = 2;
const LIVE_TERRAIN_NORMAL_SYNC_INTERVAL = 4;
const LIVE_TERRAIN_HELPER_SYNC_INTERVAL = 6;
const DEFAULT_2D_GRAPH_CONFIG = {
    xz: {
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
        extendBefore: 358,
        extendAfter: 358,
    },
    yz: {
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
        extendBefore: 358,
        extendAfter: 358,
    },
};

const clampUnit = (value) => THREE.MathUtils.clamp(value, 0, 1);

export class SpectrogramTerrain {
    constructor(scene, options = {}) {
        this.scene = scene;
        this.settings = null;
        this.visible = false;

        this.binCount = Math.max(8, options.binCount ?? 128);
        this.timeDepth = Math.max(8, options.timeDepth ?? 180);

        this.group = new THREE.Group();
        this.group.visible = false;
        this.scene.add(this.group);

        this.accumulatedGroup = new THREE.Group();
        this.group.add(this.accumulatedGroup);

        this.projectionGroup = new THREE.Group();
        this.group.add(this.projectionGroup);

        this.mesh = null;
        this.geometry = null;
        this.material = null;
        this.unselectedWireOverlay = null;
        this._unselectedWireOverlayMeta = null;

        this.floorGraphMesh = null;
        this.floorGraphBackground = null;
        this.extendedFloorGraphMesh = null;
        this.extendedFloorGraphBackground = null;
        this.wallGraphFill = null;
        this.wallGraphLine = null;
        this.wallGraphSpectrogram = null;
        this.wallGraphBackground = null;
        this.extendedWallGraphFill = null;
        this.extendedWallGraphLine = null;
        this.extendedWallGraphSpectrogram = null;
        this.extendedWallGraphBackground = null;

        this._positions = null;
        this._colors = null;
        this._basePositions = null;
        this._baseColors = null;

        this._sourceBinCount = this.binCount;
        this._autoScaleBounds = this._buildDefaultScaleBounds();
        this._activeScaleBounds = this._cloneScaleBounds(this._autoScaleBounds);

        this._ySmoothingState = new Float32Array(this.binCount);
        this._adaptiveGain = 1;
        this._frameRows = [];
        this._frameDataVersion = 0;
        this._terrainEnvelopeData = null;
        this._projectionHelperStatus = {
            summary: '2D Helper: Idle',
            detail: 'No helper activity yet.',
            activeSource: 'idle',
            preference: 'Prefer Precomputed',
        };
        this._currentFrameIndex = 0;
        this._colorAccumulator = new THREE.Color();
        this._axisColorScratch = new THREE.Color();
        this._graphHeatScratch = new THREE.Color();
        this._frameProfileCache = null;
        this._graphWindowSampleCache = new Map();
        this._graphWindowSampleCacheVersion = 0;
        this._liveFrameSyncCount = 0;
        this._extendedGraphLayouts = {
            xz: { rowCount: 0, depth: 0 },
            yz: { rowCount: 0, depth: 0 },
        };
        this._rebuildGeometry();
    }

    setSettings(settings) {
        this.settings = settings;
        this._invalidateGraphWindowSamples();
        this._applyMaterialSettings();
    }

    setVisible(visible) {
        this.visible = !!visible;
        this.group.visible = this.visible;
    }

    setDisplayScale({ x = 1, y = 1, z = 1 } = {}) {
        this.group.scale.set(x, y, z);
    }

    _disposeObject3D(obj) {
        if (!obj) return;
        if (obj.parent) obj.parent.remove(obj);
        obj.traverse((child) => {
            if (child.geometry && typeof child.geometry.dispose === 'function') {
                child.geometry.dispose();
            }
            if (child.material) {
                if (Array.isArray(child.material)) {
                    child.material.forEach((material) => material?.dispose?.());
                } else if (typeof child.material.dispose === 'function') {
                    child.material.dispose();
                }
            }
        });
    }

    accumulateCurrentView() {
        if (!this.mesh) return;
        const snapshot = this.mesh.clone();
        snapshot.geometry = this.mesh.geometry.clone();
        snapshot.material = this.mesh.material.clone();
        snapshot.frustumCulled = false;
        this.accumulatedGroup.add(snapshot);
    }

    clearAccumulatedView() {
        const children = [...this.accumulatedGroup.children];
        for (const child of children) {
            this._disposeObject3D(child);
        }
        this.accumulatedGroup.clear();
    }

    getAutoScaleBounds() {
        return this._cloneScaleBounds(this._autoScaleBounds);
    }

    setScaleBounds(bounds) {
        const nextBounds = this._normalizeScaleBounds(bounds, this._autoScaleBounds);
        if (this._scaleBoundsEqual(nextBounds, this._activeScaleBounds)) return;

        this._activeScaleBounds = nextBounds;
        this._invalidateFrameProfiles();
        this._rebuildGeometry();
        this._restoreVisibleWindow();
    }

    refreshGeometry() {
        this._updateAutoScaleBounds();
        this._invalidateFrameProfiles();
        this._rebuildGeometry();
        this._restoreVisibleWindow();
    }

    refreshColors() {
        this._syncRenderGeometry();
    }

    configure({ binCount, timeDepth }) {
        const nextBinCount = Math.max(8, binCount ?? this.binCount);
        const nextTimeDepth = Math.max(8, timeDepth ?? this.timeDepth);
        if (nextBinCount === this.binCount && nextTimeDepth === this.timeDepth) return;

        this.binCount = nextBinCount;
        this.timeDepth = nextTimeDepth;
        this._ySmoothingState = new Float32Array(this.binCount);
        this._adaptiveGain = 1;
        this._updateAutoScaleBounds();
        this._invalidateFrameProfiles();
        this._rebuildGeometry();
        this._restoreVisibleWindow();
    }

    hasFrameData() {
        return Array.isArray(this._frameRows) && this._frameRows.length > 0;
    }

    getFrameDataCount() {
        return this.hasFrameData() ? this._frameRows.length : 0;
    }

    getFrameDataRowAt(frameIndex) {
        if (!this.hasFrameData() || !Number.isFinite(frameIndex)) return null;
        const safeIndex = Math.max(0, Math.min(this._frameRows.length - 1, Math.round(frameIndex)));
        return this._frameRows[safeIndex] || null;
    }

    getAlignedFrameWindow() {
        const alignedWindow = this._getAlignedFrameWindow();
        return {
            start: alignedWindow.start,
            endExclusive: alignedWindow.endExclusive,
        };
    }

    pickSurfaceIntersection(raycaster) {
        if (!raycaster || !this.mesh || !this.group.visible || !this.mesh.visible) return null;
        const intersections = raycaster.intersectObject(this.mesh, false);
        return intersections[0] || null;
    }

    getSurfaceProfileForFrame(frameIndex) {
        if (!this.hasFrameData() || !Number.isFinite(frameIndex)) return null;

        const safeIndex = Math.max(0, Math.min(this._frameRows.length - 1, Math.round(frameIndex)));
        const profileCache = this._ensureFrameGraphProfiles();
        const yValues = profileCache?.yValuesByFrame?.[safeIndex];
        if (!profileCache?.xPositionsByBin || !yValues) return null;

        const alignedFrameWindow = this._getAlignedFrameWindow();
        return {
            frameIndex: safeIndex,
            xPositions: profileCache.xPositionsByBin,
            yValues,
            z: this._getWorldZForSourceFrame(safeIndex, alignedFrameWindow),
            alignedFrameWindow: {
                start: alignedFrameWindow.start,
                endExclusive: alignedFrameWindow.endExclusive,
            },
        };
    }

    getClosestVisibleFrameIndexForLocalZ(localZ) {
        if (!this.hasFrameData() || !Number.isFinite(localZ)) return null;

        const alignedFrameWindow = this._getAlignedFrameWindow();
        let bestFrameIndex = null;
        let bestDistance = Infinity;

        for (let frameIndex = alignedFrameWindow.start; frameIndex < alignedFrameWindow.endExclusive; frameIndex++) {
            const frameZ = this._getWorldZForSourceFrame(frameIndex, alignedFrameWindow);
            const distance = Math.abs(frameZ - localZ);
            if (distance < bestDistance) {
                bestDistance = distance;
                bestFrameIndex = frameIndex;
            }
        }

        return bestFrameIndex;
    }

    getProjectionHelperStatus() {
        return {
            ...this._projectionHelperStatus,
        };
    }

    loadTerrainEnvelopeData(payload) {
        if (!payload) {
            this._terrainEnvelopeData = null;
            return;
        }

        let parsed = payload;
        if (typeof payload === 'string') {
            try {
                parsed = JSON.parse(payload);
            } catch (error) {
                console.warn('Failed to parse terrain envelope helper data:', error);
                this._terrainEnvelopeData = null;
                return;
            }
        }

        const peakSmoothedValues = Array.isArray(parsed?.peakSmoothedValues) ? parsed.peakSmoothedValues : [];
        const peakDisplayBins = Array.isArray(parsed?.peakDisplayBins) ? parsed.peakDisplayBins : [];
        const frameCount = Math.max(0, Math.round(Number(parsed?.frameCount ?? peakSmoothedValues.length)));
        const displayBinCount = Math.max(1, Math.round(Number(parsed?.displayBinCount ?? this.binCount)));
        const helperVersion = Math.round(Number(parsed?.version ?? 0));
        const helperKind = typeof parsed?.kind === 'string' ? parsed.kind : '';
        const expectedSpectrogramValueCount = frameCount * displayBinCount;
        const spectrogramDisplayBins = Array.isArray(parsed?.wallSpectrogramDisplayBins)
            ? parsed.wallSpectrogramDisplayBins
            : [];
        const spectrogramIntensityBytes = Array.isArray(parsed?.wallSpectrogramIntensityBytes)
            ? parsed.wallSpectrogramIntensityBytes
            : Array.isArray(parsed?.wallSpectrogramIntensities)
                ? parsed.wallSpectrogramIntensities
                : [];
        const spectrogramIntensityScale = Math.max(
            1,
            Number.isFinite(Number(parsed?.wallSpectrogramIntensityScale))
                ? Number(parsed.wallSpectrogramIntensityScale)
                : TERRAIN_ENVELOPE_SPECTROGRAM_INTENSITY_SCALE,
        );

        if (
            !TERRAIN_ENVELOPE_SUPPORTED_VERSIONS.has(helperVersion) ||
            ![TERRAIN_ENVELOPE_V1_KIND, TERRAIN_ENVELOPE_V2_KIND].includes(helperKind) ||
            frameCount === 0 ||
            peakSmoothedValues.length < frameCount ||
            peakDisplayBins.length < frameCount
        ) {
            this._terrainEnvelopeData = null;
            return;
        }

        this._terrainEnvelopeData = {
            version: helperVersion,
            kind: helperKind,
            frameCount,
            displayBinCount,
            sourceBinCount: Math.max(1, Math.round(Number(parsed?.sourceBinCount ?? this._sourceBinCount ?? displayBinCount))),
            smoothing: Number.isFinite(Number(parsed?.smoothing)) ? Number(parsed.smoothing) : TERRAIN_ENVELOPE_DEFAULT_SMOOTHING,
            powerExponent: Number.isFinite(Number(parsed?.powerExponent)) ? Number(parsed.powerExponent) : TERRAIN_ENVELOPE_DEFAULT_POWER,
            amplitudePaddingPercent: Number.isFinite(Number(parsed?.amplitudePaddingPercent)) ? Number(parsed.amplitudePaddingPercent) : TERRAIN_ENVELOPE_DEFAULT_AMP_PADDING_PERCENT,
            peakSmoothedValues: Float32Array.from(peakSmoothedValues.slice(0, frameCount), (value) => THREE.MathUtils.clamp(Number(value) || 0, 0, 1)),
            peakDisplayBins: Int32Array.from(peakDisplayBins.slice(0, frameCount), (value) => Math.max(0, Math.round(Number(value) || 0))),
            wallSpectrogramDisplayBins: helperVersion >= 2 && spectrogramDisplayBins.length >= expectedSpectrogramValueCount
                ? Int32Array.from(
                    spectrogramDisplayBins.slice(0, expectedSpectrogramValueCount),
                    (value) => Math.max(0, Math.round(Number(value) || 0)),
                )
                : null,
            wallSpectrogramIntensity: helperVersion >= 2 && spectrogramIntensityBytes.length >= expectedSpectrogramValueCount
                ? Float32Array.from(
                    spectrogramIntensityBytes.slice(0, expectedSpectrogramValueCount),
                    (value) => THREE.MathUtils.clamp((Number(value) || 0) / spectrogramIntensityScale, 0, 1),
                )
                : null,
        };
    }

    _invalidateGraphWindowSamples() {
        this._graphWindowSampleCacheVersion += 1;
        this._graphWindowSampleCache.clear();
    }

    _invalidateFrameProfiles() {
        this._frameProfileCache = null;
        this._invalidateGraphWindowSamples();
    }

    _getTerrainHelperPreference() {
        return this.settings?.terrainHelperPreference === 'Prefer FFT Fallback'
            ? 'Prefer FFT Fallback'
            : 'Prefer Precomputed';
    }

    _getTerrainEnvelopeHelperProfile() {
        const helper = this._terrainEnvelopeData;
        const preference = this._getTerrainHelperPreference();
        const preferFallback = preference === 'Prefer FFT Fallback';
        const profile = {
            helper,
            preference,
            loaded: !!helper,
            compatible: false,
            plotSupported: false,
            spectrogramSupported: false,
            plotActive: false,
            spectrogramActive: false,
            reason: 'No precomputed helper loaded for this asset.',
        };
        if (!helper || !this.hasFrameData()) return profile;
        if (!TERRAIN_ENVELOPE_SUPPORTED_VERSIONS.has(helper.version)) {
            profile.reason = 'Helper version is not supported by this renderer.';
            return profile;
        }
        if (helper.frameCount !== this._frameRows.length) {
            profile.reason = 'Helper frame count does not match the loaded FFT data.';
            return profile;
        }
        if (helper.displayBinCount !== this.binCount) {
            profile.reason = 'Helper was exported for a different terrain bin count.';
            return profile;
        }
        if (!!this.settings?.terrainManualScaling) {
            profile.reason = 'Manual terrain scaling disables helper compatibility.';
            return profile;
        }

        const smoothing = Math.min(0.99, Math.max(0, this.settings?.terrainSmoothing ?? TERRAIN_ENVELOPE_DEFAULT_SMOOTHING));
        const amplitudePaddingPercent = Math.max(0, Number(this.settings?.terrainAutoPadAmpPercent ?? TERRAIN_ENVELOPE_DEFAULT_AMP_PADDING_PERCENT));
        if (Math.abs(helper.smoothing - smoothing) > 1e-6) {
            profile.reason = 'Helper smoothing does not match the current terrain smoothing.';
            return profile;
        }
        if (Math.abs(helper.powerExponent - TERRAIN_ENVELOPE_DEFAULT_POWER) > 1e-6) {
            profile.reason = 'Helper power curve does not match the current terrain profile.';
            return profile;
        }
        if (Math.abs(helper.amplitudePaddingPercent - amplitudePaddingPercent) > 1e-6) {
            profile.reason = 'Helper amplitude padding does not match the current terrain auto-padding.';
            return profile;
        }

        profile.compatible = true;
        profile.plotSupported = helper.peakSmoothedValues instanceof Float32Array && helper.peakDisplayBins instanceof Int32Array;
        profile.spectrogramSupported = helper.wallSpectrogramDisplayBins instanceof Int32Array && helper.wallSpectrogramIntensity instanceof Float32Array;
        profile.plotActive = profile.plotSupported && !preferFallback;
        profile.spectrogramActive = profile.spectrogramSupported && !preferFallback;
        profile.reason = preferFallback
            ? 'Helper is available, but the current preference forces FFT fallback.'
            : 'Helper is available and compatible.';
        return profile;
    }

    _setProjectionHelperStatus(status) {
        this._projectionHelperStatus = {
            summary: status?.summary ?? '2D Helper: Idle',
            detail: status?.detail ?? 'No helper activity yet.',
            activeSource: status?.activeSource ?? 'idle',
            preference: status?.preference ?? this._getTerrainHelperPreference(),
        };
    }

    _copyPeakColorFromArray(targetColor, colorArray, row, peakBinIndex) {
        const clampedPeakBin = THREE.MathUtils.clamp(Math.round(peakBinIndex ?? 0), 0, Math.max(0, this.binCount - 1));
        const colorOffset = ((row * this.binCount) + clampedPeakBin) * 3;
        targetColor.setRGB(
            colorArray[colorOffset + 0] ?? DEFAULT_SURFACE_COLOR.r,
            colorArray[colorOffset + 1] ?? DEFAULT_SURFACE_COLOR.g,
            colorArray[colorOffset + 2] ?? DEFAULT_SURFACE_COLOR.b,
        );
        return targetColor;
    }

    _getHelperPeakDataForFrame(helper, frameIndex, targetColor, colorArray, row) {
        if (!helper || frameIndex < 0 || frameIndex >= helper.frameCount) return null;

        const peakBinIndex = THREE.MathUtils.clamp(helper.peakDisplayBins[frameIndex] ?? 0, 0, Math.max(0, this.binCount - 1));
        const peakSmoothedValue = THREE.MathUtils.clamp(helper.peakSmoothedValues[frameIndex] ?? 0, 0, 1);
        this._copyPeakColorFromArray(targetColor, colorArray, row, peakBinIndex);

        return {
            peakBinIndex,
            peakY: this._computeAmplitudeY(peakSmoothedValue),
        };
    }

    _sampleWallSpectrogramFromHelper(helper, frameIndex, ampIndex, width, axisConfig, backgroundColor, heatStrength, targetColor) {
        if (!helper?.wallSpectrogramDisplayBins || !helper?.wallSpectrogramIntensity) {
            return null;
        }

        const clampedAmpIndex = THREE.MathUtils.clamp(Math.round(ampIndex ?? 0), 0, Math.max(0, this.binCount - 1));
        const lookupIndex = (frameIndex * this.binCount) + clampedAmpIndex;
        const displayBinIndex = THREE.MathUtils.clamp(
            helper.wallSpectrogramDisplayBins[lookupIndex] ?? 0,
            0,
            Math.max(0, this.binCount - 1),
        );
        const x = this._getWorldXForBin(displayBinIndex);
        const frequencyNorm = width > 0 ? ((x + width * 0.5) / width) : 0;
        const intensity = (helper.wallSpectrogramIntensity[lookupIndex] ?? 0) * heatStrength;

        return this._sampleHeatColor(axisConfig, frequencyNorm, backgroundColor, intensity, targetColor);
    }

    _buildProjectionHelperStatus(graphConfig, helperProfile, usage) {
        const preference = helperProfile.preference;
        if (!graphConfig?.yz?.enabled) {
            return {
                summary: '2D Helper: Idle (YZ Off)',
                detail: 'The precomputed helper path is idle because the Amplitude x Time graph is disabled.',
                activeSource: 'idle',
                preference,
            };
        }

        if (graphConfig.yz.graphType === 'Plot') {
            if (usage.plotActive) {
                return {
                    summary: '2D Helper: Precomputed Envelope',
                    detail: 'Amplitude x Time plot mode is using the precomputed envelope helper.',
                    activeSource: 'precomputed',
                    preference,
                };
            }

            if (helperProfile.loaded && helperProfile.compatible && !helperProfile.plotSupported) {
                return {
                    summary: '2D Helper: FFT Fallback',
                    detail: 'The loaded helper does not include plot support, so the renderer is using the FFT fallback path.',
                    activeSource: 'fallback',
                    preference,
                };
            }

            const activeSource = helperProfile.preference === 'Prefer FFT Fallback'
                ? 'manual-fallback'
                : helperProfile.loaded
                    ? helperProfile.compatible ? 'fallback' : 'incompatible'
                    : 'unavailable';

            return {
                summary: helperProfile.preference === 'Prefer FFT Fallback'
                    ? '2D Helper: FFT Fallback (Manual)'
                    : '2D Helper: FFT Fallback',
                detail: helperProfile.reason,
                activeSource,
                preference,
            };
        }

        if (usage.spectrogramActive) {
            return {
                summary: '2D Helper: Precomputed Spectrogram',
                detail: 'Amplitude x Time spectrogram mode is using the precomputed lookup helper.',
                activeSource: 'precomputed',
                preference,
            };
        }

        if (helperProfile.loaded && helperProfile.compatible && !helperProfile.spectrogramSupported) {
            return {
                summary: '2D Helper: FFT Fallback',
                detail: 'The loaded helper only supports envelope mode, so spectrogram mode is using the FFT fallback path.',
                activeSource: 'fallback',
                preference,
            };
        }

        const activeSource = helperProfile.preference === 'Prefer FFT Fallback'
            ? 'manual-fallback'
            : helperProfile.loaded
                ? helperProfile.compatible ? 'fallback' : 'incompatible'
                : 'unavailable';

        return {
            summary: helperProfile.preference === 'Prefer FFT Fallback'
                ? '2D Helper: FFT Fallback (Manual)'
                : '2D Helper: FFT Fallback',
            detail: helperProfile.reason,
            activeSource,
            preference,
        };
    }

    _buildGraphWindowEnvelopeSamples(frameWindow, alignedFrameWindow, helper, axisColors, timeWindows, planeSelections, width, height, depth) {
        const rowCount = Math.max(0, frameWindow.endExclusive - frameWindow.start);
        if (!helper || rowCount === 0) return null;

        const rowZ = new Float32Array(rowCount);
        const peakYValues = new Float32Array(rowCount);
        const peakBinIndices = new Int32Array(rowCount);
        const rowColors = new Float32Array(rowCount * 3);
        let minZ = Infinity;
        let maxZ = -Infinity;

        for (let frameIndex = frameWindow.start; frameIndex < frameWindow.endExclusive; frameIndex++) {
            const displayRow = frameWindow.endExclusive - 1 - frameIndex;
            const z = this._getWorldZForSourceFrame(frameIndex, alignedFrameWindow);
            const peakBinIndex = THREE.MathUtils.clamp(helper.peakDisplayBins[frameIndex] ?? 0, 0, Math.max(0, this.binCount - 1));
            const peakSmoothedValue = THREE.MathUtils.clamp(helper.peakSmoothedValues[frameIndex] ?? 0, 0, 1);
            const peakY = this._computeAmplitudeY(peakSmoothedValue);
            const x = this._getWorldXForBin(peakBinIndex);
            const sampledColor = this._sampleVertexColor(axisColors, timeWindows, planeSelections, x, peakY, z, width, height, depth);

            rowZ[displayRow] = z;
            peakYValues[displayRow] = peakY;
            peakBinIndices[displayRow] = peakBinIndex;
            rowColors[(displayRow * 3) + 0] = sampledColor.r;
            rowColors[(displayRow * 3) + 1] = sampledColor.g;
            rowColors[(displayRow * 3) + 2] = sampledColor.b;
            minZ = Math.min(minZ, z);
            maxZ = Math.max(maxZ, z);
        }

        return {
            rowCount,
            rowZ,
            peakYValues,
            peakBinIndices,
            rowColors,
            minZ: Number.isFinite(minZ) ? minZ : 0,
            maxZ: Number.isFinite(maxZ) ? maxZ : 0,
        };
    }

    loadFrameData(csvText) {
        const lines = csvText.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
        if (lines.length === 0) {
            this._frameRows = [];
            this._frameDataVersion += 1;
            this._sourceBinCount = this.binCount;
            this._currentFrameIndex = 0;
            this._updateAutoScaleBounds();
            this._invalidateFrameProfiles();
            this._resetSurface();
            return;
        }

        const firstValues = lines[0].split(',').map(value => Number.parseFloat(value));
        const hasHeader = firstValues.some(value => Number.isNaN(value));
        const dataLines = hasHeader ? lines.slice(1) : lines;

        const frameRows = [];
        for (const line of dataLines) {
            if (!line) continue;
            const values = line.split(',').map(value => Number.parseFloat(value));
            if (values.some(value => Number.isNaN(value))) continue;
            frameRows.push(new Float32Array(values));
        }

        this._frameRows = frameRows;
        this._frameDataVersion += 1;
        this._sourceBinCount = frameRows[0]?.length ?? this.binCount;
        this._currentFrameIndex = 0;
        this._liveFrameSyncCount = 0;
        this._updateAutoScaleBounds();
        this._invalidateFrameProfiles();
        this._resetSurface();
    }

    syncToProgress(progress) {
        if (!this.hasFrameData()) return;

        const frameCount = this._frameRows.length;
        const targetFrame = Math.max(0, Math.min(frameCount - 1, Math.floor(progress * frameCount)));
        const currentTarget = targetFrame + 1;

        if (currentTarget < this._currentFrameIndex) {
            this._currentFrameIndex = 0;
            this._resetSurface();
        }

        for (let frameIndex = this._currentFrameIndex; frameIndex < currentTarget; frameIndex++) {
            this._pushFrameData(this._frameRows[frameIndex]);
        }

        this._currentFrameIndex = currentTarget;
    }

    pushFrame(byteFrequencyData) {
        if (!this.visible || !this.mesh || !this.geometry || !this._positions || !this._colors) return;
        if (!this.hasFrameData()) {
            this._sourceBinCount = Math.max(1, byteFrequencyData.length);
            this._updateAutoScaleBounds();
        }
        this._pushFrameData(byteFrequencyData);
    }

    _pushFrameData(byteFrequencyData) {
        if (!this.mesh || !this.geometry || !this._positions || !this._colors) return;

        const s = this.settings || {};
        const smoothing = Math.min(0.99, Math.max(0, s.terrainSmoothing ?? 0.65));
        const isLiveFrame = byteFrequencyData instanceof Uint8Array;

        if (isLiveFrame) {
            this._liveFrameSyncCount += 1;
            let framePeak = 0;
            for (let i = 0; i < byteFrequencyData.length; i++) {
                framePeak = Math.max(framePeak, byteFrequencyData[i] ?? 0);
            }
            const targetGain = framePeak > 0 ? Math.min(6, 180 / framePeak) : 6;
            this._adaptiveGain = (this._adaptiveGain * 0.92) + (targetGain * 0.08);
        } else {
            this._adaptiveGain = 1;
            this._liveFrameSyncCount = 0;
        }

        // Shift all older rows one step back in time along Z.
        for (let row = this.timeDepth - 1; row > 0; row--) {
            for (let bin = 0; bin < this.binCount; bin++) {
                const dst = row * this.binCount + bin;
                const src = (row - 1) * this.binCount + bin;

                this._positions[dst * 3 + 1] = this._positions[src * 3 + 1];
            }
        }

        // Write newest row at the front (row = 0).
        for (let bin = 0; bin < this.binCount; bin++) {
            const rawValue = this._sampleFrameValue(byteFrequencyData, bin);
            const adjustedValue = isLiveFrame ? rawValue * this._adaptiveGain : rawValue;
            const clampedValue = THREE.MathUtils.clamp(
                adjustedValue,
                this._activeScaleBounds.amplitudeMin,
                this._activeScaleBounds.amplitudeMax
            );
            const enhanced = Math.pow(this._normalizeAmplitude(clampedValue), TERRAIN_ENVELOPE_DEFAULT_POWER);

            const prev = this._ySmoothingState[bin] ?? 0;
            const smoothValue = prev * smoothing + enhanced * (1 - smoothing);
            this._ySmoothingState[bin] = smoothValue;

            const y = this._computeAmplitudeY(smoothValue);
            const idx = bin;
            this._positions[idx * 3 + 1] = y;
        }

        const shouldRefreshColors = !isLiveFrame
            || this._liveFrameSyncCount === 1
            || (this._liveFrameSyncCount % LIVE_TERRAIN_COLOR_SYNC_INTERVAL) === 0;
        const shouldRefreshNormals = !isLiveFrame
            || this._liveFrameSyncCount === 1
            || (this._liveFrameSyncCount % LIVE_TERRAIN_NORMAL_SYNC_INTERVAL) === 0;
        const shouldRefreshHelpers = !isLiveFrame
            || this._liveFrameSyncCount === 1
            || (this._liveFrameSyncCount % LIVE_TERRAIN_HELPER_SYNC_INTERVAL) === 0;

        this._syncRenderGeometry({
            updateColors: shouldRefreshColors,
            updateNormals: shouldRefreshNormals,
            sync2DGraphs: shouldRefreshHelpers,
            syncWireOverlay: shouldRefreshHelpers,
        });
    }

    _resetSurface() {
        if (!this.geometry || !this._basePositions || !this._baseColors) return;
        this._positions.set(this._basePositions);
        this._colors.set(this._baseColors);
        this._ySmoothingState.fill(0);
        this._liveFrameSyncCount = 0;
        this._syncRenderGeometry();
    }

    _restoreVisibleWindow() {
        if (!this.geometry || !this._basePositions || !this._baseColors) return;

        this._positions.set(this._basePositions);
        this._colors.set(this._baseColors);
        this._ySmoothingState.fill(0);

        if (this.hasFrameData() && this._currentFrameIndex > 0) {
            const firstVisibleFrame = Math.max(0, this._currentFrameIndex - this.timeDepth);
            for (let frameIndex = firstVisibleFrame; frameIndex < this._currentFrameIndex; frameIndex++) {
                this._pushFrameData(this._frameRows[frameIndex]);
            }
            return;
        }

        this._syncRenderGeometry();
    }

    _syncRenderGeometry({ updateColors = true, updateNormals = true, sync2DGraphs = true, syncWireOverlay = true } = {}) {
        if (!this.geometry || !this._positions || !this._colors) return;

        const compiledPlaneSelections = (updateColors || syncWireOverlay)
            ? this._getCompiledPlaneSelectionConfig()
            : null;
        if (updateColors) {
            this._refreshAllVertexColors(compiledPlaneSelections);
        }
        
        // With a simple plane geometry, we don't need a separate render buffer,
        // we write directly to the geometry's buffers.
        const positionAttr = this.geometry.attributes.position;
        const colorAttr = this.geometry.attributes.color;

        if (positionAttr?.array?.length === this._positions.length && typeof positionAttr.array.set === 'function') {
            positionAttr.array.set(this._positions);
        } else {
            for (let i = 0; i < this._positions.length; i++) {
                positionAttr.array[i] = this._positions[i];
            }
        }

        if (updateColors) {
            if (colorAttr?.array?.length === this._colors.length && typeof colorAttr.array.set === 'function') {
                colorAttr.array.set(this._colors);
            } else {
                for (let i = 0; i < this._colors.length; i++) {
                    colorAttr.array[i] = this._colors[i];
                }
            }
            colorAttr.needsUpdate = true;
        }

        positionAttr.needsUpdate = true;
        
        if (updateNormals && this.geometry.computeVertexNormals) {
            this.geometry.computeVertexNormals();
        }

        if (sync2DGraphs) {
            this._sync2DGraphGeometry();
        }
        if (syncWireOverlay) {
            this._syncUnselectedWireOverlay(compiledPlaneSelections);
        }
    }

    _refreshAllVertexColors(compiledPlaneSelections = this._getCompiledPlaneSelectionConfig()) {
        const compiledAxisColors = this._getCompiledAxisColorConfig();
        const compiledTimeWindows = this._getCompiledTimeWindowConfig();
        const width = this._getFrequencyWorldLength();
        const height = this._getAmplitudeWorldLength();
        const depth = this._getTimeWorldLength();
        const vertexCount = this.binCount * this.timeDepth;

        for (let vertexIndex = 0; vertexIndex < vertexCount; vertexIndex++) {
            const colorOffset = vertexIndex * 3;
            const x = this._positions[colorOffset + 0];
            const y = this._positions[colorOffset + 1];
            const z = this._positions[colorOffset + 2];
            const color = this._sampleVertexColor(compiledAxisColors, compiledTimeWindows, compiledPlaneSelections, x, y, z, width, height, depth);

            this._colors[colorOffset + 0] = color.r;
            this._colors[colorOffset + 1] = color.g;
            this._colors[colorOffset + 2] = color.b;
        }
    }

    _sampleVertexColor(axisColors, timeWindows, planeSelections, x, y, z, width, height, depth) {
        const accumulator = this._colorAccumulator;
        const scratch = this._axisColorScratch;
        let activeAxisWeight = 0;
        const xNorm = width > 0 ? ((x + width * 0.5) / width) : 0;
        const yNorm = height > 0 ? (y / height) : 0;
        const zNorm = depth > 0 ? ((-z) / depth) : 0;

        accumulator.setRGB(0, 0, 0);

        if (axisColors.x.enabled && axisColors.x.weight > 0) {
            this._sampleAxisIntervalColor(axisColors.x, xNorm, scratch);
            scratch.multiplyScalar(axisColors.x.weight);
            accumulator.add(scratch);
            activeAxisWeight += axisColors.x.weight;
        }
        if (axisColors.y.enabled && axisColors.y.weight > 0) {
            this._sampleAxisIntervalColor(axisColors.y, yNorm, scratch);
            scratch.multiplyScalar(axisColors.y.weight);
            accumulator.add(scratch);
            activeAxisWeight += axisColors.y.weight;
        }
        if (axisColors.z.enabled && axisColors.z.weight > 0) {
            this._sampleAxisIntervalColor(axisColors.z, zNorm, scratch);
            scratch.multiplyScalar(axisColors.z.weight);
            accumulator.add(scratch);
            activeAxisWeight += axisColors.z.weight;
        }

        if (activeAxisWeight === 0) {
            accumulator.copy(DEFAULT_SURFACE_COLOR);
        } else {
            accumulator.multiplyScalar(1 / activeAxisWeight);
        }

        this._applyTimeWindowTints(accumulator, timeWindows, zNorm);
        this._applyPlaneSelectionTints(accumulator, planeSelections, xNorm, yNorm, zNorm);
        this._applyVolumeSelectionTint(accumulator, planeSelections.volume, xNorm, yNorm, zNorm);
        this._applyUnselectedRegionAppearance(accumulator, planeSelections, xNorm, yNorm, zNorm);
        return accumulator;
    }

    _sampleAxisIntervalColor(axisConfig, normalizedValue, targetColor) {
        const intervals = axisConfig.intervals;
        const clampedValue = clampUnit(normalizedValue);
        let interval = intervals[intervals.length - 1];

        for (const candidate of intervals) {
            if (clampedValue <= candidate.end) {
                interval = candidate;
                break;
            }
        }

        const intervalRange = Math.max(SCALE_EPSILON, interval.end - interval.start);
        const localT = clampUnit((clampedValue - interval.start) / intervalRange);

        targetColor.copy(interval.minColor).lerp(interval.maxColor, localT);
        return targetColor;
    }

    _applyTimeWindowTints(baseColor, timeWindows, normalizedTime) {
        if (!timeWindows.enabled) return baseColor;

        for (const region of timeWindows.regions) {
            if (normalizedTime < region.start || normalizedTime > region.end) continue;
            baseColor.lerp(region.tintColor, region.strength);
        }

        return baseColor;
    }

    _applyPlaneSelectionTints(baseColor, planeSelections, xNorm, yNorm, zNorm) {
        if (planeSelections?.enabled === false) return baseColor;

        const applyTint = (selection, axis1Value, axis2Value) => {
            if (!selection.enabled) return;
            if (axis1Value < selection.axis1Min || axis1Value > selection.axis1Max) return;
            if (axis2Value < selection.axis2Min || axis2Value > selection.axis2Max) return;
            baseColor.lerp(selection.tintColor, selection.strength);
        };

        applyTint(planeSelections.xz, xNorm, zNorm);
        applyTint(planeSelections.yz, yNorm, zNorm);
        applyTint(planeSelections.xy, xNorm, yNorm);
        return baseColor;
    }

    _applyVolumeSelectionTint(baseColor, volumeSelection, xNorm, yNorm, zNorm) {
        if (volumeSelection?.selectionEnabled === false) return baseColor;
        if (!volumeSelection?.enabled) return baseColor;
        if (xNorm < volumeSelection.xMin || xNorm > volumeSelection.xMax) return baseColor;
        if (yNorm < volumeSelection.yMin || yNorm > volumeSelection.yMax) return baseColor;
        if (zNorm < volumeSelection.zMin || zNorm > volumeSelection.zMax) return baseColor;

        baseColor.lerp(volumeSelection.tintColor, volumeSelection.strength);
        return baseColor;
    }

    _isPointInVolumeSelection(volumeSelection, xNorm, yNorm, zNorm) {
        if (volumeSelection?.selectionEnabled === false) return false;
        if (!volumeSelection?.enabled) return false;
        if (xNorm < volumeSelection.xMin || xNorm > volumeSelection.xMax) return false;
        if (yNorm < volumeSelection.yMin || yNorm > volumeSelection.yMax) return false;
        if (zNorm < volumeSelection.zMin || zNorm > volumeSelection.zMax) return false;
        return true;
    }

    _applyUnselectedRegionAppearance(baseColor, planeSelections, xNorm, yNorm, zNorm) {
        if (!planeSelections?.enabled) return baseColor;
        if (planeSelections.unselectedRegionMode === 'Normal Surface') return baseColor;
        if (this._isPointInVolumeSelection(planeSelections.volume, xNorm, yNorm, zNorm)) return baseColor;

        const strength = planeSelections.unselectedRegionMode === 'Wiremesh Only'
            ? Math.max(planeSelections.unselectedRegionStrength, 0.94)
            : planeSelections.unselectedRegionStrength;
        baseColor.lerp(planeSelections.unselectedRegionColor, strength);
        return baseColor;
    }

    _getCompiledAxisColorConfig() {
        const rawConfig = this.settings?.terrainAxisColors ?? {};
        return {
            x: this._compileAxisColorAxis(rawConfig.x, DEFAULT_AXIS_COLOR_CONFIG.x),
            y: this._compileAxisColorAxis(rawConfig.y, DEFAULT_AXIS_COLOR_CONFIG.y),
            z: this._compileAxisColorAxis(rawConfig.z, DEFAULT_AXIS_COLOR_CONFIG.z),
        };
    }

    _getCompiledTimeWindowConfig() {
        return this._compileTimeWindowConfig(this.settings?.terrainTimeWindows, DEFAULT_TIME_WINDOW_CONFIG);
    }

    _getCompiledPlaneSelectionConfig() {
        return this._compilePlaneSelectionConfig(this.settings?.terrainPlaneSelections, DEFAULT_PLANE_SELECTION_CONFIG);
    }

    _getCompiled2DGraphConfig() {
        return this._compile2DGraphConfig(this.settings?.terrain2DGraphs, DEFAULT_2D_GRAPH_CONFIG);
    }

    _compileAxisColorAxis(rawAxis, fallbackAxis) {
        const intervalCount = Math.max(1, Math.round(rawAxis?.intervalCount ?? fallbackAxis.intervalCount ?? 1));
        const rawIntervals = Array.isArray(rawAxis?.intervals) && rawAxis.intervals.length > 0
            ? rawAxis.intervals
            : fallbackAxis.intervals;
        let previousEndPct = 0;

        return {
            enabled: !!(rawAxis?.enabled ?? fallbackAxis.enabled),
            weight: Math.max(0, Number(rawAxis?.weight ?? fallbackAxis.weight ?? 1)),
            intervals: Array.from({ length: intervalCount }, (_, index) => {
                const fallbackInterval = rawIntervals[Math.min(index, rawIntervals.length - 1)] ?? fallbackAxis.intervals[0];
                const requestedEndPct = Number.isFinite(Number(fallbackInterval.endPct))
                    ? Number(fallbackInterval.endPct)
                    : (((index + 1) / intervalCount) * 100);
                const endPct = index === intervalCount - 1
                    ? 100
                    : THREE.MathUtils.clamp(requestedEndPct, previousEndPct + 0.1, 100);
                const start = previousEndPct / 100;
                const end = endPct / 100;
                previousEndPct = endPct;
                return {
                    start,
                    end,
                    minColor: new THREE.Color(fallbackInterval.minColor ?? fallbackAxis.intervals[0].minColor),
                    maxColor: new THREE.Color(fallbackInterval.maxColor ?? fallbackAxis.intervals[0].maxColor),
                };
            }),
        };
    }

    _compileTimeWindowConfig(rawConfig, fallbackConfig) {
        const rawRegions = Array.isArray(rawConfig?.regions) ? rawConfig.regions : fallbackConfig.regions;

        return {
            enabled: !!(rawConfig?.enabled ?? fallbackConfig.enabled),
            regions: rawRegions.map((region) => {
                const startPct = Number.isFinite(Number(region?.startPct)) ? Number(region.startPct) : 0;
                const endPct = Number.isFinite(Number(region?.endPct)) ? Number(region.endPct) : 100;
                return {
                    start: clampUnit(Math.min(startPct, endPct) / 100),
                    end: clampUnit(Math.max(startPct, endPct) / 100),
                    tintColor: new THREE.Color(region?.tintColor ?? '#ffffff'),
                    strength: THREE.MathUtils.clamp(Number(region?.strength ?? 0.25), 0, 1),
                };
            }),
        };
    }

    _compilePlaneSelectionConfig(rawConfig, fallbackConfig) {
        const compiledSelections = {
            enabled: !!(rawConfig?.enabled ?? DEFAULT_PLANE_SELECTION_ENABLED),
            xz: this._compilePlaneSelection(rawConfig?.xz, fallbackConfig.xz),
            yz: this._compilePlaneSelection(rawConfig?.yz, fallbackConfig.yz),
            xy: this._compilePlaneSelection(rawConfig?.xy, fallbackConfig.xy),
            unselectedRegionMode: rawConfig?.unselectedRegionMode === 'Normal Surface'
                ? 'Normal Surface'
                : rawConfig?.unselectedRegionMode === 'Dim Surface'
                    ? 'Dim Surface'
                    : rawConfig?.unselectedRegionMode === 'Wiremesh Only'
                        ? 'Wiremesh Only'
                        : DEFAULT_UNSELECTED_REGION_MODE,
            unselectedRegionColor: new THREE.Color(rawConfig?.unselectedRegionColor ?? DEFAULT_UNSELECTED_REGION_COLOR),
            unselectedRegionStrength: THREE.MathUtils.clamp(
                Number(rawConfig?.unselectedRegionStrength ?? DEFAULT_UNSELECTED_REGION_STRENGTH),
                0,
                1,
            ),
            unselectedWireColor: new THREE.Color(rawConfig?.unselectedWireColor ?? DEFAULT_UNSELECTED_WIRE_COLOR),
            unselectedWireOpacity: THREE.MathUtils.clamp(
                Number(rawConfig?.unselectedWireOpacity ?? DEFAULT_UNSELECTED_WIRE_OPACITY),
                0,
                1,
            ),
            unselectedWireStep: THREE.MathUtils.clamp(
                Math.round(Number(rawConfig?.unselectedWireStep ?? DEFAULT_UNSELECTED_WIRE_STEP)),
                2,
                12,
            ),
        };
        compiledSelections.volume = compiledSelections.enabled
            ? this._compilePlaneSelectionVolume(compiledSelections)
            : { enabled: false, selectionEnabled: false };
        return compiledSelections;
    }

    _compilePlaneSelection(rawSelection, fallbackSelection) {
        const axis1MinPct = Number.isFinite(Number(rawSelection?.axis1MinPct)) ? Number(rawSelection.axis1MinPct) : fallbackSelection.axis1MinPct;
        const axis1MaxPct = Number.isFinite(Number(rawSelection?.axis1MaxPct)) ? Number(rawSelection.axis1MaxPct) : fallbackSelection.axis1MaxPct;
        const axis2MinPct = Number.isFinite(Number(rawSelection?.axis2MinPct)) ? Number(rawSelection.axis2MinPct) : fallbackSelection.axis2MinPct;
        const axis2MaxPct = Number.isFinite(Number(rawSelection?.axis2MaxPct)) ? Number(rawSelection.axis2MaxPct) : fallbackSelection.axis2MaxPct;

        return {
            enabled: !!(rawSelection?.enabled ?? fallbackSelection.enabled),
            tintColor: new THREE.Color(rawSelection?.tintColor ?? fallbackSelection.tintColor),
            strength: THREE.MathUtils.clamp(Number(rawSelection?.strength ?? fallbackSelection.strength), 0, 1),
            axis1Min: clampUnit(Math.min(axis1MinPct, axis1MaxPct) / 100),
            axis1Max: clampUnit(Math.max(axis1MinPct, axis1MaxPct) / 100),
            axis2Min: clampUnit(Math.min(axis2MinPct, axis2MaxPct) / 100),
            axis2Max: clampUnit(Math.max(axis2MinPct, axis2MaxPct) / 100),
        };
    }

    _compile2DGraphConfig(rawConfig, fallbackConfig) {
        return {
            xz: this._compile2DGraphPlane(rawConfig?.xz, fallbackConfig.xz),
            yz: this._compile2DGraphPlane(rawConfig?.yz, fallbackConfig.yz),
        };
    }

    _compile2DGraphPlane(rawPlane, fallbackPlane) {
        const showGraphsAs = rawPlane?.showGraphsAs === 'Extended 2D Graphs'
            ? 'Extended 2D Graphs'
            : rawPlane?.showGraphsAs === 'Both'
                ? 'Both'
                : '3D Aligned 2D Graphs';
        const graphType = rawPlane?.graphType === 'Spectrogram' ? 'Spectrogram' : 'Plot';
        const surface = rawPlane?.surface === 'Front' ? 'Front' : 'Back';
        const defaultExtension = Math.max(1, (this.timeDepth - 1) * 2);
        return {
            enabled: !!(rawPlane?.enabled ?? fallbackPlane.enabled),
            showGraphsAs,
            graphType,
            surface,
            graphOpacity: THREE.MathUtils.clamp(Number(rawPlane?.graphOpacity ?? fallbackPlane.graphOpacity), 0, 1),
            backgroundEnabled: !!(rawPlane?.backgroundEnabled ?? fallbackPlane.backgroundEnabled),
            backgroundColor: new THREE.Color(rawPlane?.backgroundColor ?? fallbackPlane.backgroundColor),
            backgroundOpacity: THREE.MathUtils.clamp(Number(rawPlane?.backgroundOpacity ?? fallbackPlane.backgroundOpacity), 0, 1),
            offset: Math.max(0, Number(rawPlane?.offset ?? fallbackPlane.offset ?? 0)),
            heatStrength: Math.max(0, Number(rawPlane?.heatStrength ?? fallbackPlane.heatStrength ?? 1)),
            extendBefore: Math.max(0, Number(rawPlane?.extendBefore ?? fallbackPlane.extendBefore ?? defaultExtension)),
            extendAfter: Math.max(0, Number(rawPlane?.extendAfter ?? fallbackPlane.extendAfter ?? defaultExtension)),
        };
    }

    _compilePlaneSelectionVolume(planeSelections) {
        const axisRanges = { x: [], y: [], z: [] };
        const activeSelections = [];
        const tintColor = new THREE.Color(0, 0, 0);
        let tintWeight = 0;

        const registerAxisRange = (axisKey, min, max) => {
            axisRanges[axisKey].push({ min, max });
        };
        const registerSelection = (selection, rangesByAxis) => {
            if (!selection?.enabled) return;
            activeSelections.push(selection);

            const weight = Math.max(selection.strength, 0.01);
            tintColor.add(selection.tintColor.clone().multiplyScalar(weight));
            tintWeight += weight;

            for (const [axisKey, [min, max]] of Object.entries(rangesByAxis)) {
                registerAxisRange(axisKey, Math.min(min, max), Math.max(min, max));
            }
        };

        registerSelection(planeSelections.xz, {
            x: [planeSelections.xz.axis1Min, planeSelections.xz.axis1Max],
            z: [planeSelections.xz.axis2Min, planeSelections.xz.axis2Max],
        });
        registerSelection(planeSelections.yz, {
            y: [planeSelections.yz.axis1Min, planeSelections.yz.axis1Max],
            z: [planeSelections.yz.axis2Min, planeSelections.yz.axis2Max],
        });
        registerSelection(planeSelections.xy, {
            x: [planeSelections.xy.axis1Min, planeSelections.xy.axis1Max],
            y: [planeSelections.xy.axis2Min, planeSelections.xy.axis2Max],
        });

        if (axisRanges.x.length === 0 || axisRanges.y.length === 0 || axisRanges.z.length === 0) {
            return { enabled: false, selectionEnabled: planeSelections.enabled };
        }

        const xMin = Math.max(...axisRanges.x.map((range) => range.min));
        const xMax = Math.min(...axisRanges.x.map((range) => range.max));
        const yMin = Math.max(...axisRanges.y.map((range) => range.min));
        const yMax = Math.min(...axisRanges.y.map((range) => range.max));
        const zMin = Math.max(...axisRanges.z.map((range) => range.min));
        const zMax = Math.min(...axisRanges.z.map((range) => range.max));

        if (xMax <= xMin + SCALE_EPSILON || yMax <= yMin + SCALE_EPSILON || zMax <= zMin + SCALE_EPSILON) {
            return { enabled: false, selectionEnabled: planeSelections.enabled };
        }

        if (tintWeight > 0) {
            tintColor.multiplyScalar(1 / tintWeight);
        } else {
            tintColor.set(DEFAULT_HIGH_COLOR);
        }

        return {
            enabled: true,
            selectionEnabled: planeSelections.enabled,
            tintColor,
            strength: activeSelections.reduce((sum, selection) => sum + selection.strength, 0) / activeSelections.length,
            xMin,
            xMax,
            yMin,
            yMax,
            zMin,
            zMax,
        };
    }

    _dispose2DGraphs() {
        for (const object of [
            this.floorGraphMesh,
            this.floorGraphBackground,
            this.extendedFloorGraphMesh,
            this.extendedFloorGraphBackground,
            this.wallGraphFill,
            this.wallGraphLine,
            this.wallGraphSpectrogram,
            this.wallGraphBackground,
            this.extendedWallGraphFill,
            this.extendedWallGraphLine,
            this.extendedWallGraphSpectrogram,
            this.extendedWallGraphBackground,
        ]) {
            if (object) this._disposeObject3D(object);
        }

        this.floorGraphMesh = null;
        this.floorGraphBackground = null;
        this.extendedFloorGraphMesh = null;
        this.extendedFloorGraphBackground = null;
        this.wallGraphFill = null;
        this.wallGraphLine = null;
        this.wallGraphSpectrogram = null;
        this.wallGraphBackground = null;
        this.extendedWallGraphFill = null;
        this.extendedWallGraphLine = null;
        this.extendedWallGraphSpectrogram = null;
        this.extendedWallGraphBackground = null;
        this._extendedGraphLayouts = {
            xz: { rowCount: 0, depth: 0 },
            yz: { rowCount: 0, depth: 0 },
        };
    }

    _disposeUnselectedWireOverlay() {
        if (!this.unselectedWireOverlay) {
            this._unselectedWireOverlayMeta = null;
            return;
        }

        this.group.remove(this.unselectedWireOverlay);
        this.unselectedWireOverlay.geometry?.dispose?.();
        this.unselectedWireOverlay.material?.dispose?.();
        this.unselectedWireOverlay = null;
        this._unselectedWireOverlayMeta = null;
    }

    _ensureUnselectedWireOverlay(step) {
        const safeStep = THREE.MathUtils.clamp(Math.round(step || DEFAULT_UNSELECTED_WIRE_STEP), 2, 12);
        const needsRebuild = !this.unselectedWireOverlay
            || !this._unselectedWireOverlayMeta
            || this._unselectedWireOverlayMeta.step !== safeStep
            || this._unselectedWireOverlayMeta.binCount !== this.binCount
            || this._unselectedWireOverlayMeta.timeDepth !== this.timeDepth;

        if (!needsRebuild) return;

        this._disposeUnselectedWireOverlay();

        const sourcePairs = [];
        for (let row = 0; row < this.timeDepth; row += safeStep) {
            const nextRow = Math.min(this.timeDepth - 1, row + safeStep);
            for (let bin = 0; bin < this.binCount; bin += safeStep) {
                const nextBin = Math.min(this.binCount - 1, bin + safeStep);
                const startIndex = (row * this.binCount) + bin;
                if (nextBin > bin) {
                    sourcePairs.push([startIndex, (row * this.binCount) + nextBin]);
                }
                if (nextRow > row) {
                    sourcePairs.push([startIndex, (nextRow * this.binCount) + bin]);
                }
            }
        }

        const positionArray = new Float32Array(Math.max(1, sourcePairs.length * 6));
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positionArray, 3));
        geometry.setDrawRange(0, 0);

        const material = new THREE.LineBasicMaterial({
            color: DEFAULT_UNSELECTED_WIRE_COLOR,
            transparent: true,
            opacity: DEFAULT_UNSELECTED_WIRE_OPACITY,
            depthWrite: false,
        });

        const overlay = new THREE.LineSegments(geometry, material);
        overlay.frustumCulled = false;
        overlay.renderOrder = 18;
        this.group.add(overlay);

        this.unselectedWireOverlay = overlay;
        this._unselectedWireOverlayMeta = {
            step: safeStep,
            binCount: this.binCount,
            timeDepth: this.timeDepth,
            positionArray,
            sourcePairs,
        };
    }

    _isPointInCompiledVolume(volumeSelection, x, y, z, width, height, depth) {
        const xNorm = width > 0 ? ((x + width * 0.5) / width) : 0;
        const yNorm = height > 0 ? (y / height) : 0;
        const zNorm = depth > 0 ? ((-z) / depth) : 0;
        return this._isPointInVolumeSelection(volumeSelection, xNorm, yNorm, zNorm);
    }

    _syncUnselectedWireOverlay(compiledPlaneSelections) {
        const shouldShowWire = compiledPlaneSelections?.enabled
            && compiledPlaneSelections.volume?.enabled
            && UNSELECTED_WIRE_REGION_MODES.has(compiledPlaneSelections.unselectedRegionMode);

        if (!shouldShowWire || !this._positions) {
            this._disposeUnselectedWireOverlay();
            return;
        }

        this._ensureUnselectedWireOverlay(compiledPlaneSelections.unselectedWireStep);
        if (!this.unselectedWireOverlay || !this._unselectedWireOverlayMeta) return;

        const overlayMaterial = this.unselectedWireOverlay.material;
        overlayMaterial.color.copy(compiledPlaneSelections.unselectedWireColor);
        overlayMaterial.opacity = compiledPlaneSelections.unselectedWireOpacity;
        overlayMaterial.transparent = compiledPlaneSelections.unselectedWireOpacity < 1;
        overlayMaterial.needsUpdate = true;

        const width = this._getFrequencyWorldLength();
        const height = this._getAmplitudeWorldLength();
        const depth = this._getTimeWorldLength();
        const { positionArray, sourcePairs } = this._unselectedWireOverlayMeta;
        let writeOffset = 0;

        for (const [startIndex, endIndex] of sourcePairs) {
            const startOffset = startIndex * 3;
            const endOffset = endIndex * 3;
            const startX = this._positions[startOffset + 0] ?? 0;
            const startY = this._positions[startOffset + 1] ?? 0;
            const startZ = this._positions[startOffset + 2] ?? 0;
            const endX = this._positions[endOffset + 0] ?? 0;
            const endY = this._positions[endOffset + 1] ?? 0;
            const endZ = this._positions[endOffset + 2] ?? 0;

            const startInside = this._isPointInCompiledVolume(compiledPlaneSelections.volume, startX, startY, startZ, width, height, depth);
            const endInside = this._isPointInCompiledVolume(compiledPlaneSelections.volume, endX, endY, endZ, width, height, depth);
            if (startInside && endInside) continue;

            positionArray[writeOffset++] = startX;
            positionArray[writeOffset++] = startY;
            positionArray[writeOffset++] = startZ;
            positionArray[writeOffset++] = endX;
            positionArray[writeOffset++] = endY;
            positionArray[writeOffset++] = endZ;
        }

        this.unselectedWireOverlay.geometry.setDrawRange(0, writeOffset / 3);
        this.unselectedWireOverlay.geometry.attributes.position.needsUpdate = true;
    }

    _createFloorProjectionObjects(rowCount, depth, meshRenderOrder, backgroundRenderOrder) {
        const safeDepth = Math.max(SCALE_EPSILON, depth);
        const geometry = new THREE.PlaneGeometry(
            this._getFrequencyWorldLength(),
            safeDepth,
            Math.max(1, this.binCount - 1),
            Math.max(1, rowCount - 1),
        );
        geometry.rotateX(Math.PI / 2);
        geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(this.binCount * rowCount * 3), 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(this.binCount * rowCount * 3), 3));

        const mesh = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
            vertexColors: true,
            transparent: true,
            opacity: 0.82,
            side: THREE.DoubleSide,
            depthWrite: false,
        }));
        mesh.frustumCulled = false;
        mesh.renderOrder = meshRenderOrder;

        const backgroundGeometry = new THREE.PlaneGeometry(this._getFrequencyWorldLength(), safeDepth, 1, 1);
        backgroundGeometry.rotateX(Math.PI / 2);
        const background = new THREE.Mesh(backgroundGeometry, new THREE.MeshBasicMaterial({
            color: '#07131f',
            transparent: true,
            opacity: 0.34,
            side: THREE.DoubleSide,
            depthWrite: false,
        }));
        background.frustumCulled = false;
        background.renderOrder = backgroundRenderOrder;

        this.projectionGroup.add(mesh);
        this.projectionGroup.add(background);
        return { mesh, background };
    }

    _createWallProjectionObjects(rowCount, depth, height, fillRenderOrder, lineRenderOrder, spectrogramRenderOrder, backgroundRenderOrder) {
        const safeDepth = Math.max(SCALE_EPSILON, depth);
        const safeRowCount = Math.max(2, rowCount);
        const fillGeometry = new THREE.BufferGeometry();
        fillGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(safeRowCount * 2 * 3), 3));
        fillGeometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(safeRowCount * 2 * 3), 3));
        const indices = [];
        for (let row = 0; row < safeRowCount - 1; row++) {
            const a = row * 2;
            const b = a + 1;
            const c = a + 2;
            const d = a + 3;
            indices.push(a, b, c, b, d, c);
        }
        fillGeometry.setIndex(indices);

        const fill = new THREE.Mesh(fillGeometry, new THREE.MeshBasicMaterial({
            vertexColors: true,
            transparent: true,
            opacity: 0.32,
            side: THREE.DoubleSide,
            depthWrite: false,
        }));
        fill.frustumCulled = false;
        fill.renderOrder = fillRenderOrder;

        const lineGeometry = new THREE.BufferGeometry();
        lineGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(safeRowCount * 3), 3));
        lineGeometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(safeRowCount * 3), 3));

        const line = new THREE.Line(lineGeometry, new THREE.LineBasicMaterial({
            vertexColors: true,
            transparent: true,
            opacity: 0.88,
            depthWrite: false,
        }));
        line.frustumCulled = false;
        line.renderOrder = lineRenderOrder;

        const spectrogramGeometry = new THREE.PlaneGeometry(
            safeDepth,
            height,
            Math.max(1, safeRowCount - 1),
            Math.max(1, this.binCount - 1),
        );
        spectrogramGeometry.rotateY(Math.PI / 2);
        spectrogramGeometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(safeRowCount * this.binCount * 3), 3));

        const spectrogram = new THREE.Mesh(spectrogramGeometry, new THREE.MeshBasicMaterial({
            vertexColors: true,
            transparent: true,
            opacity: 0.88,
            side: THREE.DoubleSide,
            depthWrite: false,
        }));
        spectrogram.frustumCulled = false;
        spectrogram.renderOrder = spectrogramRenderOrder;

        const backgroundGeometry = new THREE.PlaneGeometry(safeDepth, height, 1, 1);
        backgroundGeometry.rotateY(Math.PI / 2);
        const background = new THREE.Mesh(backgroundGeometry, new THREE.MeshBasicMaterial({
            color: '#180f0a',
            transparent: true,
            opacity: 0.32,
            side: THREE.DoubleSide,
            depthWrite: false,
        }));
        background.frustumCulled = false;
        background.renderOrder = backgroundRenderOrder;

        this.projectionGroup.add(fill);
        this.projectionGroup.add(line);
        this.projectionGroup.add(spectrogram);
        this.projectionGroup.add(background);
        return { fill, line, spectrogram, background };
    }

    _getAlignedFrameWindow() {
        if (!this.hasFrameData()) {
            return { start: 0, endExclusive: this.timeDepth };
        }

        const endExclusive = Math.max(1, Math.min(this._frameRows.length, this._currentFrameIndex || 1));
        const start = Math.max(0, endExclusive - this.timeDepth);
        return { start, endExclusive };
    }

    _getExtendedFrameWindow(planeConfig) {
        const aligned = this._getAlignedFrameWindow();
        if (!this.hasFrameData()) return aligned;

        return {
            start: Math.max(0, aligned.start - Math.round(planeConfig.extendBefore ?? 0)),
            endExclusive: Math.min(this._frameRows.length, aligned.endExclusive + Math.round(planeConfig.extendAfter ?? 0)),
        };
    }

    _getTimeStepWorld() {
        if (this.timeDepth <= 1) return DEFAULT_TERRAIN_TIME_SPACING;

        const firstVisibleRow = Math.min(
            this.timeDepth - 1,
            Math.max(0, Math.ceil(Number(this._activeScaleBounds?.timeMin ?? 0))),
        );
        const secondVisibleRow = Math.min(this.timeDepth - 1, firstVisibleRow + 1);
        if (secondVisibleRow > firstVisibleRow) {
            const visibleStep = Math.abs(this._getWorldZForRow(secondVisibleRow) - this._getWorldZForRow(firstVisibleRow));
            if (visibleStep > SCALE_EPSILON) return visibleStep;
        }

        const autoRange = this._getRange(this._autoScaleBounds.timeMin, this._autoScaleBounds.timeMax);
        return autoRange > 0
            ? (this._getBaseTimeDepth() / autoRange)
            : DEFAULT_TERRAIN_TIME_SPACING;
    }

    _getWorldZForSourceFrame(frameIndex, alignedFrameWindow) {
        const latestAlignedFrame = alignedFrameWindow.endExclusive - 1;
        const alignedRow = latestAlignedFrame - frameIndex;
        const step = this._getTimeStepWorld();

        if (alignedRow < 0) {
            return Math.abs(alignedRow) * step;
        }

        if (alignedRow <= this.timeDepth - 1) {
            return this._getWorldZForRow(alignedRow);
        }

        return this._getWorldZForRow(this.timeDepth - 1) - ((alignedRow - (this.timeDepth - 1)) * step);
    }

    _getFrameProfileCacheSignature() {
        const smoothing = Math.min(0.99, Math.max(0, this.settings?.terrainSmoothing ?? 0.65));
        return [
            this._frameDataVersion,
            this.binCount,
            this._sourceBinCount,
            smoothing,
            this._getFrequencyWorldLength(),
            this._getAmplitudeWorldLength(),
            this._activeScaleBounds.frequencyMin,
            this._activeScaleBounds.frequencyMax,
            this._autoScaleBounds.frequencyMin,
            this._autoScaleBounds.frequencyMax,
            this._activeScaleBounds.amplitudeMin,
            this._activeScaleBounds.amplitudeMax,
            this._autoScaleBounds.amplitudeMin,
            this._autoScaleBounds.amplitudeMax,
        ].map((value) => Number.isFinite(Number(value)) ? Number(value).toFixed(6) : String(value)).join('|');
    }

    _ensureFrameGraphProfiles() {
        if (!this.hasFrameData()) return null;

        const signature = this._getFrameProfileCacheSignature();
        if (this._frameProfileCache?.signature === signature) {
            return this._frameProfileCache;
        }

        const frameCount = this._frameRows.length;
        const smoothing = Math.min(0.99, Math.max(0, this.settings?.terrainSmoothing ?? 0.65));
        const height = this._getAmplitudeWorldLength();
        const width = this._getFrequencyWorldLength();
        const smoothingState = new Float32Array(this.binCount);
        const yValuesByFrame = new Array(frameCount);
        const peakYValues = new Float32Array(frameCount);
        const peakBinIndices = new Int32Array(frameCount);
        const spectrogramFrequencyNormsByFrame = new Array(frameCount);
        const spectrogramIntensityByFrame = new Array(frameCount);
        const xPositionsByBin = new Float32Array(this.binCount);
        const frequencyNormByBin = new Float32Array(this.binCount);

        for (let bin = 0; bin < this.binCount; bin++) {
            const x = this._getWorldXForBin(bin);
            xPositionsByBin[bin] = x;
            frequencyNormByBin[bin] = width > 0 ? ((x + width * 0.5) / width) : 0;
        }

        for (let frameIndex = 0; frameIndex < frameCount; frameIndex++) {
            const frameData = this._frameRows[frameIndex];
            const yProfile = new Float32Array(this.binCount);
            let peakY = 0;
            let peakBinIndex = 0;

            for (let bin = 0; bin < this.binCount; bin++) {
                const rawValue = this._sampleFrameValue(frameData, bin);
                const clampedValue = THREE.MathUtils.clamp(
                    rawValue,
                    this._activeScaleBounds.amplitudeMin,
                    this._activeScaleBounds.amplitudeMax,
                );
                const enhanced = Math.pow(this._normalizeAmplitude(clampedValue), TERRAIN_ENVELOPE_DEFAULT_POWER);
                const prev = smoothingState[bin] ?? 0;
                const smoothValue = prev * smoothing + enhanced * (1 - smoothing);
                smoothingState[bin] = smoothValue;

                const y = this._computeAmplitudeY(smoothValue);
                yProfile[bin] = y;

                if (y >= peakY) {
                    peakY = y;
                    peakBinIndex = bin;
                }
            }

            const frequencyNorms = new Float32Array(this.binCount);
            const intensities = new Float32Array(this.binCount);
            for (let ampIndex = 0; ampIndex < this.binCount; ampIndex++) {
                const amplitudeNorm = this.binCount > 1 ? (ampIndex / (this.binCount - 1)) : 0;
                const targetY = amplitudeNorm * height;
                let bestDistance = Infinity;
                let bestBinIndex = 0;

                for (let bin = 0; bin < this.binCount; bin++) {
                    const distance = Math.abs((yProfile[bin] ?? 0) - targetY);
                    if (distance < bestDistance) {
                        bestDistance = distance;
                        bestBinIndex = bin;
                    }
                }

                frequencyNorms[ampIndex] = frequencyNormByBin[bestBinIndex] ?? 0;
                intensities[ampIndex] = THREE.MathUtils.clamp(
                    1 - (((height > 0 ? bestDistance / height : bestDistance) * Math.max(4, this.binCount * 0.55))),
                    0,
                    1,
                );
            }

            yValuesByFrame[frameIndex] = yProfile;
            peakYValues[frameIndex] = peakY;
            peakBinIndices[frameIndex] = peakBinIndex;
            spectrogramFrequencyNormsByFrame[frameIndex] = frequencyNorms;
            spectrogramIntensityByFrame[frameIndex] = intensities;
        }

        this._frameProfileCache = {
            signature,
            xPositionsByBin,
            yValuesByFrame,
            peakYValues,
            peakBinIndices,
            spectrogramFrequencyNormsByFrame,
            spectrogramIntensityByFrame,
        };

        return this._frameProfileCache;
    }

    _getGraphWindowSampleCacheKey(frameWindow, alignedFrameWindow, width, height, depth, profileSignature) {
        return [
            this._graphWindowSampleCacheVersion,
            profileSignature,
            frameWindow.start,
            frameWindow.endExclusive,
            alignedFrameWindow.start,
            alignedFrameWindow.endExclusive,
            width,
            height,
            depth,
        ].map((value) => Number.isFinite(Number(value)) ? Number(value).toFixed(6) : String(value)).join('|');
    }

    _buildGraphWindowSamples(frameWindow, alignedFrameWindow, axisColors, timeWindows, planeSelections, width, height, depth) {
        const rowCount = Math.max(0, frameWindow.endExclusive - frameWindow.start);
        if (!this.hasFrameData() || rowCount === 0) return null;

        const profileCache = this._ensureFrameGraphProfiles();
        if (!profileCache) return null;

        const cacheKey = this._getGraphWindowSampleCacheKey(
            frameWindow,
            alignedFrameWindow,
            width,
            height,
            depth,
            profileCache.signature,
        );
        const cached = this._graphWindowSampleCache.get(cacheKey);
        if (cached) {
            return cached;
        }

        const rowZ = new Float32Array(rowCount);
        const yValues = new Float32Array(rowCount * this.binCount);
        const colorValues = new Float32Array(rowCount * this.binCount * 3);
        const peakYValues = new Float32Array(rowCount);
        const peakBinIndices = new Int32Array(rowCount);
        const spectrogramFrequencyNorms = new Float32Array(rowCount * this.binCount);
        const spectrogramIntensity = new Float32Array(rowCount * this.binCount);
        let minZ = Infinity;
        let maxZ = -Infinity;

        for (let frameIndex = frameWindow.start; frameIndex < frameWindow.endExclusive; frameIndex++) {
            const displayRow = frameWindow.endExclusive - 1 - frameIndex;
            const z = this._getWorldZForSourceFrame(frameIndex, alignedFrameWindow);
            rowZ[displayRow] = z;
            minZ = Math.min(minZ, z);
            maxZ = Math.max(maxZ, z);

            const frameYValues = profileCache.yValuesByFrame[frameIndex];
            const frameSpectrogramFrequencyNorms = profileCache.spectrogramFrequencyNormsByFrame[frameIndex];
            const frameSpectrogramIntensity = profileCache.spectrogramIntensityByFrame[frameIndex];
            peakYValues[displayRow] = profileCache.peakYValues[frameIndex] ?? 0;
            peakBinIndices[displayRow] = profileCache.peakBinIndices[frameIndex] ?? 0;
            spectrogramFrequencyNorms.set(frameSpectrogramFrequencyNorms, displayRow * this.binCount);
            spectrogramIntensity.set(frameSpectrogramIntensity, displayRow * this.binCount);

            for (let bin = 0; bin < this.binCount; bin++) {
                const y = frameYValues[bin] ?? 0;
                const x = profileCache.xPositionsByBin[bin] ?? this._getWorldXForBin(bin);
                const vertexOffset = (displayRow * this.binCount + bin);
                const colorOffset = vertexOffset * 3;
                const sampledColor = this._sampleVertexColor(axisColors, timeWindows, planeSelections, x, y, z, width, height, depth);

                yValues[vertexOffset] = y;
                colorValues[colorOffset + 0] = sampledColor.r;
                colorValues[colorOffset + 1] = sampledColor.g;
                colorValues[colorOffset + 2] = sampledColor.b;
            }
        }

        const samples = {
            rowCount,
            rowZ,
            yValues,
            colorValues,
            peakYValues,
            peakBinIndices,
            spectrogramFrequencyNorms,
            spectrogramIntensity,
            minZ: Number.isFinite(minZ) ? minZ : 0,
            maxZ: Number.isFinite(maxZ) ? maxZ : 0,
        };

        this._graphWindowSampleCache.set(cacheKey, samples);
        if (this._graphWindowSampleCache.size > 6) {
            const oldestKey = this._graphWindowSampleCache.keys().next().value;
            if (oldestKey) this._graphWindowSampleCache.delete(oldestKey);
        }

        return samples;
    }

    _rebuild2DGraphs(width, height, depth) {
        this._dispose2DGraphs();

        const alignedFloor = this._createFloorProjectionObjects(this.timeDepth, depth, 11, 10);
        this.floorGraphMesh = alignedFloor.mesh;
        this.floorGraphBackground = alignedFloor.background;

        const alignedWall = this._createWallProjectionObjects(this.timeDepth, depth, height, 13, 14, 13, 12);
        this.wallGraphFill = alignedWall.fill;
        this.wallGraphLine = alignedWall.line;
        this.wallGraphSpectrogram = alignedWall.spectrogram;
        this.wallGraphBackground = alignedWall.background;

        this._extendedGraphLayouts = {
            xz: { rowCount: 0, depth: 0 },
            yz: { rowCount: 0, depth: 0 },
        };
    }

    _getWallGraphRowPeak(row, targetColor) {
        const rowOffset = row * this.binCount;
        let peakY = 0;
        let peakColorOffset = -1;

        for (let bin = 0; bin < this.binCount; bin++) {
            const vertexIndex = rowOffset + bin;
            const colorOffset = vertexIndex * 3;
            const y = this._positions[colorOffset + 1] ?? 0;
            if (y >= peakY) {
                peakY = y;
                peakColorOffset = colorOffset;
            }
        }

        if (peakColorOffset >= 0) {
            targetColor.setRGB(
                this._colors[peakColorOffset + 0] ?? DEFAULT_SURFACE_COLOR.r,
                this._colors[peakColorOffset + 1] ?? DEFAULT_SURFACE_COLOR.g,
                this._colors[peakColorOffset + 2] ?? DEFAULT_SURFACE_COLOR.b,
            );
        } else {
            targetColor.copy(DEFAULT_SURFACE_COLOR);
        }

        return peakY;
    }

    _getProjectionSurfaceOffsets(axisKey, surface, offset, width, height, layerIndex = 0) {
        const gap = Math.max(0.02, offset);
        const layerGap = layerIndex * Math.max(0.08, gap * 0.85 + 0.08);
        if (axisKey === 'y') {
            const boxMin = 0;
            const boxMax = height;
            return surface === 'Front'
                ? { graph: boxMax + gap + layerGap, background: boxMax + gap * 1.35 + layerGap }
                : { graph: boxMin - gap - layerGap, background: boxMin - gap * 1.35 - layerGap };
        }

        const boxMin = -width * 0.5;
        const boxMax = width * 0.5;
        return surface === 'Front'
            ? { graph: boxMax + gap + layerGap, background: boxMax + gap * 1.35 + layerGap }
            : { graph: boxMin - gap - layerGap, background: boxMin - gap * 1.35 - layerGap };
    }

    _sampleHeatColor(axisConfig, normalizedValue, baseColor, strength, targetColor) {
        const heatColor = this._axisColorScratch;
        this._sampleAxisIntervalColor(axisConfig, normalizedValue, heatColor);
        targetColor.copy(baseColor).lerp(heatColor, THREE.MathUtils.clamp(strength, 0, 1));
        return targetColor;
    }

    _sampleWallSpectrogramCell(row, amplitudeNorm, width, height, axisConfig, backgroundColor, heatStrength, targetColor) {
        const rowOffset = row * this.binCount;
        let bestDistance = Infinity;
        let bestFrequencyNorm = 0;

        for (let bin = 0; bin < this.binCount; bin++) {
            const vertexIndex = rowOffset + bin;
            const offset = vertexIndex * 3;
            const y = this._positions[offset + 1] ?? 0;
            const yNorm = height > 0 ? (y / height) : 0;
            const distance = Math.abs(yNorm - amplitudeNorm);
            if (distance < bestDistance) {
                bestDistance = distance;
                const x = this._positions[offset + 0] ?? 0;
                bestFrequencyNorm = width > 0 ? ((x + width * 0.5) / width) : 0;
            }
        }

        const closeness = THREE.MathUtils.clamp(1 - (bestDistance * Math.max(4, this.binCount * 0.55)), 0, 1);
        return this._sampleHeatColor(axisConfig, bestFrequencyNorm, backgroundColor, closeness * heatStrength, targetColor);
    }

    _getWallGraphRowPeakFromSamples(samples, row, targetColor) {
        const cachedPeakY = samples.peakYValues?.[row];
        const cachedPeakBinIndex = samples.peakBinIndices?.[row];
        if (Number.isFinite(cachedPeakY) && Number.isFinite(cachedPeakBinIndex)) {
            const peakColorOffset = ((row * this.binCount) + cachedPeakBinIndex) * 3;
            targetColor.setRGB(
                samples.colorValues[peakColorOffset + 0] ?? DEFAULT_SURFACE_COLOR.r,
                samples.colorValues[peakColorOffset + 1] ?? DEFAULT_SURFACE_COLOR.g,
                samples.colorValues[peakColorOffset + 2] ?? DEFAULT_SURFACE_COLOR.b,
            );
            return cachedPeakY;
        }

        const rowOffset = row * this.binCount;
        let peakY = 0;
        let peakColorOffset = -1;

        for (let bin = 0; bin < this.binCount; bin++) {
            const vertexIndex = rowOffset + bin;
            const y = samples.yValues[vertexIndex] ?? 0;
            if (y >= peakY) {
                peakY = y;
                peakColorOffset = vertexIndex * 3;
            }
        }

        if (peakColorOffset >= 0) {
            targetColor.setRGB(
                samples.colorValues[peakColorOffset + 0] ?? DEFAULT_SURFACE_COLOR.r,
                samples.colorValues[peakColorOffset + 1] ?? DEFAULT_SURFACE_COLOR.g,
                samples.colorValues[peakColorOffset + 2] ?? DEFAULT_SURFACE_COLOR.b,
            );
        } else {
            targetColor.copy(DEFAULT_SURFACE_COLOR);
        }

        return peakY;
    }

    _sampleWallSpectrogramFromSamples(samples, row, amplitudeNorm, width, height, axisConfig, backgroundColor, heatStrength, targetColor) {
        const cachedSpectrogramFrequencyNorms = samples.spectrogramFrequencyNorms;
        const cachedSpectrogramIntensity = samples.spectrogramIntensity;
        if (cachedSpectrogramFrequencyNorms && cachedSpectrogramIntensity) {
            const ampIndex = this.binCount > 1
                ? Math.round(THREE.MathUtils.clamp(amplitudeNorm, 0, 1) * (this.binCount - 1))
                : 0;
            const lookupIndex = row * this.binCount + ampIndex;
            return this._sampleHeatColor(
                axisConfig,
                cachedSpectrogramFrequencyNorms[lookupIndex] ?? 0,
                backgroundColor,
                (cachedSpectrogramIntensity[lookupIndex] ?? 0) * heatStrength,
                targetColor,
            );
        }

        const rowOffset = row * this.binCount;
        let bestDistance = Infinity;
        let bestFrequencyNorm = 0;

        for (let bin = 0; bin < this.binCount; bin++) {
            const vertexIndex = rowOffset + bin;
            const y = samples.yValues[vertexIndex] ?? 0;
            const yNorm = height > 0 ? (y / height) : 0;
            const distance = Math.abs(yNorm - amplitudeNorm);
            if (distance < bestDistance) {
                bestDistance = distance;
                const x = this._getWorldXForBin(bin);
                bestFrequencyNorm = width > 0 ? ((x + width * 0.5) / width) : 0;
            }
        }

        const closeness = THREE.MathUtils.clamp(1 - (bestDistance * Math.max(4, this.binCount * 0.55)), 0, 1);
        return this._sampleHeatColor(axisConfig, bestFrequencyNorm, backgroundColor, closeness * heatStrength, targetColor);
    }

    _ensureExtended2DGraphObjects(graphConfig, width, height, alignedFrameWindow) {
        if (!this.hasFrameData()) {
            if (this.extendedFloorGraphMesh) this.extendedFloorGraphMesh.visible = false;
            if (this.extendedFloorGraphBackground) this.extendedFloorGraphBackground.visible = false;
            if (this.extendedWallGraphFill) this.extendedWallGraphFill.visible = false;
            if (this.extendedWallGraphLine) this.extendedWallGraphLine.visible = false;
            if (this.extendedWallGraphSpectrogram) this.extendedWallGraphSpectrogram.visible = false;
            if (this.extendedWallGraphBackground) this.extendedWallGraphBackground.visible = false;
            return null;
        }

        const xzWindow = this._getExtendedFrameWindow(graphConfig.xz);
        const yzWindow = this._getExtendedFrameWindow(graphConfig.yz);
        const xzRowCount = Math.max(0, xzWindow.endExclusive - xzWindow.start);
        const yzRowCount = Math.max(0, yzWindow.endExclusive - yzWindow.start);
        const step = this._getTimeStepWorld();
        const xzDepth = Math.max(SCALE_EPSILON, Math.max(0, xzRowCount - 1) * step);
        const yzDepth = Math.max(SCALE_EPSILON, Math.max(0, yzRowCount - 1) * step);

        if (xzRowCount > 0 && (
            !this.extendedFloorGraphMesh ||
            this._extendedGraphLayouts.xz.rowCount !== xzRowCount ||
            Math.abs(this._extendedGraphLayouts.xz.depth - xzDepth) > SCALE_EPSILON
        )) {
            if (this.extendedFloorGraphMesh) this._disposeObject3D(this.extendedFloorGraphMesh);
            if (this.extendedFloorGraphBackground) this._disposeObject3D(this.extendedFloorGraphBackground);
            const layer = this._createFloorProjectionObjects(xzRowCount, xzDepth, 9, 8);
            this.extendedFloorGraphMesh = layer.mesh;
            this.extendedFloorGraphBackground = layer.background;
            this._extendedGraphLayouts.xz = { rowCount: xzRowCount, depth: xzDepth };
        }

        if (yzRowCount > 0 && (
            !this.extendedWallGraphFill ||
            this._extendedGraphLayouts.yz.rowCount !== yzRowCount ||
            Math.abs(this._extendedGraphLayouts.yz.depth - yzDepth) > SCALE_EPSILON
        )) {
            if (this.extendedWallGraphFill) this._disposeObject3D(this.extendedWallGraphFill);
            if (this.extendedWallGraphLine) this._disposeObject3D(this.extendedWallGraphLine);
            if (this.extendedWallGraphSpectrogram) this._disposeObject3D(this.extendedWallGraphSpectrogram);
            if (this.extendedWallGraphBackground) this._disposeObject3D(this.extendedWallGraphBackground);
            const layer = this._createWallProjectionObjects(yzRowCount, yzDepth, height, 9, 10, 9, 8);
            this.extendedWallGraphFill = layer.fill;
            this.extendedWallGraphLine = layer.line;
            this.extendedWallGraphSpectrogram = layer.spectrogram;
            this.extendedWallGraphBackground = layer.background;
            this._extendedGraphLayouts.yz = { rowCount: yzRowCount, depth: yzDepth };
        }

        return { xzWindow, yzWindow };
    }

    _sync2DGraphGeometry() {
        if (!this.floorGraphMesh || !this.wallGraphFill || !this.wallGraphLine || !this.wallGraphSpectrogram || !this.floorGraphBackground || !this.wallGraphBackground) {
            this._setProjectionHelperStatus({
                summary: '2D Helper: Idle',
                detail: 'Projection geometry is not ready yet.',
                activeSource: 'idle',
            });
            return;
        }

        const graphConfig = this._getCompiled2DGraphConfig();
        const axisColors = this._getCompiledAxisColorConfig();
        const timeWindows = this._getCompiledTimeWindowConfig();
        const planeSelections = this._getCompiledPlaneSelectionConfig();
        const helperProfile = this._getTerrainEnvelopeHelperProfile();
        const terrainEnvelopeHelper = graphConfig.yz.graphType === 'Plot' && helperProfile.plotActive
            ? helperProfile.helper
            : null;
        const terrainSpectrogramHelper = graphConfig.yz.graphType === 'Spectrogram' && helperProfile.spectrogramActive
            ? helperProfile.helper
            : null;
        const width = this._getFrequencyWorldLength();
        const height = this._getAmplitudeWorldLength();
        const depth = this._getTimeWorldLength();
        const alignedFrameWindow = this._getAlignedFrameWindow();
        const extendedWindows = this._ensureExtended2DGraphObjects(graphConfig, width, height, alignedFrameWindow);

        const showAlignedXz = graphConfig.xz.enabled && graphConfig.xz.showGraphsAs !== 'Extended 2D Graphs';
        const showExtendedXz = graphConfig.xz.enabled && graphConfig.xz.showGraphsAs !== '3D Aligned 2D Graphs' && !!extendedWindows;
        const showAlignedYz = graphConfig.yz.enabled && graphConfig.yz.showGraphsAs !== 'Extended 2D Graphs';
        const showExtendedYz = graphConfig.yz.enabled && graphConfig.yz.showGraphsAs !== '3D Aligned 2D Graphs' && !!extendedWindows;

        const floorPosition = this.floorGraphMesh.geometry.attributes.position;
        const floorColor = this.floorGraphMesh.geometry.attributes.color;
        const floorSurfaceOffsets = this._getProjectionSurfaceOffsets('y', graphConfig.xz.surface, graphConfig.xz.offset, width, height, 0);
        const floorGraphY = floorSurfaceOffsets.graph;
        const floorBackgroundY = floorSurfaceOffsets.background;
        const floorResultColor = new THREE.Color();
        const floorBackgroundColor = graphConfig.xz.backgroundColor.clone();

        this.floorGraphMesh.visible = showAlignedXz;
        this.floorGraphBackground.visible = showAlignedXz && graphConfig.xz.backgroundEnabled;
        this.floorGraphMesh.material.opacity = graphConfig.xz.graphOpacity;
        this.floorGraphMesh.material.transparent = graphConfig.xz.graphOpacity < 1;
        this.floorGraphBackground.material.color.copy(graphConfig.xz.backgroundColor);
        this.floorGraphBackground.material.opacity = graphConfig.xz.backgroundOpacity;
        this.floorGraphBackground.material.transparent = graphConfig.xz.backgroundOpacity < 1;
        this.floorGraphBackground.position.set(0, floorBackgroundY, -depth * 0.5);

        for (let index = 0; index < this._positions.length; index += 3) {
            const y = this._positions[index + 1] ?? 0;
            const yNorm = height > 0 ? (y / height) : 0;
            floorPosition.array[index + 0] = this._positions[index + 0];
            floorPosition.array[index + 1] = floorGraphY;
            floorPosition.array[index + 2] = this._positions[index + 2];

            if (graphConfig.xz.graphType === 'Spectrogram') {
                const intensity = Math.pow(THREE.MathUtils.clamp(yNorm, 0, 1), 0.65) * graphConfig.xz.heatStrength;
                this._sampleHeatColor(axisColors.y, yNorm, floorBackgroundColor, intensity, floorResultColor);
                floorColor.array[index + 0] = floorResultColor.r;
                floorColor.array[index + 1] = floorResultColor.g;
                floorColor.array[index + 2] = floorResultColor.b;
            } else {
                floorColor.array[index + 0] = this._colors[index + 0];
                floorColor.array[index + 1] = this._colors[index + 1];
                floorColor.array[index + 2] = this._colors[index + 2];
            }
        }
        floorPosition.needsUpdate = true;
        floorColor.needsUpdate = true;

        let extendedXzSamples = null;
        if (showExtendedXz && extendedWindows?.xzWindow) {
            extendedXzSamples = this._buildGraphWindowSamples(
                extendedWindows.xzWindow,
                alignedFrameWindow,
                axisColors,
                timeWindows,
                planeSelections,
                width,
                height,
                depth,
            );
        }

        if (this.extendedFloorGraphMesh && this.extendedFloorGraphBackground) {
            const floorLayerIndex = showAlignedXz ? 1 : 0;
            const extendedFloorOffsets = this._getProjectionSurfaceOffsets('y', graphConfig.xz.surface, graphConfig.xz.offset, width, height, floorLayerIndex);
            this.extendedFloorGraphMesh.visible = !!extendedXzSamples;
            this.extendedFloorGraphBackground.visible = !!extendedXzSamples && graphConfig.xz.backgroundEnabled;
            this.extendedFloorGraphMesh.material.opacity = graphConfig.xz.graphOpacity;
            this.extendedFloorGraphMesh.material.transparent = graphConfig.xz.graphOpacity < 1;
            this.extendedFloorGraphBackground.material.color.copy(graphConfig.xz.backgroundColor);
            this.extendedFloorGraphBackground.material.opacity = graphConfig.xz.backgroundOpacity;
            this.extendedFloorGraphBackground.material.transparent = graphConfig.xz.backgroundOpacity < 1;

            if (extendedXzSamples) {
                const position = this.extendedFloorGraphMesh.geometry.attributes.position;
                const color = this.extendedFloorGraphMesh.geometry.attributes.color;
                const centerZ = (extendedXzSamples.minZ + extendedXzSamples.maxZ) * 0.5;

                this.extendedFloorGraphBackground.position.set(0, extendedFloorOffsets.background, centerZ);

                for (let row = 0; row < extendedXzSamples.rowCount; row++) {
                    const z = extendedXzSamples.rowZ[row];
                    for (let bin = 0; bin < this.binCount; bin++) {
                        const vertexIndex = row * this.binCount + bin;
                        const colorOffset = vertexIndex * 3;
                        const x = this._getWorldXForBin(bin);
                        const y = extendedXzSamples.yValues[vertexIndex] ?? 0;
                        const yNorm = height > 0 ? (y / height) : 0;

                        position.array[colorOffset + 0] = x;
                        position.array[colorOffset + 1] = extendedFloorOffsets.graph;
                        position.array[colorOffset + 2] = z;

                        if (graphConfig.xz.graphType === 'Spectrogram') {
                            const intensity = Math.pow(THREE.MathUtils.clamp(yNorm, 0, 1), 0.65) * graphConfig.xz.heatStrength;
                            this._sampleHeatColor(axisColors.y, yNorm, floorBackgroundColor, intensity, floorResultColor);
                            color.array[colorOffset + 0] = floorResultColor.r;
                            color.array[colorOffset + 1] = floorResultColor.g;
                            color.array[colorOffset + 2] = floorResultColor.b;
                        } else {
                            color.array[colorOffset + 0] = extendedXzSamples.colorValues[colorOffset + 0] ?? 0;
                            color.array[colorOffset + 1] = extendedXzSamples.colorValues[colorOffset + 1] ?? 0;
                            color.array[colorOffset + 2] = extendedXzSamples.colorValues[colorOffset + 2] ?? 0;
                        }
                    }
                }

                position.needsUpdate = true;
                color.needsUpdate = true;
            }
        }

        const wallFillPosition = this.wallGraphFill.geometry.attributes.position;
        const wallFillColor = this.wallGraphFill.geometry.attributes.color;
        const wallLinePosition = this.wallGraphLine.geometry.attributes.position;
        const wallLineColor = this.wallGraphLine.geometry.attributes.color;
        const wallSpectrogramColor = this.wallGraphSpectrogram.geometry.attributes.color;
        const wallSurfaceOffsets = this._getProjectionSurfaceOffsets('x', graphConfig.yz.surface, graphConfig.yz.offset, width, height, 0);
        const graphWallX = wallSurfaceOffsets.graph;
        const wallBackgroundX = wallSurfaceOffsets.background;
        const rowColor = new THREE.Color();
        const rowShadowColor = new THREE.Color();
        const wallBackgroundColor = graphConfig.yz.backgroundColor.clone();

        this.wallGraphFill.visible = showAlignedYz && graphConfig.yz.graphType === 'Plot';
        this.wallGraphLine.visible = showAlignedYz && graphConfig.yz.graphType === 'Plot';
        this.wallGraphSpectrogram.visible = showAlignedYz && graphConfig.yz.graphType === 'Spectrogram';
        this.wallGraphBackground.visible = showAlignedYz && graphConfig.yz.backgroundEnabled;
        this.wallGraphFill.material.opacity = graphConfig.yz.graphOpacity * 0.38;
        this.wallGraphFill.material.transparent = this.wallGraphFill.material.opacity < 1;
        this.wallGraphLine.material.opacity = graphConfig.yz.graphOpacity;
        this.wallGraphLine.material.transparent = graphConfig.yz.graphOpacity < 1;
        this.wallGraphSpectrogram.material.opacity = graphConfig.yz.graphOpacity;
        this.wallGraphSpectrogram.material.transparent = graphConfig.yz.graphOpacity < 1;
        this.wallGraphBackground.material.color.copy(graphConfig.yz.backgroundColor);
        this.wallGraphBackground.material.opacity = graphConfig.yz.backgroundOpacity;
        this.wallGraphBackground.material.transparent = graphConfig.yz.backgroundOpacity < 1;
        this.wallGraphBackground.position.set(wallBackgroundX, height * 0.5, -depth * 0.5);
        this.wallGraphSpectrogram.position.set(graphWallX, height * 0.5, -depth * 0.5);

        for (let row = 0; row < this.timeDepth; row++) {
            const z = this._positions[(row * this.binCount) * 3 + 2] ?? this._getWorldZForRow(row);
            const alignedFrameIndex = alignedFrameWindow.endExclusive - 1 - row;
            const helperPeak = this._getHelperPeakDataForFrame(terrainEnvelopeHelper, alignedFrameIndex, rowColor, this._colors, row);
            const envelopeY = helperPeak ? helperPeak.peakY : this._getWallGraphRowPeak(row, rowColor);
            rowShadowColor.copy(rowColor).multiplyScalar(0.18);

            const fillBaseIndex = row * 2;
            wallFillPosition.array[(fillBaseIndex + 0) * 3 + 0] = graphWallX;
            wallFillPosition.array[(fillBaseIndex + 0) * 3 + 1] = 0;
            wallFillPosition.array[(fillBaseIndex + 0) * 3 + 2] = z;
            wallFillPosition.array[(fillBaseIndex + 1) * 3 + 0] = graphWallX;
            wallFillPosition.array[(fillBaseIndex + 1) * 3 + 1] = envelopeY;
            wallFillPosition.array[(fillBaseIndex + 1) * 3 + 2] = z;

            wallFillColor.array[(fillBaseIndex + 0) * 3 + 0] = rowShadowColor.r;
            wallFillColor.array[(fillBaseIndex + 0) * 3 + 1] = rowShadowColor.g;
            wallFillColor.array[(fillBaseIndex + 0) * 3 + 2] = rowShadowColor.b;
            wallFillColor.array[(fillBaseIndex + 1) * 3 + 0] = rowColor.r;
            wallFillColor.array[(fillBaseIndex + 1) * 3 + 1] = rowColor.g;
            wallFillColor.array[(fillBaseIndex + 1) * 3 + 2] = rowColor.b;

            wallLinePosition.array[row * 3 + 0] = graphWallX;
            wallLinePosition.array[row * 3 + 1] = envelopeY;
            wallLinePosition.array[row * 3 + 2] = z;
            wallLineColor.array[row * 3 + 0] = rowColor.r;
            wallLineColor.array[row * 3 + 1] = rowColor.g;
            wallLineColor.array[row * 3 + 2] = rowColor.b;
        }

        const wallSpectrogramVertexCount = this.timeDepth * this.binCount;
        for (let vertexIndex = 0; vertexIndex < wallSpectrogramVertexCount; vertexIndex++) {
            const row = Math.floor(vertexIndex / this.binCount);
            const ampIndex = vertexIndex % this.binCount;
            const amplitudeNorm = this.binCount > 1 ? (ampIndex / (this.binCount - 1)) : 0;
            const alignedFrameIndex = alignedFrameWindow.endExclusive - 1 - row;
            const color = terrainSpectrogramHelper
                ? this._sampleWallSpectrogramFromHelper(
                    terrainSpectrogramHelper,
                    alignedFrameIndex,
                    ampIndex,
                    width,
                    axisColors.x,
                    wallBackgroundColor,
                    graphConfig.yz.heatStrength,
                    rowColor,
                )
                : this._sampleWallSpectrogramCell(
                    row,
                    amplitudeNorm,
                    width,
                    height,
                    axisColors.x,
                    wallBackgroundColor,
                    graphConfig.yz.heatStrength,
                    rowColor,
                );

            wallSpectrogramColor.array[vertexIndex * 3 + 0] = color.r;
            wallSpectrogramColor.array[vertexIndex * 3 + 1] = color.g;
            wallSpectrogramColor.array[vertexIndex * 3 + 2] = color.b;
        }

        wallFillPosition.needsUpdate = true;
        wallFillColor.needsUpdate = true;
        wallLinePosition.needsUpdate = true;
        wallLineColor.needsUpdate = true;
        wallSpectrogramColor.needsUpdate = true;

        let extendedYzSamples = null;
        let extendedYzEnvelopeSamples = null;
        if (showExtendedYz && extendedWindows?.yzWindow && graphConfig.yz.graphType === 'Plot' && terrainEnvelopeHelper) {
            extendedYzEnvelopeSamples = this._buildGraphWindowEnvelopeSamples(
                extendedWindows.yzWindow,
                alignedFrameWindow,
                terrainEnvelopeHelper,
                axisColors,
                timeWindows,
                planeSelections,
                width,
                height,
                depth,
            );
        } else if (showExtendedYz && extendedWindows?.yzWindow) {
            extendedYzSamples = this._buildGraphWindowSamples(
                extendedWindows.yzWindow,
                alignedFrameWindow,
                axisColors,
                timeWindows,
                planeSelections,
                width,
                height,
                depth,
            );
        }

        const hasExtendedYzPlotData = !!extendedYzEnvelopeSamples || !!extendedYzSamples;
        const hasExtendedYzSpectrogramHelper = !!(showExtendedYz && extendedWindows?.yzWindow && graphConfig.yz.graphType === 'Spectrogram' && terrainSpectrogramHelper);

        if (this.extendedWallGraphFill && this.extendedWallGraphLine && this.extendedWallGraphSpectrogram && this.extendedWallGraphBackground) {
            const wallLayerIndex = showAlignedYz ? 1 : 0;
            const extendedWallOffsets = this._getProjectionSurfaceOffsets('x', graphConfig.yz.surface, graphConfig.yz.offset, width, height, wallLayerIndex);

            this.extendedWallGraphFill.visible = hasExtendedYzPlotData && graphConfig.yz.graphType === 'Plot';
            this.extendedWallGraphLine.visible = hasExtendedYzPlotData && graphConfig.yz.graphType === 'Plot';
            this.extendedWallGraphSpectrogram.visible = (!!extendedYzSamples || hasExtendedYzSpectrogramHelper) && graphConfig.yz.graphType === 'Spectrogram';
            this.extendedWallGraphBackground.visible = (!!extendedYzEnvelopeSamples || !!extendedYzSamples || hasExtendedYzSpectrogramHelper) && graphConfig.yz.backgroundEnabled;
            this.extendedWallGraphFill.material.opacity = graphConfig.yz.graphOpacity * 0.38;
            this.extendedWallGraphFill.material.transparent = this.extendedWallGraphFill.material.opacity < 1;
            this.extendedWallGraphLine.material.opacity = graphConfig.yz.graphOpacity;
            this.extendedWallGraphLine.material.transparent = graphConfig.yz.graphOpacity < 1;
            this.extendedWallGraphSpectrogram.material.opacity = graphConfig.yz.graphOpacity;
            this.extendedWallGraphSpectrogram.material.transparent = graphConfig.yz.graphOpacity < 1;
            this.extendedWallGraphBackground.material.color.copy(graphConfig.yz.backgroundColor);
            this.extendedWallGraphBackground.material.opacity = graphConfig.yz.backgroundOpacity;
            this.extendedWallGraphBackground.material.transparent = graphConfig.yz.backgroundOpacity < 1;

            if (extendedYzEnvelopeSamples) {
                const centerZ = (extendedYzEnvelopeSamples.minZ + extendedYzEnvelopeSamples.maxZ) * 0.5;
                this.extendedWallGraphBackground.position.set(extendedWallOffsets.background, height * 0.5, centerZ);
                this.extendedWallGraphSpectrogram.position.set(extendedWallOffsets.graph, height * 0.5, centerZ);

                const fillPosition = this.extendedWallGraphFill.geometry.attributes.position;
                const fillColor = this.extendedWallGraphFill.geometry.attributes.color;
                const linePosition = this.extendedWallGraphLine.geometry.attributes.position;
                const lineColor = this.extendedWallGraphLine.geometry.attributes.color;

                for (let row = 0; row < extendedYzEnvelopeSamples.rowCount; row++) {
                    const z = extendedYzEnvelopeSamples.rowZ[row];
                    const envelopeY = extendedYzEnvelopeSamples.peakYValues[row] ?? 0;
                    rowColor.setRGB(
                        extendedYzEnvelopeSamples.rowColors[(row * 3) + 0] ?? DEFAULT_SURFACE_COLOR.r,
                        extendedYzEnvelopeSamples.rowColors[(row * 3) + 1] ?? DEFAULT_SURFACE_COLOR.g,
                        extendedYzEnvelopeSamples.rowColors[(row * 3) + 2] ?? DEFAULT_SURFACE_COLOR.b,
                    );
                    rowShadowColor.copy(rowColor).multiplyScalar(0.18);

                    const fillBaseIndex = row * 2;
                    fillPosition.array[(fillBaseIndex + 0) * 3 + 0] = extendedWallOffsets.graph;
                    fillPosition.array[(fillBaseIndex + 0) * 3 + 1] = 0;
                    fillPosition.array[(fillBaseIndex + 0) * 3 + 2] = z;
                    fillPosition.array[(fillBaseIndex + 1) * 3 + 0] = extendedWallOffsets.graph;
                    fillPosition.array[(fillBaseIndex + 1) * 3 + 1] = envelopeY;
                    fillPosition.array[(fillBaseIndex + 1) * 3 + 2] = z;

                    fillColor.array[(fillBaseIndex + 0) * 3 + 0] = rowShadowColor.r;
                    fillColor.array[(fillBaseIndex + 0) * 3 + 1] = rowShadowColor.g;
                    fillColor.array[(fillBaseIndex + 0) * 3 + 2] = rowShadowColor.b;
                    fillColor.array[(fillBaseIndex + 1) * 3 + 0] = rowColor.r;
                    fillColor.array[(fillBaseIndex + 1) * 3 + 1] = rowColor.g;
                    fillColor.array[(fillBaseIndex + 1) * 3 + 2] = rowColor.b;

                    linePosition.array[row * 3 + 0] = extendedWallOffsets.graph;
                    linePosition.array[row * 3 + 1] = envelopeY;
                    linePosition.array[row * 3 + 2] = z;
                    lineColor.array[row * 3 + 0] = rowColor.r;
                    lineColor.array[row * 3 + 1] = rowColor.g;
                    lineColor.array[row * 3 + 2] = rowColor.b;
                }

                fillPosition.needsUpdate = true;
                fillColor.needsUpdate = true;
                linePosition.needsUpdate = true;
                lineColor.needsUpdate = true;
            } else if (hasExtendedYzSpectrogramHelper) {
                const zLatest = this._getWorldZForSourceFrame(extendedWindows.yzWindow.endExclusive - 1, alignedFrameWindow);
                const zOldest = this._getWorldZForSourceFrame(extendedWindows.yzWindow.start, alignedFrameWindow);
                const centerZ = (zLatest + zOldest) * 0.5;
                this.extendedWallGraphBackground.position.set(extendedWallOffsets.background, height * 0.5, centerZ);
                this.extendedWallGraphSpectrogram.position.set(extendedWallOffsets.graph, height * 0.5, centerZ);

                const spectrogramColor = this.extendedWallGraphSpectrogram.geometry.attributes.color;
                const rowCount = Math.max(0, extendedWindows.yzWindow.endExclusive - extendedWindows.yzWindow.start);

                for (let vertexIndex = 0; vertexIndex < rowCount * this.binCount; vertexIndex++) {
                    const row = Math.floor(vertexIndex / this.binCount);
                    const ampIndex = vertexIndex % this.binCount;
                    const frameIndex = extendedWindows.yzWindow.endExclusive - 1 - row;
                    const color = this._sampleWallSpectrogramFromHelper(
                        terrainSpectrogramHelper,
                        frameIndex,
                        ampIndex,
                        width,
                        axisColors.x,
                        wallBackgroundColor,
                        graphConfig.yz.heatStrength,
                        rowColor,
                    );

                    spectrogramColor.array[vertexIndex * 3 + 0] = color.r;
                    spectrogramColor.array[vertexIndex * 3 + 1] = color.g;
                    spectrogramColor.array[vertexIndex * 3 + 2] = color.b;
                }

                spectrogramColor.needsUpdate = true;
            } else if (extendedYzSamples) {
                const centerZ = (extendedYzSamples.minZ + extendedYzSamples.maxZ) * 0.5;
                this.extendedWallGraphBackground.position.set(extendedWallOffsets.background, height * 0.5, centerZ);
                this.extendedWallGraphSpectrogram.position.set(extendedWallOffsets.graph, height * 0.5, centerZ);

                const fillPosition = this.extendedWallGraphFill.geometry.attributes.position;
                const fillColor = this.extendedWallGraphFill.geometry.attributes.color;
                const linePosition = this.extendedWallGraphLine.geometry.attributes.position;
                const lineColor = this.extendedWallGraphLine.geometry.attributes.color;
                const spectrogramColor = this.extendedWallGraphSpectrogram.geometry.attributes.color;

                for (let row = 0; row < extendedYzSamples.rowCount; row++) {
                    const z = extendedYzSamples.rowZ[row];
                    const envelopeY = this._getWallGraphRowPeakFromSamples(extendedYzSamples, row, rowColor);
                    rowShadowColor.copy(rowColor).multiplyScalar(0.18);

                    const fillBaseIndex = row * 2;
                    fillPosition.array[(fillBaseIndex + 0) * 3 + 0] = extendedWallOffsets.graph;
                    fillPosition.array[(fillBaseIndex + 0) * 3 + 1] = 0;
                    fillPosition.array[(fillBaseIndex + 0) * 3 + 2] = z;
                    fillPosition.array[(fillBaseIndex + 1) * 3 + 0] = extendedWallOffsets.graph;
                    fillPosition.array[(fillBaseIndex + 1) * 3 + 1] = envelopeY;
                    fillPosition.array[(fillBaseIndex + 1) * 3 + 2] = z;

                    fillColor.array[(fillBaseIndex + 0) * 3 + 0] = rowShadowColor.r;
                    fillColor.array[(fillBaseIndex + 0) * 3 + 1] = rowShadowColor.g;
                    fillColor.array[(fillBaseIndex + 0) * 3 + 2] = rowShadowColor.b;
                    fillColor.array[(fillBaseIndex + 1) * 3 + 0] = rowColor.r;
                    fillColor.array[(fillBaseIndex + 1) * 3 + 1] = rowColor.g;
                    fillColor.array[(fillBaseIndex + 1) * 3 + 2] = rowColor.b;

                    linePosition.array[row * 3 + 0] = extendedWallOffsets.graph;
                    linePosition.array[row * 3 + 1] = envelopeY;
                    linePosition.array[row * 3 + 2] = z;
                    lineColor.array[row * 3 + 0] = rowColor.r;
                    lineColor.array[row * 3 + 1] = rowColor.g;
                    lineColor.array[row * 3 + 2] = rowColor.b;
                }

                const spectrogramVertexCount = extendedYzSamples.rowCount * this.binCount;
                for (let vertexIndex = 0; vertexIndex < spectrogramVertexCount; vertexIndex++) {
                    const row = Math.floor(vertexIndex / this.binCount);
                    const ampIndex = vertexIndex % this.binCount;
                    const amplitudeNorm = this.binCount > 1 ? (ampIndex / (this.binCount - 1)) : 0;
                    const color = this._sampleWallSpectrogramFromSamples(
                        extendedYzSamples,
                        row,
                        amplitudeNorm,
                        width,
                        height,
                        axisColors.x,
                        wallBackgroundColor,
                        graphConfig.yz.heatStrength,
                        rowColor,
                    );

                    spectrogramColor.array[vertexIndex * 3 + 0] = color.r;
                    spectrogramColor.array[vertexIndex * 3 + 1] = color.g;
                    spectrogramColor.array[vertexIndex * 3 + 2] = color.b;
                }

                fillPosition.needsUpdate = true;
                fillColor.needsUpdate = true;
                linePosition.needsUpdate = true;
                lineColor.needsUpdate = true;
                spectrogramColor.needsUpdate = true;
            }
        }

        this._setProjectionHelperStatus(this._buildProjectionHelperStatus(graphConfig, helperProfile, {
            plotActive: !!terrainEnvelopeHelper,
            spectrogramActive: !!terrainSpectrogramHelper,
        }));
    }

    _rebuildGeometry() {
        if (this.mesh) {
            this.group.remove(this.mesh);
            this.geometry.dispose();
            this.material.dispose();
            this.mesh = null;
            this.geometry = null;
            this.material = null;
        }

        this._disposeUnselectedWireOverlay();
        this._dispose2DGraphs();

        const width = this._getFrequencyWorldLength();
        const height = this._getAmplitudeWorldLength();
        const depth = this._getTimeWorldLength();

        // We use PlaneGeometry which naturally provides the correct triangulation indices.
        // widthSegments = binCount - 1, heightSegments = timeDepth - 1
        const geometry = new THREE.PlaneGeometry(
            width,
            depth,
            Math.max(1, this.binCount - 1),
            Math.max(1, this.timeDepth - 1)
        );

        // The plane geometry by default is on the XY plane.
        // Rotate it to be on the XZ plane with newer frames at the front:
        geometry.rotateX(Math.PI / 2);

        // PlaneGeometry builds vertices from top-left to bottom-right 
        // across rows and columns. We'll track the vertex count.
        const vertexCount = this.binCount * this.timeDepth;
        const positions = new Float32Array(vertexCount * 3);
        const colors = new Float32Array(vertexCount * 3);

        for (let row = 0; row < this.timeDepth; row++) {
            for (let bin = 0; bin < this.binCount; bin++) {
                const index = row * this.binCount + bin;
                positions[index * 3 + 0] = this._getWorldXForBin(bin);
                positions[index * 3 + 1] = 0;
                positions[index * 3 + 2] = this._getWorldZForRow(row);

                colors[index * 3 + 0] = 0.1;
                colors[index * 3 + 1] = 0.4;
                colors[index * 3 + 2] = 0.8;
            }
        }

        geometry.setAttribute('position', new THREE.BufferAttribute(positions.slice(), 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors.slice(), 3));

        const material = new THREE.MeshStandardMaterial({
            vertexColors: true,
            side: THREE.DoubleSide,
            wireframe: false,
            roughness: 0.6,
            metalness: 0.2
        });

        const mesh = new THREE.Mesh(geometry, material);
        mesh.frustumCulled = false;
        
        // Add minimal lighting to the terrain group to ensure StandardMaterial shows up nicely
        if (!this.group.getObjectByName('terrainAmbLight')) {
            const ambLight = new THREE.AmbientLight(0xffffff, 0.6);
            ambLight.name = 'terrainAmbLight';
            const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
            dirLight.name = 'terrainDirLight';
            dirLight.position.set(0, 100, 50);
            this.group.add(ambLight, dirLight);
        }

        this.group.add(mesh);
        this.mesh = mesh;
        this.geometry = geometry;
        this.material = material;
        this._positions = positions;
        this._colors = colors;
        this._basePositions = positions.slice();
        this._baseColors = colors.slice();

        this._rebuild2DGraphs(width, height, depth);

        this._syncRenderGeometry();
        this._applyMaterialSettings();
    }

    _applyMaterialSettings() {
        if (!this.material) return;
        const s = this.settings || {};
        this.material.opacity = Math.min(1, Math.max(0.05, s.terrainOpacity ?? 0.95));
        this.material.transparent = this.material.opacity < 1;
        this.material.wireframe = !!s.terrainWireframe;
        this.material.needsUpdate = true;
    }

    /** Returns the world-space extents of the terrain mesh for axis construction. */
    getTerrainWorldBounds() {
        const width = this._getFrequencyWorldLength();
        return {
            width,
            halfWidth: width * 0.5,
            height: this._getAmplitudeWorldLength(),
            zDepth: this._getTimeWorldLength(),
        };
    }

    _buildDefaultScaleBounds() {
        return {
            frequencyMin: 0,
            frequencyMax: Math.max(1, this._sourceBinCount - 1),
            amplitudeMin: 0,
            amplitudeMax: 255,
            timeMin: 0,
            timeMax: Math.max(1, this.timeDepth - 1),
        };
    }

    _cloneScaleBounds(bounds) {
        return {
            frequencyMin: bounds.frequencyMin,
            frequencyMax: bounds.frequencyMax,
            amplitudeMin: bounds.amplitudeMin,
            amplitudeMax: bounds.amplitudeMax,
            timeMin: bounds.timeMin,
            timeMax: bounds.timeMax,
        };
    }

    _normalizeScaleBounds(bounds, fallback = this._buildDefaultScaleBounds()) {
        const next = {
            frequencyMin: bounds?.frequencyMin ?? fallback.frequencyMin,
            frequencyMax: bounds?.frequencyMax ?? fallback.frequencyMax,
            amplitudeMin: bounds?.amplitudeMin ?? fallback.amplitudeMin,
            amplitudeMax: bounds?.amplitudeMax ?? fallback.amplitudeMax,
            timeMin: bounds?.timeMin ?? fallback.timeMin,
            timeMax: bounds?.timeMax ?? fallback.timeMax,
        };

        const normalizePair = (minKey, maxKey, fallbackMin, fallbackMax) => {
            const rawMin = Number.isFinite(next[minKey]) ? next[minKey] : fallbackMin;
            const rawMax = Number.isFinite(next[maxKey]) ? next[maxKey] : fallbackMax;
            next[minKey] = Math.min(rawMin, rawMax - SCALE_EPSILON);
            next[maxKey] = Math.max(rawMax, next[minKey] + SCALE_EPSILON);
        };

        normalizePair('frequencyMin', 'frequencyMax', fallback.frequencyMin, fallback.frequencyMax);
        normalizePair('amplitudeMin', 'amplitudeMax', fallback.amplitudeMin, fallback.amplitudeMax);
        normalizePair('timeMin', 'timeMax', fallback.timeMin, fallback.timeMax);

        return next;
    }

    _scaleBoundsEqual(a, b) {
        if (!a || !b) return false;
        return a.frequencyMin === b.frequencyMin
            && a.frequencyMax === b.frequencyMax
            && a.amplitudeMin === b.amplitudeMin
            && a.amplitudeMax === b.amplitudeMax
            && a.timeMin === b.timeMin
            && a.timeMax === b.timeMax;
    }

    _getRange(min, max) {
        return Math.max(SCALE_EPSILON, max - min);
    }

    _updateAutoScaleBounds() {
        const nextBounds = this._buildDefaultScaleBounds();
        nextBounds.timeMin = 0;
        nextBounds.timeMax = Math.max(1, this.timeDepth - 1);

        if (this.hasFrameData()) {
            let maxAmplitude = 0;
            let highestNonZeroBin = 0;
            const frequencyPaddingRatio = Math.max(0, (this.settings?.terrainAutoPadFreqPercent ?? 2) / 100);
            const amplitudePaddingRatio = Math.max(0, (this.settings?.terrainAutoPadAmpPercent ?? 5) / 100);

            for (const row of this._frameRows) {
                if (!row) continue;
                for (let bin = 0; bin < row.length; bin++) {
                    const value = row[bin] ?? 0;
                    if (value > maxAmplitude) maxAmplitude = value;
                    if (value > 0) highestNonZeroBin = Math.max(highestNonZeroBin, bin);
                }
            }

            this._sourceBinCount = this._frameRows[0]?.length ?? this._sourceBinCount;

            const rawFrequencyMax = Math.max(1, highestNonZeroBin || (this._sourceBinCount - 1));
            const frequencyPadding = rawFrequencyMax * frequencyPaddingRatio;
            nextBounds.frequencyMin = 0;
            nextBounds.frequencyMax = rawFrequencyMax + frequencyPadding;

            nextBounds.amplitudeMin = 0;
            nextBounds.amplitudeMax = maxAmplitude > 0 ? (maxAmplitude * (1 + amplitudePaddingRatio)) : 1;
        } else {
            this._sourceBinCount = Math.max(1, this._sourceBinCount || this.binCount);
            nextBounds.frequencyMin = 0;
            nextBounds.frequencyMax = Math.max(1, this._sourceBinCount - 1);
            nextBounds.amplitudeMin = 0;
            nextBounds.amplitudeMax = 255;
        }

        this._autoScaleBounds = this._normalizeScaleBounds(nextBounds, nextBounds);
        if (!this._activeScaleBounds) {
            this._activeScaleBounds = this._cloneScaleBounds(this._autoScaleBounds);
        }
    }

    _getBaseFrequencyWidth() {
        return DEFAULT_TERRAIN_WIDTH;
    }

    _getBaseAmplitudeHeight() {
        return Math.max(1, this.settings?.terrainAmplitudeScale ?? 45);
    }

    _getBaseTimeDepth() {
        return Math.max(1, this.timeDepth - 1) * DEFAULT_TERRAIN_TIME_SPACING;
    }

    _getFrequencyWorldLength() {
        return this._getBaseFrequencyWidth()
            * (this._getRange(this._activeScaleBounds.frequencyMin, this._activeScaleBounds.frequencyMax)
            / this._getRange(this._autoScaleBounds.frequencyMin, this._autoScaleBounds.frequencyMax));
    }

    _getAmplitudeWorldLength() {
        return this._getBaseAmplitudeHeight()
            * (this._getRange(this._activeScaleBounds.amplitudeMin, this._activeScaleBounds.amplitudeMax)
            / this._getRange(this._autoScaleBounds.amplitudeMin, this._autoScaleBounds.amplitudeMax));
    }

    _getTimeWorldLength() {
        return this._getBaseTimeDepth()
            * (this._getRange(this._activeScaleBounds.timeMin, this._activeScaleBounds.timeMax)
            / this._getRange(this._autoScaleBounds.timeMin, this._autoScaleBounds.timeMax));
    }

    _getWorldXForBin(bin) {
        const normalizedBin = this.binCount > 1 ? (bin / (this.binCount - 1)) : 0;
        const sourceFrequencyValue = normalizedBin * Math.max(0, this._sourceBinCount - 1);
        const currentRange = this._getRange(this._activeScaleBounds.frequencyMin, this._activeScaleBounds.frequencyMax);
        const autoRange = this._getRange(this._autoScaleBounds.frequencyMin, this._autoScaleBounds.frequencyMax);
        const clampedDelta = THREE.MathUtils.clamp(
            sourceFrequencyValue - this._activeScaleBounds.frequencyMin,
            0,
            currentRange
        );

        return (-this._getFrequencyWorldLength() * 0.5) + ((clampedDelta / autoRange) * this._getBaseFrequencyWidth());
    }

    _getWorldZForRow(row) {
        const currentRange = this._getRange(this._activeScaleBounds.timeMin, this._activeScaleBounds.timeMax);
        const autoRange = this._getRange(this._autoScaleBounds.timeMin, this._autoScaleBounds.timeMax);
        const clampedDelta = THREE.MathUtils.clamp(row - this._activeScaleBounds.timeMin, 0, currentRange);

        return -((clampedDelta / autoRange) * this._getBaseTimeDepth());
    }

    _normalizeAmplitude(value) {
        const autoRange = this._getRange(this._autoScaleBounds.amplitudeMin, this._autoScaleBounds.amplitudeMax);
        return clampUnit((value - this._activeScaleBounds.amplitudeMin) / autoRange);
    }

    _computeAmplitudeY(smoothValue) {
        return Math.min(this._getAmplitudeWorldLength(), smoothValue * this._getBaseAmplitudeHeight());
    }

    _sampleFrameValue(frameData, bin) {
        const skipDcComponent = frameData instanceof Uint8Array;
        const firstBin = skipDcComponent ? 1 : 0;
        const availableBins = Math.max(1, frameData.length - firstBin);
        const normalizedBin = this.binCount > 1 ? (bin / (this.binCount - 1)) : 0;
        const sampleIndex = firstBin + Math.min(
            availableBins - 1,
            Math.round(normalizedBin * (availableBins - 1))
        );

        return frameData[sampleIndex] ?? 0;
    }
}
