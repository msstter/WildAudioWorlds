const clampPct = (value) => Math.max(0, Math.min(100, value));

export const normalizePlaneSelectionRange = (selection, minKey, maxKey) => {
    const rawMin = Number.isFinite(Number(selection[minKey])) ? Number(selection[minKey]) : 0;
    const rawMax = Number.isFinite(Number(selection[maxKey])) ? Number(selection[maxKey]) : 100;
    selection[minKey] = clampPct(Math.min(rawMin, rawMax));
    selection[maxKey] = clampPct(Math.max(rawMin, rawMax));

    if (selection[maxKey] <= selection[minKey]) {
        selection[maxKey] = Math.min(100, selection[minKey] + 0.1);
    }
};

export const shiftPlaneSelectionWindow = (startMinPct, startMaxPct, deltaPct) => {
    const sizePct = Math.max(0.1, startMaxPct - startMinPct);
    let minPct = startMinPct + deltaPct;
    let maxPct = startMaxPct + deltaPct;

    if (minPct < 0) {
        maxPct -= minPct;
        minPct = 0;
    }
    if (maxPct > 100) {
        minPct -= (maxPct - 100);
        maxPct = 100;
    }

    minPct = clampPct(Math.min(minPct, Math.max(0, 100 - sizePct)));
    maxPct = clampPct(Math.max(minPct + 0.1, Math.min(minPct + sizePct, 100)));
    return { minPct, maxPct };
};