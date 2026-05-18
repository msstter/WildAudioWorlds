export const createAnimationLoop = ({
    controls,
    settings,
    getPlaybackTimeSec,
    updateSelectionPlaybackMask,
    isTerrainMode,
    terrainController,
    getTrajectoryDurationSec,
    advanceTimbreSelectionOnsetPulses,
    trajectoryVisualizer,
    readFrequencyFrame,
    renderer,
    scene,
    camera,
    shouldRenderAxisLabels,
    labelRenderer,
    fpsMeter,
    updateTerrainHelperIndicator,
    updateTerrainModeRuntime,
    updateCameraMotion,
    shouldUpdateControls = () => true,
    requestFrame = requestAnimationFrame,
    performanceObject = performance,
} = {}) => {
    let started = false;
    let lastFrameTime = 0;
    let fpsSampleStart = performanceObject.now();
    let fpsSampleFrames = 0;

    const updateFpsMeter = (now) => {
        if (!settings?.showFPSMeter || !fpsMeter) return;
        fpsSampleFrames += 1;
        const elapsed = now - fpsSampleStart;
        if (elapsed >= 400) {
            const fps = Math.round((fpsSampleFrames * 1000) / elapsed);
            fpsMeter.textContent = `FPS ${fps}`;
            fpsSampleFrames = 0;
            fpsSampleStart = now;
        }
    };

    const animate = () => {
        requestFrame(animate);

        const now = performanceObject.now();
        const frameBudgetMs = 1000 / Math.max(20, settings?.maxFPS || 20);
        if (lastFrameTime && (now - lastFrameTime) < frameBudgetMs) {
            if (shouldUpdateControls?.()) {
                controls?.update?.();
            }
            return;
        }
        const deltaSec = lastFrameTime ? (now - lastFrameTime) / 1000 : frameBudgetMs / 1000;
        lastFrameTime = now;

        updateCameraMotion?.(deltaSec, now);
        if (shouldUpdateControls?.()) {
            controls?.update?.();
        }

        const playbackTimeSec = getPlaybackTimeSec?.() || 0;
        updateSelectionPlaybackMask?.(playbackTimeSec);

        if (isTerrainMode?.()) {
            terrainController?.runFrame({
                playbackTimeSec,
                durationSec: getTrajectoryDurationSec?.() || 0,
            });
            updateTerrainModeRuntime?.({
                playbackTimeSec,
                durationSec: getTrajectoryDurationSec?.() || 0,
                now,
            });
        } else {
            advanceTimbreSelectionOnsetPulses?.(playbackTimeSec, now);
            trajectoryVisualizer?.syncToTime?.(playbackTimeSec, getTrajectoryDurationSec?.() || 0);

            const liveFrequencyFrame = settings?.enableBreathing ? readFrequencyFrame?.() : null;
            if (liveFrequencyFrame) {
                const totalAmplitude = liveFrequencyFrame.reduce((accumulator, value) => accumulator + value, 0);
                const normalizedAmplitude = (totalAmplitude / liveFrequencyFrame.length) / 255;
                trajectoryVisualizer?.applyBreathing?.(normalizedAmplitude);
            }
        }

        renderer?.render?.(scene, camera);
        if (shouldRenderAxisLabels?.()) {
            labelRenderer?.render?.(scene, camera);
        }
        updateFpsMeter(now);
        updateTerrainHelperIndicator?.();
    };

    return {
        start: () => {
            if (started) return;
            started = true;
            animate();
        },
    };
};