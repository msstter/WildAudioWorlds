export const createAudioEngine = ({
    getAnalyserFftSize,
    getPlaybackMaskGainAttacher,
    onContextReady,
    initialPlaybackRate = 1,
} = {}) => {
    const audio = new Audio();
    audio.preload = 'auto';
    audio.playbackRate = initialPlaybackRate;
    audio.defaultPlaybackRate = initialPlaybackRate;

    let audioContext = null;
    let analyser = null;
    let frequencyData = null;
    let playbackMaskGain = null;
    let mediaSource = null;

    const ensureAudioContextCreated = () => {
        if (!audioContext) {
            audioContext = new AudioContext();
        }
        return audioContext;
    };

    const refreshFrequencyDataBuffer = () => {
        if (!analyser) return null;
        frequencyData = new Uint8Array(analyser.frequencyBinCount);
        return frequencyData;
    };

    const ensurePlaybackGraph = () => {
        const context = ensureAudioContextCreated();
        if (analyser) return context;

        analyser = context.createAnalyser();
        analyser.fftSize = Math.max(32, Number(getAnalyserFftSize?.()) || 256);
        playbackMaskGain = context.createGain();
        getPlaybackMaskGainAttacher?.()?.(playbackMaskGain);

        mediaSource = context.createMediaElementSource(audio);
        mediaSource.connect(playbackMaskGain);
        playbackMaskGain.connect(analyser);
        analyser.connect(context.destination);
        refreshFrequencyDataBuffer();
        return context;
    };

    const notifyContextReady = () => {
        onContextReady?.({
            audioContext,
            analyser,
            frequencyData,
            playbackMaskGain,
            mediaSource,
        });
    };

    const ensureAudioContext = () => {
        const context = ensurePlaybackGraph();
        if (context.state === 'suspended') {
            context.resume().then(() => {
                notifyContextReady();
            }).catch(() => {
                // Ignore resume failures; the media element clock remains available.
            });
        } else {
            notifyContextReady();
        }
        return context;
    };

    const decodeAudioData = async (arrayBuffer) => {
        const context = ensureAudioContextCreated();
        return context.decodeAudioData(arrayBuffer);
    };

    const syncAnalyserBinCount = (binCount) => {
        if (!analyser || !Number.isFinite(binCount) || binCount <= 0) return null;
        if (analyser.frequencyBinCount !== binCount) {
            analyser.fftSize = binCount * 2;
            refreshFrequencyDataBuffer();
        }
        return frequencyData;
    };

    const readFrequencyFrame = () => {
        if (!analyser || !frequencyData) return null;
        analyser.getByteFrequencyData(frequencyData);
        return frequencyData;
    };

    const createRecordingDestination = () => {
        const context = ensurePlaybackGraph();
        const destination = context.createMediaStreamDestination();
        analyser.connect(destination);
        return destination;
    };

    const disconnectRecordingDestination = (destination) => {
        if (!analyser || !destination) return;
        try {
            analyser.disconnect(destination);
        } catch {
            // Ignore disconnect errors for already-removed recording branches.
        }
    };

    return {
        audio,
        createRecordingDestination,
        decodeAudioData,
        disconnectRecordingDestination,
        ensureAudioContext,
        getAnalyser: () => analyser,
        getAudioContext: () => audioContext,
        readFrequencyFrame,
        syncAnalyserBinCount,
    };
};