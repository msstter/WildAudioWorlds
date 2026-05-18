export const createModeAudioFolder = ({ gui } = {}) => gui.addFolder('Mode_Audio/Data');

export const createModeTerrainGuiFolders = ({
    gui,
    modeAudioFolder,
    settings,
    modeActions,
    timbreSelectionActions,
    terrainHelperPreferences,
    terrainAxisValueModes,
    terrain2DGraphMeta,
    terrain2DGraphShowModes,
    terrain2DGraphTypes,
    terrain2DGraphSurfaces,
    applyVisualizationMode,
    updateSelectionPlaybackMask,
    updateTimbreSelectionBadge,
    applyTerrainSettings,
    applyTerrainAmplitudeScale,
    terrainVisualizer,
    applyTerrainHelperPreference,
    rebuildTerrainAxisColorControls,
    ensureTerrain2DGraphSettings,
    applyTerrain2DGraphSettings,
    buildTerrainGraphControls,
    terrainScaleControlRegistry,
    isTerrainMode,
    buildTerrainAxes,
    applyTerrainGraphSettings,
    updateLabelRendererVisibility,
    applyTerrainAxisScaling,
    applyTerrainAutoPaddingSettings,
    applyTerrainStretch,
} = {}) => {
    modeAudioFolder.add(settings, 'visualizationMode', ['TimbreCube', 'SpectroTerrain'])
        .name('Pipeline')
        .onChange(() => {
            applyVisualizationMode();
        });
    modeAudioFolder.add(settings, 'accumulateView').name('Accumulate View');
    modeAudioFolder.add(settings, 'enableSelectionPlaybackMask').name('Mask To Selection').onChange(() => {
        updateSelectionPlaybackMask();
        updateTimbreSelectionBadge();
    });
    modeAudioFolder.add(modeActions, 'resetGraph').name('Reset Graph');

    const fTimbreSelectionActions = modeAudioFolder.addFolder('Selection Actions');
    fTimbreSelectionActions.add(timbreSelectionActions, 'playSelection').name('Play Selection');
    fTimbreSelectionActions.add(timbreSelectionActions, 'jumpToSelection').name('Jump To First Window');
    fTimbreSelectionActions.add(timbreSelectionActions, 'clearSelection').name('Clear Selection');
    fTimbreSelectionActions.add(timbreSelectionActions, 'invertSelection').name('Invert Selection');
    fTimbreSelectionActions.add(timbreSelectionActions, 'exportSelectionJson').name('Export Selection JSON');
    fTimbreSelectionActions.add(timbreSelectionActions, 'exportSelectionCsv').name('Export Selection CSV');
    fTimbreSelectionActions.add(timbreSelectionActions, 'exportSelectionAudio').name('Export Selection Audio');
    fTimbreSelectionActions.add(timbreSelectionActions, 'exportSelectionIoiCsv').name('Export Onsets + IOI CSV');
    fTimbreSelectionActions.add(timbreSelectionActions, 'exportSelectionIoiCsv2').name('Export Onsets + IOI 2');

    const fSelectionSculpt = gui.addFolder('Selection Sculpt (Full Mask)');
    const fTerrain = gui.addFolder('Terrain (FFT Spectrogram)');
    fTerrain.add(settings, 'terrainFrequencyBins', [128, 256, 512]).name('Frequency Bins').onChange(applyTerrainSettings);
    fTerrain.add(settings, 'terrainTimeDepth', 40, 320, 1).name('Time Depth').onChange(applyTerrainSettings);
    fTerrain.add(settings, 'terrainAmplitudeScale', 1, 120, 1).name('Amplitude Scale').onChange(applyTerrainAmplitudeScale);
    fTerrain.add(settings, 'terrainSmoothing', 0, 0.95, 0.01).name('Smoothing');
    fTerrain.add(settings, 'terrainOpacity', 0.1, 1, 0.01).name('Opacity').onChange(() => terrainVisualizer.setSettings(settings));
    fTerrain.add(settings, 'terrainWireframe').name('Wireframe').onChange(() => terrainVisualizer.setSettings(settings));

    const fTerrainHelpers = fTerrain.addFolder('Precomputed Helpers');
    fTerrainHelpers.add(settings, 'terrainHelperPreference', terrainHelperPreferences).name('Helper Preference').onChange(applyTerrainHelperPreference);

    const fTerrainAxisColors = fTerrain.addFolder('Axis Colors');
    const terrainAxisColorValueModeController = fTerrainAxisColors.add(settings, 'terrainAxisColorValueMode', terrainAxisValueModes).name('Breakpoint Units').onChange(() => {
        rebuildTerrainAxisColorControls();
    });

    const fTerrain2DGraphs = fTerrain.addFolder('2D Graphs');
    const terrain2DGraphs = ensureTerrain2DGraphSettings();
    for (const [graphKey, graphMeta] of Object.entries(terrain2DGraphMeta)) {
        const graphSettings = terrain2DGraphs[graphKey];
        const graphFolder = fTerrain2DGraphs.addFolder(graphMeta.label);
        const showGraphsController = graphFolder.add(graphSettings, 'showGraphsAs', terrain2DGraphShowModes).name('Show Graphs as:');
        graphFolder.add(graphSettings, 'enabled').name('Enabled').onChange(applyTerrain2DGraphSettings);
        graphFolder.add(graphSettings, 'graphType', terrain2DGraphTypes).name('2D Graph Type').onChange(applyTerrain2DGraphSettings);
        graphFolder.add(graphSettings, 'surface', terrain2DGraphSurfaces).name('Surface').onChange(applyTerrain2DGraphSettings);
        graphFolder.add(graphSettings, 'graphOpacity', 0, 1, 0.01).name('Graph Opacity').onChange(applyTerrain2DGraphSettings);
        graphFolder.add(graphSettings, 'heatStrength', 0, 3, 0.01).name('Heat Strength').onChange(applyTerrain2DGraphSettings);
        graphFolder.add(graphSettings, 'offset', 0, 3, 0.01).name('Graph Offset').onChange(applyTerrain2DGraphSettings);
        const extendBeforeController = graphFolder.add(graphSettings, 'extendBefore', 0, 10000, 1).name('Extend Before:').onChange(applyTerrain2DGraphSettings);
        const extendAfterController = graphFolder.add(graphSettings, 'extendAfter', 0, 10000, 1).name('Extend After:').onChange(applyTerrain2DGraphSettings);

        const syncExtendedGraphModeVisibility = () => {
            const showExtendControls = graphSettings.showGraphsAs === 'Extended 2D Graphs' || graphSettings.showGraphsAs === 'Both';
            extendBeforeController.domElement.style.display = showExtendControls ? '' : 'none';
            extendAfterController.domElement.style.display = showExtendControls ? '' : 'none';
        };

        showGraphsController.onChange(() => {
            syncExtendedGraphModeVisibility();
            applyTerrain2DGraphSettings();
        });
        syncExtendedGraphModeVisibility();

        const backgroundFolder = graphFolder.addFolder('Background');
        backgroundFolder.add(graphSettings, 'backgroundEnabled').name('Enabled').onChange(applyTerrain2DGraphSettings);
        backgroundFolder.addColor(graphSettings, 'backgroundColor').name('Color').onChange(applyTerrain2DGraphSettings);
        backgroundFolder.add(graphSettings, 'backgroundOpacity', 0, 1, 0.01).name('Opacity').onChange(applyTerrain2DGraphSettings);
    }

    buildTerrainGraphControls({
        terrainFolder: fTerrain,
        settings,
        isTerrainMode,
        buildTerrainAxes,
        applyTerrainGraphSettings,
        updateLabelRendererVisibility,
        applyTerrainAxisScaling,
        applyTerrainAutoPaddingSettings,
        applyTerrainStretch,
        controlRegistry: terrainScaleControlRegistry,
    });

    return {
        fSelectionSculpt,
        fTerrain,
        fTerrainAxisColors,
        terrainAxisColorValueModeController,
        fTimbreSelectionActions,
    };
};

