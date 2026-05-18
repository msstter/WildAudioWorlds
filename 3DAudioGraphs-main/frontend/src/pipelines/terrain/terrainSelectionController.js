import * as THREE from 'three';

export const createTerrainSelectionController = ({
    scene,
    camera,
    controls,
    renderer,
    terrainVisualizer,
    settings,
    isTerrainMode,
    ensureTerrainPlaneSelectionSettings,
    terrainPlaneSelectionMeta,
    terrainSelectionHandleRoles,
    getTerrainSceneBounds,
    deriveTerrainVolumeSelection,
    createTerrainSelectionVolumeMesh,
    createTerrainSelectionPlaneMesh,
    createTerrainSelectionHandlePosition,
    disposeTerrainSelectionObject,
    getTerrainPlaneSelectionPointPcts,
    normalizeTerrainPlaneSelectionRange,
    shiftTerrainPlaneSelectionWindow,
    getTerrainSelectionVisualOffset,
    onInteractionTargetChange,
} = {}) => {
    const terrainSelectionHandleGroup = new THREE.Group();
    terrainSelectionHandleGroup.visible = false;
    scene.add(terrainSelectionHandleGroup);

    const terrainSelectionRaycaster = new THREE.Raycaster();
    const terrainSelectionPointer = new THREE.Vector2();
    const terrainSelectionIntersection = new THREE.Vector3();
    const terrainSelectionDragPlane = new THREE.Plane();

    let terrainSelectionHandleRecords = [];
    let terrainSelectionSurfaceRecords = [];
    let activeTerrainSelectionDrag = null;
    let controlsWereEnabledBeforeTerrainDrag = true;

    const rebuildVisuals = () => {
        for (const child of [...terrainSelectionHandleGroup.children]) {
            terrainSelectionHandleGroup.remove(child);
            disposeTerrainSelectionObject(child);
        }
        terrainSelectionHandleRecords = [];
        terrainSelectionSurfaceRecords = [];

        const terrainMode = isTerrainMode();
        const planeSelections = ensureTerrainPlaneSelectionSettings();
    terrainSelectionHandleGroup.visible = terrainMode && !!planeSelections.enabled;
    if (!terrainMode || !planeSelections.enabled) return;

        const bounds = getTerrainSceneBounds();
        const handleRadius = Math.max(Math.min(bounds.width, bounds.height, bounds.depth) * 0.018, 1.1);
        const volumeSelection = deriveTerrainVolumeSelection(planeSelections);
        const showCenterHandle = planeSelections.grabType === 'Center Node';

        if (planeSelections.showVolumeBox && volumeSelection.enabled) {
            terrainSelectionHandleGroup.add(createTerrainSelectionVolumeMesh(volumeSelection, bounds));
        }

        for (const [planeKey] of Object.entries(terrainPlaneSelectionMeta)) {
            const selection = planeSelections[planeKey];
            if (!selection.enabled) continue;

            const tintColor = new THREE.Color(selection.tintColor);
            const planeRoot = createTerrainSelectionPlaneMesh(planeKey, selection, bounds, tintColor);
            terrainSelectionHandleGroup.add(planeRoot);
            const surfaceMesh = planeRoot.children.find((child) => child.isMesh);
            if (surfaceMesh) {
                terrainSelectionSurfaceRecords.push({ mesh: surfaceMesh, planeKey, role: 'center' });
            }

            const handleMaterial = new THREE.MeshBasicMaterial({
                color: tintColor,
                transparent: true,
                opacity: planeSelections.showSceneHandles ? 0.95 : 0,
                depthWrite: false,
                depthTest: false,
            });

            for (const role of terrainSelectionHandleRoles) {
                if (role === 'center' && !showCenterHandle) continue;
                const handleGeometry = role === 'center'
                    ? new THREE.OctahedronGeometry(handleRadius * 1.12, 0)
                    : new THREE.SphereGeometry(handleRadius * (role.startsWith('corner') ? 0.85 : 1), 14, 14);
                const handleMesh = new THREE.Mesh(handleGeometry, handleMaterial.clone());
                handleMesh.position.copy(createTerrainSelectionHandlePosition(planeKey, role, selection, bounds));
                handleMesh.visible = !!planeSelections.showSceneHandles;
                handleMesh.renderOrder = role === 'center' ? 41 : 40;
                handleMesh.userData = { planeKey, role };
                terrainSelectionHandleGroup.add(handleMesh);
                terrainSelectionHandleRecords.push({ mesh: handleMesh, planeKey, role });
            }
        }
    };

    const applySettings = () => {
        ensureTerrainPlaneSelectionSettings();
        terrainVisualizer.setSettings(settings);
        terrainVisualizer.refreshColors();
        rebuildVisuals();
    };

    const findDragTarget = () => {
        const handleHits = terrainSelectionRaycaster.intersectObjects(
            terrainSelectionHandleRecords.map((record) => record.mesh),
            false,
        );
        if (handleHits.length > 0) {
            const hit = handleHits[0].object;
            return { planeKey: hit.userData.planeKey, role: hit.userData.role };
        }

        if (settings.terrainPlaneSelections?.grabType === 'Selection Surface') {
            const surfaceHits = terrainSelectionRaycaster.intersectObjects(
                terrainSelectionSurfaceRecords.map((record) => record.mesh),
                false,
            );
            if (surfaceHits.length > 0) {
                const hit = surfaceHits[0].object;
                return { planeKey: hit.userData.planeKey, role: 'center' };
            }
        }

        return null;
    };

    const updatePointer = (event) => {
        const rect = renderer.domElement.getBoundingClientRect();
        terrainSelectionPointer.set(
            ((event.clientX - rect.left) / rect.width) * 2 - 1,
            -(((event.clientY - rect.top) / rect.height) * 2 - 1),
        );
    };

    const setCursor = (cursor = '') => {
        renderer.domElement.style.cursor = cursor;
    };

    const getDragPlaneForKey = (planeKey, bounds) => {
        const offset = getTerrainSelectionVisualOffset(bounds);
        if (planeKey === 'xz') {
            terrainSelectionDragPlane.set(new THREE.Vector3(0, 1, 0), -(bounds.minY + offset));
        } else if (planeKey === 'yz') {
            terrainSelectionDragPlane.set(new THREE.Vector3(1, 0, 0), -(bounds.minX + offset));
        } else {
            terrainSelectionDragPlane.set(new THREE.Vector3(0, 0, 1), -(bounds.maxZ - offset));
        }
        return terrainSelectionDragPlane;
    };

    const updateSelectionFromPoint = (dragState, point) => {
        const selection = settings.terrainPlaneSelections?.[dragState.planeKey];
        if (!selection) return false;

        const { axis1Pct, axis2Pct } = getTerrainPlaneSelectionPointPcts(dragState.planeKey, point, dragState.bounds);

        const prevState = {
            axis1MinPct: selection.axis1MinPct,
            axis1MaxPct: selection.axis1MaxPct,
            axis2MinPct: selection.axis2MinPct,
            axis2MaxPct: selection.axis2MaxPct,
        };

        if (dragState.role === 'axis1Min') {
            selection.axis1MinPct = Math.min(axis1Pct, selection.axis1MaxPct - 0.1);
            normalizeTerrainPlaneSelectionRange(selection, 'axis1MinPct', 'axis1MaxPct');
        } else if (dragState.role === 'axis1Max') {
            selection.axis1MaxPct = Math.max(axis1Pct, selection.axis1MinPct + 0.1);
            normalizeTerrainPlaneSelectionRange(selection, 'axis1MinPct', 'axis1MaxPct');
        } else if (dragState.role === 'axis2Min') {
            selection.axis2MinPct = Math.min(axis2Pct, selection.axis2MaxPct - 0.1);
            normalizeTerrainPlaneSelectionRange(selection, 'axis2MinPct', 'axis2MaxPct');
        } else if (dragState.role === 'axis2Max') {
            selection.axis2MaxPct = Math.max(axis2Pct, selection.axis2MinPct + 0.1);
            normalizeTerrainPlaneSelectionRange(selection, 'axis2MinPct', 'axis2MaxPct');
        } else if (dragState.role === 'cornerMinMin') {
            selection.axis1MinPct = Math.min(axis1Pct, selection.axis1MaxPct - 0.1);
            selection.axis2MinPct = Math.min(axis2Pct, selection.axis2MaxPct - 0.1);
            normalizeTerrainPlaneSelectionRange(selection, 'axis1MinPct', 'axis1MaxPct');
            normalizeTerrainPlaneSelectionRange(selection, 'axis2MinPct', 'axis2MaxPct');
        } else if (dragState.role === 'cornerMaxMin') {
            selection.axis1MaxPct = Math.max(axis1Pct, selection.axis1MinPct + 0.1);
            selection.axis2MinPct = Math.min(axis2Pct, selection.axis2MaxPct - 0.1);
            normalizeTerrainPlaneSelectionRange(selection, 'axis1MinPct', 'axis1MaxPct');
            normalizeTerrainPlaneSelectionRange(selection, 'axis2MinPct', 'axis2MaxPct');
        } else if (dragState.role === 'cornerMinMax') {
            selection.axis1MinPct = Math.min(axis1Pct, selection.axis1MaxPct - 0.1);
            selection.axis2MaxPct = Math.max(axis2Pct, selection.axis2MinPct + 0.1);
            normalizeTerrainPlaneSelectionRange(selection, 'axis1MinPct', 'axis1MaxPct');
            normalizeTerrainPlaneSelectionRange(selection, 'axis2MinPct', 'axis2MaxPct');
        } else if (dragState.role === 'cornerMaxMax') {
            selection.axis1MaxPct = Math.max(axis1Pct, selection.axis1MinPct + 0.1);
            selection.axis2MaxPct = Math.max(axis2Pct, selection.axis2MinPct + 0.1);
            normalizeTerrainPlaneSelectionRange(selection, 'axis1MinPct', 'axis1MaxPct');
            normalizeTerrainPlaneSelectionRange(selection, 'axis2MinPct', 'axis2MaxPct');
        } else if (dragState.role === 'center') {
            const deltaAxis1Pct = axis1Pct - dragState.startPointPcts.axis1Pct;
            const deltaAxis2Pct = axis2Pct - dragState.startPointPcts.axis2Pct;
            const nextAxis1Range = shiftTerrainPlaneSelectionWindow(
                dragState.startSelection.axis1MinPct,
                dragState.startSelection.axis1MaxPct,
                deltaAxis1Pct,
            );
            const nextAxis2Range = shiftTerrainPlaneSelectionWindow(
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

    const startDrag = (event) => {
        const planeSelections = settings.terrainPlaneSelections;
        if (!isTerrainMode() || !planeSelections || (!planeSelections.showSceneHandles && planeSelections.grabType !== 'Selection Surface')) {
            return false;
        }

        updatePointer(event);
        terrainSelectionRaycaster.setFromCamera(terrainSelectionPointer, camera);

        const dragTarget = findDragTarget();
        if (!dragTarget) return false;

        const bounds = getTerrainSceneBounds();
        const { planeKey, role } = dragTarget;
        const dragPlane = getDragPlaneForKey(planeKey, bounds);
        if (!terrainSelectionRaycaster.ray.intersectPlane(dragPlane, terrainSelectionIntersection)) {
            return false;
        }

        const selection = planeSelections?.[planeKey];
        activeTerrainSelectionDrag = {
            planeKey,
            role,
            bounds,
            startPointPcts: getTerrainPlaneSelectionPointPcts(planeKey, terrainSelectionIntersection, bounds),
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
        onInteractionTargetChange?.({ source: '3d-terrain', planeKey, role, phase: 'drag-start' });
        controlsWereEnabledBeforeTerrainDrag = controls.enabled;
        controls.enabled = false;
        renderer.domElement.setPointerCapture?.(event.pointerId);
        setCursor('grabbing');
        event.preventDefault();
        event.stopPropagation();
        return true;
    };

    const updateDrag = (event) => {
        if (!activeTerrainSelectionDrag) return;

        updatePointer(event);
        terrainSelectionRaycaster.setFromCamera(terrainSelectionPointer, camera);
        const dragPlane = getDragPlaneForKey(activeTerrainSelectionDrag.planeKey, activeTerrainSelectionDrag.bounds);
        if (!terrainSelectionRaycaster.ray.intersectPlane(dragPlane, terrainSelectionIntersection)) return;

        if (updateSelectionFromPoint(activeTerrainSelectionDrag, terrainSelectionIntersection)) {
            applySettings();
        }

        event.preventDefault();
        event.stopPropagation();
    };

    const finishDrag = (event) => {
        if (!activeTerrainSelectionDrag) return;

        onInteractionTargetChange?.({
            source: '3d-terrain',
            planeKey: activeTerrainSelectionDrag.planeKey,
            role: activeTerrainSelectionDrag.role,
            phase: 'drag-end',
        });
        activeTerrainSelectionDrag = null;
        controls.enabled = controlsWereEnabledBeforeTerrainDrag;
        if (event?.pointerId !== undefined) {
            renderer.domElement.releasePointerCapture?.(event.pointerId);
        }
        setCursor('');
    };

    const updateHover = (event) => {
        if (activeTerrainSelectionDrag) return;
        if (!isTerrainMode() || !settings.terrainPlaneSelections) {
            onInteractionTargetChange?.({ source: 'render-window', phase: 'inactive' });
            setCursor('');
            return;
        }

        updatePointer(event);
        terrainSelectionRaycaster.setFromCamera(terrainSelectionPointer, camera);
        const dragTarget = findDragTarget();
        onInteractionTargetChange?.(
            dragTarget
                ? { source: '3d-terrain', planeKey: dragTarget.planeKey, role: dragTarget.role, phase: 'hover' }
                : { source: 'render-window', phase: 'hover' }
        );
        setCursor(dragTarget ? 'grab' : '');
    };

    const handlePointerLeave = () => {
        onInteractionTargetChange?.({ source: 'render-window', phase: 'leave' });
        if (!activeTerrainSelectionDrag) setCursor('');
    };

    return {
        applySettings,
        finishDrag,
        handlePointerLeave,
        rebuildVisuals,
        startDrag,
        updateDrag,
        updateHover,
    };
};