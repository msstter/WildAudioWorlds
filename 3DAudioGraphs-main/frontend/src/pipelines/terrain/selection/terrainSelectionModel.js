import * as THREE from 'three';

export const TERRAIN_FULL_MASK_LABEL = 'Full Sculpt Mask';
export const TERRAIN_RENDER_WINDOW_LABEL = 'Rendered Slice Window';

const TERRAIN_SELECTION_AXIS_LABELS = {
    x: 'Frequency',
    y: 'Amplitude',
    z: 'Time',
};

const formatTerrainPercent = (value) => {
    if (!Number.isFinite(value)) return '?';
    const rounded = Math.round(value * 10) / 10;
    if (Math.abs(rounded - Math.round(rounded)) < 1e-6) {
        return String(Math.round(rounded));
    }
    return rounded.toFixed(1).replace(/\.0$/, '');
};

const formatTerrainPctRangeLabel = (minPct, maxPct) => (
    `${formatTerrainPercent(minPct)}-${formatTerrainPercent(maxPct)}%`
);

export const createTerrainSculptStatusState = ({
    currentTarget = TERRAIN_FULL_MASK_LABEL,
    renderWindow = 'Waiting for SpectroTerrain frame data',
} = {}) => ({
    currentlySelected: currentTarget,
    selectionModel: TERRAIN_FULL_MASK_LABEL,
    renderWindow,
    state: 'Active',
    activePlanes: 'None',
    frequency: '0-100%',
    amplitude: '0-100%',
    time: '0-100%',
});

export const terrainSelectionSpaceLabel = (planeKey, planeSelectionMeta, { compact = false } = {}) => {
    const planeMeta = planeSelectionMeta?.[planeKey];
    if (!planeMeta) {
        return compact ? String(planeKey || 'Unknown') : `Selection Space: ${String(planeKey || 'Unknown')}`;
    }
    if (compact) {
        return `${String(planeKey).toUpperCase()} (${planeMeta.label})`;
    }
    return `Selection Space: ${planeMeta.label}`;
};

export const getDefaultTerrainSculptTargetLabel = ({
    terrainMode = false,
    fullMaskLabel = TERRAIN_FULL_MASK_LABEL,
    renderWindowLabel = TERRAIN_RENDER_WINDOW_LABEL,
} = {}) => (terrainMode ? fullMaskLabel : renderWindowLabel);

export const resolveTerrainSculptTargetLabel = ({
    nextTarget,
    terrainMode = false,
    fullMaskLabel = TERRAIN_FULL_MASK_LABEL,
    renderWindowLabel = TERRAIN_RENDER_WINDOW_LABEL,
} = {}) => {
    if (typeof nextTarget === 'string' && nextTarget.trim() !== '') {
        return nextTarget.trim();
    }
    return getDefaultTerrainSculptTargetLabel({ terrainMode, fullMaskLabel, renderWindowLabel });
};

export const describeTerrainInteractionTarget = ({
    planeKey,
    source,
    planeSelectionMeta,
    fullMaskLabel = TERRAIN_FULL_MASK_LABEL,
    renderWindowLabel = TERRAIN_RENDER_WINDOW_LABEL,
} = {}) => {
    if (source === '2d-overview') {
        return 'Selection Space: 2D Frequency x Time';
    }
    if (source === 'render-window') {
        return renderWindowLabel;
    }
    if (planeKey) {
        return terrainSelectionSpaceLabel(planeKey, planeSelectionMeta);
    }
    return fullMaskLabel;
};

export const getTerrainVisibleFrameWindowSnapshot = (terrainVisualizer) => {
    if (!terrainVisualizer?.hasFrameData?.()) {
        return { start: 0, endExclusive: 0 };
    }

    return terrainVisualizer.getAlignedFrameWindow?.() || {
        start: 0,
        endExclusive: Math.max(0, terrainVisualizer.getFrameDataCount?.() ?? 0),
    };
};

