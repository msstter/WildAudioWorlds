import { MathUtils, Vector3 } from 'three';

import { DEFAULT_KEYBOARD_HOTKEYS } from './inputBindings.js';

const DEFAULT_FPV_MOVE_SPEED = 55;
const DEFAULT_FPV_SPRINT_MULTIPLIER = 2;
const DEFAULT_FPV_LOOK_SENSITIVITY = 0.0022;
const DEFAULT_FPV_FOCUS_DISTANCE = 120;
const MIN_FPV_FOCUS_DISTANCE = 8;
const WORLD_UP = new Vector3(0, 1, 0);

const clampOrbitHandoffDistance = (distance) => MathUtils.clamp(
    Number.isFinite(distance) ? distance : DEFAULT_FPV_FOCUS_DISTANCE,
    MIN_FPV_FOCUS_DISTANCE,
    DEFAULT_FPV_FOCUS_DISTANCE,
);

const isEditableElement = (documentObject) => {
    const activeElement = documentObject.activeElement;
    if (!activeElement) return false;
    const tagName = activeElement.tagName;
    return tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'SELECT' || activeElement.isContentEditable;
};

const matchesBindingCode = (bindingCode, event) => {
    if (!bindingCode) return false;
    if (bindingCode === event.code) return true;
    if (bindingCode.startsWith('Shift') && event.key === 'Shift') return true;
    return false;
};

const POINTER_LOCK_BLOCKER_SELECTOR = [
    '#ui-container',
    '.lil-gui',
    'button',
    'input',
    'select',
    'textarea',
    'option',
    'label',
    'a[href]',
    '[role="button"]',
    '[role="dialog"]',
    '[contenteditable="true"]',
    '[contenteditable="plaintext-only"]',
    '[data-fpv-pointer-lock-blocker="true"]',
].join(',');

