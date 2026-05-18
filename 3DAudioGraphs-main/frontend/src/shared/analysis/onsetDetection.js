const clampPositiveNumber = (value, fallback = 0) => {
    const numericValue = Number(value);
    return Number.isFinite(numericValue) ? Math.max(0, numericValue) : fallback;
};

export const dedupeNearbyOnsetEvents = (events, minGapSec = 0.01) => {
    const sortedEvents = [...events].sort((a, b) => a.timeSec - b.timeSec);
    const dedupedEvents = [];

    for (const event of sortedEvents) {
        const previousEvent = dedupedEvents[dedupedEvents.length - 1];
        if (!previousEvent || (event.timeSec - previousEvent.timeSec) > minGapSec) {
            dedupedEvents.push(event);
            continue;
        }

        if ((event.strength || 0) > (previousEvent.strength || 0)) {
            dedupedEvents[dedupedEvents.length - 1] = event;
        }
    }

    return dedupedEvents;
};

const buildWindowVolumeDeltaStrengths = (window, volumeColumn) => window.pointIndices.map((pointIndex, localIndex) => {
    if (localIndex === 0) return 0;
    const currentVolume = Number(volumeColumn[pointIndex]) || 0;
    const previousVolume = Number(volumeColumn[window.pointIndices[localIndex - 1]]) || 0;
    return Math.max(0, currentVolume - previousVolume);
});

const buildWindowSpectralFluxStrengths = (window, {
    hasSpectralFrameData,
    getSpectralFrameDataRow,
} = {}) => {
    if (typeof hasSpectralFrameData !== 'function' || !hasSpectralFrameData()) return null;
    if (typeof getSpectralFrameDataRow !== 'function') return null;

    const strengths = new Array(window.pointIndices.length).fill(0);
    let resolvedPairCount = 0;

    for (let localIndex = 1; localIndex < window.frameRecords.length; localIndex++) {
        const currentFrameRecord = window.frameRecords[localIndex];
        const previousFrameRecord = window.frameRecords[localIndex - 1];
        const currentRowIndex = Number.isFinite(currentFrameRecord?.rowIndex)
            ? currentFrameRecord.rowIndex
            : window.pointIndices[localIndex];
        const previousRowIndex = Number.isFinite(previousFrameRecord?.rowIndex)
            ? previousFrameRecord.rowIndex
            : window.pointIndices[localIndex - 1];

        const currentFrame = getSpectralFrameDataRow(currentRowIndex);
        const previousFrame = getSpectralFrameDataRow(previousRowIndex);
        if (!currentFrame || !previousFrame) continue;

        const compareBinCount = Math.min(currentFrame.length, previousFrame.length);
        if (compareBinCount <= 1) continue;

        let positiveDeltaSum = 0;
        for (let binIndex = 1; binIndex < compareBinCount; binIndex++) {
            const positiveDelta = (currentFrame[binIndex] || 0) - (previousFrame[binIndex] || 0);
            if (positiveDelta > 0) positiveDeltaSum += positiveDelta;
        }

        strengths[localIndex] = positiveDeltaSum / (compareBinCount - 1);
        resolvedPairCount += 1;
    }

    return resolvedPairCount > 0 ? strengths : null;
};

