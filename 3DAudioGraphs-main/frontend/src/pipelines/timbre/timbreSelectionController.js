import * as THREE from 'three';

export const createTimbreSelectionController = ({
    scene,
    camera,
    controls,
    renderer,
    trajectoryVisualizer,
    settings,
    isTerrainMode,
    ensureTimbrePlaneSelectionSettings,
    timbrePlaneSelectionMeta,
    timbreSelectionHandleRoles,
    getTimbreSceneBounds,
    evaluateTimbreSelectionFromPlaneSettings,
    createTimbreSelectionVolumeMesh,
    createTimbreSelectionGuidePlaneMesh,
    createTimbreSelectionLassoMesh,
    createTimbreSelectionPlaneMesh,
    createTimbreSelectionHandlePosition,
    disposeTimbreSelectionObject,
    getTimbrePlaneSelectionPointPcts,
    normalizeTimbrePlaneSelectionRange,
    shiftTimbrePlaneSelectionWindow,
    getTimbreSelectionVisualOffset,
    getPlaybackTimeSec,
    setBoxSelectedTimbreInstanceIds,
    timbrePlaneSelectionUsesLasso,
    getRenderableTimbreLassoPoints,
    normalizeTimbreLassoPoints,
    lassoCloseDistancePct = 4,
    onRebuildControls,
} = {}) => {
    const timbreSelectionHandleGroup = new THREE.Group();
    timbreSelectionHandleGroup.visible = false;
    scene?.add?.(timbreSelectionHandleGroup);

    const timbrePlaneSelectionRaycaster = new THREE.Raycaster();
    const timbrePlaneSelectionPointer = new THREE.Vector2();
    const timbrePlaneSelectionIntersection = new THREE.Vector3();
    const timbrePlaneSelectionDragPlane = new THREE.Plane();

    let timbreSelectionHandleRecords = [];
    let timbreSelectionSurfaceRecords = [];
    let activeTimbreSelectionDrag = null;
    let controlsWereEnabledBeforeTimbreDrag = true;
    let activeTimbreLassoDraw = null;

    const updatePointer = (event) => {
        const rect = renderer.domElement.getBoundingClientRect();
        timbrePlaneSelectionPointer.set(
            ((event.clientX - rect.left) / rect.width) * 2 - 1,
            -(((event.clientY - rect.top) / rect.height) * 2 - 1),
        );
    };

    const setCursor = (cursor = '') => {
        renderer.domElement.style.cursor = cursor;
    };

    const updateSelectionFromSettings = ({ adoptCurrentTimeSec = getPlaybackTimeSec?.() } = {}) => {
        const planeSelections = ensureTimbrePlaneSelectionSettings?.();
        if ((trajectoryVisualizer?.points?.length || 0) === 0) {
            setBoxSelectedTimbreInstanceIds?.([], { adoptCurrentTimeSec });
            return;
        }

        const bounds = getTimbreSceneBounds?.();
        const { selectedIds } = evaluateTimbreSelectionFromPlaneSettings?.(planeSelections, bounds) || { selectedIds: [] };
        setBoxSelectedTimbreInstanceIds?.(selectedIds, { adoptCurrentTimeSec });
    };

    const rebuildVisuals = ({ adoptCurrentTimeSec = getPlaybackTimeSec?.() } = {}) => {
        for (const child of [...timbreSelectionHandleGroup.children]) {
            timbreSelectionHandleGroup.remove(child);
            disposeTimbreSelectionObject?.(child);
        }
        timbreSelectionHandleRecords = [];
        timbreSelectionSurfaceRecords = [];

        const timbreMode = !isTerrainMode?.();
        timbreSelectionHandleGroup.visible = timbreMode;
        if (!timbreMode) return;

        const planeSelections = ensureTimbrePlaneSelectionSettings?.();
        if ((trajectoryVisualizer?.points?.length || 0) === 0) {
            setBoxSelectedTimbreInstanceIds?.([], { adoptCurrentTimeSec });
            return;
        }

        const bounds = getTimbreSceneBounds?.();
        const handleRadius = Math.max(Math.min(bounds.width, bounds.height, bounds.depth) * 0.018, 0.75);
        const { volumeSelection } = evaluateTimbreSelectionFromPlaneSettings?.(planeSelections, bounds) || { volumeSelection: { enabled: false } };
        const showCenterHandle = planeSelections.grabType === 'Center Node';

        if (planeSelections.showVolumeBox && volumeSelection.enabled) {
            timbreSelectionHandleGroup.add(createTimbreSelectionVolumeMesh?.(volumeSelection, bounds));
        }

        for (const [planeKey] of Object.entries(timbrePlaneSelectionMeta || {})) {
            const selection = planeSelections[planeKey];
            if (!selection?.enabled) continue;

            const tintColor = new THREE.Color(selection.tintColor);

            if (timbrePlaneSelectionUsesLasso?.(selection)) {
                const renderableLassoPoints = getRenderableTimbreLassoPoints?.(planeKey, selection, activeTimbreLassoDraw) || [];
                timbreSelectionHandleGroup.add(createTimbreSelectionGuidePlaneMesh?.(planeKey, bounds, tintColor));
                timbreSelectionHandleGroup.add(createTimbreSelectionLassoMesh?.(
                    planeKey,
                    renderableLassoPoints,
                    bounds,
                    tintColor,
                    {
                        closed: activeTimbreLassoDraw?.planeKey !== planeKey,
                        showHandles: !!planeSelections.showSceneHandles,
                    },
                ));
                continue;
            }

            const planeRoot = createTimbreSelectionPlaneMesh?.(planeKey, selection, bounds, tintColor);
            timbreSelectionHandleGroup.add(planeRoot);
            const surfaceMesh = planeRoot?.children?.find((child) => child.isMesh);
            if (surfaceMesh) {
                timbreSelectionSurfaceRecords.push({ mesh: surfaceMesh, planeKey, role: 'center' });
            }

            const handleMaterial = new THREE.MeshBasicMaterial({
                color: tintColor,
                transparent: true,
                opacity: planeSelections.showSceneHandles ? 0.95 : 0,
                depthWrite: false,
                depthTest: false,
            });

            for (const role of timbreSelectionHandleRoles || []) {
                if (role === 'center' && !showCenterHandle) continue;
                const handleGeometry = role === 'center'
                    ? new THREE.OctahedronGeometry(handleRadius * 1.12, 0)
                    : new THREE.SphereGeometry(handleRadius * (role.startsWith('corner') ? 0.85 : 1), 12, 12);
                const handleMesh = new THREE.Mesh(handleGeometry, handleMaterial.clone());
                handleMesh.position.copy(createTimbreSelectionHandlePosition?.(planeKey, role, selection, bounds));
                handleMesh.visible = !!planeSelections.showSceneHandles;
                handleMesh.renderOrder = role === 'center' ? 41 : 40;
                handleMesh.userData = { planeKey, role };
                timbreSelectionHandleGroup.add(handleMesh);
                timbreSelectionHandleRecords.push({ mesh: handleMesh, planeKey, role });
            }
        }

        updateSelectionFromSettings({ adoptCurrentTimeSec });
    };

    const applySettings = () => {
        ensureTimbrePlaneSelectionSettings?.();
        rebuildVisuals();
    };

    const getDragPlaneForKey = (planeKey, bounds) => {
        const offset = getTimbreSelectionVisualOffset?.(bounds);
        if (planeKey === 'xz') {
            timbrePlaneSelectionDragPlane.set(new THREE.Vector3(0, 1, 0), -(bounds.minY + offset));
        } else if (planeKey === 'yz') {
            timbrePlaneSelectionDragPlane.set(new THREE.Vector3(1, 0, 0), -(bounds.minX + offset));
        } else {
            timbrePlaneSelectionDragPlane.set(new THREE.Vector3(0, 0, 1), -(bounds.maxZ + offset));
        }
        return timbrePlaneSelectionDragPlane;
    };

    const findDragTarget = () => {
        const handleHits = timbrePlaneSelectionRaycaster.intersectObjects(
            timbreSelectionHandleRecords.map((record) => record.mesh),
            false,
        );
        if (handleHits.length > 0) {
            const hit = handleHits[0].object;
            return { planeKey: hit.userData.planeKey, role: hit.userData.role };
        }

        if (settings.timbrePlaneSelections?.grabType === 'Selection Surface') {
            const surfaceHits = timbrePlaneSelectionRaycaster.intersectObjects(
                timbreSelectionSurfaceRecords.map((record) => record.mesh),
                false,
            );
            if (surfaceHits.length > 0) {
                const hit = surfaceHits[0].object;
                return { planeKey: hit.userData.planeKey, role: 'center' };
            }
        }

        return null;
    };

    const updateSelectionFromPoint = (dragState, point) => {
        const selection = settings.timbrePlaneSelections?.[dragState.planeKey];
        if (!selection) return false;

        const { axis1Pct, axis2Pct } = getTimbrePlaneSelectionPointPcts?.(dragState.planeKey, point, dragState.bounds) || {};
        const prevState = {
            axis1MinPct: selection.axis1MinPct,
            axis1MaxPct: selection.axis1MaxPct,
            axis2MinPct: selection.axis2MinPct,
            axis2MaxPct: selection.axis2MaxPct,
        };

        if (dragState.role === 'axis1Min') {
            selection.axis1MinPct = Math.min(axis1Pct, selection.axis1MaxPct - 0.1);
            normalizeTimbrePlaneSelectionRange?.(selection, 'axis1MinPct', 'axis1MaxPct');
        } else if (dragState.role === 'axis1Max') {
            selection.axis1MaxPct = Math.max(axis1Pct, selection.axis1MinPct + 0.1);
            normalizeTimbrePlaneSelectionRange?.(selection, 'axis1MinPct', 'axis1MaxPct');
        } else if (dragState.role === 'axis2Min') {
            selection.axis2MinPct = Math.min(axis2Pct, selection.axis2MaxPct - 0.1);
            normalizeTimbrePlaneSelectionRange?.(selection, 'axis2MinPct', 'axis2MaxPct');
        } else if (dragState.role === 'axis2Max') {
            selection.axis2MaxPct = Math.max(axis2Pct, selection.axis2MinPct + 0.1);
            normalizeTimbrePlaneSelectionRange?.(selection, 'axis2MinPct', 'axis2MaxPct');
        } else if (dragState.role === 'cornerMinMin') {
            selection.axis1MinPct = Math.min(axis1Pct, selection.axis1MaxPct - 0.1);
            selection.axis2MinPct = Math.min(axis2Pct, selection.axis2MaxPct - 0.1);
            normalizeTimbrePlaneSelectionRange?.(selection, 'axis1MinPct', 'axis1MaxPct');
            normalizeTimbrePlaneSelectionRange?.(selection, 'axis2MinPct', 'axis2MaxPct');
        } else if (dragState.role === 'cornerMaxMin') {
            selection.axis1MaxPct = Math.max(axis1Pct, selection.axis1MinPct + 0.1);
            selection.axis2MinPct = Math.min(axis2Pct, selection.axis2MaxPct - 0.1);
            normalizeTimbrePlaneSelectionRange?.(selection, 'axis1MinPct', 'axis1MaxPct');
            normalizeTimbrePlaneSelectionRange?.(selection, 'axis2MinPct', 'axis2MaxPct');
        } else if (dragState.role === 'cornerMinMax') {
            selection.axis1MinPct = Math.min(axis1Pct, selection.axis1MaxPct - 0.1);
            selection.axis2MaxPct = Math.max(axis2Pct, selection.axis2MinPct + 0.1);
            normalizeTimbrePlaneSelectionRange?.(selection, 'axis1MinPct', 'axis1MaxPct');
            normalizeTimbrePlaneSelectionRange?.(selection, 'axis2MinPct', 'axis2MaxPct');
        } else if (dragState.role === 'cornerMaxMax') {
            selection.axis1MaxPct = Math.max(axis1Pct, selection.axis1MinPct + 0.1);
            selection.axis2MaxPct = Math.max(axis2Pct, selection.axis2MinPct + 0.1);
            normalizeTimbrePlaneSelectionRange?.(selection, 'axis1MinPct', 'axis1MaxPct');
            normalizeTimbrePlaneSelectionRange?.(selection, 'axis2MinPct', 'axis2MaxPct');
        } else if (dragState.role === 'center') {
            const deltaAxis1Pct = axis1Pct - dragState.startPointPcts.axis1Pct;
            const deltaAxis2Pct = axis2Pct - dragState.startPointPcts.axis2Pct;
            const nextAxis1Range = shiftTimbrePlaneSelectionWindow?.(
                dragState.startSelection.axis1MinPct,
                dragState.startSelection.axis1MaxPct,
                deltaAxis1Pct,
            );
            const nextAxis2Range = shiftTimbrePlaneSelectionWindow?.(
                dragState.startSelection.axis2MinPct,
                dragState.startSelection.axis2MaxPct,
                deltaAxis2Pct,
            );
            selection.axis1MinPct = nextAxis1Range.minPct;
            selection.axis1MaxPct = nextAxis1Range.maxPct;
            selection.axis2MinPct = nextAxis2Range.minPct;
            selection.axis2MaxPct = nextAxis2Range.maxPct;
        }

        return (
            prevState.axis1MinPct !== selection.axis1MinPct ||
            prevState.axis1MaxPct !== selection.axis1MaxPct ||
            prevState.axis2MinPct !== selection.axis2MinPct ||
            prevState.axis2MaxPct !== selection.axis2MaxPct
        );
    };

    const startLassoDraw = (planeKey) => {
        const planeSelections = ensureTimbrePlaneSelectionSettings?.();
        const selection = planeSelections?.[planeKey];
        if (!selection) return;

        selection.enabled = true;
        selection.selectionMode = 'Lasso';
        activeTimbreLassoDraw = {
            planeKey,
            points: [],
        };
        onRebuildControls?.();
        rebuildVisuals({ adoptCurrentTimeSec: getPlaybackTimeSec?.() });
    };

    const cancelActiveLassoDraw = ({ refresh = true } = {}) => {
        activeTimbreLassoDraw = null;
        if (!refresh) return;

        onRebuildControls?.();
        rebuildVisuals({ adoptCurrentTimeSec: getPlaybackTimeSec?.() });
    };

    const completeActiveLassoDraw = ({ adoptCurrentTimeSec = getPlaybackTimeSec?.() } = {}) => {
        if (!activeTimbreLassoDraw) return false;

        const selection = settings.timbrePlaneSelections?.[activeTimbreLassoDraw.planeKey];
        const lassoPoints = normalizeTimbreLassoPoints?.(activeTimbreLassoDraw.points) || [];
        if (!selection || lassoPoints.length < 3) return false;

        selection.enabled = true;
        selection.selectionMode = 'Lasso';
        selection.lassoPoints = lassoPoints;
        activeTimbreLassoDraw = null;
        onRebuildControls?.();
        rebuildVisuals({ adoptCurrentTimeSec });
        return true;
    };

    const clearPlaneLasso = (planeKey) => {
        const selection = settings.timbrePlaneSelections?.[planeKey];
        if (!selection) return;

        selection.lassoPoints = [];
        if (activeTimbreLassoDraw?.planeKey === planeKey) {
            activeTimbreLassoDraw = null;
        }
        onRebuildControls?.();
        rebuildVisuals({ adoptCurrentTimeSec: getPlaybackTimeSec?.() });
    };

    const appendPointToActiveLasso = (event) => {
        if (!activeTimbreLassoDraw) return false;

        const bounds = getTimbreSceneBounds?.();
        updatePointer(event);
        timbrePlaneSelectionRaycaster.setFromCamera(timbrePlaneSelectionPointer, camera);
        const dragPlane = getDragPlaneForKey(activeTimbreLassoDraw.planeKey, bounds);
        if (!timbrePlaneSelectionRaycaster.ray.intersectPlane(dragPlane, timbrePlaneSelectionIntersection)) {
            return false;
        }

        const point = getTimbrePlaneSelectionPointPcts?.(activeTimbreLassoDraw.planeKey, timbrePlaneSelectionIntersection, bounds);
        const normalizedPoint = normalizeTimbreLassoPoints?.([point])?.[0];
        if (!normalizedPoint) return false;

        const existingPoints = normalizeTimbreLassoPoints?.(activeTimbreLassoDraw.points) || [];
        const firstPoint = existingPoints[0];
        const previousPoint = existingPoints[existingPoints.length - 1];
        if (previousPoint && Math.hypot(normalizedPoint.axis1Pct - previousPoint.axis1Pct, normalizedPoint.axis2Pct - previousPoint.axis2Pct) < 0.25) {
            return true;
        }

        if (firstPoint && existingPoints.length >= 3 && Math.hypot(normalizedPoint.axis1Pct - firstPoint.axis1Pct, normalizedPoint.axis2Pct - firstPoint.axis2Pct) <= lassoCloseDistancePct) {
            return completeActiveLassoDraw();
        }

        activeTimbreLassoDraw.points = [...existingPoints, normalizedPoint];
        rebuildVisuals({ adoptCurrentTimeSec: getPlaybackTimeSec?.() });
        return true;
    };

    const startDrag = (event) => {
        const planeSelections = settings.timbrePlaneSelections;
        if (activeTimbreLassoDraw || isTerrainMode?.() || !planeSelections || (!planeSelections.showSceneHandles && planeSelections.grabType !== 'Selection Surface')) {
            return false;
        }

        updatePointer(event);
        timbrePlaneSelectionRaycaster.setFromCamera(timbrePlaneSelectionPointer, camera);

        const dragTarget = findDragTarget();
        if (!dragTarget) return false;

        const bounds = getTimbreSceneBounds?.();
        const { planeKey, role } = dragTarget;
        const dragPlane = getDragPlaneForKey(planeKey, bounds);
        if (!timbrePlaneSelectionRaycaster.ray.intersectPlane(dragPlane, timbrePlaneSelectionIntersection)) {
            return false;
        }

        const selection = planeSelections?.[planeKey];
        activeTimbreSelectionDrag = {
            planeKey,
            role,
            bounds,
            startPointPcts: getTimbrePlaneSelectionPointPcts?.(planeKey, timbrePlaneSelectionIntersection, bounds),
            startSelection: selection ? {
                axis1MinPct: selection.axis1MinPct,
                axis1MaxPct: selection.axis1MaxPct,
                axis2MinPct: selection.axis2MinPct,
                axis2MaxPct: selection.axis2MaxPct,
            } : {
                axis1MinPct: 0,
                axis1MaxPct: 100,
                axis2MinPct: 0,
                axis2MaxPct: 100,
            },
        };
        controlsWereEnabledBeforeTimbreDrag = controls.enabled;
        controls.enabled = false;
        renderer.domElement.setPointerCapture?.(event.pointerId);
        setCursor('grabbing');
        event.preventDefault();
        event.stopPropagation();
        return true;
    };

    const updateDrag = (event) => {
        if (!activeTimbreSelectionDrag) return;

        updatePointer(event);
        timbrePlaneSelectionRaycaster.setFromCamera(timbrePlaneSelectionPointer, camera);
        const dragPlane = getDragPlaneForKey(activeTimbreSelectionDrag.planeKey, activeTimbreSelectionDrag.bounds);
        if (!timbrePlaneSelectionRaycaster.ray.intersectPlane(dragPlane, timbrePlaneSelectionIntersection)) return;

        if (updateSelectionFromPoint(activeTimbreSelectionDrag, timbrePlaneSelectionIntersection)) {
            rebuildVisuals({ adoptCurrentTimeSec: getPlaybackTimeSec?.() });
        }

        event.preventDefault();
        event.stopPropagation();
    };

    const finishDrag = (event) => {
        if (!activeTimbreSelectionDrag) return;

        activeTimbreSelectionDrag = null;
        controls.enabled = controlsWereEnabledBeforeTimbreDrag;
        if (event?.pointerId !== undefined) {
            renderer.domElement.releasePointerCapture?.(event.pointerId);
        }
        setCursor('');
    };

    const updateHover = (event) => {
        if (activeTimbreSelectionDrag || isTerrainMode?.()) return;
        if (!settings.timbrePlaneSelections) {
            setCursor('');
            return;
        }

        if (activeTimbreLassoDraw) {
            setCursor('crosshair');
            return;
        }

        updatePointer(event);
        timbrePlaneSelectionRaycaster.setFromCamera(timbrePlaneSelectionPointer, camera);
        const dragTarget = findDragTarget();
        setCursor(dragTarget ? 'grab' : '');
    };

    const handlePointerLeave = () => {
        if (!activeTimbreSelectionDrag && !activeTimbreLassoDraw && !isTerrainMode?.()) {
            setCursor('');
        }
    };

    return {
        appendPointToActiveLasso,
        applySettings,
        cancelActiveLassoDraw,
        clearPlaneLasso,
        completeActiveLassoDraw,
        finishDrag,
        getActiveLassoDraw: () => activeTimbreLassoDraw,
        handlePointerLeave,
        isDragging: () => !!activeTimbreSelectionDrag,
        rebuildVisuals,
        startDrag,
        startLassoDraw,
        updateDrag,
        updateHover,
    };
};