export const createFpvControls = ({
    documentObject = document,
    windowObject = window,
    renderer,
    camera,
    controls,
    settings,
    getCurrentHotkeys,
    onTogglePlayPause,
    onModeChange,
} = {}) => {
    let bound = false;
    let enabled = false;
    let pointerLocked = false;
    let pointerLockRequestPending = false;
    let yaw = 0;
    let pitch = 0;
    let focusDistance = DEFAULT_FPV_FOCUS_DISTANCE;

    const pressedCodes = new Set();
    const directionVector = new Vector3();
    const movementForward = new Vector3();
    const horizontalForward = new Vector3();
    const horizontalRight = new Vector3();
    const worldForward = new Vector3();
    const fpvCrosshair = documentObject.createElement('div');
    fpvCrosshair.className = 'fpv-crosshair';
    documentObject.body.appendChild(fpvCrosshair);

    const getHotkeys = () => ({
        ...DEFAULT_KEYBOARD_HOTKEYS,
        ...(getCurrentHotkeys?.() || {}),
    });

    const syncAnglesFromCamera = () => {
        camera.getWorldDirection(worldForward);
        yaw = Math.atan2(-worldForward.x, -worldForward.z);
        pitch = Math.asin(MathUtils.clamp(worldForward.y, -1, 1));

        const orbitDistance = controls?.target?.distanceTo?.(camera.position) ?? DEFAULT_FPV_FOCUS_DISTANCE;
        focusDistance = clampOrbitHandoffDistance(orbitDistance);
    };

    const syncOrbitTargetFromLook = () => {
        if (!controls?.target) return;
        camera.getWorldDirection(worldForward);
        controls.target.copy(camera.position).add(worldForward.multiplyScalar(focusDistance));
    };

    const applyLookAngles = () => {
        camera.rotation.order = 'YXZ';
        camera.rotation.y = yaw;
        camera.rotation.x = pitch;
        camera.rotation.z = 0;
        camera.updateMatrixWorld?.();
        syncOrbitTargetFromLook();
    };

    const focusRendererElement = () => {
        windowObject.focus?.();
        renderer?.domElement?.focus?.({ preventScroll: true });
    };

    const isPointerLockBlockedTarget = (target) => {
        if (!target || typeof target.closest !== 'function') return false;
        if (target === renderer?.domElement) return false;
        return !!target.closest(POINTER_LOCK_BLOCKER_SELECTOR);
    };

    const isEventInsideRendererBounds = (event) => {
        const rect = renderer?.domElement?.getBoundingClientRect?.();
        if (!rect) return false;
        return event.clientX >= rect.left
            && event.clientX <= rect.right
            && event.clientY >= rect.top
            && event.clientY <= rect.bottom;
    };

    const requestMouseLook = () => {
        const domElement = renderer?.domElement;
        if (!enabled || pointerLocked || pointerLockRequestPending || !domElement?.requestPointerLock) {
            return;
        }

        pointerLockRequestPending = true;
        focusRendererElement();

        try {
            const requestResult = domElement.requestPointerLock();
            if (typeof requestResult?.catch === 'function') {
                requestResult.catch((error) => {
                    pointerLockRequestPending = false;
                    console.warn('FPV pointer lock request failed.', error);
                });
            }
        } catch (error) {
            pointerLockRequestPending = false;
            console.warn('FPV pointer lock request failed.', error);
        }
    };

    const releaseMouseLook = () => {
        if (documentObject.pointerLockElement === renderer?.domElement) {
            documentObject.exitPointerLock?.();
        }
    };

    const notifyModeChange = () => {
        fpvCrosshair.classList.toggle('is-visible', enabled);
        onModeChange?.(enabled, pointerLocked);
    };

    const setEnabled = (nextEnabled, { requestPointerLock = false } = {}) => {
        if (enabled === nextEnabled) {
            if (enabled && requestPointerLock) {
                requestMouseLook();
            }
            return enabled;
        }

        enabled = nextEnabled;
        pressedCodes.clear();

        if (enabled) {
            syncAnglesFromCamera();
            if (controls) {
                controls.enabled = false;
            }
            if (requestPointerLock) {
                requestMouseLook();
            }
        } else {
            pointerLocked = false;
            pointerLockRequestPending = false;
            releaseMouseLook();
            if (controls) {
                controls.enabled = true;
                focusDistance = clampOrbitHandoffDistance(focusDistance);
                syncOrbitTargetFromLook();
                controls.update?.();
            }
        }

        notifyModeChange();
        return enabled;
    };

    const toggleEnabled = (options = {}) => setEnabled(!enabled, options);

    const isMovementBinding = (event, hotkeys) => (
        matchesBindingCode(hotkeys.fpvMoveForward, event)
        || matchesBindingCode(hotkeys.fpvMoveBackward, event)
        || matchesBindingCode(hotkeys.fpvMoveLeft, event)
        || matchesBindingCode(hotkeys.fpvMoveRight, event)
        || matchesBindingCode(hotkeys.fpvMoveUp, event)
        || matchesBindingCode(hotkeys.fpvMoveDown, event)
        || matchesBindingCode(hotkeys.fpvSprint, event)
    );

    const isBindingPressed = (bindingCode) => {
        if (!bindingCode) return false;
        if (pressedCodes.has(bindingCode)) return true;
        if (bindingCode.startsWith('Shift')) {
            return pressedCodes.has('ShiftLeft') || pressedCodes.has('ShiftRight');
        }
        return false;
    };

    const handleKeyDown = (event) => {
        const hotkeys = getHotkeys();
        if (!pointerLocked && isEditableElement(documentObject)) {
            return;
        }

        if (matchesBindingCode(hotkeys.toggleFpvMode, event)) {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
            toggleEnabled();
            return;
        }

        if (!enabled) return;

        if (matchesBindingCode(hotkeys.fpvPlayPause, event)) {
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
            onTogglePlayPause?.();
            return;
        }

        if (!isMovementBinding(event, hotkeys)) return;

        pressedCodes.add(event.code);
        if (event.key === 'Shift') {
            pressedCodes.add('ShiftLeft');
            pressedCodes.add('ShiftRight');
        }
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
    };

    const handleKeyUp = (event) => {
        if (!enabled) return;

        pressedCodes.delete(event.code);
        if (event.key === 'Shift') {
            pressedCodes.delete('ShiftLeft');
            pressedCodes.delete('ShiftRight');
        }
    };

    const handleMouseMove = (event) => {
        if (!enabled || !pointerLocked) return;

        yaw -= event.movementX * DEFAULT_FPV_LOOK_SENSITIVITY;
        pitch = MathUtils.clamp(
            pitch - (event.movementY * DEFAULT_FPV_LOOK_SENSITIVITY),
            MathUtils.degToRad(-89.5),
            MathUtils.degToRad(89.5),
        );
        applyLookAngles();
        event.preventDefault();
        event.stopPropagation();
    };

    const handleWindowPointerDown = (event) => {
        if (!enabled || pointerLocked || event.button !== 0) return;
        if (!isEventInsideRendererBounds(event)) return;
        if (isPointerLockBlockedTarget(event.target)) return;

        requestMouseLook();
        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();
    };

    const bind = () => {
        if (bound) return;
        bound = true;

        documentObject.addEventListener('pointerlockchange', () => {
            pointerLockRequestPending = false;
            pointerLocked = documentObject.pointerLockElement === renderer?.domElement;
            if (!pointerLocked) {
                pressedCodes.clear();
            }
            notifyModeChange();
        });

        documentObject.addEventListener('pointerlockerror', (event) => {
            pointerLockRequestPending = false;
            console.warn('FPV pointer lock request was denied.', event);
            notifyModeChange();
        });

        windowObject.addEventListener('keydown', handleKeyDown, true);
        windowObject.addEventListener('keyup', handleKeyUp, true);
        windowObject.addEventListener('pointerdown', handleWindowPointerDown, { capture: true });
        windowObject.addEventListener('blur', () => {
            pressedCodes.clear();
            pointerLockRequestPending = false;
        });
        documentObject.addEventListener('mousemove', handleMouseMove, true);

        renderer?.domElement?.addEventListener('wheel', (event) => {
            if (!enabled) return;
            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();
        }, { passive: false, capture: true });
    };

    return {
        bind,
        isEnabled: () => enabled,
        isPointerLocked: () => pointerLocked,
        setEnabled: (nextEnabled, options = {}) => setEnabled(!!nextEnabled, options),
        toggleEnabled,
        update: (deltaSec) => {
            if (!enabled || deltaSec <= 0) return false;

            const hotkeys = getHotkeys();
            const moveSpeed = DEFAULT_FPV_MOVE_SPEED * (isBindingPressed(hotkeys.fpvSprint) ? DEFAULT_FPV_SPRINT_MULTIPLIER : 1);
            const useLookDirectionMovement = settings?.fpvForwardFollowsLook !== false;

            camera.getWorldDirection(horizontalForward);
            movementForward.copy(horizontalForward);
            horizontalForward.y = 0;
            if (horizontalForward.lengthSq() <= 0.000001) {
                horizontalForward.set(Math.sin(yaw), 0, Math.cos(yaw));
            }
            horizontalForward.normalize();

            if (movementForward.lengthSq() <= 0.000001) {
                movementForward.copy(horizontalForward);
            } else if (!useLookDirectionMovement) {
                movementForward.copy(horizontalForward);
            } else {
                movementForward.normalize();
            }

            horizontalRight.crossVectors(horizontalForward, WORLD_UP).normalize();

            directionVector.set(0, 0, 0);
            if (isBindingPressed(hotkeys.fpvMoveForward)) directionVector.add(movementForward);
            if (isBindingPressed(hotkeys.fpvMoveBackward)) directionVector.addScaledVector(movementForward, -1);
            if (isBindingPressed(hotkeys.fpvMoveRight)) directionVector.add(horizontalRight);
            if (isBindingPressed(hotkeys.fpvMoveLeft)) directionVector.addScaledVector(horizontalRight, -1);
            if (isBindingPressed(hotkeys.fpvMoveUp)) directionVector.y += 1;
            if (isBindingPressed(hotkeys.fpvMoveDown)) directionVector.y -= 1;

            if (directionVector.lengthSq() <= 0.000001) return false;

            directionVector.normalize().multiplyScalar(moveSpeed * deltaSec);
            camera.position.add(directionVector);
            if (controls?.target) {
                syncOrbitTargetFromLook();
            }
            return true;
        },
    };
};