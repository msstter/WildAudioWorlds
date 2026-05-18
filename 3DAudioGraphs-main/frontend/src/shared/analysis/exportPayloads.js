export const buildSelectionAnalysisPayload = (analysis, {
    label = 'Selection',
    assetId = null,
    assetLabel = null,
    onsetMethod = '',
    resolveFrameRecordTimeBounds = () => ({}),
} = {}) => {
    const summary = analysis?.summary;
    if (!summary) return null;

    return {
        assetId,
        assetLabel,
        targetLabel: label,
        onsetMethod: analysis.onsetMethod || onsetMethod,
        selectedFrameCount: summary.selectedRecords.length,
        frameRange: [summary.frameMin, summary.frameMax],
        timeRangeSec: [summary.timeMin, summary.timeMax],
        durationSec: summary.durationSec,
        windows: (analysis.contiguousWindows || []).map((window) => ({
            windowIndex: window.windowIndex,
            timeStartSec: window.timeStartSec,
            timeEndSec: window.timeEndSec,
            pointIndices: [...window.pointIndices],
        })),
        onsetEvents: (analysis.onsetEvents || []).map((event) => ({
            pointIndex: event.pointIndex,
            frameIndex: event.frameIndex,
            timeSec: event.timeSec,
            strength: event.strength,
            threshold: event.threshold,
            windowIndex: event.windowIndex,
            method: event.method || analysis.onsetMethod || onsetMethod,
        })),
        interOnsetIntervals: (analysis.interOnsetIntervals || []).map((interval) => ({
            onsetIndex: interval.onsetIndex,
            fromPointIndex: interval.fromPointIndex,
            toPointIndex: interval.toPointIndex,
            fromTimeSec: interval.fromTimeSec,
            toTimeSec: interval.toTimeSec,
            intervalSec: interval.intervalSec,
        })),
        records: summary.selectedRecords.map(({ instanceId, frameRecord }) => ({
            instanceId,
            ...frameRecord,
            ...resolveFrameRecordTimeBounds(frameRecord),
        })),
    };
};

export const buildSelectionAnalysisCsvMatrix = (analysis, {
    resolveFrameRecordTimeBounds = () => ({}),
    getPointForInstanceId = () => ({ x: '', y: '', z: '' }),
} = {}) => {
    const summary = analysis?.summary;
    if (!summary) return null;

    return {
        header: [
            'instanceId',
            'frameIndex',
            'rowIndex',
            'timeStartSec',
            'timeCenterSec',
            'timeEndSec',
            'sampleStart',
            'sampleCenter',
            'sampleEnd',
            'x',
            'y',
            'z',
        ],
        rows: summary.selectedRecords.map(({ instanceId, frameRecord }) => {
            const timeBounds = resolveFrameRecordTimeBounds(frameRecord);
            const point = getPointForInstanceId(instanceId) || { x: '', y: '', z: '' };
            return [
                instanceId,
                frameRecord.frameIndex,
                Number.isFinite(frameRecord.rowIndex) ? frameRecord.rowIndex : '',
                timeBounds.timeStartSec,
                timeBounds.timeCenterSec,
                timeBounds.timeEndSec,
                Number.isFinite(frameRecord.sampleStart) ? frameRecord.sampleStart : '',
                Number.isFinite(frameRecord.sampleCenter) ? frameRecord.sampleCenter : '',
                Number.isFinite(frameRecord.sampleEnd) ? frameRecord.sampleEnd : '',
                point.x,
                point.y,
                point.z,
            ];
        }),
    };
};

