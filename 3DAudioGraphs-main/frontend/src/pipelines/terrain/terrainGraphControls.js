export const createTerrainScaleControlRegistry = ({ settings } = {}) => {
    let manualScalingController = null;
    let scaleValueControllers = [];
    let autoPaddingControllers = [];

    const setControllerEnabled = (controller, enabled) => {
        if (!controller?.domElement) return;
        controller.domElement.style.pointerEvents = enabled ? '' : 'none';
        controller.domElement.style.opacity = enabled ? '1' : '0.55';
    };

    const register = ({
        manualScalingController: nextManualScalingController = null,
        scaleValueControllers: nextScaleValueControllers = [],
        autoPaddingControllers: nextAutoPaddingControllers = [],
    } = {}) => {
        manualScalingController = nextManualScalingController;
        scaleValueControllers = Array.isArray(nextScaleValueControllers)
            ? nextScaleValueControllers.filter(Boolean)
            : [];
        autoPaddingControllers = Array.isArray(nextAutoPaddingControllers)
            ? nextAutoPaddingControllers.filter(Boolean)
            : [];
    };

    const syncDisplays = () => {
        if (manualScalingController) manualScalingController.updateDisplay();

        const manualEnabled = !!settings?.terrainManualScaling;
        for (const controller of scaleValueControllers) {
            controller.updateDisplay();
            setControllerEnabled(controller, manualEnabled);
        }
        for (const controller of autoPaddingControllers) {
            controller.updateDisplay();
            setControllerEnabled(controller, !manualEnabled);
        }
    };

    return {
        register,
        syncDisplays,
    };
};

export const buildTerrainGraphControls = ({
    terrainFolder,
    settings,
    isTerrainMode,
    buildTerrainAxes,
    applyTerrainGraphSettings,
    updateLabelRendererVisibility,
    applyTerrainAxisScaling,
    applyTerrainAutoPaddingSettings,
    applyTerrainStretch,
    controlRegistry,
} = {}) => {
    const terrainGraphFolder = terrainFolder.addFolder('Graph');
    terrainGraphFolder.add(settings, 'terrainShowAxesLines').name('Show Axes Lines').onChange(applyTerrainGraphSettings);
    terrainGraphFolder.add(settings, 'terrainShowAxesText').name('Show Axes Text').onChange(() => {
        applyTerrainGraphSettings();
        updateLabelRendererVisibility();
    });
    terrainGraphFolder.addColor(settings, 'terrainAxesColor').name('Axes Color').onChange(applyTerrainGraphSettings);
    terrainGraphFolder.add(settings, 'terrainAxesTextFreq').name('Freq Axis Label').onChange(() => {
        if (isTerrainMode()) buildTerrainAxes();
    });
    terrainGraphFolder.add(settings, 'terrainAxesTextAmp').name('Amp Axis Label').onChange(() => {
        if (isTerrainMode()) buildTerrainAxes();
    });
    terrainGraphFolder.add(settings, 'terrainAxesTextTime').name('Time Axis Label').onChange(() => {
        if (isTerrainMode()) buildTerrainAxes();
    });

    const terrainAxisScalingFolder = terrainGraphFolder.addFolder('Axis Scaling');
    const terrainManualScalingController = terrainAxisScalingFolder.add(settings, 'terrainManualScaling').name('Manual Scaling').onChange(() => {
        applyTerrainAxisScaling({ syncFromAuto: !settings.terrainManualScaling });
    });
    const terrainScaleFreqMinController = terrainAxisScalingFolder.add(settings, 'terrainScaleFreqMin').name('Freq Min').onChange(() => {
        if (settings.terrainManualScaling) applyTerrainAxisScaling();
    });
    const terrainScaleFreqMaxController = terrainAxisScalingFolder.add(settings, 'terrainScaleFreqMax').name('Freq Max').onChange(() => {
        if (settings.terrainManualScaling) applyTerrainAxisScaling();
    });
    const terrainScaleAmpMinController = terrainAxisScalingFolder.add(settings, 'terrainScaleAmpMin').name('Amp Min').onChange(() => {
        if (settings.terrainManualScaling) applyTerrainAxisScaling();
    });
    const terrainScaleAmpMaxController = terrainAxisScalingFolder.add(settings, 'terrainScaleAmpMax').name('Amp Max').onChange(() => {
        if (settings.terrainManualScaling) applyTerrainAxisScaling();
    });
    const terrainScaleTimeMinController = terrainAxisScalingFolder.add(settings, 'terrainScaleTimeMin').name('Time Min').onChange(() => {
        if (settings.terrainManualScaling) applyTerrainAxisScaling();
    });
    const terrainScaleTimeMaxController = terrainAxisScalingFolder.add(settings, 'terrainScaleTimeMax').name('Time Max').onChange(() => {
        if (settings.terrainManualScaling) applyTerrainAxisScaling();
    });

    const terrainAutoPaddingFolder = terrainAxisScalingFolder.addFolder('Auto Padding');
    const terrainAutoPadFreqController = terrainAutoPaddingFolder.add(settings, 'terrainAutoPadFreqPercent', 0, 100, 0.5).name('Freq Pad %').onChange(() => {
        if (!settings.terrainManualScaling) applyTerrainAutoPaddingSettings();
    });
    const terrainAutoPadAmpController = terrainAutoPaddingFolder.add(settings, 'terrainAutoPadAmpPercent', 0, 100, 0.5).name('Amp Headroom %').onChange(() => {
        if (!settings.terrainManualScaling) applyTerrainAutoPaddingSettings();
    });

    controlRegistry?.register({
        manualScalingController: terrainManualScalingController,
        scaleValueControllers: [
            terrainScaleFreqMinController,
            terrainScaleFreqMaxController,
            terrainScaleAmpMinController,
            terrainScaleAmpMaxController,
            terrainScaleTimeMinController,
            terrainScaleTimeMaxController,
        ],
        autoPaddingControllers: [
            terrainAutoPadFreqController,
            terrainAutoPadAmpController,
        ],
    });
    controlRegistry?.syncDisplays();

    const terrainStretchFolder = terrainGraphFolder.addFolder('Axis Stretch');
    terrainStretchFolder.add(settings, 'terrainStretchFreq', 0.25, 10, 0.01).name('Frequency').onChange(applyTerrainStretch);
    terrainStretchFolder.add(settings, 'terrainStretchAmp', 0.25, 10, 0.01).name('Amplitude').onChange(applyTerrainStretch);
    terrainStretchFolder.add(settings, 'terrainStretchTime', 0.25, 10, 0.01).name('Time').onChange(applyTerrainStretch);

    return {
        terrainGraphFolder,
        terrainAxisScalingFolder,
        terrainAutoPaddingFolder,
        terrainStretchFolder,
    };
};