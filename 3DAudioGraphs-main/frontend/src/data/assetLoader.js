const encodeAssetUrl = (assetPath) => encodeURI(assetPath);

const loadOptionalText = async (fetchImpl, assetUrl, onWarn) => {
    if (!assetUrl) return null;
    try {
        const response = await fetchImpl(encodeAssetUrl(assetUrl));
        if (!response.ok) {
            onWarn?.(`Failed to fetch terrain envelope helper: ${response.status}`);
            return null;
        }
        return response.text();
    } catch (error) {
        onWarn?.('Failed to fetch terrain envelope helper:', error);
        return null;
    }
};

export const createAudioAssetLoader = ({
    audio,
    decodeAudioData,
    trajectoryVisualizer,
    terrainVisualizer,
    getSelectedAsset,
    setSelectedAsset,
    syncSelectedAssetId,
    shouldAccumulateView,
    clearAccumulatedViews,
    accumulateCurrentPipelineView,
    clearSelectedTimbreInstances,
    onPlaybackReset,
    onAssetLoaded,
    fetchImpl = fetch,
    onWarn,
    onError,
} = {}) => {
    let decodedAudioBuffer = null;
    let decodedAudioBufferAssetId = null;
    let audioWaveform = null;

    const loadAudioWaveform = async (audioUrl, { assetId = getSelectedAsset?.()?.id || null } = {}) => {
        try {
            const response = await fetchImpl(encodeAssetUrl(audioUrl));
            if (!response.ok) throw new Error(`Failed to fetch audio: ${response.status}`);
            const arrayBuffer = await response.arrayBuffer();
            const audioBuffer = await decodeAudioData(arrayBuffer);
            if (assetId && assetId !== (getSelectedAsset?.()?.id || null)) return;

            decodedAudioBuffer = audioBuffer;
            decodedAudioBufferAssetId = assetId;
            const channelData = audioBuffer.getChannelData(0);

            const targetSamples = Math.min(channelData.length, 88200);
            const stride = Math.ceil(channelData.length / targetSamples);
            audioWaveform = new Float32Array(Math.ceil(channelData.length / stride));

            for (let i = 0; i < audioWaveform.length; i++) {
                audioWaveform[i] = channelData[i * stride] || 0;
            }

            trajectoryVisualizer.setAudioWaveform(audioWaveform);
        } catch (error) {
            if (assetId === (getSelectedAsset?.()?.id || null)) {
                decodedAudioBuffer = null;
                decodedAudioBufferAssetId = assetId;
            }
            onError?.('Failed to load audio waveform:', error);
        }
    };

    const ensureDecodedAudioBufferForSelectedAsset = async () => {
        const asset = getSelectedAsset?.();
        const assetId = asset?.id || null;
        const audioUrl = asset?.audioUrl || null;
        if (!assetId || !audioUrl) return null;
        if (decodedAudioBuffer && decodedAudioBufferAssetId === assetId) return decodedAudioBuffer;

        await loadAudioWaveform(audioUrl, { assetId });
        return decodedAudioBufferAssetId === assetId ? decodedAudioBuffer : null;
    };

    const loadAudioAsset = async (asset, options = {}) => {
        if (!asset) return;

        const previousAsset = getSelectedAsset?.();
        const allowAccumulate = options.allowAccumulate !== false;
        if (!shouldAccumulateView?.() || !allowAccumulate) {
            clearAccumulatedViews?.();
        } else if (previousAsset && previousAsset.id !== asset.id) {
            accumulateCurrentPipelineView?.();
        }

        setSelectedAsset?.(asset);
        syncSelectedAssetId?.(asset.id);
        clearSelectedTimbreInstances?.();
        decodedAudioBuffer = null;
        decodedAudioBufferAssetId = null;

        audio.pause();
        audio.currentTime = 0;
        onPlaybackReset?.();
        audio.src = encodeAssetUrl(asset.audioUrl);
        audio.load();

        const terrainEnvelopePromise = loadOptionalText(fetchImpl, asset.terrainEnvelopeUrl, onWarn);
        const trajectoryRequest = asset.mfccCsvUrl
            ? fetchImpl(encodeAssetUrl(asset.mfccCsvUrl))
            : Promise.resolve(null);
        const [trajectoryResponse, fftResponse, terrainEnvelopeText] = await Promise.all([
            trajectoryRequest,
            fetchImpl(encodeAssetUrl(asset.fftCsvUrl)),
            terrainEnvelopePromise,
        ]);

        if (trajectoryResponse && !trajectoryResponse.ok) throw new Error(`Failed to fetch MFCC CSV: ${trajectoryResponse.status}`);
        if (!fftResponse.ok) throw new Error(`Failed to fetch FFT CSV: ${fftResponse.status}`);

        const trajectoryText = trajectoryResponse ? await trajectoryResponse.text() : null;
        const fftText = await fftResponse.text();

        const bounds = trajectoryText
            ? trajectoryVisualizer.loadData(trajectoryText)
            : (trajectoryVisualizer.clearData?.(), null);
        terrainVisualizer.loadFrameData(fftText);
        terrainVisualizer.loadTerrainEnvelopeData(terrainEnvelopeText);

        await loadAudioWaveform(asset.audioUrl, { assetId: asset.id });
        onAssetLoaded?.({
            asset,
            bounds,
            trajectoryText,
            fftText,
            terrainEnvelopeText,
            hasMfccData: !!trajectoryText,
        });
    };

    const resetGraphToCurrentAsset = async () => {
        clearAccumulatedViews?.();
        const asset = getSelectedAsset?.();
        if (asset) {
            await loadAudioAsset(asset, { allowAccumulate: false });
        }
    };

    return {
        ensureDecodedAudioBufferForSelectedAsset,
        loadAudioAsset,
        resetGraphToCurrentAsset,
    };
};