const buildOnsetEventsFromStrengths = (windows, {
    strengthResolver,
    resolveFrameRecordTimeBounds,
    method,
    sensitivity = 1,
    thresholdMultiplier = 1,
    minGapSec = 0.01,
} = {}) => {
    if (typeof strengthResolver !== 'function' || typeof resolveFrameRecordTimeBounds !== 'function') {
        return [];
    }

    const onsetEvents = [];
    const onsetSensitivity = Math.max(0.2, clampPositiveNumber(sensitivity, 1));
    const onsetThresholdScale = Math.max(0.1, clampPositiveNumber(thresholdMultiplier, 1));

    for (const window of windows) {
        if (!Array.isArray(window.pointIndices) || window.pointIndices.length < 2) continue;

        const strengths = strengthResolver(window);
        if (!Array.isArray(strengths) || strengths.length !== window.pointIndices.length) continue;

        const positiveStrengths = strengths.filter((value, index) => index > 0 && Number.isFinite(value) && value > 0);
        if (positiveStrengths.length === 0) continue;

        const meanStrength = positiveStrengths.reduce((sum, value) => sum + value, 0) / positiveStrengths.length;
        const variance = positiveStrengths.reduce((sum, value) => sum + ((value - meanStrength) ** 2), 0) / positiveStrengths.length;
        const stdDev = Math.sqrt(variance);
        const sortedStrengths = [...positiveStrengths].sort((a, b) => a - b);
        const medianStrength = sortedStrengths[Math.floor(sortedStrengths.length / 2)] || 0;
        const baselineThreshold = Math.max(1e-6, medianStrength * 1.15, meanStrength + (stdDev * 0.18));
        const threshold = Math.max(1e-6, (baselineThreshold * onsetThresholdScale) / onsetSensitivity);

        const candidates = [];
        for (let localIndex = 1; localIndex < strengths.length; localIndex++) {
            const strength = Number(strengths[localIndex]) || 0;
            const prevStrength = strengths[localIndex - 1] ?? 0;
            const nextStrength = strengths[localIndex + 1] ?? 0;
            if (strength < threshold) continue;
            if (strength < prevStrength || strength < nextStrength) continue;

            const frameRecord = window.frameRecords[localIndex];
            const timeBounds = resolveFrameRecordTimeBounds(frameRecord);
            candidates.push({
                pointIndex: window.pointIndices[localIndex],
                frameIndex: frameRecord.frameIndex,
                timeSec: timeBounds.timeCenterSec,
                strength,
                threshold,
                windowIndex: window.windowIndex,
                method,
            });
        }

        if (candidates.length === 0) {
            let strongestLocalIndex = 1;
            for (let localIndex = 2; localIndex < strengths.length; localIndex++) {
                if (strengths[localIndex] > strengths[strongestLocalIndex]) {
                    strongestLocalIndex = localIndex;
                }
            }

            const strongestStrength = strengths[strongestLocalIndex] ?? 0;
            if (strongestStrength >= threshold * 0.9) {
                const frameRecord = window.frameRecords[strongestLocalIndex];
                const timeBounds = resolveFrameRecordTimeBounds(frameRecord);
                candidates.push({
                    pointIndex: window.pointIndices[strongestLocalIndex],
                    frameIndex: frameRecord.frameIndex,
                    timeSec: timeBounds.timeCenterSec,
                    strength: strongestStrength,
                    threshold,
                    windowIndex: window.windowIndex,
                    method,
                });
            }
        }

        onsetEvents.push(...candidates);
    }

    return dedupeNearbyOnsetEvents(onsetEvents, minGapSec);
};

export const buildSelectionOnsetEvents = (windows, {
    onsetMethod,
    supportedMethodLabels = ['Spectral Flux', 'Volume Delta'],
    spectralFluxMethodLabel = 'Spectral Flux',
    volumeDeltaMethodLabel = 'Volume Delta',
    volumeColumn = [],
    hasSpectralFrameData,
    getSpectralFrameDataRow,
    resolveFrameRecordTimeBounds,
    analysisHopDurationSec = 0,
    sensitivity = 1,
    thresholdMultiplier = 1,
} = {}) => {
    const supportedMethods = Array.isArray(supportedMethodLabels) && supportedMethodLabels.length > 0
        ? supportedMethodLabels
        : [spectralFluxMethodLabel, volumeDeltaMethodLabel];
    const requestedMethod = supportedMethods.includes(onsetMethod)
        ? onsetMethod
        : supportedMethods[0];
    const minGapSec = Math.max(0.01, clampPositiveNumber(analysisHopDurationSec, 0) * 1.5);
    const hasSpectralData = typeof hasSpectralFrameData === 'function' && hasSpectralFrameData();

    if (requestedMethod === spectralFluxMethodLabel && hasSpectralData) {
        return {
            onsetEvents: buildOnsetEventsFromStrengths(windows, {
                strengthResolver: (window) => buildWindowSpectralFluxStrengths(window, {
                    hasSpectralFrameData,
                    getSpectralFrameDataRow,
                }),
                resolveFrameRecordTimeBounds,
                method: spectralFluxMethodLabel,
                sensitivity,
                thresholdMultiplier,
                minGapSec,
            }),
            onsetMethod: spectralFluxMethodLabel,
        };
    }

    return {
        onsetEvents: buildOnsetEventsFromStrengths(windows, {
            strengthResolver: (window) => buildWindowVolumeDeltaStrengths(window, volumeColumn),
            resolveFrameRecordTimeBounds,
            method: volumeDeltaMethodLabel,
            sensitivity,
            thresholdMultiplier,
            minGapSec,
        }),
        onsetMethod: requestedMethod === spectralFluxMethodLabel ? volumeDeltaMethodLabel : requestedMethod,
    };
};