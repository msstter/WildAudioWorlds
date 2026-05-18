import * as THREE from 'three';

export const createTimbreTransportRuntime = ({
    audio,
    getAudioContext,
    getTrajectoryDurationSec,
    getAnalysisHopDurationSec,
    getSelectionAnalysisState,
    trajectoryVisualizer,
    isTerrainMode,
    getEnableSelectionPlaybackMask,
    getEnableNodeFlash,
    highlightOnset,
    onsetResetMinSec = 0.2,
    nowFactory = () => globalThis.performance?.now?.() ?? Date.now(),
} = {}) => {
    const trajectoryPlaybackAnchor = {
        mediaTimeSec: 0,
        contextTimeSec: 0,
        playbackRate: 1,
        isActive: false,
    };

    let playbackMaskGain = null;
    let playbackMaskGainTarget = 1;

    const getMediaElementPlaybackTimeSec = () => {
        const currentTimeSec = Number(audio?.currentTime);
        return Number.isFinite(currentTimeSec) ? Math.max(0, currentTimeSec) : 0;
    };

    const attachPlaybackMaskGain = (gainNode) => {
        playbackMaskGain = gainNode || null;
        if (playbackMaskGain) {
            playbackMaskGain.gain.value = playbackMaskGainTarget;
        }
    };

    const resetPlaybackAnchor = (mediaTimeSec = getMediaElementPlaybackTimeSec()) => {
        const durationSec = getTrajectoryDurationSec?.() || 0;
        const audioContext = getAudioContext?.() || null;
        const clampedTimeSec = durationSec > 0
            ? THREE.MathUtils.clamp(mediaTimeSec, 0, durationSec)
            : Math.max(0, mediaTimeSec);

        trajectoryPlaybackAnchor.mediaTimeSec = clampedTimeSec;
        trajectoryPlaybackAnchor.contextTimeSec = audioContext ? audioContext.currentTime : 0;
        trajectoryPlaybackAnchor.playbackRate = Number.isFinite(audio?.playbackRate) ? audio.playbackRate : 1;
        trajectoryPlaybackAnchor.isActive = !!audioContext && !audio?.paused && audioContext.state === 'running';
    };

    const getPlaybackTimeSec = () => {
        const durationSec = getTrajectoryDurationSec?.() || 0;
        const mediaTimeSec = getMediaElementPlaybackTimeSec();
        const audioContext = getAudioContext?.() || null;

        if (!audioContext || !trajectoryPlaybackAnchor.isActive || audio?.paused || audioContext.state !== 'running') {
            return durationSec > 0
                ? THREE.MathUtils.clamp(mediaTimeSec, 0, durationSec)
                : mediaTimeSec;
        }

        const elapsedSec = Math.max(0, audioContext.currentTime - trajectoryPlaybackAnchor.contextTimeSec);
        const anchoredTimeSec = trajectoryPlaybackAnchor.mediaTimeSec + (elapsedSec * trajectoryPlaybackAnchor.playbackRate);
        return durationSec > 0
            ? THREE.MathUtils.clamp(anchoredTimeSec, 0, durationSec)
            : Math.max(0, anchoredTimeSec);
    };

    const setPlaybackMaskGainTarget = (targetGain) => {
        const clampedTarget = targetGain > 0 ? 1 : 0;
        const audioContext = getAudioContext?.() || null;
        const graphAtTarget = !playbackMaskGain || !audioContext
            ? true
            : Math.abs(playbackMaskGain.gain.value - clampedTarget) < 0.001;

        if (Math.abs(playbackMaskGainTarget - clampedTarget) < 0.001 && graphAtTarget) return;

        playbackMaskGainTarget = clampedTarget;
        if (!playbackMaskGain || !audioContext) return;

        playbackMaskGain.gain.cancelScheduledValues(audioContext.currentTime);
        playbackMaskGain.gain.setTargetAtTime(clampedTarget, audioContext.currentTime, 0.008);
    };

    const updateSelectionPlaybackMask = (playbackTimeSec = getPlaybackTimeSec()) => {
        const selectionAnalysis = getSelectionAnalysisState?.();
        const contiguousWindows = selectionAnalysis?.contiguousWindows || [];

        if (!getEnableSelectionPlaybackMask?.() || contiguousWindows.length === 0) {
            setPlaybackMaskGainTarget(1);
            return;
        }

        const paddingSec = Math.max(0.005, (getAnalysisHopDurationSec?.() || 0) * 0.6);
        const insideWindow = contiguousWindows.some((window) =>
            playbackTimeSec >= (window.timeStartSec - paddingSec) &&
            playbackTimeSec <= (window.timeEndSec + paddingSec)
        );
        setPlaybackMaskGainTarget(insideWindow ? 1 : 0);
    };

    const resetRuntime = (playbackTimeSec = getPlaybackTimeSec(), { clearPulses = true } = {}) => {
        if (clearPulses) trajectoryVisualizer?.clearOnsetPulses?.();

        const selectionAnalysis = getSelectionAnalysisState?.();
        if (selectionAnalysis) {
            selectionAnalysis.lastPlaybackTimeSec = playbackTimeSec;
        }
    };

    const advanceOnsetPulses = (playbackTimeSec, nowMs = nowFactory()) => {
        const selectionAnalysis = getSelectionAnalysisState?.();
        const onsetEvents = selectionAnalysis?.onsetEvents || [];

        if (!getEnableNodeFlash?.() || onsetEvents.length === 0) {
            if (!getEnableNodeFlash?.()) trajectoryVisualizer?.clearOnsetPulses?.();
            if (selectionAnalysis) {
                selectionAnalysis.lastPlaybackTimeSec = playbackTimeSec;
            }
            return;
        }

        const lastPlaybackTimeSec = selectionAnalysis?.lastPlaybackTimeSec;
        const jumpResetThresholdSec = Math.max(onsetResetMinSec, Math.abs(audio?.playbackRate || 0) * 0.25);

        if (!Number.isFinite(lastPlaybackTimeSec)) {
            if (selectionAnalysis) {
                selectionAnalysis.lastPlaybackTimeSec = playbackTimeSec;
            }
            return;
        }

        if (playbackTimeSec < lastPlaybackTimeSec || (playbackTimeSec - lastPlaybackTimeSec) > jumpResetThresholdSec) {
            trajectoryVisualizer?.clearOnsetPulses?.();
            if (selectionAnalysis) {
                selectionAnalysis.lastPlaybackTimeSec = playbackTimeSec;
            }
            return;
        }

        for (const onsetEvent of onsetEvents) {
            if (onsetEvent.timeSec > lastPlaybackTimeSec && onsetEvent.timeSec <= playbackTimeSec + 1e-6) {
                highlightOnset?.(selectionAnalysis, onsetEvent, { nowMs });
            }
        }

        if (selectionAnalysis) {
            selectionAnalysis.lastPlaybackTimeSec = playbackTimeSec;
        }
    };

    const syncVisualizerToCurrentTime = () => {
        if (isTerrainMode?.()) return;
        trajectoryVisualizer?.syncToTime?.(getPlaybackTimeSec(), getTrajectoryDurationSec?.() || 0);
    };

    return {
        advanceOnsetPulses,
        attachPlaybackMaskGain,
        getPlaybackTimeSec,
        resetPlaybackAnchor,
        resetRuntime,
        syncVisualizerToCurrentTime,
        updateSelectionPlaybackMask,
    };
};