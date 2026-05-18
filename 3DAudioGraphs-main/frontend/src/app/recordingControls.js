import { GIFEncoder, quantize, applyPalette } from 'gifenc';
import { triggerFileSave } from '../shared/ui/fileSave.js';

const VIDEO_FORMATS = [
    { value: 'mp4', label: 'MP4 (.mp4)' },
    { value: 'webm', label: 'WebM (.webm)' },
    { value: 'mkv', label: 'MKV (.mkv)' },
    { value: 'mov', label: 'MOV (.mov)' },
    { value: 'm4v', label: 'M4V (.m4v)' },
    { value: 'm4p', label: 'M4P (.m4p)' },
];

const GIF_FORMATS = [
    { value: 'gif', label: 'Animated GIF (.gif)' },
    { value: 'webp', label: 'Animated WebP (.webp)' },
    { value: 'apng', label: 'APNG (.apng)' },
    { value: 'avif', label: 'AVIF (.avif)' },
];

const RESOLUTION_MAP = {
    '720': { w: 1280, h: 720 },
    '1080': { w: 1920, h: 1080 },
    '1440': { w: 2560, h: 1440 },
    '2160': { w: 3840, h: 2160 },
};

const pickVideoMime = (MediaRecorderClass) => {
    const candidates = [
        'video/mp4;codecs=h264',
        'video/mp4',
        'video/webm;codecs=vp9',
        'video/webm;codecs=vp8',
        'video/webm',
    ];

    return candidates.find((candidate) => MediaRecorderClass.isTypeSupported(candidate)) || 'video/webm';
};

export const createRecordingControls = ({
    documentObject = document,
    MediaRecorderClass = MediaRecorder,
    setIntervalFn = setInterval,
    clearIntervalFn = clearInterval,
    renderer,
    settings,
    ensureAudioContext,
    createRecordingDestination,
    disconnectRecordingDestination,
    recordBtn,
    recModalOverlay,
    recResolution,
    recFormat,
    recGifToggle,
    recAudioToggle,
    recStartBtn,
    recCancelBtn,
    beforeOpenModal,
} = {}) => {
    let bound = false;
    let recMediaRecorder = null;
    let recChunks = [];
    let recGifCapture = null;
    let isRecording = false;
    let recAudioDest = null;

    const recOffscreen = documentObject.createElement('canvas');
    const recCtx = recOffscreen.getContext('2d');

    const populateFormatSelect = (isGif) => {
        const formats = isGif ? GIF_FORMATS : VIDEO_FORMATS;
        recFormat.replaceChildren();
        for (const format of formats) {
            const option = documentObject.createElement('option');
            option.value = format.value;
            option.textContent = format.label;
            recFormat.appendChild(option);
        }
    };

    const syncAudioRowVisibility = () => {
        const audioRow = documentObject.getElementById('rec-audio-row');
        if (!audioRow) return;
        audioRow.style.display = recGifToggle.checked ? 'none' : 'flex';
    };

    const closeRecordingModal = () => {
        recModalOverlay.classList.remove('open');
    };

    const setRecordingState = (recording) => {
        isRecording = recording;
        recordBtn.classList.toggle('recording', recording);
    };

    const encodeGifFrames = async (frames, width, height, extension) => {
        const encoder = GIFEncoder();
        for (const frameData of frames) {
            const palette = quantize(frameData, 256);
            const indexed = applyPalette(frameData, palette);
            encoder.writeFrame(indexed, width, height, { palette, delay: 50 });
        }
        encoder.finish();

        const blob = new Blob([encoder.bytes()], { type: 'image/gif' });
        await triggerFileSave(blob, extension);
    };

    const stopRecording = async () => {
        if (!isRecording) return;
        setRecordingState(false);

        if (recGifCapture) {
            clearIntervalFn(recGifCapture.interval);
            const { frames, width, height } = recGifCapture;
            recGifCapture = null;

            if (recAudioDest) {
                disconnectRecordingDestination(recAudioDest);
                recAudioDest = null;
            }

            const extension = recFormat.value === 'gif' ? 'gif' : recFormat.value;
            await encodeGifFrames(frames, width, height, extension);
            return;
        }

        if (recMediaRecorder) {
            recMediaRecorder.stop();
        }
    };

    const startVideoRecording = () => {
        const mimeType = pickVideoMime(MediaRecorderClass);
        const extension = recFormat.value;
        const fps = Math.min(settings.maxFPS, 60);
        const canvasStream = renderer.domElement.captureStream(fps);

        if (recAudioToggle.checked) {
            ensureAudioContext?.();
            recAudioDest = createRecordingDestination?.();
            recAudioDest?.stream.getAudioTracks().forEach((track) => canvasStream.addTrack(track));
        }

        recChunks = [];
        recMediaRecorder = new MediaRecorderClass(canvasStream, {
            mimeType,
            videoBitsPerSecond: 8_000_000,
        });
        recMediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) recChunks.push(event.data);
        };
        recMediaRecorder.onstop = async () => {
            if (recAudioDest) {
                disconnectRecordingDestination(recAudioDest);
                recAudioDest = null;
            }
            const blob = new Blob(recChunks, { type: mimeType });
            recChunks = [];
            await triggerFileSave(blob, extension);
            recMediaRecorder = null;
        };
        recMediaRecorder.start(100);
        setRecordingState(true);
    };

    const startGifRecording = () => {
        const resolution = RESOLUTION_MAP[recResolution.value] || RESOLUTION_MAP['1080'];
        const width = resolution.w;
        const height = resolution.h;
        recOffscreen.width = width;
        recOffscreen.height = height;

        const frames = [];
        const frameRateMs = 50;
        const interval = setIntervalFn(() => {
            recCtx.drawImage(renderer.domElement, 0, 0, width, height);
            const imageData = recCtx.getImageData(0, 0, width, height);
            frames.push(new Uint8Array(imageData.data.buffer));
        }, frameRateMs);

        recGifCapture = { interval, frames, width, height };
        setRecordingState(true);
    };

    const bind = () => {
        if (bound) return;
        bound = true;

        recGifToggle.addEventListener('change', () => {
            populateFormatSelect(recGifToggle.checked);
            syncAudioRowVisibility();
        });

        recordBtn.addEventListener('click', () => {
            if (isRecording) {
                void stopRecording();
            } else {
                beforeOpenModal?.();
                recModalOverlay.classList.add('open');
            }
        });

        recCancelBtn.addEventListener('click', () => {
            closeRecordingModal();
        });

        recModalOverlay.addEventListener('click', (event) => {
            if (event.target === recModalOverlay) {
                closeRecordingModal();
            }
        });

        recStartBtn.addEventListener('click', () => {
            closeRecordingModal();
            if (recGifToggle.checked) {
                startGifRecording();
            } else {
                startVideoRecording();
            }
        });
    };

    return {
        applyInitialState: () => {
            populateFormatSelect(false);
            syncAudioRowVisibility();
        },
        bind,
    };
};