export const terrainFrameIndexToFullClipPct = (frameIndex, frameCount = 0) => {
    const safeFrameCount = Math.max(0, Math.round(frameCount || 0));
    const maxIndex = Math.max(1, safeFrameCount - 1);
    return THREE.MathUtils.clamp((Math.max(0, Math.min(maxIndex, Math.round(frameIndex || 0))) / maxIndex) * 100, 0, 100);
};

const getTerrainFramePctRange = (startFrame, endFrame, frameCount = 0) => {
    if (frameCount <= 0) return null;
    return {
        minPct: terrainFrameIndexToFullClipPct(Math.min(startFrame, endFrame), frameCount),
        maxPct: terrainFrameIndexToFullClipPct(Math.max(startFrame, endFrame), frameCount),
    };
};

export const formatTerrainRenderedSliceLabel = (visibleWindow, frameCount = 0) => {
    if (frameCount <= 0) return 'Waiting for SpectroTerrain frame data';
    const startFrame = Math.max(0, visibleWindow?.start || 0);
    const endFrame = Math.max(startFrame, (visibleWindow?.endExclusive || 0) - 1);
    const pctRange = getTerrainFramePctRange(startFrame, endFrame, frameCount);
    if (!pctRange) return 'Waiting for SpectroTerrain frame data';
    return `${formatTerrainPercent(pctRange.minPct)}-${formatTerrainPercent(pctRange.maxPct)}% of full clip | Frames ${startFrame}-${endFrame}`;
};

export const getTerrainFullClipTimeRangePct = (planeSelections) => ({
    minPct: THREE.MathUtils.clamp(Math.min(
        Number(planeSelections?.fullClipTimeMinPct ?? 0),
        Number(planeSelections?.fullClipTimeMaxPct ?? 100),
    ), 0, 100),
    maxPct: THREE.MathUtils.clamp(Math.max(
        Number(planeSelections?.fullClipTimeMinPct ?? 0),
        Number(planeSelections?.fullClipTimeMaxPct ?? 100),
    ), 0, 100),
});

export const getTerrainFullClipFrameRange = (planeSelections, frameCount = 0) => {
    if (frameCount <= 0) return null;
    const maxIndex = Math.max(0, frameCount - 1);
    const timeRangePct = getTerrainFullClipTimeRangePct(planeSelections);
    const startFrame = Math.round((timeRangePct.minPct / 100) * maxIndex);
    const endFrame = Math.round((timeRangePct.maxPct / 100) * maxIndex);
    return {
        startFrame: Math.max(0, Math.min(startFrame, endFrame)),
        endFrame: Math.min(maxIndex, Math.max(startFrame, endFrame)),
    };
};

export const terrainVisibleDepthPctToFrameIndex = (depthPct, visibleWindow) => {
    const startFrame = Math.max(0, Math.round(visibleWindow?.start || 0));
    const latestVisibleFrame = Math.max(startFrame, Math.round((visibleWindow?.endExclusive || 0) - 1));
    const visibleRowMax = Math.max(1, latestVisibleFrame - startFrame);
    return latestVisibleFrame - Math.round((THREE.MathUtils.clamp(depthPct, 0, 100) / 100) * visibleRowMax);
};

export const terrainFullClipFrameRangeToVisibleDepthPctRange = (startFrame, endFrame, visibleWindow) => {
    const windowStart = Math.max(0, Math.round(visibleWindow?.start || 0));
    const windowEnd = Math.max(windowStart, Math.round((visibleWindow?.endExclusive || 0) - 1));
    const visibleRowMax = Math.max(1, windowEnd - windowStart);
    const clampedStart = THREE.MathUtils.clamp(Math.min(startFrame, endFrame), windowStart, windowEnd);
    const clampedEnd = THREE.MathUtils.clamp(Math.max(startFrame, endFrame), windowStart, windowEnd);
    const depthPctA = ((windowEnd - clampedStart) / visibleRowMax) * 100;
    const depthPctB = ((windowEnd - clampedEnd) / visibleRowMax) * 100;
    return {
        minPct: THREE.MathUtils.clamp(Math.min(depthPctA, depthPctB), 0, 100),
        maxPct: THREE.MathUtils.clamp(Math.max(depthPctA, depthPctB), 0, 100),
    };
};

