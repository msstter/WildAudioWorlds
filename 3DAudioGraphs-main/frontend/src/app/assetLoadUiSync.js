const MODIFIER_SETTING_KEYS = [
    'nodeScaleDataColumn',
    'nodeBrightnessDataColumn',
    'nodeHueDataColumn',
    'lineThicknessDataColumn',
    'lineBrightnessDataColumn',
    'lineHueDataColumn',
];

const syncControllerOptions = (controller, options) => {
    if (!controller || typeof controller.options !== 'function') return;
    controller.options(options);
    controller.updateDisplay();
};

export const createAssetLoadUiSync = ({
    settings,
    modifierColumnOptions,
    modifierControllers,
    terrainVisualizer,
    applyTerrainAxisScaling,
    buildAcademicAxes,
    applyRenderOrderSettings,
    applyLightingSettings,
    applyGraphSettings,
    applyVisualizationMode,
    syncVisualizerToCurrentTime,
    updateTransportOnsetMarkers,
} = {}) => {
    const syncModifierColumnOptions = (bounds) => {
        if (!Array.isArray(bounds?.modifierColumns) || bounds.modifierColumns.length === 0) return;

        modifierColumnOptions.splice(0, modifierColumnOptions.length, ...bounds.modifierColumns);

        for (const settingKey of MODIFIER_SETTING_KEYS) {
            if (!modifierColumnOptions.includes(settings[settingKey])) {
                settings[settingKey] = modifierColumnOptions[0];
            }
        }

        syncControllerOptions(modifierControllers?.nodeScale, modifierColumnOptions);
        syncControllerOptions(modifierControllers?.nodeBrightness, modifierColumnOptions);
        syncControllerOptions(modifierControllers?.nodeHue, modifierColumnOptions);
        syncControllerOptions(modifierControllers?.lineThickness, modifierColumnOptions);
        syncControllerOptions(modifierControllers?.lineBrightness, modifierColumnOptions);
        syncControllerOptions(modifierControllers?.lineHue, modifierColumnOptions);
    };

    const handleAssetLoaded = ({ bounds } = {}) => {
        terrainVisualizer?.setSettings(settings);
        applyTerrainAxisScaling?.({ syncFromAuto: !settings.terrainManualScaling });
        syncModifierColumnOptions(bounds);
        buildAcademicAxes?.(bounds);
        applyRenderOrderSettings?.();
        applyLightingSettings?.();
        applyGraphSettings?.();
        applyVisualizationMode?.();
        syncVisualizerToCurrentTime?.();
        updateTransportOnsetMarkers?.();
    };

    return {
        handleAssetLoaded,
        syncModifierColumnOptions,
    };
};