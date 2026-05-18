const DEFAULT_MANIFEST_SOURCE_LABEL = 'Bundled Assets';

const normalizeBundledAssetPath = (value) => {
    if (typeof value !== 'string') return value;

    const trimmed = value.trim();
    if (trimmed === '') return trimmed;
    if (/^(?:[a-z]+:)?\/\//i.test(trimmed) || /^(?:data|blob):/i.test(trimmed)) {
        return trimmed;
    }
    if (trimmed.startsWith('/')) {
        return `.${trimmed}`;
    }
    return trimmed;
};

const resolveManifestAssetPath = (value, manifestResponseUrl) => {
    if (typeof value !== 'string') return value;

    const trimmed = value.trim();
    if (trimmed === '') return trimmed;
    if (/^(?:[a-z]+:)?\/\//i.test(trimmed) || /^(?:data|blob|file):/i.test(trimmed)) {
        return trimmed;
    }

    if (!manifestResponseUrl) {
        return normalizeBundledAssetPath(trimmed);
    }

    try {
        const manifestBaseUrl = new URL(manifestResponseUrl, globalThis.location?.href);
        const normalizedPath = manifestBaseUrl.protocol === 'file:' && trimmed.startsWith('/')
            ? `.${trimmed}`
            : trimmed;
        return new URL(normalizedPath, manifestBaseUrl).toString();
    } catch (_error) {
        return normalizeBundledAssetPath(trimmed);
    }
};

const normalizeAudioAssets = (data, manifestResponseUrl) => {
    if (!Array.isArray(data?.assets)) return [];
    return data.assets.map((asset) => ({
        ...asset,
        audioUrl: resolveManifestAssetPath(asset.audioUrl, manifestResponseUrl),
        mfccCsvUrl: resolveManifestAssetPath(asset.mfccCsvUrl, manifestResponseUrl),
        fftCsvUrl: resolveManifestAssetPath(asset.fftCsvUrl, manifestResponseUrl),
        terrainEnvelopeUrl: typeof asset.terrainEnvelopeUrl === 'string' && asset.terrainEnvelopeUrl.trim() !== ''
            ? resolveManifestAssetPath(asset.terrainEnvelopeUrl, manifestResponseUrl)
            : null,
    }));
};

export const createAudioAssetCatalog = ({
    folder,
    audioSourceState,
    onSelectAsset,
    fetchImpl = fetch,
    manifestUrl = './audio_assets_manifest.json',
    onManifestUnavailable,
} = {}) => {
    let availableAudioAssets = [];
    let audioSourceController = null;
    let currentManifestUrl = manifestUrl;
    let currentManifestSourceLabel = DEFAULT_MANIFEST_SOURCE_LABEL;

    const rebuildSourceController = () => {
        if (audioSourceController) {
            folder.remove(audioSourceController);
            audioSourceController = null;
        }

        const options = {};
        for (const asset of availableAudioAssets) {
            options[asset.label] = asset.id;
        }

        if (availableAudioAssets.length === 0) return null;

        audioSourceState.selectedAudioAssetId = audioSourceState.selectedAudioAssetId || availableAudioAssets[0].id;
        audioSourceController = folder.add(audioSourceState, 'selectedAudioAssetId', options).name('Audio/Data');
        audioSourceController.onChange(async (assetId) => {
            const asset = availableAudioAssets.find((entry) => entry.id === assetId);
            if (asset) {
                await onSelectAsset?.(asset);
            }
        });
        return audioSourceController;
    };

    const loadManifest = async ({ manifestUrl: nextManifestUrl, sourceLabel } = {}) => {
        const requestedManifestUrl = typeof nextManifestUrl === 'string' && nextManifestUrl.trim() !== ''
            ? nextManifestUrl.trim()
            : currentManifestUrl;
        const requestedSourceLabel = typeof sourceLabel === 'string' && sourceLabel.trim() !== ''
            ? sourceLabel.trim()
            : currentManifestSourceLabel;
        let manifestError = null;
        let didLoadManifest = false;

        try {
            const response = await fetchImpl(requestedManifestUrl);
            if (!response.ok) throw new Error(`Failed to fetch manifest: ${response.status}`);
            const data = await response.json();
            availableAudioAssets = normalizeAudioAssets(data, response.url || requestedManifestUrl);
            didLoadManifest = true;
        } catch (error) {
            manifestError = error;
            onManifestUnavailable?.(error);
            availableAudioAssets = [];
        }

        currentManifestUrl = requestedManifestUrl;
        currentManifestSourceLabel = requestedSourceLabel;

        rebuildSourceController();
        return {
            assets: availableAudioAssets,
            error: manifestError,
            manifestUrl: currentManifestUrl,
            ok: didLoadManifest,
            sourceLabel: currentManifestSourceLabel,
        };
    };

    const setManifestSource = ({ manifestUrl: nextManifestUrl, sourceLabel } = {}) => {
        if (typeof nextManifestUrl === 'string' && nextManifestUrl.trim() !== '') {
            currentManifestUrl = nextManifestUrl.trim();
        }
        if (typeof sourceLabel === 'string' && sourceLabel.trim() !== '') {
            currentManifestSourceLabel = sourceLabel.trim();
        }
    };

    const getManifestSource = () => ({
        manifestUrl: currentManifestUrl,
        sourceLabel: currentManifestSourceLabel,
    });

    const syncSelectedAssetId = (assetId) => {
        if (assetId) {
            audioSourceState.selectedAudioAssetId = assetId;
        }
        audioSourceController?.updateDisplay();
    };

    return {
        getAvailableAudioAssets: () => availableAudioAssets,
        getManifestSource,
        loadManifest,
        rebuildSourceController,
        setManifestSource,
        syncSelectedAssetId,
    };
};