export const syncTerrainDisplayedTimeRangesFromFullClipSelection = ({
    planeSelections,
    visibleWindow,
    normalizePlaneSelectionRange,
    planeKeys = ['xz', 'yz'],
} = {}) => {
    if (!planeSelections?.enabled || planeSelections.workflowMode !== 'Sculpt Full Selection') return false;
    const frameRange = getTerrainFullClipFrameRange(planeSelections);
    if (!frameRange) return false;

    if (((visibleWindow?.endExclusive || 0) - (visibleWindow?.start || 0)) <= 0) return false;

    const nextDepthRange = terrainFullClipFrameRangeToVisibleDepthPctRange(
        frameRange.startFrame,
        frameRange.endFrame,
        visibleWindow,
    );

    let changed = false;
    for (const planeKey of planeKeys) {
        const selection = planeSelections?.[planeKey];
        if (!selection) continue;
        if (selection.axis2MinPct !== nextDepthRange.minPct || selection.axis2MaxPct !== nextDepthRange.maxPct) {
            selection.axis2MinPct = nextDepthRange.minPct;
            selection.axis2MaxPct = nextDepthRange.maxPct;
            normalizePlaneSelectionRange?.(selection, 'axis2MinPct', 'axis2MaxPct');
            changed = true;
        }
    }

    return changed;
};

export const deriveTerrainVolumeSelection = (planeSelections) => {
    const axisRanges = { x: [], y: [], z: [] };
    const activeSelections = [];
    const tintAccumulator = new THREE.Color(0, 0, 0);
    let tintWeight = 0;

    const registerAxisRange = (axisKey, minPct, maxPct) => {
        axisRanges[axisKey].push({
            minPct: THREE.MathUtils.clamp(Math.min(minPct, maxPct), 0, 100),
            maxPct: THREE.MathUtils.clamp(Math.max(minPct, maxPct), 0, 100),
        });
    };

    const registerSelection = (selection, rangesByAxis) => {
        if (!selection?.enabled) return;
        activeSelections.push(selection);

        const color = new THREE.Color(selection.tintColor ?? '#ffffff');
        const weight = Math.max(Number(selection.strength) || 0, 0.01);
        tintAccumulator.add(color.multiplyScalar(weight));
        tintWeight += weight;

        for (const [axisKey, [minPct, maxPct]] of Object.entries(rangesByAxis)) {
            registerAxisRange(axisKey, minPct, maxPct);
        }
    };

    registerSelection(planeSelections?.xz, {
        x: [planeSelections?.xz?.axis1MinPct ?? 0, planeSelections?.xz?.axis1MaxPct ?? 100],
        z: [planeSelections?.xz?.axis2MinPct ?? 0, planeSelections?.xz?.axis2MaxPct ?? 100],
    });
    registerSelection(planeSelections?.yz, {
        y: [planeSelections?.yz?.axis1MinPct ?? 0, planeSelections?.yz?.axis1MaxPct ?? 100],
        z: [planeSelections?.yz?.axis2MinPct ?? 0, planeSelections?.yz?.axis2MaxPct ?? 100],
    });
    registerSelection(planeSelections?.xy, {
        x: [planeSelections?.xy?.axis1MinPct ?? 0, planeSelections?.xy?.axis1MaxPct ?? 100],
        y: [planeSelections?.xy?.axis2MinPct ?? 0, planeSelections?.xy?.axis2MaxPct ?? 100],
    });

    if (axisRanges.x.length === 0 || axisRanges.y.length === 0 || axisRanges.z.length === 0) {
        return { enabled: false };
    }

    const xMinPct = Math.max(...axisRanges.x.map((range) => range.minPct));
    const xMaxPct = Math.min(...axisRanges.x.map((range) => range.maxPct));
    const yMinPct = Math.max(...axisRanges.y.map((range) => range.minPct));
    const yMaxPct = Math.min(...axisRanges.y.map((range) => range.maxPct));
    const zMinPct = Math.max(...axisRanges.z.map((range) => range.minPct));
    const zMaxPct = Math.min(...axisRanges.z.map((range) => range.maxPct));

    if (xMaxPct <= xMinPct || yMaxPct <= yMinPct || zMaxPct <= zMinPct) {
        return { enabled: false };
    }

    const tintColor = tintWeight > 0
        ? tintAccumulator.multiplyScalar(1 / tintWeight)
        : new THREE.Color('#ffffff');
    const strength = activeSelections.length > 0
        ? activeSelections.reduce((sum, selection) => sum + (Number(selection.strength) || 0), 0) / activeSelections.length
        : 0;

    return {
        enabled: true,
        xMinPct,
        xMaxPct,
        yMinPct,
        yMaxPct,
        zMinPct,
        zMaxPct,
        tintColor,
        strength,
    };
};

