import { MathUtils, Spherical, Vector3 } from 'three';

import { DEFAULT_KEYBOARD_HOTKEYS } from './inputBindings.js';

const CAMERA_CONTROL_STORAGE_KEY = '3daudio_camera_controls';
const MIN_CAMERA_DISTANCE = 0.5;
const MAX_CAMERA_PITCH_DEG = 89.5;

const CAMERA_HOTKEY_META = [
    {
        key: 'captureCameraKeyframe',
        label: 'Set Keyframe',
        detail: 'Capture the current camera as a new keyframe.',
    },
    {
        key: 'nextCameraKeyframe',
        label: 'Next Keyframe',
        detail: 'Move to the next keyframe in the cycle order.',
    },
    {
        key: 'previousCameraKeyframe',
        label: 'Previous Keyframe',
        detail: 'Move to the previous keyframe in the cycle order.',
    },
];

const roundTo = (value, decimals = 3) => {
    const factor = 10 ** decimals;
    return Math.round(value * factor) / factor;
};

const toFiniteNumber = (value, fallback = 0) => {
    const numericValue = Number(value);
    return Number.isFinite(numericValue) ? numericValue : fallback;
};

const cloneKeyframe = (keyframe) => ({ ...keyframe });

const cloneState = (state) => ({
    ...state,
    keyframes: (state.keyframes || []).map(cloneKeyframe),
});

const buildKeyframeTarget = (keyframe) => {
    const yawRad = MathUtils.degToRad(toFiniteNumber(keyframe.yawDeg, 0));
    const pitchRad = MathUtils.degToRad(MathUtils.clamp(toFiniteNumber(keyframe.pitchDeg, 0), -MAX_CAMERA_PITCH_DEG, MAX_CAMERA_PITCH_DEG));
    const distance = Math.max(MIN_CAMERA_DISTANCE, toFiniteNumber(keyframe.distance, 120));

    const forward = new Vector3(
        Math.sin(yawRad) * Math.cos(pitchRad),
        Math.sin(pitchRad),
        Math.cos(yawRad) * Math.cos(pitchRad),
    ).normalize();

    return new Vector3(
        toFiniteNumber(keyframe.x, 0),
        toFiniteNumber(keyframe.y, 0),
        toFiniteNumber(keyframe.z, 0),
    ).add(forward.multiplyScalar(distance));
};

const buildKeyframeFromPose = ({
    id,
    name,
    isBase = false,
    position,
    target,
}) => {
    const forward = target.clone().sub(position);
    const safeDistance = Math.max(MIN_CAMERA_DISTANCE, forward.length() || MIN_CAMERA_DISTANCE);
    if (forward.lengthSq() <= 0.000001) {
        forward.set(0, 0, -1);
    } else {
        forward.normalize();
    }

    return {
        id,
        name,
        isBase,
        x: roundTo(position.x),
        y: roundTo(position.y),
        z: roundTo(position.z),
        yawDeg: roundTo(MathUtils.radToDeg(Math.atan2(forward.x, forward.z)), 1),
        pitchDeg: roundTo(MathUtils.radToDeg(Math.asin(MathUtils.clamp(forward.y, -1, 1))), 1),
        distance: roundTo(safeDistance),
    };
};

const sanitizeKeyframe = (keyframe, fallbackKeyframe) => ({
    id: typeof keyframe?.id === 'string' && keyframe.id ? keyframe.id : fallbackKeyframe?.id,
    name: typeof keyframe?.name === 'string' && keyframe.name.trim()
        ? keyframe.name.trim()
        : (fallbackKeyframe?.name || 'Keyframe'),
    isBase: keyframe?.isBase ?? fallbackKeyframe?.isBase ?? false,
    x: roundTo(toFiniteNumber(keyframe?.x, fallbackKeyframe?.x ?? 0)),
    y: roundTo(toFiniteNumber(keyframe?.y, fallbackKeyframe?.y ?? 0)),
    z: roundTo(toFiniteNumber(keyframe?.z, fallbackKeyframe?.z ?? 0)),
    yawDeg: roundTo(toFiniteNumber(keyframe?.yawDeg, fallbackKeyframe?.yawDeg ?? 0), 1),
    pitchDeg: roundTo(MathUtils.clamp(
        toFiniteNumber(keyframe?.pitchDeg, fallbackKeyframe?.pitchDeg ?? 0),
        -MAX_CAMERA_PITCH_DEG,
        MAX_CAMERA_PITCH_DEG,
    ), 1),
    distance: roundTo(Math.max(
        MIN_CAMERA_DISTANCE,
        toFiniteNumber(keyframe?.distance, fallbackKeyframe?.distance ?? 120),
    )),
});

const createDirectionSelect = ({ documentObject, options, value, onChange }) => {
    const select = documentObject.createElement('select');
    select.className = 'rec-inline-select';
    for (const optionMeta of options) {
        const option = documentObject.createElement('option');
        option.value = `${optionMeta.value}`;
        option.textContent = optionMeta.label;
        select.appendChild(option);
    }
    select.value = `${value}`;
    select.addEventListener('change', () => {
        onChange(Number(select.value));
    });
    return select;
};

const createNumberInput = ({
    documentObject,
    value,
    min,
    max,
    step,
    onChange,
}) => {
    const input = documentObject.createElement('input');
    input.type = 'number';
    input.className = 'rec-inline-number';
    input.value = `${value}`;
    if (Number.isFinite(min)) input.min = `${min}`;
    if (Number.isFinite(max)) input.max = `${max}`;
    if (Number.isFinite(step)) input.step = `${step}`;
    input.addEventListener('change', () => {
        onChange(input.value);
    });
    return input;
};

