import { encodeAudioDataAsWavBlob } from '../shared/analysis/exportPayloads.js';
import { sanitizeFileLabel, triggerFileSave } from '../shared/ui/fileSave.js';

const DEFAULT_FFT_SIZE = 512;
const DEFAULT_STATUS_LABEL = 'Inactive';
const ASSET_CAPTURE_BUFFER_SIZE = 4096;
const AUDIO_MIME_CANDIDATES = [
    { mimeType: 'audio/webm;codecs=opus', extension: 'webm' },
    { mimeType: 'audio/webm', extension: 'webm' },
    { mimeType: 'audio/ogg;codecs=opus', extension: 'ogg' },
    { mimeType: 'audio/ogg', extension: 'ogg' },
    { mimeType: 'audio/mp4', extension: 'm4a' },
];

const formatTimestamp = (date) => {
    const parts = [
        date.getFullYear(),
        `${date.getMonth() + 1}`.padStart(2, '0'),
        `${date.getDate()}`.padStart(2, '0'),
        `${date.getHours()}`.padStart(2, '0'),
        `${date.getMinutes()}`.padStart(2, '0'),
        `${date.getSeconds()}`.padStart(2, '0'),
    ];
    return `${parts[0]}${parts[1]}${parts[2]}-${parts[3]}${parts[4]}${parts[5]}`;
};

const buildDefaultState = () => ({
    active: false,
    mode: 'inactive',
    deviceId: '',
    deviceLabel: '',
    fftSize: DEFAULT_FFT_SIZE,
    monitorOutput: false,
    statusLabel: DEFAULT_STATUS_LABEL,
    errorMessage: '',
});

const buildDeviceLabel = (device, index) => {
    const label = String(device?.label || '').trim();
    if (label) return label;
    return index === 0 ? 'Default Microphone' : `Microphone ${index + 1}`;
};

const pickAudioMime = (MediaRecorderClass) => {
    if (typeof MediaRecorderClass?.isTypeSupported !== 'function') {
        return AUDIO_MIME_CANDIDATES[0];
    }

    return AUDIO_MIME_CANDIDATES.find((candidate) => MediaRecorderClass.isTypeSupported(candidate.mimeType))
        || AUDIO_MIME_CANDIDATES[0];
};

const stopMediaTracks = (stream) => {
    if (!stream) return;
    for (const track of stream.getTracks()) {
        try {
            track.stop();
        } catch {
            // Ignore track shutdown failures.
        }
    }
};

const buildRecordedAssetLabel = ({ requestedLabel = '', deviceLabel = '', startedAt = new Date() } = {}) => {
    const trimmedLabel = String(requestedLabel || '').trim();
    if (trimmedLabel) return trimmedLabel;

    const fallbackDeviceLabel = String(deviceLabel || '').trim() || 'Recorded Session';
    return `${fallbackDeviceLabel} ${formatTimestamp(startedAt)}`;
};

const buildWavBlobFromPcmChunks = (session) => {
    const pcmChunks = Array.isArray(session?.pcmChunks) ? session.pcmChunks : [];
    if (pcmChunks.length === 0) {
        throw new Error('No microphone PCM data was captured for the new asset.');
    }

    const totalSamples = pcmChunks.reduce((sum, chunk) => sum + (chunk?.length || 0), 0);
    if (!Number.isFinite(totalSamples) || totalSamples <= 0) {
        throw new Error('Recorded asset capture produced an empty audio buffer.');
    }
    if (totalSamples < 1024) {
        throw new Error('Recorded asset is too short. Record a slightly longer sound and try again.');
    }

    const monoChannel = new Float32Array(totalSamples);
    let writeOffset = 0;
    for (const chunk of pcmChunks) {
        if (!(chunk instanceof Float32Array) || chunk.length === 0) continue;
        monoChannel.set(chunk, writeOffset);
        writeOffset += chunk.length;
    }

    return encodeAudioDataAsWavBlob({
        sampleRate: Math.max(1, Math.round(Number(session?.sampleRate) || 44100)),
        channelData: [monoChannel],
        totalSamples: monoChannel.length,
    });
};