export const syncTerrainFullClipTimeSelectionFromDisplayedPlanes = ({
    planeSelections,
    visibleWindow,
    volumeSelection = deriveTerrainVolumeSelection(planeSelections),
    frameCount = 0,
} = {}) => {
    if (!planeSelections?.enabled || planeSelections.workflowMode !== 'Sculpt Full Selection') return false;
    if (((visibleWindow?.endExclusive || 0) - (visibleWindow?.start || 0)) <= 0) return false;

    let depthMinPct = null;
    let depthMaxPct = null;

    if (volumeSelection.enabled) {
        depthMinPct = volumeSelection.zMinPct;
        depthMaxPct = volumeSelection.zMaxPct;
    } else if (planeSelections?.xz?.enabled) {
        depthMinPct = planeSelections.xz.axis2MinPct;
        depthMaxPct = planeSelections.xz.axis2MaxPct;
    } else if (planeSelections?.yz?.enabled) {
        depthMinPct = planeSelections.yz.axis2MinPct;
        depthMaxPct = planeSelections.yz.axis2MaxPct;
    }

    if (!Number.isFinite(depthMinPct) || !Number.isFinite(depthMaxPct)) return false;

    const frameA = terrainVisibleDepthPctToFrameIndex(depthMinPct, visibleWindow);
    const frameB = terrainVisibleDepthPctToFrameIndex(depthMaxPct, visibleWindow);
    const nextMinPct = terrainFrameIndexToFullClipPct(Math.min(frameA, frameB), frameCount);
    const nextMaxPct = terrainFrameIndexToFullClipPct(Math.max(frameA, frameB), frameCount);
    const changed = nextMinPct !== planeSelections.fullClipTimeMinPct || nextMaxPct !== planeSelections.fullClipTimeMaxPct;
    planeSelections.fullClipTimeMinPct = nextMinPct;
    planeSelections.fullClipTimeMaxPct = nextMaxPct;
    return changed;
};

export const applyTerrainFullSpaceSelection = (planeSelections, {
    planeSelectionMeta,
    normalizePlaneSelectionRange,
} = {}) => {
    if (!planeSelections || typeof planeSelections !== 'object') return planeSelections;

    planeSelections.enabled = true;
    planeSelections.workflowMode = 'Sculpt Full Selection';
    planeSelections.fullClipTimeMinPct = 0;
    planeSelections.fullClipTimeMaxPct = 100;
    planeSelections.showSceneHandles = true;
    planeSelections.showVolumeBox = true;

    for (const [planeKey, planeMeta] of Object.entries(planeSelectionMeta || {})) {
        const selection = planeSelections[planeKey] && typeof planeSelections[planeKey] === 'object'
            ? planeSelections[planeKey]
            : {};
        planeSelections[planeKey] = selection;

        selection.enabled = true;
        selection.tintColor = selection.tintColor ?? planeMeta.tintColor;
        selection.strength = THREE.MathUtils.clamp(
            Number.isFinite(Number(selection.strength)) ? Number(selection.strength) : planeMeta.strength,
            0,
            1,
        );
        selection.axis1MinPct = 0;
        selection.axis1MaxPct = 100;
        selection.axis2MinPct = 0;
        selection.axis2MaxPct = 100;
        normalizePlaneSelectionRange?.(selection, 'axis1MinPct', 'axis1MaxPct');
        normalizePlaneSelectionRange?.(selection, 'axis2MinPct', 'axis2MaxPct');
    }

    return planeSelections;
};

