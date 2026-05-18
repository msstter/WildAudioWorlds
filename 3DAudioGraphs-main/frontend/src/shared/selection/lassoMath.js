const clampPct = (value) => Math.max(0, Math.min(100, value));

export const normalizeLassoPoints = (points, {
    maxPoints = Infinity,
    minDistancePct = 0,
} = {}) => {
    const normalized = [];

    for (const point of points || []) {
        const axis1Pct = clampPct(Number(point?.axis1Pct));
        const axis2Pct = clampPct(Number(point?.axis2Pct));
        if (!Number.isFinite(axis1Pct) || !Number.isFinite(axis2Pct)) continue;

        const previousPoint = normalized[normalized.length - 1];
        if (previousPoint && Math.hypot(axis1Pct - previousPoint.axis1Pct, axis2Pct - previousPoint.axis2Pct) < minDistancePct) {
            continue;
        }

        normalized.push({ axis1Pct, axis2Pct });
        if (normalized.length >= maxPoints) break;
    }

    return normalized;
};

export const isPointInsidePolygon = (pointPct, polygonPoints) => {
    let inside = false;
    for (let index = 0, prevIndex = polygonPoints.length - 1; index < polygonPoints.length; prevIndex = index++) {
        const current = polygonPoints[index];
        const previous = polygonPoints[prevIndex];
        const intersects = ((current.axis2Pct > pointPct.axis2Pct) !== (previous.axis2Pct > pointPct.axis2Pct)) &&
            (pointPct.axis1Pct < ((previous.axis1Pct - current.axis1Pct) * (pointPct.axis2Pct - current.axis2Pct)) /
                Math.max(previous.axis2Pct - current.axis2Pct, 1e-6) + current.axis1Pct);
        if (intersects) inside = !inside;
    }
    return inside;
};