export const createCameraControlPanel = ({
    documentObject = document,
    storageObject = localStorage,
    camera,
    controls,
    fpvControls,
    recModalRoot,
    recStartBtn,
    getCurrentHotkeys,
    saveHotkeysToStorage,
} = {}) => {
    let generatedKeyframeIndex = 0;

    const makeKeyframeId = () => {
        generatedKeyframeIndex += 1;
        return `camera-keyframe-${Date.now()}-${generatedKeyframeIndex}`;
    };

    const captureCurrentView = ({
        id = makeKeyframeId(),
        name = `Keyframe ${generatedKeyframeIndex}`,
        isBase = false,
    } = {}) => {
        const currentTarget = controls?.target?.clone?.() || new Vector3(0, 0, 0);
        return buildKeyframeFromPose({
            id,
            name,
            isBase,
            position: camera.position.clone(),
            target: currentTarget,
        });
    };

    const buildDefaultState = () => {
        const baseKeyframe = captureCurrentView({
            id: makeKeyframeId(),
            name: 'Base Keyframe',
            isBase: true,
        });
        const baseTarget = buildKeyframeTarget(baseKeyframe);
        const baseDistance = Math.max(MIN_CAMERA_DISTANCE, baseKeyframe.distance);

        const xyKeyframe = buildKeyframeFromPose({
            id: makeKeyframeId(),
            name: 'XY Plane',
            position: baseTarget.clone().add(new Vector3(0, 0, baseDistance)),
            target: baseTarget,
        });
        const xzKeyframe = buildKeyframeFromPose({
            id: makeKeyframeId(),
            name: 'XZ Plane',
            position: baseTarget.clone().add(new Vector3(0, baseDistance, 0)),
            target: baseTarget,
        });
        const yzKeyframe = buildKeyframeFromPose({
            id: makeKeyframeId(),
            name: 'YZ Plane',
            position: baseTarget.clone().add(new Vector3(baseDistance, 0, 0)),
            target: baseTarget,
        });

        return {
            enableKeyframeHotkeys: true,
            currentKeyframeId: baseKeyframe.id,
            keyframes: [baseKeyframe, xyKeyframe, xzKeyframe, yzKeyframe],
            snapOrbitToKeyframeOnFpvExit: false,
            autoMoveEnabled: false,
            autoSpinEnabled: false,
            autoSpinXSpeed: 18,
            autoSpinXDirection: 1,
            autoSpinYSpeed: 0,
            autoSpinYDirection: 1,
            autoZoomEnabled: false,
            autoZoomSpeed: 12,
            autoZoomDirection: -1,
            autoSlideEnabled: false,
            autoSlideXSpeed: 0,
            autoSlideXDirection: 1,
            autoSlideYSpeed: 0,
            autoSlideYDirection: 1,
        };
    };

    const defaultState = buildDefaultState();
    const fallbackBaseKeyframe = cloneKeyframe(defaultState.keyframes[0]);

    const loadState = () => {
        try {
            const storedValue = storageObject.getItem(CAMERA_CONTROL_STORAGE_KEY);
            if (!storedValue) return cloneState(defaultState);

            const parsedState = JSON.parse(storedValue);
            const candidateKeyframes = Array.isArray(parsedState?.keyframes) && parsedState.keyframes.length > 0
                ? parsedState.keyframes
                : defaultState.keyframes;
            const sanitizedKeyframes = candidateKeyframes.map((keyframe, index) => sanitizeKeyframe(
                keyframe,
                defaultState.keyframes[Math.min(index, defaultState.keyframes.length - 1)] || fallbackBaseKeyframe,
            ));

            return {
                ...cloneState(defaultState),
                ...parsedState,
                enableKeyframeHotkeys: parsedState?.enableKeyframeHotkeys ?? defaultState.enableKeyframeHotkeys,
                currentKeyframeId: sanitizedKeyframes.some((keyframe) => keyframe.id === parsedState?.currentKeyframeId)
                    ? parsedState.currentKeyframeId
                    : (sanitizedKeyframes[0]?.id || null),
                keyframes: sanitizedKeyframes,
                snapOrbitToKeyframeOnFpvExit: parsedState?.snapOrbitToKeyframeOnFpvExit ?? defaultState.snapOrbitToKeyframeOnFpvExit,
                autoMoveEnabled: !!parsedState?.autoMoveEnabled,
                autoSpinEnabled: !!parsedState?.autoSpinEnabled,
                autoSpinXSpeed: toFiniteNumber(parsedState?.autoSpinXSpeed, defaultState.autoSpinXSpeed),
                autoSpinXDirection: toFiniteNumber(parsedState?.autoSpinXDirection, defaultState.autoSpinXDirection) >= 0 ? 1 : -1,
                autoSpinYSpeed: toFiniteNumber(parsedState?.autoSpinYSpeed, defaultState.autoSpinYSpeed),
                autoSpinYDirection: toFiniteNumber(parsedState?.autoSpinYDirection, defaultState.autoSpinYDirection) >= 0 ? 1 : -1,
                autoZoomEnabled: !!parsedState?.autoZoomEnabled,
                autoZoomSpeed: toFiniteNumber(parsedState?.autoZoomSpeed, defaultState.autoZoomSpeed),
                autoZoomDirection: toFiniteNumber(parsedState?.autoZoomDirection, defaultState.autoZoomDirection) >= 0 ? 1 : -1,
                autoSlideEnabled: !!parsedState?.autoSlideEnabled,
                autoSlideXSpeed: toFiniteNumber(parsedState?.autoSlideXSpeed, defaultState.autoSlideXSpeed),
                autoSlideXDirection: toFiniteNumber(parsedState?.autoSlideXDirection, defaultState.autoSlideXDirection) >= 0 ? 1 : -1,
                autoSlideYSpeed: toFiniteNumber(parsedState?.autoSlideYSpeed, defaultState.autoSlideYSpeed),
                autoSlideYDirection: toFiniteNumber(parsedState?.autoSlideYDirection, defaultState.autoSlideYDirection) >= 0 ? 1 : -1,
            };
        } catch {
            return cloneState(defaultState);
        }
    };

    const cameraControlState = loadState();
    const sectionRoot = documentObject.createElement('section');
    sectionRoot.className = 'rec-section rec-camera-section';

    if (recModalRoot && recStartBtn && recStartBtn.parentNode === recModalRoot) {
        recModalRoot.insertBefore(sectionRoot, recStartBtn);
    } else {
        recModalRoot?.appendChild(sectionRoot);
    }

    const saveState = () => {
        try {
            storageObject.setItem(CAMERA_CONTROL_STORAGE_KEY, JSON.stringify(cameraControlState));
        } catch {
            // Ignore storage failures and keep the in-memory state alive.
        }
    };

    const getCurrentHotkeyBindings = () => ({
        ...DEFAULT_KEYBOARD_HOTKEYS,
        ...(getCurrentHotkeys?.() || {}),
    });

    const persistHotkeyBinding = (key, code) => {
        const hotkeys = getCurrentHotkeys?.();
        if (!hotkeys) return;
        hotkeys[key] = code;
        saveHotkeysToStorage?.(hotkeys);
    };

    const getBaseKeyframe = () => (
        cameraControlState.keyframes.find((keyframe) => keyframe.isBase)
        || cameraControlState.keyframes[0]
        || fallbackBaseKeyframe
    );

    const getActiveOrBaseKeyframe = () => (
        cameraControlState.keyframes.find((keyframe) => keyframe.id === cameraControlState.currentKeyframeId)
        || getBaseKeyframe()
    );

    const syncCurrentKeyframeId = (keyframe) => {
        if (!keyframe || !cameraControlState.keyframes.some((candidate) => candidate.id === keyframe.id)) return false;
        if (cameraControlState.currentKeyframeId === keyframe.id) return false;

        cameraControlState.currentKeyframeId = keyframe.id;
        saveState();
        return true;
    };

    let renderPanel = () => {};
    let suppressNextFpvExitHandling = false;

    const disableFpvWithoutExitHandling = () => {
        const wasEnabled = !!fpvControls?.isEnabled?.();
        if (wasEnabled) {
            suppressNextFpvExitHandling = true;
        }
        fpvControls?.setEnabled?.(false);
        return wasEnabled;
    };

    const applyResolvedKeyframe = (keyframe, { persistSelection = true, rerender = true } = {}) => {
        if (!keyframe || !camera || !controls) return false;

        disableFpvWithoutExitHandling();

        const target = buildKeyframeTarget(keyframe);
        camera.position.set(keyframe.x, keyframe.y, keyframe.z);
        controls.target.copy(target);
        controls.update?.();

        if (persistSelection) {
            cameraControlState.currentKeyframeId = cameraControlState.keyframes.some((candidate) => candidate.id === keyframe.id)
                ? keyframe.id
                : null;
            saveState();
        }

        if (rerender) {
            renderPanel();
        }
        return true;
    };

    const applyKeyframeById = (keyframeId, options = {}) => {
        const keyframe = cameraControlState.keyframes.find((candidate) => candidate.id === keyframeId);
        if (!keyframe) return false;
        return applyResolvedKeyframe(keyframe, options);
    };

    const updateKeyframeField = (keyframeId, field, value, inputElement) => {
        const keyframeIndex = cameraControlState.keyframes.findIndex((candidate) => candidate.id === keyframeId);
        if (keyframeIndex === -1) return;

        const currentKeyframe = cameraControlState.keyframes[keyframeIndex];
        const nextKeyframe = sanitizeKeyframe({
            ...currentKeyframe,
            [field]: field === 'name' ? value : toFiniteNumber(value, currentKeyframe[field]),
        }, currentKeyframe);
        cameraControlState.keyframes[keyframeIndex] = nextKeyframe;
        saveState();

        if (inputElement) {
            inputElement.value = `${nextKeyframe[field]}`;
        }

        if (cameraControlState.currentKeyframeId === keyframeId) {
            applyResolvedKeyframe(nextKeyframe, { persistSelection: false, rerender: false });
        }
    };

    const captureCurrentKeyframe = () => {
        const activeIndex = cameraControlState.keyframes.findIndex((candidate) => candidate.id === cameraControlState.currentKeyframeId);
        const insertionIndex = activeIndex >= 0 ? activeIndex + 1 : cameraControlState.keyframes.length;
        const nextKeyframe = captureCurrentView({
            id: makeKeyframeId(),
            name: `Keyframe ${cameraControlState.keyframes.length + 1}`,
        });

        cameraControlState.keyframes.splice(insertionIndex, 0, nextKeyframe);
        cameraControlState.currentKeyframeId = nextKeyframe.id;
        saveState();
        renderPanel();
        return true;
    };

    const updateActiveKeyframeFromCurrentView = () => {
        const activeKeyframeIndex = cameraControlState.keyframes.findIndex((candidate) => candidate.id === cameraControlState.currentKeyframeId);
        if (activeKeyframeIndex === -1) return false;

        const currentKeyframe = cameraControlState.keyframes[activeKeyframeIndex];
        cameraControlState.keyframes[activeKeyframeIndex] = captureCurrentView({
            id: currentKeyframe.id,
            name: currentKeyframe.name,
            isBase: currentKeyframe.isBase,
        });
        saveState();
        renderPanel();
        return true;
    };

    const cycleKeyframe = (direction) => {
        if (!cameraControlState.enableKeyframeHotkeys || cameraControlState.keyframes.length === 0) return false;
        const currentIndex = cameraControlState.keyframes.findIndex((candidate) => candidate.id === cameraControlState.currentKeyframeId);
        const normalizedIndex = currentIndex >= 0 ? currentIndex : 0;
        const nextIndex = (normalizedIndex + (direction >= 0 ? 1 : -1) + cameraControlState.keyframes.length) % cameraControlState.keyframes.length;
        return applyKeyframeById(cameraControlState.keyframes[nextIndex].id);
    };

    const moveKeyframe = (keyframeId, direction) => {
        const currentIndex = cameraControlState.keyframes.findIndex((candidate) => candidate.id === keyframeId);
        if (currentIndex === -1) return;

        const nextIndex = currentIndex + direction;
        if (nextIndex < 0 || nextIndex >= cameraControlState.keyframes.length) return;

        const [movedKeyframe] = cameraControlState.keyframes.splice(currentIndex, 1);
        cameraControlState.keyframes.splice(nextIndex, 0, movedKeyframe);
        saveState();
        renderPanel();
    };

    const deleteKeyframe = (keyframeId) => {
        const currentIndex = cameraControlState.keyframes.findIndex((candidate) => candidate.id === keyframeId);
        if (currentIndex === -1) return;

        cameraControlState.keyframes.splice(currentIndex, 1);
        if (cameraControlState.currentKeyframeId === keyframeId) {
            cameraControlState.currentKeyframeId = cameraControlState.keyframes[Math.max(0, currentIndex - 1)]?.id || null;
        }
        saveState();
        renderPanel();
    };

    const resetKeyframes = () => {
        const resetState = cloneState(defaultState);
        cameraControlState.currentKeyframeId = resetState.currentKeyframeId;
        cameraControlState.keyframes = resetState.keyframes;
        saveState();
        applyResolvedKeyframe(getBaseKeyframe());
    };

    const resetCameraView = () => {
        const baseKeyframe = getBaseKeyframe();
        return applyResolvedKeyframe(baseKeyframe);
    };

    const recenterOrbitToSafePivot = ({ preservePosition = true, rerender = true } = {}) => {
        if (!camera || !controls) return false;

        const keyframe = getActiveOrBaseKeyframe();
        if (!keyframe) return false;

        syncCurrentKeyframeId(keyframe);

        const target = buildKeyframeTarget(keyframe);
        if (!preservePosition) {
            camera.position.set(keyframe.x, keyframe.y, keyframe.z);
        }
        controls.target.copy(target);
        controls.update?.();

        if (rerender) {
            renderPanel();
        }
        return true;
    };

    const handleFpvDisabled = () => {
        if (suppressNextFpvExitHandling) {
            suppressNextFpvExitHandling = false;
            return false;
        }
        if (!cameraControlState.snapOrbitToKeyframeOnFpvExit) return false;
        return applyResolvedKeyframe(getActiveOrBaseKeyframe());
    };

    const exitFpvAndRecenterOrbit = () => {
        disableFpvWithoutExitHandling();
        return recenterOrbitToSafePivot({ preservePosition: true });
    };

    const createLabeledField = ({ labelText, control }) => {
        const label = documentObject.createElement('label');
        label.className = 'rec-inline-field';

        const labelSpan = documentObject.createElement('span');
        labelSpan.textContent = labelText;
        label.appendChild(labelSpan);
        label.appendChild(control);

        return label;
    };

    const buildAutoMotionCard = ({
        title,
        note,
        enabled,
        onToggle,
        controlsContent,
    }) => {
        const card = documentObject.createElement('div');
        card.className = 'rec-auto-card';

        const header = documentObject.createElement('label');
        header.className = 'rec-auto-card-header';

        const checkbox = documentObject.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = enabled;
        checkbox.addEventListener('change', () => {
            onToggle(checkbox.checked);
            renderPanel();
        });

        const titleSpan = documentObject.createElement('span');
        titleSpan.textContent = title;

        header.appendChild(checkbox);
        header.appendChild(titleSpan);
        card.appendChild(header);

        const noteBlock = documentObject.createElement('div');
        noteBlock.className = 'rec-auto-card-note';
        noteBlock.textContent = note;
        card.appendChild(noteBlock);

        const fieldset = documentObject.createElement('fieldset');
        fieldset.className = 'rec-fieldset';
        fieldset.disabled = !cameraControlState.autoMoveEnabled || !enabled;
        fieldset.appendChild(controlsContent);
        card.appendChild(fieldset);

        return card;
    };

    const beginHotkeyCapture = ({ hotkeyKey, button, input }) => {
        button.disabled = true;
        button.textContent = 'Listening...';

        const handler = (event) => {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            persistHotkeyBinding(hotkeyKey, event.code);
            input.value = event.code;
            button.textContent = 'Record';
            button.disabled = false;
            documentObject.removeEventListener('keydown', handler, true);
        };

        documentObject.addEventListener('keydown', handler, true);
    };

    renderPanel = () => {
        sectionRoot.replaceChildren();

        const currentHotkeys = getCurrentHotkeyBindings();
        const currentKeyframe = cameraControlState.keyframes.find((candidate) => candidate.id === cameraControlState.currentKeyframeId) || null;

        const title = documentObject.createElement('h4');
        title.className = 'rec-section-title';
        title.textContent = 'Camera Control';
        sectionRoot.appendChild(title);

        const intro = documentObject.createElement('p');
        intro.className = 'rec-section-note';
        intro.textContent = 'Store reusable camera views, cycle them with hotkeys, and apply automatic spin, zoom, or slide motion while recording or exploring the scene.';
        sectionRoot.appendChild(intro);

        const fpvTitle = documentObject.createElement('div');
        fpvTitle.className = 'rec-subsection-title';
        fpvTitle.textContent = 'First-Person View';
        sectionRoot.appendChild(fpvTitle);

        const fpvToggleRow = documentObject.createElement('label');
        fpvToggleRow.className = 'rec-checkbox-row';
        const fpvCheckbox = documentObject.createElement('input');
        fpvCheckbox.type = 'checkbox';
        fpvCheckbox.checked = !!fpvControls?.isEnabled?.();
        fpvCheckbox.addEventListener('change', () => {
            fpvControls?.setEnabled?.(fpvCheckbox.checked);
            renderPanel();
        });
        const fpvToggleText = documentObject.createElement('span');
        fpvToggleText.textContent = 'Enable FPV Camera Control';
        fpvToggleRow.appendChild(fpvCheckbox);
        fpvToggleRow.appendChild(fpvToggleText);
        sectionRoot.appendChild(fpvToggleRow);

        const fpvNote = documentObject.createElement('div');
        fpvNote.className = 'rec-inline-note';
        fpvNote.textContent = fpvControls?.isEnabled?.()
            ? (fpvControls?.isPointerLocked?.()
                ? 'FPV is active and mouse-look is currently captured. Use Y to leave FPV, or press Escape to release the mouse and click the 3D canvas again when you want to keep looking around.'
                : 'FPV is enabled. Click the 3D canvas to capture mouse look, then use W/A/S/D plus Space, C, Shift, and E for creative-style flying and playback while the mode is active.')
            : 'FPV uses Minecraft-style creative flying: W/A/S/D for horizontal movement, Space to rise, C to drop, Shift for double speed, mouse movement for looking around, and Y to toggle the mode.';
        sectionRoot.appendChild(fpvNote);

        const snapOnExitToggle = documentObject.createElement('label');
        snapOnExitToggle.className = 'rec-checkbox-row';
        const snapOnExitCheckbox = documentObject.createElement('input');
        snapOnExitCheckbox.type = 'checkbox';
        snapOnExitCheckbox.checked = !!cameraControlState.snapOrbitToKeyframeOnFpvExit;
        snapOnExitCheckbox.addEventListener('change', () => {
            cameraControlState.snapOrbitToKeyframeOnFpvExit = snapOnExitCheckbox.checked;
            saveState();
            renderPanel();
        });
        const snapOnExitText = documentObject.createElement('span');
        snapOnExitText.textContent = 'Snap to Active/Base Keyframe When Leaving FPV';
        snapOnExitToggle.appendChild(snapOnExitCheckbox);
        snapOnExitToggle.appendChild(snapOnExitText);
        sectionRoot.appendChild(snapOnExitToggle);

        const snapOnExitNote = documentObject.createElement('div');
        snapOnExitNote.className = 'rec-inline-note';
        snapOnExitNote.textContent = 'If enabled, turning FPV off restores OrbitControls to the active keyframe, or the Base Keyframe when no active keyframe is selected.';
        sectionRoot.appendChild(snapOnExitNote);

        const fpvActionRow = documentObject.createElement('div');
        fpvActionRow.className = 'rec-action-row';

        const exitAndRecenterButton = documentObject.createElement('button');
        exitAndRecenterButton.type = 'button';
        exitAndRecenterButton.className = 'rec-secondary-btn';
        exitAndRecenterButton.textContent = 'Exit FPV and Recenter Orbit';
        exitAndRecenterButton.addEventListener('click', () => {
            exitFpvAndRecenterOrbit();
        });
        fpvActionRow.appendChild(exitAndRecenterButton);
        sectionRoot.appendChild(fpvActionRow);

        const recenterNote = documentObject.createElement('div');
        recenterNote.className = 'rec-inline-note';
        recenterNote.textContent = 'This keeps the current camera position, leaves FPV if needed, and points OrbitControls back at the active keyframe target or the Base Keyframe target.';
        sectionRoot.appendChild(recenterNote);

        const keyframeTitle = documentObject.createElement('div');
        keyframeTitle.className = 'rec-subsection-title';
        keyframeTitle.textContent = 'Set Keyframe';
        sectionRoot.appendChild(keyframeTitle);

        const keyframeToggle = documentObject.createElement('label');
        keyframeToggle.className = 'rec-checkbox-row';
        const keyframeCheckbox = documentObject.createElement('input');
        keyframeCheckbox.type = 'checkbox';
        keyframeCheckbox.checked = !!cameraControlState.enableKeyframeHotkeys;
        keyframeCheckbox.addEventListener('change', () => {
            cameraControlState.enableKeyframeHotkeys = keyframeCheckbox.checked;
            saveState();
            renderPanel();
        });
        const keyframeToggleText = documentObject.createElement('span');
        keyframeToggleText.textContent = 'Enable Keyframe Hotkeys';
        keyframeToggle.appendChild(keyframeCheckbox);
        keyframeToggle.appendChild(keyframeToggleText);
        sectionRoot.appendChild(keyframeToggle);

        const keyframeNote = documentObject.createElement('div');
        keyframeNote.className = 'rec-inline-note';
        keyframeNote.textContent = 'The Base Keyframe is used by Reset View. You can still reorder or delete any default row, and Reset Keyframes will rebuild the original starting set.';
        sectionRoot.appendChild(keyframeNote);

        const actionRow = documentObject.createElement('div');
        actionRow.className = 'rec-action-row';

        const addCurrentButton = documentObject.createElement('button');
        addCurrentButton.type = 'button';
        addCurrentButton.className = 'rec-secondary-btn';
        addCurrentButton.textContent = 'Add Current View';
        addCurrentButton.addEventListener('click', () => {
            captureCurrentKeyframe();
        });
        actionRow.appendChild(addCurrentButton);

        const updateActiveButton = documentObject.createElement('button');
        updateActiveButton.type = 'button';
        updateActiveButton.className = 'rec-secondary-btn';
        updateActiveButton.textContent = 'Update Active From Current';
        updateActiveButton.disabled = !currentKeyframe;
        updateActiveButton.addEventListener('click', () => {
            updateActiveKeyframeFromCurrentView();
        });
        actionRow.appendChild(updateActiveButton);

        const resetViewButton = documentObject.createElement('button');
        resetViewButton.type = 'button';
        resetViewButton.className = 'rec-secondary-btn';
        resetViewButton.textContent = 'Reset View';
        resetViewButton.addEventListener('click', () => {
            resetCameraView();
        });
        actionRow.appendChild(resetViewButton);

        const resetKeyframesButton = documentObject.createElement('button');
        resetKeyframesButton.type = 'button';
        resetKeyframesButton.className = 'rec-secondary-btn';
        resetKeyframesButton.textContent = 'Reset Keyframes';
        resetKeyframesButton.addEventListener('click', () => {
            resetKeyframes();
        });
        actionRow.appendChild(resetKeyframesButton);
        sectionRoot.appendChild(actionRow);

        const hotkeyFieldset = documentObject.createElement('fieldset');
        hotkeyFieldset.className = 'rec-fieldset';
        hotkeyFieldset.disabled = !cameraControlState.enableKeyframeHotkeys;

        const hotkeyGrid = documentObject.createElement('div');
        hotkeyGrid.className = 'rec-hotkey-grid';
        for (const hotkeyMeta of CAMERA_HOTKEY_META) {
            const row = documentObject.createElement('div');
            row.className = 'rec-hotkey-row';

            const labelBlock = documentObject.createElement('div');
            labelBlock.className = 'rec-hotkey-label';
            const labelText = documentObject.createElement('div');
            labelText.textContent = hotkeyMeta.label;
            const detailText = documentObject.createElement('small');
            detailText.textContent = hotkeyMeta.detail;
            labelBlock.appendChild(labelText);
            labelBlock.appendChild(detailText);

            const hotkeyInput = documentObject.createElement('input');
            hotkeyInput.type = 'text';
            hotkeyInput.readOnly = true;
            hotkeyInput.className = 'rec-hotkey-value';
            hotkeyInput.value = currentHotkeys[hotkeyMeta.key] || DEFAULT_KEYBOARD_HOTKEYS[hotkeyMeta.key] || '';

            const hotkeyRecordButton = documentObject.createElement('button');
            hotkeyRecordButton.type = 'button';
            hotkeyRecordButton.className = 'rec-mini-btn';
            hotkeyRecordButton.textContent = 'Record';
            hotkeyRecordButton.addEventListener('click', () => {
                beginHotkeyCapture({
                    hotkeyKey: hotkeyMeta.key,
                    button: hotkeyRecordButton,
                    input: hotkeyInput,
                });
            });

            row.appendChild(labelBlock);
            row.appendChild(hotkeyInput);
            row.appendChild(hotkeyRecordButton);
            hotkeyGrid.appendChild(row);
        }
        hotkeyFieldset.appendChild(hotkeyGrid);
        sectionRoot.appendChild(hotkeyFieldset);

        const keyframeWrap = documentObject.createElement('div');
        keyframeWrap.className = 'rec-keyframe-table-wrap';
        const keyframeTable = documentObject.createElement('div');
        keyframeTable.className = 'rec-keyframe-table';

        const headerRow = documentObject.createElement('div');
        headerRow.className = 'rec-keyframe-header';
        ['Keyframe', 'X', 'Y', 'Z', 'Yaw', 'Pitch', 'Dist', 'Actions'].forEach((headerText) => {
            const cell = documentObject.createElement('div');
            cell.textContent = headerText;
            headerRow.appendChild(cell);
        });
        keyframeTable.appendChild(headerRow);

        if (cameraControlState.keyframes.length === 0) {
            const emptyState = documentObject.createElement('div');
            emptyState.className = 'rec-keyframe-empty';
            emptyState.textContent = 'No keyframes saved yet. Add the current view to create one.';
            keyframeTable.appendChild(emptyState);
        } else {
            for (const keyframe of cameraControlState.keyframes) {
                const row = documentObject.createElement('div');
                row.className = 'rec-keyframe-row';
                if (keyframe.id === cameraControlState.currentKeyframeId) {
                    row.classList.add('is-active');
                }

                const nameCell = documentObject.createElement('div');
                nameCell.className = 'rec-keyframe-name';

                const nameInput = documentObject.createElement('input');
                nameInput.type = 'text';
                nameInput.value = keyframe.name;
                nameInput.className = 'rec-keyframe-text';
                nameInput.addEventListener('change', () => {
                    updateKeyframeField(keyframe.id, 'name', nameInput.value, nameInput);
                });
                nameCell.appendChild(nameInput);

                if (keyframe.isBase) {
                    const badge = documentObject.createElement('span');
                    badge.className = 'rec-keyframe-badge';
                    badge.textContent = 'Base';
                    nameCell.appendChild(badge);
                }
                row.appendChild(nameCell);

                const numericColumns = [
                    { field: 'x', min: -5000, max: 5000, step: 0.1 },
                    { field: 'y', min: -5000, max: 5000, step: 0.1 },
                    { field: 'z', min: -5000, max: 5000, step: 0.1 },
                    { field: 'yawDeg', min: -180, max: 180, step: 0.5 },
                    { field: 'pitchDeg', min: -MAX_CAMERA_PITCH_DEG, max: MAX_CAMERA_PITCH_DEG, step: 0.5 },
                    { field: 'distance', min: MIN_CAMERA_DISTANCE, max: 5000, step: 0.1 },
                ];

                for (const column of numericColumns) {
                    const input = documentObject.createElement('input');
                    input.type = 'number';
                    input.className = 'rec-keyframe-number';
                    input.value = `${keyframe[column.field]}`;
                    input.min = `${column.min}`;
                    input.max = `${column.max}`;
                    input.step = `${column.step}`;
                    input.addEventListener('change', () => {
                        updateKeyframeField(keyframe.id, column.field, input.value, input);
                    });
                    row.appendChild(input);
                }

                const actionsCell = documentObject.createElement('div');
                actionsCell.className = 'rec-keyframe-actions';

                const goButton = documentObject.createElement('button');
                goButton.type = 'button';
                goButton.className = 'rec-mini-btn';
                goButton.textContent = 'Go';
                goButton.addEventListener('click', () => {
                    applyKeyframeById(keyframe.id);
                });
                actionsCell.appendChild(goButton);

                const moveUpButton = documentObject.createElement('button');
                moveUpButton.type = 'button';
                moveUpButton.className = 'rec-mini-btn';
                moveUpButton.textContent = '↑';
                moveUpButton.addEventListener('click', () => {
                    moveKeyframe(keyframe.id, -1);
                });
                actionsCell.appendChild(moveUpButton);

                const moveDownButton = documentObject.createElement('button');
                moveDownButton.type = 'button';
                moveDownButton.className = 'rec-mini-btn';
                moveDownButton.textContent = '↓';
                moveDownButton.addEventListener('click', () => {
                    moveKeyframe(keyframe.id, 1);
                });
                actionsCell.appendChild(moveDownButton);

                const deleteButton = documentObject.createElement('button');
                deleteButton.type = 'button';
                deleteButton.className = 'rec-danger-btn';
                deleteButton.textContent = '×';
                deleteButton.addEventListener('click', () => {
                    deleteKeyframe(keyframe.id);
                });
                actionsCell.appendChild(deleteButton);

                row.appendChild(actionsCell);
                keyframeTable.appendChild(row);
            }
        }

        keyframeWrap.appendChild(keyframeTable);
        sectionRoot.appendChild(keyframeWrap);

        const autoMoveTitle = documentObject.createElement('div');
        autoMoveTitle.className = 'rec-subsection-title';
        autoMoveTitle.textContent = 'Auto-Move Camera';
        sectionRoot.appendChild(autoMoveTitle);

        const autoMoveToggle = documentObject.createElement('label');
        autoMoveToggle.className = 'rec-checkbox-row';
        const autoMoveCheckbox = documentObject.createElement('input');
        autoMoveCheckbox.type = 'checkbox';
        autoMoveCheckbox.checked = !!cameraControlState.autoMoveEnabled;
        autoMoveCheckbox.addEventListener('change', () => {
            cameraControlState.autoMoveEnabled = autoMoveCheckbox.checked;
            saveState();
            renderPanel();
        });
        const autoMoveText = documentObject.createElement('span');
        autoMoveText.textContent = 'Enable Automatic Camera Motion';
        autoMoveToggle.appendChild(autoMoveCheckbox);
        autoMoveToggle.appendChild(autoMoveText);
        sectionRoot.appendChild(autoMoveToggle);

        const autoMoveNote = documentObject.createElement('div');
        autoMoveNote.className = 'rec-inline-note';
        autoMoveNote.textContent = 'Spin orbits around the model, Zoom moves closer or farther from the current target, and Slide shifts the camera and target together across the scene.';
        sectionRoot.appendChild(autoMoveNote);

        const autoCardGrid = documentObject.createElement('div');
        autoCardGrid.className = 'rec-auto-card-grid';

        const spinGrid = documentObject.createElement('div');
        spinGrid.className = 'rec-auto-grid';
        spinGrid.appendChild(createLabeledField({
            labelText: 'Spin X Speed',
            control: createNumberInput({
                documentObject,
                value: cameraControlState.autoSpinXSpeed,
                min: 0,
                max: 180,
                step: 0.5,
                onChange: (value) => {
                    cameraControlState.autoSpinXSpeed = toFiniteNumber(value, cameraControlState.autoSpinXSpeed);
                    saveState();
                },
            }),
        }));
        spinGrid.appendChild(createLabeledField({
            labelText: 'Spin X Direction',
            control: createDirectionSelect({
                documentObject,
                options: [
                    { value: 1, label: 'Right' },
                    { value: -1, label: 'Left' },
                ],
                value: cameraControlState.autoSpinXDirection,
                onChange: (value) => {
                    cameraControlState.autoSpinXDirection = value >= 0 ? 1 : -1;
                    saveState();
                },
            }),
        }));
        spinGrid.appendChild(createLabeledField({
            labelText: 'Spin Y Speed',
            control: createNumberInput({
                documentObject,
                value: cameraControlState.autoSpinYSpeed,
                min: 0,
                max: 180,
                step: 0.5,
                onChange: (value) => {
                    cameraControlState.autoSpinYSpeed = toFiniteNumber(value, cameraControlState.autoSpinYSpeed);
                    saveState();
                },
            }),
        }));
        spinGrid.appendChild(createLabeledField({
            labelText: 'Spin Y Direction',
            control: createDirectionSelect({
                documentObject,
                options: [
                    { value: 1, label: 'Up' },
                    { value: -1, label: 'Down' },
                ],
                value: cameraControlState.autoSpinYDirection,
                onChange: (value) => {
                    cameraControlState.autoSpinYDirection = value >= 0 ? 1 : -1;
                    saveState();
                },
            }),
        }));
        autoCardGrid.appendChild(buildAutoMotionCard({
            title: 'Auto-Spin',
            note: 'Continuously orbit around the current target in horizontal and vertical directions.',
            enabled: cameraControlState.autoSpinEnabled,
            onToggle: (enabled) => {
                cameraControlState.autoSpinEnabled = enabled;
                saveState();
            },
            controlsContent: spinGrid,
        }));

        const zoomGrid = documentObject.createElement('div');
        zoomGrid.className = 'rec-auto-grid';
        zoomGrid.appendChild(createLabeledField({
            labelText: 'Zoom Speed',
            control: createNumberInput({
                documentObject,
                value: cameraControlState.autoZoomSpeed,
                min: 0,
                max: 250,
                step: 0.5,
                onChange: (value) => {
                    cameraControlState.autoZoomSpeed = toFiniteNumber(value, cameraControlState.autoZoomSpeed);
                    saveState();
                },
            }),
        }));
        zoomGrid.appendChild(createLabeledField({
            labelText: 'Zoom Direction',
            control: createDirectionSelect({
                documentObject,
                options: [
                    { value: -1, label: 'In' },
                    { value: 1, label: 'Out' },
                ],
                value: cameraControlState.autoZoomDirection,
                onChange: (value) => {
                    cameraControlState.autoZoomDirection = value >= 0 ? 1 : -1;
                    saveState();
                },
            }),
        }));
        autoCardGrid.appendChild(buildAutoMotionCard({
            title: 'Auto-Zoom',
            note: 'Push the camera toward or away from the model while keeping the current view angle.',
            enabled: cameraControlState.autoZoomEnabled,
            onToggle: (enabled) => {
                cameraControlState.autoZoomEnabled = enabled;
                saveState();
            },
            controlsContent: zoomGrid,
        }));

        const slideGrid = documentObject.createElement('div');
        slideGrid.className = 'rec-auto-grid';
        slideGrid.appendChild(createLabeledField({
            labelText: 'Slide X Speed',
            control: createNumberInput({
                documentObject,
                value: cameraControlState.autoSlideXSpeed,
                min: 0,
                max: 250,
                step: 0.5,
                onChange: (value) => {
                    cameraControlState.autoSlideXSpeed = toFiniteNumber(value, cameraControlState.autoSlideXSpeed);
                    saveState();
                },
            }),
        }));
        slideGrid.appendChild(createLabeledField({
            labelText: 'Slide X Direction',
            control: createDirectionSelect({
                documentObject,
                options: [
                    { value: 1, label: 'Right' },
                    { value: -1, label: 'Left' },
                ],
                value: cameraControlState.autoSlideXDirection,
                onChange: (value) => {
                    cameraControlState.autoSlideXDirection = value >= 0 ? 1 : -1;
                    saveState();
                },
            }),
        }));
        slideGrid.appendChild(createLabeledField({
            labelText: 'Slide Y Speed',
            control: createNumberInput({
                documentObject,
                value: cameraControlState.autoSlideYSpeed,
                min: 0,
                max: 250,
                step: 0.5,
                onChange: (value) => {
                    cameraControlState.autoSlideYSpeed = toFiniteNumber(value, cameraControlState.autoSlideYSpeed);
                    saveState();
                },
            }),
        }));
        slideGrid.appendChild(createLabeledField({
            labelText: 'Slide Y Direction',
            control: createDirectionSelect({
                documentObject,
                options: [
                    { value: 1, label: 'Up' },
                    { value: -1, label: 'Down' },
                ],
                value: cameraControlState.autoSlideYDirection,
                onChange: (value) => {
                    cameraControlState.autoSlideYDirection = value >= 0 ? 1 : -1;
                    saveState();
                },
            }),
        }));
        autoCardGrid.appendChild(buildAutoMotionCard({
            title: 'Auto-Slide',
            note: 'Move the camera and the orbit target together across the scene without changing the current view direction.',
            enabled: cameraControlState.autoSlideEnabled,
            onToggle: (enabled) => {
                cameraControlState.autoSlideEnabled = enabled;
                saveState();
            },
            controlsContent: slideGrid,
        }));

        sectionRoot.appendChild(autoCardGrid);
    };

    return {
        applyInitialState: () => {
            cameraControlState.currentKeyframeId = getBaseKeyframe()?.id || null;
            saveState();
            resetCameraView();
        },
        refresh: () => {
            renderPanel();
        },
        update: (deltaSec) => {
            if (!cameraControlState.autoMoveEnabled || deltaSec <= 0 || !camera || !controls) return false;

            let changed = false;

            const target = controls.target.clone();
            const offset = camera.position.clone().sub(target);
            if (offset.lengthSq() <= 0.000001) {
                offset.set(0, 0, 1);
            }

            if (cameraControlState.autoSpinEnabled) {
                const spherical = new Spherical().setFromVector3(offset);
                spherical.theta += MathUtils.degToRad(cameraControlState.autoSpinXSpeed * cameraControlState.autoSpinXDirection * deltaSec);
                spherical.phi = MathUtils.clamp(
                    spherical.phi + MathUtils.degToRad(cameraControlState.autoSpinYSpeed * cameraControlState.autoSpinYDirection * deltaSec),
                    0.05,
                    Math.PI - 0.05,
                );
                offset.setFromSpherical(spherical);
                camera.position.copy(target).add(offset);
                changed = true;
            }

            if (cameraControlState.autoZoomEnabled) {
                const distance = Math.max(MIN_CAMERA_DISTANCE, offset.length());
                const nextDistance = Math.max(
                    MIN_CAMERA_DISTANCE,
                    distance + (cameraControlState.autoZoomSpeed * cameraControlState.autoZoomDirection * deltaSec),
                );
                offset.setLength(nextDistance);
                camera.position.copy(target).add(offset);
                changed = true;
            }

            if (cameraControlState.autoSlideEnabled) {
                const forward = new Vector3();
                camera.getWorldDirection(forward);
                const right = new Vector3().crossVectors(forward, camera.up).normalize();
                const up = new Vector3().crossVectors(right, forward).normalize();
                const translation = right.multiplyScalar(cameraControlState.autoSlideXSpeed * cameraControlState.autoSlideXDirection * deltaSec)
                    .add(up.multiplyScalar(cameraControlState.autoSlideYSpeed * cameraControlState.autoSlideYDirection * deltaSec));

                camera.position.add(translation);
                controls.target.add(translation);
                changed = true;
            }

            return changed;
        },
        isKeyframeHotkeysEnabled: () => !!cameraControlState.enableKeyframeHotkeys,
        captureCurrentKeyframe: () => captureCurrentKeyframe(),
        cycleKeyframe,
        handleFpvDisabled,
        exitFpvAndRecenterOrbit,
        resetCameraView,
    };
};