export const createLineNodeGuiFolders = ({
    gui,
    settings,
    modifierColumnOptions,
    syncVisualizerToCurrentTime,
    invalidateTimbreOnsetProgress,
    getTrajectoryPlaybackTimeSec,
} = {}) => {
    const syncAllGuiControllers = () => {
        gui.controllersRecursive().forEach((controller) => controller.updateDisplay());
    };

    const fLines = gui.addFolder('Lines');
    fLines.add(settings, 'showLine').name('Show').onChange(syncVisualizerToCurrentTime);
    fLines.add(settings, 'deconstructiveLine').name('Deconstructive').onChange(syncVisualizerToCurrentTime);
    fLines.addColor(settings, 'lineColor').name('Base Color').onChange(syncVisualizerToCurrentTime);

    const fLineScaleBrightness = fLines.addFolder('Line Thickness & Brightness');
    fLineScaleBrightness.add(settings, 'enableLineScaleEnhancer').name('Line Scale Enhancer').onChange(syncVisualizerToCurrentTime);
    fLineScaleBrightness.add(settings, 'showLineThickness').name('Show Thickness').onChange(syncVisualizerToCurrentTime);
    const lineThickness = fLineScaleBrightness.add(settings, 'lineThicknessDataColumn', modifierColumnOptions).name('Thickness Data Used').onChange(syncVisualizerToCurrentTime);
    fLineScaleBrightness.add(settings, 'lineThicknessMin', 0.5, 40, 0.1).name('Min Thickness').onChange(syncVisualizerToCurrentTime);
    fLineScaleBrightness.add(settings, 'lineThicknessMax', 0.5, 40, 0.1).name('Max Thickness').onChange(syncVisualizerToCurrentTime);
    fLineScaleBrightness.add(settings, 'showLineBrightness').name('Show Brightness').onChange(syncVisualizerToCurrentTime);
    const lineBrightness = fLineScaleBrightness.add(settings, 'lineBrightnessDataColumn', modifierColumnOptions).name('Brightness Data Used').onChange(syncVisualizerToCurrentTime);
    fLineScaleBrightness.add(settings, 'lineBrightnessMin', 0, 1, 0.01).name('Min Brightness').onChange(syncVisualizerToCurrentTime);
    fLineScaleBrightness.add(settings, 'lineBrightnessMax', 0, 1, 0.01).name('Max Brightness').onChange(syncVisualizerToCurrentTime);

    const fLineHueRotation = fLines.addFolder('Line Hue-Rotation');
    fLineHueRotation.add(settings, 'showLineHueRotation').name('Show Hue Rotation').onChange(syncVisualizerToCurrentTime);
    const lineHue = fLineHueRotation.add(settings, 'lineHueDataColumn', modifierColumnOptions).name('Hue Data Used').onChange(syncVisualizerToCurrentTime);
    fLineHueRotation.addColor(settings, 'lineHueLowColor').name('Low Hue').onChange(syncVisualizerToCurrentTime);
    fLineHueRotation.addColor(settings, 'lineHueHighColor').name('High Hue').onChange(syncVisualizerToCurrentTime);
    const lineHueActions = {
        swapHues: () => {
            const temp = settings.lineHueLowColor;
            settings.lineHueLowColor = settings.lineHueHighColor;
            settings.lineHueHighColor = temp;
            syncAllGuiControllers();
            syncVisualizerToCurrentTime();
        },
    };
    fLineHueRotation.add(lineHueActions, 'swapHues').name('Swap Hues');

    const fLineDecay = fLines.addFolder('Line: Decay  (shortens tail)');
    fLineDecay.add(settings, 'enableLineDecay').name('Enable').onChange(syncVisualizerToCurrentTime);
    fLineDecay.add(settings, 'lineDecayTailLength', 10, 300, 1).name('Tail Length').onChange(syncVisualizerToCurrentTime);

    const fLineDull = fLines.addFolder('Line: Dull  (colour fades along tail)');
    fLineDull.add(settings, 'enableLineDull').name('Enable').onChange(syncVisualizerToCurrentTime);
    fLineDull.add(settings, 'lineDullTailLength', 10, 500, 1).name('Tail Length').onChange(syncVisualizerToCurrentTime);
    fLineDull.addColor(settings, 'lineDullColor').name('Dull Target Color').onChange(syncVisualizerToCurrentTime);

    const fLineBreathing = fLines.addFolder('Line: Breathing / Waveform');
    fLineBreathing.add(settings, 'enableLineBreathing').name('Enable Waveform Effect').onChange(syncVisualizerToCurrentTime);
    fLineBreathing.add(settings, 'lineBreathingAmplitude', 0, 5, 0.1).name('Amplitude Modifier').onChange(syncVisualizerToCurrentTime);

    const fNodes = gui.addFolder('Nodes');
    fNodes.add(settings, 'showNodes').name('Show').onChange(syncVisualizerToCurrentTime);
    fNodes.add(settings, 'deconstructiveNodes').name('Deconstructive').onChange(syncVisualizerToCurrentTime);

    const fNodeScaleBrightness = fNodes.addFolder('Node Scale & Brightness');
    fNodeScaleBrightness.add(settings, 'showNodeScale').name('Show Scale').onChange(syncVisualizerToCurrentTime);
    const nodeScale = fNodeScaleBrightness.add(settings, 'nodeScaleDataColumn', modifierColumnOptions).name('Scale Data Used').onChange(syncVisualizerToCurrentTime);
    fNodeScaleBrightness.add(settings, 'nodeScaleMin', 0, 8, 0.05).name('Min Scale').onChange(syncVisualizerToCurrentTime);
    fNodeScaleBrightness.add(settings, 'nodeScaleMax', 0, 8, 0.05).name('Max Scale').onChange(syncVisualizerToCurrentTime);
    fNodeScaleBrightness.add(settings, 'showNodeBrightness').name('Show Brightness').onChange(syncVisualizerToCurrentTime);
    const nodeBrightness = fNodeScaleBrightness.add(settings, 'nodeBrightnessDataColumn', modifierColumnOptions).name('Brightness Data Used').onChange(syncVisualizerToCurrentTime);
    fNodeScaleBrightness.add(settings, 'nodeBrightnessMin', 0, 1, 0.01).name('Min Brightness').onChange(syncVisualizerToCurrentTime);
    fNodeScaleBrightness.add(settings, 'nodeBrightnessMax', 0, 1, 0.01).name('Max Brightness').onChange(syncVisualizerToCurrentTime);

    const fNodeHueRotation = fNodes.addFolder('Node Hue-Rotation');
    fNodeHueRotation.add(settings, 'showNodeHueRotation').name('Show Hue Rotation').onChange(syncVisualizerToCurrentTime);
    const nodeHue = fNodeHueRotation.add(settings, 'nodeHueDataColumn', modifierColumnOptions).name('Hue Data Used').onChange(syncVisualizerToCurrentTime);
    fNodeHueRotation.addColor(settings, 'hueLowColor').name('Low Hue').onChange(syncVisualizerToCurrentTime);
    fNodeHueRotation.addColor(settings, 'hueHighColor').name('High Hue').onChange(syncVisualizerToCurrentTime);
    const nodeHueActions = {
        swapHues: () => {
            const temp = settings.hueLowColor;
            settings.hueLowColor = settings.hueHighColor;
            settings.hueHighColor = temp;
            syncAllGuiControllers();
            syncVisualizerToCurrentTime();
        },
    };
    fNodeHueRotation.add(nodeHueActions, 'swapHues').name('Swap Hues');

    const fNodeDecay = fNodes.addFolder('Node: Decay  (size fades to 0)');
    fNodeDecay.add(settings, 'enableDecay').name('Enable').onChange(syncVisualizerToCurrentTime);
    fNodeDecay.add(settings, 'decayTailLength', 10, 300, 1).name('Tail Length').onChange(syncVisualizerToCurrentTime);

    const fNodeDull = fNodes.addFolder('Node: Dull  (colour fades)');
    fNodeDull.add(settings, 'enableDull').name('Enable').onChange(syncVisualizerToCurrentTime);
    fNodeDull.add(settings, 'dullTailLength', 10, 500, 1).name('Tail Length').onChange(syncVisualizerToCurrentTime);
    fNodeDull.addColor(settings, 'dullColor').name('Dull Target Color').onChange(syncVisualizerToCurrentTime);

    const fBreath = fNodes.addFolder('Node: Breathing');
    fBreath.add(settings, 'enableBreathing').name('Enable Breathing');
    fBreath.add(settings, 'jitterIntensity', 0, 8, 0.1).name('Jitter Intensity');

    return {
        fLines,
        fNodes,
        modifierControllers: {
            nodeScale,
            nodeBrightness,
            nodeHue,
            lineThickness,
            lineBrightness,
            lineHue,
        },
    };
};