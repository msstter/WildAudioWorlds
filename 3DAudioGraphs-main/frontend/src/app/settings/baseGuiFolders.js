export const createBaseGuiFolders = ({
    gui,
    settings,
    sceneActions,
    hotkeyActions,
    applyGraphSettings,
    applyPerformanceSettings,
    applyLightingSettings,
    rebuildTimbreSelectionAnalysis,
    getTrajectoryPlaybackTimeSec,
    invalidateTimbreOnsetProgress,
    syncVisualizerToCurrentTime,
    updateTimbreSelectionBadge,
    updateTransportOnsetMarkers,
    refreshTerrainOnsetOverlay,
    timbreOnsetDetectionModes,
    timbreOnsetFlashModes,
} = {}) => {
    const fGraph = gui.addFolder('Graph');
    fGraph.add(settings, 'showAxesLines').name('Show Axes Lines').onChange(applyGraphSettings);
    fGraph.add(settings, 'showAxesText').name('Show Axes Text').onChange(applyGraphSettings);
    fGraph.addColor(settings, 'axesColor').name('Axes Color').onChange(applyGraphSettings);

    const axisTextControllers = [
        fGraph.add(settings, 'axesTextX').name('Axes Text X').onChange(applyGraphSettings),
        fGraph.add(settings, 'axesTextY').name('Axes Text Y').onChange(applyGraphSettings),
        fGraph.add(settings, 'axesTextZ').name('Axes Text Z').onChange(applyGraphSettings),
    ];

    const updateAxisTextEditorsVisibility = () => {
        for (const controller of axisTextControllers) {
            controller.domElement.style.display = settings.editAxesText ? '' : 'none';
        }
    };

    fGraph.add(settings, 'editAxesText').name('Edit Axes Text').onChange(() => {
        updateAxisTextEditorsVisibility();
        applyGraphSettings();
    });
    updateAxisTextEditorsVisibility();

    const fScene = gui.addFolder('Scene');
    fScene.add(sceneActions, 'openRenderOrderEditor').name('Render Order');
    fScene.addColor(settings, 'backgroundColor').name('Background').onChange(applyPerformanceSettings);
    fScene.addColor(settings, 'fogColor').name('Fog Color').onChange(applyPerformanceSettings);
    fScene.add(settings, 'fogDensity', 0, 0.01, 0.0005).name('Fog Density').onChange(applyPerformanceSettings);

    const fLight = gui.addFolder('Lighting');
    fLight.add(settings, 'enableLighting').name('Enable Lighting').onChange(applyLightingSettings);
    fLight.add(settings, 'nodeShading', ['Standard', 'Basic']).name('Node Shading').onChange(applyLightingSettings);
    fLight.add(settings, 'ambientIntensity', 0, 2, 0.05).name('Ambient Intensity').onChange(applyLightingSettings);
    fLight.add(settings, 'directionalIntensity', 0, 3, 0.05).name('Directional Intensity').onChange(applyLightingSettings);
    fLight.add(settings, 'directionalX', -300, 300, 1).name('Light X').onChange(applyLightingSettings);
    fLight.add(settings, 'directionalY', -300, 300, 1).name('Light Y').onChange(applyLightingSettings);
    fLight.add(settings, 'directionalZ', -300, 300, 1).name('Light Z').onChange(applyLightingSettings);

    const fPerf = gui.addFolder('Performance');
    fPerf.add(settings, 'maxFPS', 20, 144, 1).name('Max FPS');
    fPerf.add(settings, 'renderScale', 0.5, 1.5, 0.05).name('Render Scale').onChange(applyPerformanceSettings);
    fPerf.add(settings, 'maxBreathingNodes', 0, 400, 10).name('Breathing Node Cap');
    fPerf.add(settings, 'showLabels').name('Show Labels').onChange(applyPerformanceSettings);
    fPerf.add(settings, 'showFPSMeter').name('Show FPS Meter').onChange(applyPerformanceSettings);

    const fHotkeys = gui.addFolder('Hotkeys');
    fHotkeys.add(hotkeyActions, 'openHotkeyEditor').name('Edit Hotkeys / Controls');
    fHotkeys.add(settings, 'keyWheelStepSeconds', 0.01, 2, 0.01).name('Scroll Seek Step (sec)');
    fHotkeys.add(settings, 'keyFrameStepFrames', 1, 20, 1).name('Arrow Step (frames)');
    fHotkeys.add(settings, 'keySecondStep', 0.1, 5, 0.1).name('Shift+Arrow Step (sec)');
    fHotkeys.add(settings, 'fpvForwardFollowsLook').name('FPV W/S Follow Look');

    const fAnalysis = gui.addFolder('Analysis');
    fAnalysis.add(settings, 'timbreOnsetDetectionMode', timbreOnsetDetectionModes).name('Onset Method').onChange(() => {
        rebuildTimbreSelectionAnalysis({ adoptCurrentTimeSec: getTrajectoryPlaybackTimeSec() });
    });
    fAnalysis.add(settings, 'timbreOnsetSensitivity', 0.25, 4, 0.05).name('Onset Sensitivity').onChange(() => {
        rebuildTimbreSelectionAnalysis({ adoptCurrentTimeSec: getTrajectoryPlaybackTimeSec() });
    });
    fAnalysis.add(settings, 'timbreOnsetThresholdMultiplier', 0.25, 4, 0.05).name('Threshold Scale').onChange(() => {
        rebuildTimbreSelectionAnalysis({ adoptCurrentTimeSec: getTrajectoryPlaybackTimeSec() });
    });
    fAnalysis.add(settings, 'timbreOnsetFlashMode', timbreOnsetFlashModes).name('Flash Scope').onChange(() => {
        invalidateTimbreOnsetProgress({ clearPulses: true, adoptCurrentTimeSec: getTrajectoryPlaybackTimeSec() });
        syncVisualizerToCurrentTime();
    });
    fAnalysis.add(settings, 'showTransportOnsetMarkers').name('Transport Markers').onChange(updateTransportOnsetMarkers);

    const fNodeOnsets = fAnalysis.addFolder('Node: Onsets');
    fNodeOnsets.add(settings, 'enableNodeFlash').name('Nodes Flash').onChange(() => {
        invalidateTimbreOnsetProgress({ clearPulses: true, adoptCurrentTimeSec: getTrajectoryPlaybackTimeSec() });
        syncVisualizerToCurrentTime();
    });
    fNodeOnsets.addColor(settings, 'nodeFlashColor').name('Flash Color').onChange(syncVisualizerToCurrentTime);
    fNodeOnsets.add(settings, 'nodeFlashDurationMs', 40, 1200, 10).name('Flash Duration (ms)');
    fNodeOnsets.add(settings, 'nodeFlashBrightness', 0, 2.5, 0.05).name('Flash Brightness').onChange(syncVisualizerToCurrentTime);
    fNodeOnsets.add(settings, 'showSelectionMenu').name('Selection Menu').onChange(updateTimbreSelectionBadge);
    fNodeOnsets.add(settings, 'showNodeSelectionMenu').name('Node Selection Menu').onChange(updateTimbreSelectionBadge);

    const fTerrainOnsets = fAnalysis.addFolder('Terrain Onsets');
    fTerrainOnsets.add(settings, 'showTerrainOnsetsInModel').name('Show Onsets in Model').onChange(() => {
        refreshTerrainOnsetOverlay?.();
    });
    fTerrainOnsets.add(settings, 'enableTerrainOnsetEditor').name('Onset Editor').onChange(() => {
        refreshTerrainOnsetOverlay?.();
    });

    return {
        fGraph,
        updateAxisTextEditorsVisibility,
    };
};