export const getTerrainPlaneSelectionCoverage = (planeSelections, planeSelectionMeta) => {
    const coverage = { x: false, y: false, z: false };
    const activePlaneKeys = [];
    const activePlanes = [];

    const registerPlane = (planeKey, axisKeys) => {
        if (!planeSelections?.[planeKey]?.enabled) return;
        activePlaneKeys.push(planeKey);
        activePlanes.push(planeSelectionMeta?.[planeKey]?.label || String(planeKey).toUpperCase());
        for (const axisKey of axisKeys) {
            coverage[axisKey] = true;
        }
    };

    registerPlane('xz', ['x', 'z']);
    registerPlane('yz', ['y', 'z']);
    registerPlane('xy', ['x', 'y']);

    return {
        activePlaneKeys,
        activePlanes,
        coverage,
        missingAxes: Object.entries(coverage)
            .filter(([, isCovered]) => !isCovered)
            .map(([axisKey]) => TERRAIN_SELECTION_AXIS_LABELS[axisKey] || axisKey.toUpperCase()),
    };
};

export const buildTerrainCanonicalSelectionModel = ({
    planeSelections,
    planeSelectionMeta,
    terrainMode = false,
    currentTarget,
    frameCount = 0,
    visibleWindow = { start: 0, endExclusive: 0 },
    fullMaskLabel = TERRAIN_FULL_MASK_LABEL,
    renderWindowLabel = TERRAIN_RENDER_WINDOW_LABEL,
} = {}) => {
    const coverage = getTerrainPlaneSelectionCoverage(planeSelections, planeSelectionMeta);
    const volumeSelection = deriveTerrainVolumeSelection(planeSelections);
    const fullClipTimeRangePct = getTerrainFullClipTimeRangePct(planeSelections);
    const currentTargetLabel = resolveTerrainSculptTargetLabel({
        nextTarget: currentTarget,
        terrainMode,
        fullMaskLabel,
        renderWindowLabel,
    });
    const renderedSliceLabel = terrainMode
        ? formatTerrainRenderedSliceLabel(visibleWindow, frameCount)
        : 'SpectroTerrain mode inactive';
    const activeSelectionSpaces = planeSelections?.enabled
        ? coverage.activePlanes.map((planeKeyOrLabel) => terrainSelectionSpaceLabel(planeKeyOrLabel, planeSelectionMeta, { compact: true }))
        : [];

    let maskState = 'Active';
    if (!planeSelections?.enabled && volumeSelection.enabled) {
        maskState = 'Stored Only';
    } else if (!planeSelections?.enabled) {
        maskState = 'Off';
    } else if (volumeSelection.enabled) {
        maskState = 'Active';
    } else if (coverage.activePlanes.length === 0) {
        maskState = 'No Active Planes';
    } else {
        maskState = `Missing ${coverage.missingAxes.join(', ')}`;
    }

    return {
        currentTargetLabel,
        coverage,
        volumeSelection,
        fullClipTimeRangePct,
        fullClipFrameRange: getTerrainFullClipFrameRange(planeSelections, frameCount),
        renderedSliceLabel,
        activeSelectionSpaces,
        status: {
            currentlySelected: currentTargetLabel,
            selectionModel: planeSelections?.enabled ? fullMaskLabel : `No active ${fullMaskLabel}`,
            renderWindow: renderedSliceLabel,
            state: maskState,
            activePlanes: activeSelectionSpaces.length > 0 ? activeSelectionSpaces.join(' | ') : 'None',
            frequency: volumeSelection.enabled
                ? formatTerrainPctRangeLabel(volumeSelection.xMinPct, volumeSelection.xMaxPct)
                : 'Incomplete',
            amplitude: volumeSelection.enabled
                ? formatTerrainPctRangeLabel(volumeSelection.yMinPct, volumeSelection.yMaxPct)
                : 'Incomplete',
            time: planeSelections?.enabled
                ? formatTerrainPctRangeLabel(fullClipTimeRangePct.minPct, fullClipTimeRangePct.maxPct)
                : 'Incomplete',
        },
    };
};