export const createLivePerformanceControls = ({
    documentObject = document,
    navigatorObject = navigator,
    MediaRecorderClass = globalThis.MediaRecorder,
    ensureAudioContext,
    getAudioContext,
    liveModalOverlay,
    liveSourceInput,
    liveSourceFftSize,
    liveSourceMonitorToggle,
    liveSourceRefreshBtn,
    liveSourceStreamBtn,
    liveSourceRecordBtn,
    liveSourceCaptureBtn,
    liveSourceCancelBtn,
    liveSourceStatusText,
    liveSourceAssetLabelInput,
    liveSourceIncludeMfccToggle,
    liveSourceProgressBlock,
    liveSourceProgressBar,
    liveSourceProgressText,
    onSessionStateChange,
    onImportRecordedAsset,
    onBeforeStart,
    onWarn,
    onError,
} = {}) => {
    let bound = false;
    let availableInputs = [];
    let activeSession = null;
    let assetCaptureSession = null;
    let liveState = buildDefaultState();
    let pendingStartToken = 0;
    let isStartingSession = false;
    let isImportingAsset = false;

    const emitState = (partialState = {}) => {
        liveState = {
            ...liveState,
            ...partialState,
        };

        if (liveSourceStatusText) {
            liveSourceStatusText.textContent = liveState.statusLabel || DEFAULT_STATUS_LABEL;
            liveSourceStatusText.dataset.mode = liveState.mode || 'inactive';
        }

        onSessionStateChange?.({ ...liveState });
        return liveState;
    };

    const setProgressState = ({ visible = false, value = 0, label = 'Idle' } = {}) => {
        if (liveSourceProgressBlock) {
            liveSourceProgressBlock.hidden = !visible;
        }
        if (liveSourceProgressBar) {
            liveSourceProgressBar.value = Math.max(0, Math.min(100, Number(value) || 0));
        }
        if (liveSourceProgressText) {
            liveSourceProgressText.textContent = label;
        }
    };

    const clearProgressState = () => {
        setProgressState({ visible: false, value: 0, label: 'Idle' });
    };

    const closeModal = ({ force = false } = {}) => {
        if (!force && (assetCaptureSession || isImportingAsset)) return;
        liveModalOverlay?.classList.remove('open');
    };

    const isModalOpen = () => !!liveModalOverlay?.classList.contains('open');

    const getSelectedDeviceLabel = () => {
        const selectedId = String(liveSourceInput?.value || '').trim();
        const selectedDevice = availableInputs.find((device) => device.deviceId === selectedId);
        if (selectedDevice) return buildDeviceLabel(selectedDevice, availableInputs.indexOf(selectedDevice));
        return availableInputs.length > 0 ? buildDeviceLabel(availableInputs[0], 0) : 'Microphone';
    };

    const updateActionAvailability = () => {
        const hasInputs = availableInputs.length > 0;
        const configLocked = isStartingSession || !!activeSession || !!assetCaptureSession || isImportingAsset;

        if (liveSourceInput) liveSourceInput.disabled = !hasInputs || configLocked;
        if (liveSourceFftSize) liveSourceFftSize.disabled = configLocked;
        if (liveSourceMonitorToggle) liveSourceMonitorToggle.disabled = configLocked;
        if (liveSourceRefreshBtn) liveSourceRefreshBtn.disabled = configLocked;
        if (liveSourceStreamBtn) liveSourceStreamBtn.disabled = !hasInputs || configLocked;
        if (liveSourceRecordBtn) liveSourceRecordBtn.disabled = !hasInputs || configLocked || typeof MediaRecorderClass !== 'function';
        if (liveSourceAssetLabelInput) liveSourceAssetLabelInput.disabled = configLocked;
        if (liveSourceIncludeMfccToggle) liveSourceIncludeMfccToggle.disabled = configLocked;
        if (liveSourceCaptureBtn) {
            liveSourceCaptureBtn.disabled = !hasInputs || isStartingSession || !!activeSession || isImportingAsset;
            liveSourceCaptureBtn.textContent = assetCaptureSession ? 'Stop & Import' : 'Record New Asset';
        }
        if (liveSourceCancelBtn) {
            liveSourceCancelBtn.disabled = isImportingAsset;
            liveSourceCancelBtn.textContent = assetCaptureSession ? 'Cancel Recording' : 'Cancel';
        }
    };

    const populateDeviceOptions = (preferredDeviceId = '') => {
        if (!liveSourceInput) return;

        liveSourceInput.replaceChildren();
        if (availableInputs.length === 0) {
            const option = documentObject.createElement('option');
            option.value = '';
            option.textContent = 'No microphone found';
            liveSourceInput.appendChild(option);
            updateActionAvailability();
            return;
        }

        availableInputs.forEach((device, index) => {
            const option = documentObject.createElement('option');
            option.value = device.deviceId;
            option.textContent = buildDeviceLabel(device, index);
            liveSourceInput.appendChild(option);
        });

        const fallbackDeviceId = availableInputs.some((device) => device.deviceId === preferredDeviceId)
            ? preferredDeviceId
            : availableInputs[0].deviceId;
        liveSourceInput.value = fallbackDeviceId;
        updateActionAvailability();
    };

    const refreshInputs = async ({ preserveSelection = true } = {}) => {
        const previousSelection = preserveSelection ? String(liveSourceInput?.value || '').trim() : '';

        try {
            const devices = await navigatorObject?.mediaDevices?.enumerateDevices?.();
            availableInputs = Array.isArray(devices)
                ? devices.filter((device) => device.kind === 'audioinput')
                : [];
        } catch (error) {
            availableInputs = [];
            onWarn?.('Failed to enumerate microphone inputs:', error);
        }

        populateDeviceOptions(previousSelection);
        return availableInputs;
    };

    const syncAnalyserConfig = (binCount) => {
        if (!activeSession?.analyser || !Number.isFinite(binCount) || binCount <= 0) return null;
        activeSession.analyser.fftSize = Math.max(32, Math.round(binCount) * 2);
        activeSession.frequencyData = new Uint8Array(activeSession.analyser.frequencyBinCount);
        if (liveSourceFftSize) {
            const nextFftSize = `${activeSession.analyser.fftSize}`;
            const hasOption = Array.from(liveSourceFftSize.options || []).some((option) => option.value === nextFftSize);
            if (hasOption) {
                liveSourceFftSize.value = nextFftSize;
            }
        }
        emitState({ fftSize: activeSession.analyser.fftSize });
        return activeSession.frequencyData;
    };

    const readFrequencyFrame = () => {
        if (!activeSession?.analyser || !activeSession.frequencyData) return null;
        activeSession.analyser.getByteFrequencyData(activeSession.frequencyData);
        return activeSession.frequencyData;
    };

    const disconnectAudioNodes = (session) => {
        try {
            session?.sourceNode?.disconnect?.();
        } catch {
            // Ignore disconnect errors.
        }
        try {
            session?.monitorGainNode?.disconnect?.();
        } catch {
            // Ignore disconnect errors.
        }
        try {
            session?.processorNode?.disconnect?.();
        } catch {
            // Ignore disconnect errors.
        }
        try {
            session?.silentMonitorGainNode?.disconnect?.();
        } catch {
            // Ignore disconnect errors.
        }
    };

    const saveRecording = async (session) => {
        if (!session || !Array.isArray(session.recordedChunks) || session.recordedChunks.length === 0) return;

        const { mimeType, extension } = session.recordingFormat;
        const blob = new Blob(session.recordedChunks, { type: mimeType });
        if (blob.size === 0) return;

        const fileStem = sanitizeFileLabel(session.deviceLabel || 'live-source', 'live-source');
        const suggestedName = `${fileStem}-${formatTimestamp(session.startedAt)}.${extension}`;
        await triggerFileSave(blob, extension, {
            suggestedName,
            description: 'Live Performance Recording',
        });
    };

    const cancelPendingStart = () => {
        if (!isStartingSession) return false;

        pendingStartToken += 1;
        isStartingSession = false;
        emitState({
            active: false,
            mode: 'inactive',
            statusLabel: DEFAULT_STATUS_LABEL,
            errorMessage: '',
        });
        updateActionAvailability();
        return true;
    };

    const stopLiveSession = async ({ saveRecording: shouldSaveRecording = true, closeDialog = true } = {}) => {
        const session = activeSession;
        if (!session) {
            if (closeDialog) closeModal({ force: true });
            return false;
        }

        activeSession = null;

        if (closeDialog) closeModal({ force: true });

        if (session.mediaRecorder && session.mediaRecorder.state !== 'inactive') {
            await new Promise((resolve) => {
                const finalize = async () => {
                    if (shouldSaveRecording) {
                        await saveRecording(session);
                    }
                    resolve();
                };
                session.mediaRecorder.addEventListener('stop', () => {
                    void finalize();
                }, { once: true });
                session.mediaRecorder.stop();
            });
        } else if (shouldSaveRecording) {
            await saveRecording(session);
        }

        disconnectAudioNodes(session);
        stopMediaTracks(session.stream);

        emitState({
            active: false,
            mode: 'inactive',
            statusLabel: DEFAULT_STATUS_LABEL,
            errorMessage: '',
        });
        return true;
    };

    const stopAssetCapture = async ({ importAsset = true, closeDialog = true } = {}) => {
        const session = assetCaptureSession;
        if (!session) {
            if (closeDialog) closeModal({ force: true });
            return false;
        }

        assetCaptureSession = null;
        updateActionAvailability();

        try {
            if (importAsset) {
                emitState({
                    active: false,
                    mode: 'importing-asset',
                    statusLabel: 'Preparing recorded asset...',
                    errorMessage: '',
                });
                setProgressState({
                    visible: true,
                    value: 20,
                    label: 'Finalizing microphone recording...',
                });
            }

            if (session.mediaRecorder && session.mediaRecorder.state !== 'inactive') {
                await new Promise((resolve) => {
                    session.mediaRecorder.addEventListener('stop', () => {
                        resolve();
                    }, { once: true });
                    session.mediaRecorder.stop();
                });
            }
        } finally {
            disconnectAudioNodes(session);
            stopMediaTracks(session.stream);
        }

        if (!importAsset) {
            clearProgressState();
            emitState({
                active: false,
                mode: 'inactive',
                statusLabel: DEFAULT_STATUS_LABEL,
                errorMessage: '',
            });
            if (closeDialog) closeModal({ force: true });
            return true;
        }

        isImportingAsset = true;
        updateActionAvailability();

        try {
            const assetLabel = buildRecordedAssetLabel({
                requestedLabel: session.requestedLabel,
                deviceLabel: session.deviceLabel,
                startedAt: session.startedAt,
            });

            setProgressState({
                visible: true,
                value: 35,
                label: 'Building WAV from microphone PCM...',
            });
            const audioBlob = buildWavBlobFromPcmChunks(session);

            if (typeof onImportRecordedAsset !== 'function') {
                throw new Error('Recorded asset import is unavailable in this build.');
            }

            await onImportRecordedAsset({
                assetLabel,
                audioBlob,
                includeMfcc: session.includeMfcc,
                deviceId: session.deviceId,
                deviceLabel: session.deviceLabel,
                startedAt: session.startedAt,
                suggestedFileStem: sanitizeFileLabel(assetLabel, 'recorded-audio'),
            }, ({ value = 0, label = 'Importing recorded asset...' } = {}) => {
                setProgressState({ visible: true, value, label });
            });

            setProgressState({
                visible: true,
                value: 100,
                label: 'Rendered recorded asset.',
            });
            emitState({
                active: false,
                mode: 'inactive',
                statusLabel: `Imported: ${assetLabel}`,
                errorMessage: '',
            });
            if (liveSourceAssetLabelInput) {
                liveSourceAssetLabelInput.value = '';
            }
            if (closeDialog) closeModal({ force: true });
            return true;
        } catch (error) {
            emitState({
                active: false,
                mode: 'inactive',
                statusLabel: error?.message ? `Recorded Asset Error: ${error.message}` : 'Recorded Asset Error',
                errorMessage: error?.message || 'Failed to import recorded asset.',
            });
            setProgressState({
                visible: true,
                value: 0,
                label: error?.message || 'Recorded asset import failed.',
            });
            onError?.('Failed to import recorded asset:', error);
            return false;
        } finally {
            isImportingAsset = false;
            updateActionAvailability();
        }
    };

    const stopSession = async ({ saveRecording: shouldSaveRecording = true, closeDialog = true } = {}) => {
        if (assetCaptureSession) {
            return stopAssetCapture({ importAsset: shouldSaveRecording, closeDialog });
        }

        if (isStartingSession && !activeSession) {
            const canceled = cancelPendingStart();
            if (closeDialog) closeModal({ force: true });
            return canceled;
        }

        return stopLiveSession({ saveRecording: shouldSaveRecording, closeDialog });
    };

    const startSession = async ({ mode = 'streaming' } = {}) => {
        if (activeSession || assetCaptureSession || isStartingSession || isImportingAsset) return null;

        const selectedDeviceId = String(liveSourceInput?.value || '').trim();
        const fftSize = Math.max(256, Number.parseInt(liveSourceFftSize?.value || `${DEFAULT_FFT_SIZE}`, 10) || DEFAULT_FFT_SIZE);
        const shouldMonitorOutput = !!liveSourceMonitorToggle?.checked;
        const startToken = pendingStartToken + 1;
        pendingStartToken = startToken;
        isStartingSession = true;

        emitState({
            active: true,
            mode: 'starting',
            deviceId: selectedDeviceId,
            deviceLabel: getSelectedDeviceLabel(),
            fftSize,
            monitorOutput: shouldMonitorOutput,
            statusLabel: mode === 'recording'
                ? 'Starting live recording...'
                : 'Starting live stream...',
            errorMessage: '',
        });
        updateActionAvailability();
        closeModal({ force: true });

        try {
            await onBeforeStart?.({
                mode,
                deviceId: selectedDeviceId,
                deviceLabel: getSelectedDeviceLabel(),
                fftSize,
                monitorOutput: shouldMonitorOutput,
            });

            ensureAudioContext?.();
            const audioContext = getAudioContext?.();
            if (!audioContext) {
                throw new Error('AudioContext is unavailable for live microphone capture.');
            }
            if (audioContext.state === 'suspended') {
                await audioContext.resume();
            }

            const constraints = {
                audio: {
                    deviceId: selectedDeviceId ? { exact: selectedDeviceId } : undefined,
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false,
                },
            };
            const stream = await navigatorObject.mediaDevices.getUserMedia(constraints);
            if (startToken !== pendingStartToken) {
                stopMediaTracks(stream);
                return null;
            }

            const sourceNode = audioContext.createMediaStreamSource(stream);
            const analyser = audioContext.createAnalyser();
            analyser.fftSize = fftSize;
            analyser.smoothingTimeConstant = 0.68;
            sourceNode.connect(analyser);

            let monitorGainNode = null;
            if (shouldMonitorOutput) {
                monitorGainNode = audioContext.createGain();
                monitorGainNode.gain.value = 1;
                sourceNode.connect(monitorGainNode);
                monitorGainNode.connect(audioContext.destination);
            }

            const session = {
                mode,
                stream,
                sourceNode,
                analyser,
                frequencyData: new Uint8Array(analyser.frequencyBinCount),
                monitorGainNode,
                mediaRecorder: null,
                recordedChunks: [],
                recordingFormat: pickAudioMime(MediaRecorderClass),
                deviceId: selectedDeviceId,
                deviceLabel: getSelectedDeviceLabel(),
                startedAt: new Date(),
            };

            if (mode === 'recording') {
                if (typeof MediaRecorderClass !== 'function') {
                    throw new Error('MediaRecorder is unavailable for live audio recording.');
                }
                const recorderOptions = session.recordingFormat?.mimeType
                    ? { mimeType: session.recordingFormat.mimeType }
                    : undefined;
                session.mediaRecorder = new MediaRecorderClass(stream, recorderOptions);
                session.mediaRecorder.ondataavailable = (event) => {
                    if (event.data?.size > 0) {
                        session.recordedChunks.push(event.data);
                    }
                };
                session.mediaRecorder.start(250);
            }

            activeSession = session;
            emitState({
                active: true,
                mode,
                deviceId: session.deviceId,
                deviceLabel: session.deviceLabel,
                fftSize,
                monitorOutput: shouldMonitorOutput,
                statusLabel: mode === 'recording'
                    ? `Recording: ${session.deviceLabel}`
                    : `Streaming: ${session.deviceLabel}`,
                errorMessage: '',
            });
            return session;
        } catch (error) {
            if (startToken === pendingStartToken) {
                emitState({
                    active: false,
                    mode: 'inactive',
                    statusLabel: 'Live Source Error',
                    errorMessage: error?.message || 'Failed to start live source.',
                });
                onError?.('Failed to start live microphone source:', error);
            }
            return null;
        } finally {
            if (startToken === pendingStartToken) {
                isStartingSession = false;
                updateActionAvailability();
            }
        }
    };

    const startAssetCapture = async () => {
        if (assetCaptureSession) {
            return stopAssetCapture({ importAsset: true, closeDialog: true });
        }
        if (activeSession || isStartingSession || isImportingAsset) return null;

        const selectedDeviceId = String(liveSourceInput?.value || '').trim();
        const requestedLabel = String(liveSourceAssetLabelInput?.value || '').trim();
        const includeMfcc = !!liveSourceIncludeMfccToggle?.checked;

        try {
            ensureAudioContext?.();
            const audioContext = getAudioContext?.();
            if (!audioContext) {
                throw new Error('AudioContext is unavailable for recorded asset capture.');
            }
            if (audioContext.state === 'suspended') {
                await audioContext.resume();
            }

            const constraints = {
                audio: {
                    deviceId: selectedDeviceId ? { exact: selectedDeviceId } : undefined,
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false,
                },
            };
            const stream = await navigatorObject.mediaDevices.getUserMedia(constraints);
            const sourceNode = audioContext.createMediaStreamSource(stream);
            const processorNode = typeof audioContext.createScriptProcessor === 'function'
                ? audioContext.createScriptProcessor(ASSET_CAPTURE_BUFFER_SIZE, 1, 1)
                : null;
            if (!processorNode) {
                stopMediaTracks(stream);
                throw new Error('PCM microphone capture is unavailable in this runtime.');
            }

            const silentMonitorGainNode = audioContext.createGain();
            silentMonitorGainNode.gain.value = 0;
            const pcmChunks = [];
            const session = {
                mode: 'recording-asset',
                stream,
                sourceNode,
                processorNode,
                silentMonitorGainNode,
                mediaRecorder: null,
                recordedChunks: [],
                pcmChunks,
                deviceId: selectedDeviceId,
                deviceLabel: getSelectedDeviceLabel(),
                requestedLabel,
                includeMfcc,
                startedAt: new Date(),
                sampleRate: audioContext.sampleRate,
            };

            processorNode.onaudioprocess = (event) => {
                const inputBuffer = event?.inputBuffer;
                if (!inputBuffer || inputBuffer.numberOfChannels < 1) return;
                const inputChannel = inputBuffer.getChannelData(0);
                if (!inputChannel || inputChannel.length === 0) return;
                pcmChunks.push(new Float32Array(inputChannel));
            };

            sourceNode.connect(processorNode);
            processorNode.connect(silentMonitorGainNode);
            silentMonitorGainNode.connect(audioContext.destination);

            assetCaptureSession = session;
            emitState({
                active: false,
                mode: 'recording-asset',
                deviceId: session.deviceId,
                deviceLabel: session.deviceLabel,
                fftSize: Number.parseInt(liveSourceFftSize?.value || `${DEFAULT_FFT_SIZE}`, 10) || DEFAULT_FFT_SIZE,
                monitorOutput: false,
                statusLabel: `Recording new asset: ${session.deviceLabel}`,
                errorMessage: '',
            });
            setProgressState({
                visible: true,
                value: 10,
                label: 'Recording microphone input. Click Stop & Import when ready.',
            });
            updateActionAvailability();
            return session;
        } catch (error) {
            emitState({
                active: false,
                mode: 'inactive',
                statusLabel: error?.message ? `Recorded Asset Error: ${error.message}` : 'Recorded Asset Error',
                errorMessage: error?.message || 'Failed to start recorded asset capture.',
            });
            clearProgressState();
            updateActionAvailability();
            onError?.('Failed to start recorded asset capture:', error);
            return null;
        }
    };

    const openModal = async () => {
        if (!assetCaptureSession && !isImportingAsset) {
            clearProgressState();
        }
        await refreshInputs({ preserveSelection: true });
        liveModalOverlay?.classList.add('open');
    };

    const bind = () => {
        if (bound) return;
        bound = true;

        liveSourceRefreshBtn?.addEventListener('click', () => {
            void refreshInputs({ preserveSelection: true });
        });

        liveSourceStreamBtn?.addEventListener('click', () => {
            void startSession({ mode: 'streaming' });
        });

        liveSourceRecordBtn?.addEventListener('click', () => {
            void startSession({ mode: 'recording' });
        });

        liveSourceCaptureBtn?.addEventListener('click', () => {
            if (assetCaptureSession) {
                void stopAssetCapture({ importAsset: true, closeDialog: true });
                return;
            }
            void startAssetCapture();
        });

        liveSourceCancelBtn?.addEventListener('click', () => {
            if (assetCaptureSession) {
                void stopAssetCapture({ importAsset: false, closeDialog: true });
                return;
            }
            if (isStartingSession) {
                cancelPendingStart();
            }
            clearProgressState();
            closeModal({ force: true });
        });

        liveModalOverlay?.addEventListener('click', (event) => {
            if (event.target === liveModalOverlay && !assetCaptureSession && !isImportingAsset) {
                clearProgressState();
                closeModal({ force: true });
            }
        });

        navigatorObject?.mediaDevices?.addEventListener?.('devicechange', () => {
            void refreshInputs({ preserveSelection: true });
        });
    };

    return {
        applyInitialState: () => {
            emitState(buildDefaultState());
            if (liveSourceIncludeMfccToggle) {
                liveSourceIncludeMfccToggle.checked = true;
            }
            clearProgressState();
            updateActionAvailability();
            void refreshInputs({ preserveSelection: false });
        },
        bind,
        closeModal: () => closeModal({ force: true }),
        getState: () => ({ ...liveState }),
        isActive: () => !!activeSession || !!assetCaptureSession || isStartingSession,
        isModalOpen,
        openModal,
        readFrequencyFrame,
        stopSession,
        syncAnalyserBinCount: syncAnalyserConfig,
    };
};