export const buildSelectionAnalysisIoiCsvMatrix = (analysis, {
    label = 'Selection',
    assetId = '',
    assetLabel = '',
    onsetMethod = '',
} = {}) => {
    const onsetEvents = analysis?.onsetEvents || [];
    const interOnsetIntervals = analysis?.interOnsetIntervals || [];
    const intervalsByOnsetIndex = new Map(interOnsetIntervals.map((interval) => [interval.onsetIndex, interval]));

    return {
        header: [
            'targetLabel',
            'assetId',
            'assetLabel',
            'onsetMethod',
            'onsetIndex',
            'windowIndex',
            'pointIndex',
            'frameIndex',
            'timeSec',
            'strength',
            'threshold',
            'ioiFromPreviousSec',
        ],
        rows: onsetEvents.map((event, onsetIndex) => {
            const interval = intervalsByOnsetIndex.get(onsetIndex);
            return [
                label,
                assetId,
                assetLabel,
                analysis?.onsetMethod || onsetMethod,
                onsetIndex,
                event.windowIndex,
                event.pointIndex,
                event.frameIndex,
                event.timeSec,
                event.strength,
                event.threshold,
                interval ? interval.intervalSec : '',
            ];
        }),
    };
};

export const buildConcatenatedAudioDataFromWindows = (audioBuffer, windows) => {
    if (!audioBuffer) return null;

    const normalizedWindows = (windows || []).filter((window) => Number.isFinite(window.timeStartSec) && Number.isFinite(window.timeEndSec));
    if (normalizedWindows.length === 0) return null;

    const sampleRate = audioBuffer.sampleRate;
    const totalSourceSamples = audioBuffer.length;
    const segments = normalizedWindows
        .map((window) => {
            const startSample = Math.max(0, Math.min(totalSourceSamples, Math.floor(window.timeStartSec * sampleRate)));
            const endSample = Math.min(totalSourceSamples, Math.max(startSample + 1, Math.ceil(window.timeEndSec * sampleRate)));
            if (endSample <= startSample) return null;
            return { startSample, endSample };
        })
        .filter(Boolean);
    if (segments.length === 0) return null;

    const totalSamples = segments.reduce((sum, segment) => sum + (segment.endSample - segment.startSample), 0);
    const channelData = Array.from({ length: audioBuffer.numberOfChannels }, () => new Float32Array(totalSamples));

    let writeOffset = 0;
    for (const segment of segments) {
        const segmentLength = segment.endSample - segment.startSample;
        for (let channelIndex = 0; channelIndex < audioBuffer.numberOfChannels; channelIndex++) {
            const sourceChannelData = audioBuffer.getChannelData(channelIndex);
            channelData[channelIndex].set(sourceChannelData.subarray(segment.startSample, segment.endSample), writeOffset);
        }
        writeOffset += segmentLength;
    }

    return {
        sampleRate,
        channelData,
        totalSamples,
    };
};

export const encodeAudioDataAsWavBlob = ({ sampleRate, channelData, totalSamples }) => {
    const channelCount = channelData.length;
    const bytesPerSample = 2;
    const blockAlign = channelCount * bytesPerSample;
    const dataSize = totalSamples * blockAlign;
    const buffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(buffer);
    const writeAscii = (offset, text) => {
        for (let index = 0; index < text.length; index++) {
            view.setUint8(offset + index, text.charCodeAt(index));
        }
    };

    writeAscii(0, 'RIFF');
    view.setUint32(4, 36 + dataSize, true);
    writeAscii(8, 'WAVE');
    writeAscii(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, channelCount, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * blockAlign, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bytesPerSample * 8, true);
    writeAscii(36, 'data');
    view.setUint32(40, dataSize, true);

    let writeOffset = 44;
    for (let sampleIndex = 0; sampleIndex < totalSamples; sampleIndex++) {
        for (let channelIndex = 0; channelIndex < channelCount; channelIndex++) {
            const sample = Math.max(-1, Math.min(1, channelData[channelIndex][sampleIndex] || 0));
            const pcmValue = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
            view.setInt16(writeOffset, pcmValue, true);
            writeOffset += bytesPerSample;
        }
    }

    return new Blob([buffer], { type: 'audio/wav' });
};