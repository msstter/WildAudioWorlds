import { MOUSE } from 'three';

import { DEFAULT_INPUT_BINDINGS } from './inputBindings.js';

const clampPlaybackRate = (value) => Math.max(0.01, Math.min(20, value));

const formatPlaybackRate = (value) => {
    const rounded = Math.round(value * 100) / 100;
    return Number.isInteger(rounded) ? `${rounded}` : `${rounded}`;
};

const formatTransportTime = (timeSec) => Math.floor(timeSec / 60) + ':' + (`0${Math.floor(timeSec % 60)}`).slice(-2);

export const createAppRuntimeBindings = ({
    documentObject = document,
    windowObject = window,
    performanceObject = performance,
    settings,
    gui,
    uiContainer,
    renderer,
    labelRenderer,
    controls,
    camera,
    trajectoryVisualizer,
    floatingPanelDragManager,
    timbreSelectionBadge,
    timbreSelectionPanel,
    aboutOverlay,
    renderOrderModal,
    hotkeyModal,
    playBtn,
    restartBtn,
    speedBtn,
    speedMenu,
    customSpeedBtn,
    customSpeedRow,
    customSpeedInput,
    applyCustomSpeedBtn,
    preservePitchCheckbox,
    speedOptionButtons,
    progressBar,
    timeDisplay,
    audio,
    getCurrentHotkeys,
    saveHotkeysToStorage,
    ensureAudioContext,
    getTrajectoryDurationSec,
    getTrajectoryPlaybackTimeSec,
    resetTrajectoryPlaybackAnchor,
    syncVisualizerToCurrentTime,
    applyTerrainSettings,
    applyVisualizationMode,
    updateTimbreSelectionBadge,
    canDeleteSelectedTerrainOnset,
    deleteSelectedTerrainOnset,
    isTransportPlaybackLocked = () => false,
    isFirstPersonModeEnabled,
    isCameraKeyframeHotkeysEnabled,
    captureCameraKeyframe,
    cycleCameraKeyframe,
} = {}) => {
    let bound = false;
    let isSidebarCollapsed = false;
    let wheelGestureMode = null;
    let wheelGestureLastTs = 0;

    const mouseButtonActionToOrbitAction = {
        'Rotate Camera': MOUSE.ROTATE,
        'Zoom Camera': MOUSE.DOLLY,
        'Pan Camera': MOUSE.PAN,
        Disabled: -1,
    };

    const getCurrentInputBindings = () => ({
        ...DEFAULT_INPUT_BINDINGS,
        ...(getCurrentHotkeys?.() || {}),
    });

    const getBindingValue = (bindings, key) => bindings?.[key] ?? DEFAULT_INPUT_BINDINGS[key];

    const syncOrbitMouseBindings = (bindings = getCurrentInputBindings()) => {
        if (!controls?.mouseButtons) return;
        controls.mouseButtons.LEFT = mouseButtonActionToOrbitAction[getBindingValue(bindings, 'pointerLeftMouseButtonAction')] ?? MOUSE.ROTATE;
        controls.mouseButtons.MIDDLE = mouseButtonActionToOrbitAction[getBindingValue(bindings, 'pointerMiddleMouseButtonAction')] ?? MOUSE.DOLLY;
        controls.mouseButtons.RIGHT = mouseButtonActionToOrbitAction[getBindingValue(bindings, 'pointerRightMouseButtonAction')] ?? MOUSE.PAN;
    };

    const syncOrbitZoomDirection = (flipDirection = false) => {
        if (!controls) return;
        controls.zoomSpeed = flipDirection ? -1 : 1;
    };

    const getWheelBindingKeys = (gestureMode) => {
        switch (gestureMode) {
            case 'vertical':
                return {
                    actionKey: 'pointerVerticalScrollAction',
                    flipKey: 'pointerVerticalScrollFlipDirection',
                };
            case 'shift-vertical':
                return {
                    actionKey: 'pointerShiftVerticalScrollAction',
                    flipKey: 'pointerShiftVerticalScrollFlipDirection',
                };
            case 'mouse-horizontal':
                return {
                    actionKey: 'pointerMouseHorizontalScrollAction',
                    flipKey: 'pointerMouseHorizontalScrollFlipDirection',
                };
            case 'trackpad-horizontal':
                return {
                    actionKey: 'pointerTrackpadHorizontalScrollAction',
                    flipKey: 'pointerTrackpadHorizontalScrollFlipDirection',
                };
            default:
                return null;
        }
    };

    const updateBottomUiLayout = () => {
        const baseInset = 20;
        const sidebarVisible = gui.domElement.style.display !== 'none';
        const sidebarWidth = sidebarVisible ? gui.domElement.offsetWidth : 0;
        uiContainer.style.left = `${baseInset}px`;
        uiContainer.style.right = `${baseInset + sidebarWidth}px`;
    };

    const closeSpeedMenu = () => {
        speedMenu.classList.remove('open');
        customSpeedRow.classList.remove('open');
    };

    const setPreservePitch = (enabled) => {
        if ('preservesPitch' in audio) audio.preservesPitch = enabled;
        if ('mozPreservesPitch' in audio) audio.mozPreservesPitch = enabled;
        if ('webkitPreservesPitch' in audio) audio.webkitPreservesPitch = enabled;
    };

    const updateSpeedButtonState = () => {
        speedBtn.textContent = `⚙ ${formatPlaybackRate(audio.playbackRate)}x`;
        const activeRate = audio.playbackRate;
        for (const button of speedOptionButtons) {
            const rate = Number.parseFloat(button.dataset.rate);
            button.classList.toggle('active', Math.abs(rate - activeRate) < 0.0001);
        }
    };

    const applyPlaybackRate = (value) => {
        const nextRate = clampPlaybackRate(value);
        const currentAnchoredTimeSec = getTrajectoryPlaybackTimeSec?.() || 0;
        audio.playbackRate = nextRate;
        audio.defaultPlaybackRate = nextRate;
        resetTrajectoryPlaybackAnchor?.(currentAnchoredTimeSec);
        customSpeedInput.value = nextRate.toFixed(2);
        updateSpeedButtonState();
    };

    const togglePlayPause = () => {
        if (isTransportPlaybackLocked?.()) return;
        ensureAudioContext?.();
        if (audio.paused) {
            audio.play();
            playBtn.innerText = '⏸';
        } else {
            audio.pause();
            playBtn.innerText = '▶';
        }
    };

    const seekBySeconds = (deltaSeconds) => {
        if (isTransportPlaybackLocked?.()) return;
        const durationSec = getTrajectoryDurationSec?.() || 0;
        if (durationSec <= 0) return;
        const nextTimeSec = Math.max(0, Math.min(durationSec, (getTrajectoryPlaybackTimeSec?.() || 0) + deltaSeconds));
        audio.currentTime = nextTimeSec;
        resetTrajectoryPlaybackAnchor?.(nextTimeSec);
        syncVisualizerToCurrentTime?.();
    };

    const seekByFrames = (deltaFrames) => {
        if (isTransportPlaybackLocked?.()) return;
        const frameCount = trajectoryVisualizer?.points?.length || 0;
        const durationSec = getTrajectoryDurationSec?.() || 0;
        if (frameCount <= 0 || durationSec <= 0) return;

        const currentFrameIndex = trajectoryVisualizer.getFrameIndexAtTime(getTrajectoryPlaybackTimeSec?.() || 0, durationSec);
        const nextFrameIndex = Math.max(0, Math.min(frameCount - 1, currentFrameIndex + deltaFrames));
        audio.currentTime = trajectoryVisualizer.getFrameTimeAtIndex(nextFrameIndex, durationSec);
        resetTrajectoryPlaybackAnchor?.(audio.currentTime);
        syncVisualizerToCurrentTime?.();
    };

    const toggleFullscreen = () => {
        if (!documentObject.fullscreenElement) {
            documentObject.documentElement.requestFullscreen?.();
        } else {
            documentObject.exitFullscreen?.();
        }
    };

    const shouldIgnoreHotkeys = () => {
        const recordingOverlay = documentObject.getElementById('rec-modal-overlay');
        if (recordingOverlay?.classList.contains('open')) return true;

        const liveSourceOverlay = documentObject.getElementById('live-source-modal-overlay');
        if (liveSourceOverlay?.classList.contains('open')) return true;

        const activeElement = documentObject.activeElement;
        if (!activeElement) return false;
        const tagName = activeElement.tagName;
        return tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'SELECT' || activeElement.isContentEditable;
    };

    const toggleSettingsSidebar = () => {
        isSidebarCollapsed = !isSidebarCollapsed;
        gui.domElement.style.display = isSidebarCollapsed ? 'none' : 'block';
        updateBottomUiLayout();
    };

    const closeTransientMenus = () => {
        let closedAny = false;

        if (speedMenu.classList.contains('open') || customSpeedRow.classList.contains('open')) {
            closeSpeedMenu();
            closedAny = true;
        }
        if (aboutOverlay.style.display === 'flex') {
            aboutOverlay.style.display = 'none';
            closedAny = true;
        }
        if (renderOrderModal.style.display === 'flex') {
            renderOrderModal.style.display = 'none';
            closedAny = true;
        }
        if (hotkeyModal.style.display === 'flex') {
            hotkeyModal.style.display = 'none';
            saveHotkeysToStorage?.(getCurrentHotkeys?.());
            closedAny = true;
        }

        const recordingOverlay = documentObject.getElementById('rec-modal-overlay');
        if (recordingOverlay && recordingOverlay.classList.contains('open')) {
            recordingOverlay.classList.remove('open');
            closedAny = true;
        }

        const liveSourceOverlay = documentObject.getElementById('live-source-modal-overlay');
        if (liveSourceOverlay && liveSourceOverlay.classList.contains('open')) {
            liveSourceOverlay.classList.remove('open');
            closedAny = true;
        }

        return closedAny;
    };

    const bind = () => {
        if (bound) return;
        bound = true;

        syncOrbitMouseBindings();

        playBtn.addEventListener('click', () => {
            togglePlayPause();
        });

        renderer.domElement.addEventListener('pointerdown', () => {
            syncOrbitMouseBindings();
            syncOrbitZoomDirection(false);
        }, { capture: true });

        restartBtn.addEventListener('click', () => {
            if (isTransportPlaybackLocked?.()) return;
            if ((getTrajectoryDurationSec?.() || 0) <= 0) return;
            ensureAudioContext?.();
            audio.currentTime = 0;
            resetTrajectoryPlaybackAnchor?.(0);
            syncVisualizerToCurrentTime?.();
            if (audio.paused) {
                audio.play();
                playBtn.innerText = '⏸';
            }
        });

        speedBtn.addEventListener('click', (event) => {
            event.stopPropagation();
            speedMenu.classList.toggle('open');
        });

        customSpeedBtn.addEventListener('click', () => {
            customSpeedRow.classList.toggle('open');
            if (customSpeedRow.classList.contains('open')) {
                customSpeedInput.focus();
                customSpeedInput.select();
            }
        });

        applyCustomSpeedBtn.addEventListener('click', () => {
            applyPlaybackRate(Number.parseFloat(customSpeedInput.value || '1'));
        });

        customSpeedInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                applyPlaybackRate(Number.parseFloat(customSpeedInput.value || '1'));
            }
        });

        for (const button of speedOptionButtons) {
            button.addEventListener('click', () => {
                applyPlaybackRate(Number.parseFloat(button.dataset.rate));
            });
        }

        preservePitchCheckbox.addEventListener('change', () => {
            setPreservePitch(preservePitchCheckbox.checked);
        });

        documentObject.addEventListener('pointerdown', (event) => {
            const target = event.target;
            if (target instanceof Node && !speedMenu.contains(target) && target !== speedBtn) {
                closeSpeedMenu();
            }
        });

        documentObject.addEventListener('keydown', (event) => {
            if (!settings.enableHotkeys) return;

            const currentHotkeys = getCurrentHotkeys?.() || {};
            if (event.code === currentHotkeys.toggleSidebarOrCloseMenus) {
                event.preventDefault();
                const closed = closeTransientMenus();
                if (!closed) toggleSettingsSidebar();
                return;
            }

            if (shouldIgnoreHotkeys()) return;

            if ((event.code === 'Delete' || event.code === 'Backspace') && canDeleteSelectedTerrainOnset?.()) {
                event.preventDefault();
                if (deleteSelectedTerrainOnset?.()) return;
            }

            if (event.code === currentHotkeys.togglePlayPause) {
                event.preventDefault();
                togglePlayPause();
                return;
            }

            if (event.code === currentHotkeys.toggleFullscreen) {
                event.preventDefault();
                toggleFullscreen();
                return;
            }

            if (event.code === currentHotkeys.toggleRecordControl) {
                event.preventDefault();
                const recordButton = documentObject.getElementById('record-btn');
                recordButton?.click();
                return;
            }

            if (event.code === currentHotkeys.playFromBeginning) {
                event.preventDefault();
                restartBtn.click();
                return;
            }

            if (event.code === currentHotkeys.toggleSpeedMenu) {
                event.preventDefault();
                speedBtn.click();
                return;
            }

            if (isCameraKeyframeHotkeysEnabled?.()) {
                if (event.code === currentHotkeys.captureCameraKeyframe) {
                    event.preventDefault();
                    captureCameraKeyframe?.();
                    return;
                }

                if (event.code === currentHotkeys.nextCameraKeyframe || event.code === currentHotkeys.previousCameraKeyframe) {
                    event.preventDefault();
                    const direction = event.code === currentHotkeys.nextCameraKeyframe ? 1 : -1;
                    cycleCameraKeyframe?.(direction);
                    return;
                }
            }

            if (event.code === currentHotkeys.seekForward || event.code === currentHotkeys.seekBackward) {
                event.preventDefault();
                const direction = event.code === currentHotkeys.seekForward ? 1 : -1;
                if (event.shiftKey) {
                    seekBySeconds(direction * settings.keySecondStep);
                } else {
                    seekByFrames(direction * settings.keyFrameStepFrames);
                }
                return;
            }

            if (event.code === 'ArrowUp' || event.code === 'ArrowDown') {
                event.preventDefault();
                const direction = event.code === 'ArrowUp' ? 1 : -1;
                const delta = event.shiftKey ? 0.25 : 0.1;
                applyPlaybackRate(audio.playbackRate + direction * delta);
            }
        });

        renderer.domElement.addEventListener('wheel', (event) => {
            if (isFirstPersonModeEnabled?.()) return;
            const target = event.target;
            if (target instanceof Element) {
                if (
                    target.closest('.lil-gui') ||
                    target.closest('#ui-container') ||
                    target.closest('#speed-menu') ||
                    target.closest('#rec-modal-overlay') ||
                    target.closest('#hotkey-modal')
                ) {
                    return;
                }
            }

            const absX = Math.abs(event.deltaX);
            const absY = Math.abs(event.deltaY);
            const now = performanceObject.now();
            const gestureGapMs = 120;
            const currentBindings = getCurrentInputBindings();

            if ((now - wheelGestureLastTs) > gestureGapMs) {
                wheelGestureMode = null;
            }

            const isTrackpadLike = event.deltaMode === 0;
            const hasHorizontal = absX > 0.01;
            const hasVertical = absY > 0.01;

            if (!wheelGestureMode) {
                if (event.shiftKey && hasVertical) {
                    wheelGestureMode = 'shift-vertical';
                } else if (
                    getBindingValue(currentBindings, 'pointerTrackpadHorizontalScrollAction') !== 'Disabled'
                    && isTrackpadLike
                    && hasHorizontal
                    && absX >= absY * 0.6
                ) {
                    wheelGestureMode = 'trackpad-horizontal';
                } else if (
                    getBindingValue(currentBindings, 'pointerMouseHorizontalScrollAction') !== 'Disabled'
                    && !isTrackpadLike
                    && hasHorizontal
                ) {
                    wheelGestureMode = 'mouse-horizontal';
                } else if (hasVertical) {
                    wheelGestureMode = 'vertical';
                } else {
                    return;
                }
            }

            let rawDelta = 0;
            if (wheelGestureMode === 'trackpad-horizontal' || wheelGestureMode === 'mouse-horizontal') {
                if (!hasHorizontal) return;
                rawDelta = event.deltaX;
            } else if (wheelGestureMode === 'shift-vertical' || wheelGestureMode === 'vertical') {
                if (!hasVertical) return;
                rawDelta = event.deltaY;
            } else {
                return;
            }

            const bindingKeys = getWheelBindingKeys(wheelGestureMode);
            if (!bindingKeys) return;

            wheelGestureLastTs = now;

            const action = getBindingValue(currentBindings, bindingKeys.actionKey);
            const flipDirection = !!getBindingValue(currentBindings, bindingKeys.flipKey);

            if (action === 'Zoom Camera') {
                syncOrbitZoomDirection(flipDirection);
                return;
            }

            event.preventDefault();
            event.stopPropagation();
            event.stopImmediatePropagation();

            syncOrbitZoomDirection(false);

            if (action === 'Disabled') {
                return;
            }
            let direction = rawDelta > 0 ? 1 : -1;
            if (flipDirection) direction *= -1;
            seekBySeconds(direction * settings.keyWheelStepSeconds);
        }, { passive: false, capture: true });

        audio.addEventListener('timeupdate', () => {
            progressBar.value = (audio.currentTime / (audio.duration || 1)) * 100;
            timeDisplay.innerText = `${formatTransportTime(audio.currentTime)} / ${formatTransportTime(audio.duration || 0)}`;
        });

        ['play', 'playing', 'pause', 'seeked', 'ratechange', 'loadedmetadata', 'ended'].forEach((eventName) => {
            audio.addEventListener(eventName, () => {
                resetTrajectoryPlaybackAnchor?.();
            });
        });

        progressBar.addEventListener('input', () => {
            if (isTransportPlaybackLocked?.()) return;
            const durationSec = getTrajectoryDurationSec?.() || 0;
            if (durationSec <= 0) return;
            const progress = progressBar.value / 100;
            audio.currentTime = progress * durationSec;
            resetTrajectoryPlaybackAnchor?.(audio.currentTime);
            syncVisualizerToCurrentTime?.();
        });

        windowObject.addEventListener('resize', () => {
            camera.aspect = windowObject.innerWidth / windowObject.innerHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(windowObject.innerWidth, windowObject.innerHeight);
            labelRenderer.setSize(windowObject.innerWidth, windowObject.innerHeight);
            trajectoryVisualizer.setViewportSize(windowObject.innerWidth, windowObject.innerHeight);
            floatingPanelDragManager.setPanelPosition(
                timbreSelectionBadge,
                Number.parseFloat(timbreSelectionBadge.style.left) || 12,
                Number.parseFloat(timbreSelectionBadge.style.top) || 72,
            );
            floatingPanelDragManager.setPanelPosition(
                timbreSelectionPanel,
                Number.parseFloat(timbreSelectionPanel.style.left) || 12,
                Number.parseFloat(timbreSelectionPanel.style.top) || 188,
            );
            updateBottomUiLayout();
        });
    };

    return {
        applyInitialState: () => {
            const initialBindings = getCurrentInputBindings();
            syncOrbitMouseBindings(initialBindings);
            syncOrbitZoomDirection(false);
            setPreservePitch(true);
            applyPlaybackRate(1);
            applyTerrainSettings?.();
            applyVisualizationMode?.();
            updateBottomUiLayout();
            updateTimbreSelectionBadge?.();
        },
        bind,
        updateBottomUiLayout,
    };
};