export const resolveFrameRecordTimeBounds = (frameRecord, {
    getAnalysisHopDurationSec,
    getFallbackFrameCenterSec,
} = {}) => {
    const pointIndex = Number.isFinite(frameRecord?.rowIndex)
        ? frameRecord.rowIndex
        : Math.max(0, Number(frameRecord?.frameIndex) || 0);
    const hopDurationSec = typeof getAnalysisHopDurationSec === 'function'
        ? Math.max(0, Number(getAnalysisHopDurationSec()) || 0)
        : 0;
    const fallbackCenterSec = typeof getFallbackFrameCenterSec === 'function'
        ? Number(getFallbackFrameCenterSec(pointIndex)) || 0
        : 0;
    const timeCenterSec = Number.isFinite(frameRecord?.timeCenterSec) ? frameRecord.timeCenterSec : fallbackCenterSec;
    const timeStartSec = Number.isFinite(frameRecord?.timeStartSec)
        ? frameRecord.timeStartSec
        : Math.max(0, timeCenterSec - (hopDurationSec * 0.5));
    const timeEndSec = Number.isFinite(frameRecord?.timeEndSec)
        ? frameRecord.timeEndSec
        : (timeCenterSec + (hopDurationSec * 0.5));

    return {
        pointIndex,
        timeStartSec,
        timeCenterSec,
        timeEndSec,
    };
};

export const buildContiguousSelectionWindows = (selectedRecords, {
    getAnalysisHopDurationSec,
    resolveFrameRecordTimeBounds: resolveTimeBounds = (frameRecord) => resolveFrameRecordTimeBounds(frameRecord, {
        getAnalysisHopDurationSec,
    }),
} = {}) => {
    if (selectedRecords.length === 0) return [];

    const hopDurationSec = typeof getAnalysisHopDurationSec === 'function'
        ? Math.max(0, Number(getAnalysisHopDurationSec()) || 0)
        : 0;
    const maxGapSec = Math.max(0.001, hopDurationSec * 1.25);
    const sortedRecords = selectedRecords
        .map((entry) => ({
            ...entry,
            ...resolveTimeBounds(entry.frameRecord),
        }))
        .sort((a, b) => a.instanceId - b.instanceId || a.timeCenterSec - b.timeCenterSec);

    const windows = [];
    let currentWindow = null;

    const startWindow = (entry) => ({
        startPointIndex: entry.instanceId,
        endPointIndex: entry.instanceId,
        startFrameIndex: entry.frameRecord.frameIndex,
        endFrameIndex: entry.frameRecord.frameIndex,
        timeStartSec: entry.timeStartSec,
        timeEndSec: entry.timeEndSec,
        pointIndices: [entry.instanceId],
        frameRecords: [entry.frameRecord],
    });

    for (const entry of sortedRecords) {
        if (!currentWindow) {
            currentWindow = startWindow(entry);
            continue;
        }

        const adjacentByPointIndex = entry.instanceId <= currentWindow.endPointIndex + 1;
        const adjacentByTime = entry.timeStartSec <= currentWindow.timeEndSec + maxGapSec;

        if (adjacentByPointIndex || adjacentByTime) {
            currentWindow.endPointIndex = entry.instanceId;
            currentWindow.endFrameIndex = entry.frameRecord.frameIndex;
            currentWindow.timeEndSec = Math.max(currentWindow.timeEndSec, entry.timeEndSec);
            currentWindow.pointIndices.push(entry.instanceId);
            currentWindow.frameRecords.push(entry.frameRecord);
            continue;
        }

        windows.push(currentWindow);
        currentWindow = startWindow(entry);
    }

    if (currentWindow) windows.push(currentWindow);

    return windows.map((window, windowIndex) => ({
        ...window,
        windowIndex,
    }));
};