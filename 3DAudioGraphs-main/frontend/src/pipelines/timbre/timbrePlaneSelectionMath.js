import * as THREE from 'three';
import { isPointInsidePolygon, normalizeLassoPoints } from '../../shared/selection/lassoMath.js';

export const normalizeTimbreLassoPoints = (points, {
    maxPoints = 96,
    minDistancePct = 0.15,
} = {}) => normalizeLassoPoints(points, {
    maxPoints,
    minDistancePct,
});

export const timbrePlaneSelectionUsesLasso = (selection) => (selection?.selectionMode ?? 'Box') === 'Lasso';

export const getRenderableTimbreLassoPoints = (planeKey, selection, {
    activeLassoDraw = null,
    normalizePoints = normalizeTimbreLassoPoints,
} = {}) => {
    if (activeLassoDraw?.planeKey === planeKey) {
        return normalizePoints(activeLassoDraw.points);
    }
    return normalizePoints(selection?.lassoPoints);
};

const getActiveTimbrePlaneSelectionEntries = (planeSelections, planeSelectionMeta) => Object.entries(planeSelectionMeta)
    .filter(([planeKey]) => planeSelections?.[planeKey]?.enabled);

const activeTimbrePlaneSelectionsCoverAllAxes = (activeEntries) => {
    const coveredAxes = new Set();
    for (const [, planeMeta] of activeEntries) {
        coveredAxes.add(planeMeta.axis1Key);
        coveredAxes.add(planeMeta.axis2Key);
    }
    return coveredAxes.size === 3;
};

const pointMatchesTimbrePlaneSelection = ({
    point,
    planeKey,
    selection,
    bounds,
    getPointPcts,
    normalizePoints = normalizeTimbreLassoPoints,
}) => {
    const pointPcts = getPointPcts(planeKey, point, bounds);

    if (timbrePlaneSelectionUsesLasso(selection)) {
        const lassoPoints = normalizePoints(selection?.lassoPoints);
        if (lassoPoints.length < 3) return false;
        return isPointInsidePolygon(pointPcts, lassoPoints);
    }

    return (
        pointPcts.axis1Pct >= selection.axis1MinPct &&
        pointPcts.axis1Pct <= selection.axis1MaxPct &&
        pointPcts.axis2Pct >= selection.axis2MinPct &&
        pointPcts.axis2Pct <= selection.axis2MaxPct
    );
};

const deriveTimbreSelectionVolumeFromIds = ({
    selectedIds,
    activeEntries,
    points,
}) => {
    if (!Array.isArray(selectedIds) || selectedIds.length === 0) {
        return { enabled: false };
    }

    let minX = Infinity;
    let minY = Infinity;
    let minZ = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    let maxZ = -Infinity;
    const tintAccumulator = new THREE.Color(0, 0, 0);
    let tintWeight = 0;

    for (const instanceId of selectedIds) {
        const point = points[instanceId];
        if (!point) continue;
        minX = Math.min(minX, point.x);
        minY = Math.min(minY, point.y);
        minZ = Math.min(minZ, point.z);
        maxX = Math.max(maxX, point.x);
        maxY = Math.max(maxY, point.y);
        maxZ = Math.max(maxZ, point.z);
    }

    for (const [, , selection] of activeEntries) {
        if (!selection?.enabled) continue;
        const color = new THREE.Color(selection.tintColor ?? '#ffffff');
        const weight = Math.max(Number(selection.strength) || 0, 0.01);
        tintAccumulator.add(color.multiplyScalar(weight));
        tintWeight += weight;
    }

    if (!Number.isFinite(minX) || !Number.isFinite(maxX) || !Number.isFinite(minY) || !Number.isFinite(maxY) || !Number.isFinite(minZ) || !Number.isFinite(maxZ)) {
        return { enabled: false };
    }

    return {
        enabled: true,
        minX,
        maxX,
        minY,
        maxY,
        minZ,
        maxZ,
        tintColor: tintWeight > 0 ? tintAccumulator.multiplyScalar(1 / tintWeight) : new THREE.Color('#ffffff'),
        strength: activeEntries.length > 0
            ? activeEntries.reduce((sum, [, , selection]) => sum + (Number(selection?.strength) || 0), 0) / activeEntries.length
            : 0.22,
    };
};

export const evaluateTimbreSelectionFromPlaneSettings = (planeSelections, {
    bounds,
    planeSelectionMeta,
    points,
    getPointPcts,
    normalizePoints = normalizeTimbreLassoPoints,
} = {}) => {
    const activeEntries = getActiveTimbrePlaneSelectionEntries(planeSelections, planeSelectionMeta)
        .map(([planeKey, planeMeta]) => [planeKey, planeMeta, planeSelections[planeKey]]);

    if (activeEntries.length === 0 || !activeTimbrePlaneSelectionsCoverAllAxes(activeEntries.map(([planeKey, planeMeta]) => [planeKey, planeMeta]))) {
        return {
            selectedIds: [],
            volumeSelection: { enabled: false },
        };
    }

    const selectedIds = points
        .map((point, index) => ({ point, index }))
        .filter(({ point }) => activeEntries.every(([planeKey, , selection]) => pointMatchesTimbrePlaneSelection({
            point,
            planeKey,
            selection,
            bounds,
            getPointPcts,
            normalizePoints,
        })))
        .map(({ index }) => index);

    return {
        selectedIds,
        volumeSelection: deriveTimbreSelectionVolumeFromIds({
            selectedIds,
            activeEntries,
            points,
        }),
    };
};