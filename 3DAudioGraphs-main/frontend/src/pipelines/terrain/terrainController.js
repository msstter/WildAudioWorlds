export const createTerrainController = ({
    settings,
    terrainVisualizer,
    terrainHelperBadge,
    isTerrainMode,
    ensureTerrainAxisColorSettings,
    ensureTerrainTimeWindowSettings,
    ensureTerrainPlaneSelectionSettings,
    ensureTerrain2DGraphSettings,
    applyTerrainAxisScaling,
    syncAnalyserBinCount,
    centerCameraOnTerrain,
    getPlaybackTimeSec,
    getDurationSec,
    readLiveFrequencyFrame,
    resetTimbreRuntime,
} = {}) => {
    const applySettings = () => {
        terrainVisualizer.configure({
            binCount: settings.terrainFrequencyBins,
            timeDepth: settings.terrainTimeDepth,
        });
        ensureTerrainAxisColorSettings?.();
        ensureTerrainTimeWindowSettings?.();
        ensureTerrainPlaneSelectionSettings?.();
        ensureTerrain2DGraphSettings?.();
        terrainVisualizer.setSettings(settings);
        terrainVisualizer.refreshColors();
        syncAnalyserBinCount?.(settings.terrainFrequencyBins);
        applyTerrainAxisScaling?.({ syncFromAuto: !settings.terrainManualScaling });
    };

    const applyAxisColorSettings = () => {
        ensureTerrainAxisColorSettings?.();
        ensureTerrainTimeWindowSettings?.();
        ensureTerrainPlaneSelectionSettings?.();
        ensureTerrain2DGraphSettings?.();
        terrainVisualizer.setSettings(settings);
        terrainVisualizer.refreshColors();
    };

    const apply2DGraphSettings = () => {
        ensureTerrain2DGraphSettings?.();
        terrainVisualizer.setSettings(settings);
        terrainVisualizer.refreshColors();
    };

    const applyHelperPreference = () => {
        terrainVisualizer.setSettings(settings);
        terrainVisualizer.refreshColors();
    };

    const activateMode = ({
        playbackTimeSec = getPlaybackTimeSec?.() || 0,
        durationSec = getDurationSec?.() || 0,
    } = {}) => {
        applySettings();
        if (terrainVisualizer.hasFrameData?.() && durationSec > 0) {
            terrainVisualizer.syncToProgress(playbackTimeSec / durationSec);
        }
        centerCameraOnTerrain?.();
    };

    const runFrame = ({
        playbackTimeSec = getPlaybackTimeSec?.() || 0,
        durationSec = getDurationSec?.() || 0,
    } = {}) => {
        resetTimbreRuntime?.(playbackTimeSec);

        if (terrainVisualizer.hasFrameData?.()) {
            if (durationSec > 0) {
                terrainVisualizer.syncToProgress(playbackTimeSec / durationSec);
            }
            return;
        }

        const liveFrame = readLiveFrequencyFrame?.();
        if (liveFrame) {
            terrainVisualizer.pushFrame(liveFrame);
        }
    };

    const updateHelperIndicator = () => {
        if (!isTerrainMode?.()) {
            terrainHelperBadge.style.display = 'none';
            return;
        }

        const status = terrainVisualizer.getProjectionHelperStatus?.() ?? {
            summary: '2D Helper: FFT Fallback',
            detail: 'Renderer status unavailable.',
            activeSource: 'fallback',
        };

        terrainHelperBadge.style.display = 'block';
        terrainHelperBadge.textContent = status.summary ?? '2D Helper: FFT Fallback';
        terrainHelperBadge.title = status.detail ?? '';

        const styleMap = {
            precomputed: {
                border: '#0f766e',
                color: '#ccfbf1',
                background: 'rgba(17, 94, 89, 0.82)',
            },
            fallback: {
                border: '#b45309',
                color: '#fde68a',
                background: 'rgba(120, 53, 15, 0.82)',
            },
            'manual-fallback': {
                border: '#2563eb',
                color: '#dbeafe',
                background: 'rgba(30, 64, 175, 0.82)',
            },
            incompatible: {
                border: '#7c3aed',
                color: '#ede9fe',
                background: 'rgba(91, 33, 182, 0.82)',
            },
            unavailable: {
                border: '#4b5563',
                color: '#e5e7eb',
                background: 'rgba(55, 65, 81, 0.82)',
            },
            idle: {
                border: '#4b5563',
                color: '#d1d5db',
                background: 'rgba(31, 41, 55, 0.78)',
            },
        };

        const badgeStyle = styleMap[status.activeSource] ?? styleMap.idle;
        terrainHelperBadge.style.borderColor = badgeStyle.border;
        terrainHelperBadge.style.color = badgeStyle.color;
        terrainHelperBadge.style.background = badgeStyle.background;
    };

    return {
        activateMode,
        apply2DGraphSettings,
        applyAxisColorSettings,
        applyHelperPreference,
        applySettings,
        runFrame,
        updateHelperIndicator,
    };
};