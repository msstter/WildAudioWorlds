const DEFAULT_SELECTION_AMPLITUDE_MIN_PCT = 0.0;
const DEFAULT_SELECTION_AMPLITUDE_MAX_PCT = 100.0;

function mappingOrEmpty(value) {
    return value && typeof value === 'object' && !Array.isArray(value)
        ? { ...value }
        : {};
}

function coerceFloat(value, fallback = 0.0) {
    const number = Number(value);
    return Number.isFinite(number) ? number : Number(fallback);
}

function coerceInt(value, fallback = 0) {
    const number = Math.round(Number(value));
    return Number.isFinite(number) ? number : Number(fallback);
}

function clamp(value, lower, upper) {
    return Math.max(lower, Math.min(upper, value));
}

function normalizeBackendSelectionContract(selectionPayload) {
    const selection = mappingOrEmpty(selectionPayload);
    return {
        ...selection,
        isReady: !!selection.isReady,
        frameRange: mappingOrEmpty(selection.frameRange),
        sampleRange: mappingOrEmpty(selection.sampleRange),
        timeRangeSec: mappingOrEmpty(selection.timeRangeSec),
        frequencyBinRange: mappingOrEmpty(selection.frequencyBinRange),
        amplitudePctRange: mappingOrEmpty(selection.amplitudePctRange),
    };
}

function normalizeSelectionTimeWindow(selectionPayload, clipDurationSec) {
    const selection = normalizeBackendSelectionContract(selectionPayload);
    const timeRange = mappingOrEmpty(selection.timeRangeSec);

    let startSec = coerceFloat(timeRange.start, 0.0);
    let endSec = coerceFloat(timeRange.end, clipDurationSec);

    if (clipDurationSec > 0) {
        startSec = clamp(startSec, 0.0, clipDurationSec);
        endSec = clamp(endSec, 0.0, clipDurationSec);
    } else {
        startSec = Math.max(0.0, startSec);
        endSec = Math.max(0.0, endSec);
    }

    if (endSec <= startSec) {
        throw new RangeError('Selection time window is empty. Enable terrain plane selections that define a non-zero time slice.');
    }

    return {
        startSec,
        endSec,
        durationSec: endSec - startSec,
    };
}

function normalizeSelectionFrequencyWindow(selectionPayload, availableBinCount, preferredTotalBins) {
    const selection = normalizeBackendSelectionContract(selectionPayload);
    const frequencyRange = mappingOrEmpty(selection.frequencyBinRange);

    let totalBins = Math.max(1, Math.min(coerceInt(availableBinCount, 1), coerceInt(preferredTotalBins, 1)));
    const requestedTotalBins = coerceInt(frequencyRange.totalBins, totalBins);
    totalBins = Math.max(1, Math.min(totalBins, requestedTotalBins));

    let startBin = coerceInt(frequencyRange.startBin, 0);
    let endBin = coerceInt(frequencyRange.endBin, totalBins - 1);
    startBin = coerceInt(clamp(startBin, 0, Math.max(0, totalBins - 1)), 0);
    endBin = coerceInt(clamp(endBin, startBin, Math.max(0, totalBins - 1)), totalBins - 1);

    return {
        startBin,
        endBin,
        totalBins,
    };
}

function normalizeSelectionAmplitudePctRange(selectionPayload, { clampValues = false } = {}) {
    const selection = normalizeBackendSelectionContract(selectionPayload);
    const amplitudeRange = mappingOrEmpty(selection.amplitudePctRange);

    let minPct = coerceFloat(amplitudeRange.min, DEFAULT_SELECTION_AMPLITUDE_MIN_PCT);
    let maxPct = coerceFloat(amplitudeRange.max, DEFAULT_SELECTION_AMPLITUDE_MAX_PCT);

    if (clampValues) {
        minPct = clamp(minPct, DEFAULT_SELECTION_AMPLITUDE_MIN_PCT, DEFAULT_SELECTION_AMPLITUDE_MAX_PCT);
        maxPct = clamp(maxPct, minPct, DEFAULT_SELECTION_AMPLITUDE_MAX_PCT);
    }

    return {
        min: minPct,
        max: maxPct,
    };
}

function normalizeReadySelectionForRequest(assetPayload, selectionPayload) {
    const selection = normalizeBackendSelectionContract(selectionPayload);
    if (!selection.isReady) {
        return selection;
    }

    const asset = mappingOrEmpty(assetPayload);
    const requestedTotalBins = coerceInt(selection.frequencyBinRange.totalBins, 0);
    const fftBinCount = coerceInt(asset.analysisFftNfft, 0);
    const preferredTotalBins = Math.max(1, requestedTotalBins || fftBinCount || 1);
    const availableBinCount = Math.max(1, Math.min(preferredTotalBins, fftBinCount || preferredTotalBins));
    const normalizedTimeWindow = normalizeSelectionTimeWindow(selection, coerceFloat(asset.analysisClipDurationSec, 0.0));

    return {
        ...selection,
        timeRangeSec: {
            start: normalizedTimeWindow.startSec,
            end: normalizedTimeWindow.endSec,
            duration: normalizedTimeWindow.durationSec,
        },
        frequencyBinRange: normalizeSelectionFrequencyWindow(selection, availableBinCount, preferredTotalBins),
        amplitudePctRange: normalizeSelectionAmplitudePctRange(selection, { clampValues: true }),
    };
}

module.exports = {
    DEFAULT_SELECTION_AMPLITUDE_MAX_PCT,
    DEFAULT_SELECTION_AMPLITUDE_MIN_PCT,
    normalizeBackendSelectionContract,
    normalizeReadySelectionForRequest,
    normalizeSelectionAmplitudePctRange,
    normalizeSelectionFrequencyWindow,
    normalizeSelectionTimeWindow,
};