export const createTimbrePlaneSelectionControls = ({
    modeAudioFolder,
    ensureTimbrePlaneSelectionSettings,
    planeSelectionMeta,
    planeSelectionModes,
    selectionGrabTypes,
    rebuildVisuals,
    applySettings,
    cancelActiveLassoDraw,
    startLassoDraw,
    getActiveLassoDraw,
    completeActiveLassoDraw,
    clearPlaneLasso,
    bindGuiFolderTitleShortcuts,
} = {}) => {
    let planeSelectionsFolder = null;

    const destroyFolder = () => {
        if (!planeSelectionsFolder) return;
        planeSelectionsFolder.destroy();
        planeSelectionsFolder = null;
    };

    const setVisible = (visible) => {
        if (!planeSelectionsFolder?.domElement) return;
        planeSelectionsFolder.domElement.style.display = visible ? '' : 'none';
    };

    const rebuild = () => {
        const planeSelections = ensureTimbrePlaneSelectionSettings?.();
        if (!modeAudioFolder || !planeSelections) return null;

        destroyFolder();
        planeSelectionsFolder = modeAudioFolder.addFolder('Plane Selections');

        planeSelectionsFolder.add(planeSelections, 'showSceneHandles').name('Show Scene Handles').onChange(() => {
            rebuildVisuals?.();
        });
        planeSelectionsFolder.add(planeSelections, 'showVolumeBox').name('Show 3D Box').onChange(() => {
            rebuildVisuals?.();
        });
        planeSelectionsFolder.add(planeSelections, 'grabType', selectionGrabTypes).name('Grab Type').onChange(() => {
            rebuildVisuals?.();
        });

        for (const [planeKey, planeMeta] of Object.entries(planeSelectionMeta || {})) {
            const selection = planeSelections[planeKey];
            const planeFolder = planeSelectionsFolder.addFolder(planeMeta.label);

            planeFolder.add(selection, 'enabled').name('Enabled').onChange(applySettings);
            planeFolder.add(selection, 'selectionMode', planeSelectionModes).name('Selection Mode').onChange(() => {
                cancelActiveLassoDraw?.({ refresh: false });
                applySettings?.();
            });
            planeFolder.addColor(selection, 'tintColor').name('Tint Color').onChange(applySettings);
            planeFolder.add(selection, 'strength', 0, 1, 0.01).name('Tint Strength').onChange(applySettings);

            const planeActions = {
                startLasso: () => {
                    startLassoDraw?.(planeKey);
                },
                completeLasso: () => {
                    if (getActiveLassoDraw?.()?.planeKey === planeKey) {
                        completeActiveLassoDraw?.();
                    }
                },
                clearLasso: () => {
                    clearPlaneLasso?.(planeKey);
                },
                resetBounds: () => {
                    selection.axis1MinPct = planeMeta.axis1MinPct;
                    selection.axis1MaxPct = planeMeta.axis1MaxPct;
                    selection.axis2MinPct = planeMeta.axis2MinPct;
                    selection.axis2MaxPct = planeMeta.axis2MaxPct;
                    applySettings?.();
                },
            };

            planeFolder.add(planeActions, 'startLasso').name(getActiveLassoDraw?.()?.planeKey === planeKey ? 'Redraw Lasso' : 'Start Lasso');
            planeFolder.add(planeActions, 'completeLasso').name('Complete Lasso');
            planeFolder.add(planeActions, 'clearLasso').name('Clear Lasso');
            planeFolder.add(planeActions, 'resetBounds').name('Reset Bounds');
        }

        bindGuiFolderTitleShortcuts?.();
        return planeSelectionsFolder;
    };

    return {
        rebuild,
        setVisible,
    };
};