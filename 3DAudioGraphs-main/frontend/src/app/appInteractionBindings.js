export const createAppInteractionBindings = ({
    windowObject = window,
    renderer,
    isTerrainMode,
    isFirstPersonModeEnabled,
    isFirstPersonPointerLocked,
    getActiveTimbreLassoDraw,
    isTimbrePlaneSelectionDragging,
    startTerrainPlaneSelectionDrag,
    startTimbrePlaneSelectionDrag,
    updateTerrainPlaneSelectionHover,
    updateTimbrePlaneSelectionHover,
    handleTerrainPlaneSelectionPointerLeave,
    handleTimbrePlaneSelectionPointerLeave,
    updateTerrainPlaneSelectionDrag,
    updateTimbrePlaneSelectionDrag,
    finishTerrainPlaneSelectionDrag,
    finishTimbrePlaneSelectionDrag,
    appendPointToActiveTimbreLasso,
    pickTimbreSelectionIntersection,
    pickCenteredTimbreSelectionIntersection,
    setSelectedTimbreInstanceIds,
    toggleSelectedTimbreInstanceId,
    handleTerrainOnsetEditorPointerDown,
    handleTerrainOnsetEditorPointerMove,
    handleTerrainOnsetEditorPointerUp,
    handleTerrainOnsetEditorPointerLeave,
    handleTerrainOnsetEditorContextMenu,
    selectionClickDistancePx = 6,
} = {}) => {
    let bound = false;
    let timbreSelectionPointerDown = null;
    let timbreLassoPointerDown = null;

    const clearTimbreSelectionPointerDown = () => {
        timbreSelectionPointerDown = null;
    };

    const clearTimbreLassoPointerDown = () => {
        timbreLassoPointerDown = null;
    };

    const clearTimbrePointerState = () => {
        clearTimbreSelectionPointerDown();
        clearTimbreLassoPointerDown();
    };

    const bind = () => {
        if (bound) return;
        bound = true;

        renderer.domElement.addEventListener('pointerdown', (event) => {
            if (isFirstPersonModeEnabled?.()) return;
            if (event.button === 0 && getActiveTimbreLassoDraw?.() && !isTerrainMode?.()) {
                timbreLassoPointerDown = {
                    pointerId: event.pointerId,
                    x: event.clientX,
                    y: event.clientY,
                };
                event.preventDefault();
                event.stopPropagation();
                return;
            }

            if (handleTerrainOnsetEditorPointerDown?.(event)) {
                event.preventDefault();
                event.stopImmediatePropagation();
                return;
            }

            if (startTerrainPlaneSelectionDrag?.(event)) return;
            startTimbrePlaneSelectionDrag?.(event);
        }, { capture: true });

        renderer.domElement.addEventListener('pointerdown', () => {
            renderer.domElement.focus();
        });

        renderer.domElement.addEventListener('pointerdown', (event) => {
            if (isFirstPersonModeEnabled?.()) return;
            if (event.button !== 0 || isTerrainMode?.() || isTimbrePlaneSelectionDragging?.() || getActiveTimbreLassoDraw?.()) return;
            timbreSelectionPointerDown = {
                pointerId: event.pointerId,
                x: event.clientX,
                y: event.clientY,
            };
        });

        renderer.domElement.addEventListener('pointermove', (event) => {
            if (isFirstPersonModeEnabled?.()) return;
            if (handleTerrainOnsetEditorPointerMove?.(event)) {
                event.preventDefault();
                event.stopImmediatePropagation();
                return;
            }
            updateTerrainPlaneSelectionHover?.(event);
            updateTimbrePlaneSelectionHover?.(event);
        });

        renderer.domElement.addEventListener('contextmenu', (event) => {
            if (isFirstPersonModeEnabled?.()) return;
            if (!handleTerrainOnsetEditorContextMenu?.(event)) return;
            event.preventDefault();
            event.stopImmediatePropagation();
        }, { capture: true });

        renderer.domElement.addEventListener('pointerleave', () => {
            if (isFirstPersonModeEnabled?.()) return;
            handleTerrainOnsetEditorPointerLeave?.();
            handleTerrainPlaneSelectionPointerLeave?.();
            handleTimbrePlaneSelectionPointerLeave?.();
            clearTimbrePointerState();
        });

        windowObject.addEventListener('pointermove', (event) => {
            if (isFirstPersonModeEnabled?.()) return;
            if (!handleTerrainOnsetEditorPointerMove?.(event)) return;
            event.preventDefault();
            event.stopImmediatePropagation();
        }, { capture: true });
        windowObject.addEventListener('pointermove', updateTerrainPlaneSelectionDrag, { capture: true });
        windowObject.addEventListener('pointermove', updateTimbrePlaneSelectionDrag, { capture: true });
        windowObject.addEventListener('pointerup', (event) => {
            if (isFirstPersonModeEnabled?.()) return;
            if (!handleTerrainOnsetEditorPointerUp?.(event)) return;
            event.preventDefault();
            event.stopImmediatePropagation();
        }, { capture: true });
        windowObject.addEventListener('pointerup', finishTerrainPlaneSelectionDrag, { capture: true });
        windowObject.addEventListener('pointerup', finishTimbrePlaneSelectionDrag, { capture: true });
        windowObject.addEventListener('pointercancel', (event) => {
            if (isFirstPersonModeEnabled?.()) return;
            if (!handleTerrainOnsetEditorPointerUp?.(event)) return;
            event.preventDefault();
            event.stopImmediatePropagation();
        }, { capture: true });
        windowObject.addEventListener('pointercancel', finishTerrainPlaneSelectionDrag, { capture: true });
        windowObject.addEventListener('pointercancel', finishTimbrePlaneSelectionDrag, { capture: true });

        windowObject.addEventListener('pointerup', (event) => {
            if (isFirstPersonModeEnabled?.()) return;
            if (!timbreLassoPointerDown || event.pointerId !== timbreLassoPointerDown.pointerId) return;

            const startPoint = timbreLassoPointerDown;
            timbreLassoPointerDown = null;
            if (event.button !== 0 || isTerrainMode?.() || !getActiveTimbreLassoDraw?.()) return;

            const dragDistance = Math.hypot(event.clientX - startPoint.x, event.clientY - startPoint.y);
            if (dragDistance > selectionClickDistancePx) return;

            if (appendPointToActiveTimbreLasso?.(event)) {
                event.preventDefault();
                event.stopPropagation();
            }
        }, { capture: true });

        windowObject.addEventListener('pointerup', (event) => {
            if (isFirstPersonModeEnabled?.()) {
                if (!isFirstPersonPointerLocked?.()) return;
                if (event.button !== 0 || isTerrainMode?.()) return;

                const intersection = pickCenteredTimbreSelectionIntersection?.();
                if (!intersection) {
                    if (!event.shiftKey && !event.metaKey && !event.ctrlKey) {
                        setSelectedTimbreInstanceIds?.([]);
                    }
                    return;
                }

                const instanceId = intersection.instanceId;
                if (event.shiftKey || event.metaKey || event.ctrlKey) {
                    toggleSelectedTimbreInstanceId?.(instanceId);
                    return;
                }

                setSelectedTimbreInstanceIds?.([instanceId]);
                return;
            }
            if (!timbreSelectionPointerDown || event.pointerId !== timbreSelectionPointerDown.pointerId) return;

            const startPoint = timbreSelectionPointerDown;
            timbreSelectionPointerDown = null;
            if (event.button !== 0 || isTerrainMode?.()) return;

            const dragDistance = Math.hypot(event.clientX - startPoint.x, event.clientY - startPoint.y);
            if (dragDistance > selectionClickDistancePx) return;

            const intersection = pickTimbreSelectionIntersection?.(event);
            if (!intersection) {
                if (!event.shiftKey && !event.metaKey && !event.ctrlKey) {
                    setSelectedTimbreInstanceIds?.([]);
                }
                return;
            }

            const instanceId = intersection.instanceId;
            if (event.shiftKey || event.metaKey || event.ctrlKey) {
                toggleSelectedTimbreInstanceId?.(instanceId);
                return;
            }

            setSelectedTimbreInstanceIds?.([instanceId]);
        }, { capture: true });

        windowObject.addEventListener('pointercancel', () => {
            clearTimbrePointerState();
        }, { capture: true });
    };

    return {
        bind,
        clearTimbreSelectionPointerDown,
        clearTimbreLassoPointerDown,
        clearTimbrePointerState,
    };
};