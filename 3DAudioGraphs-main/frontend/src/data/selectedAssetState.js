export const createSelectedAudioAssetState = ({ initialSelectedAudioAssetId = '' } = {}) => {
    const audioSourceState = {
        selectedAudioAssetId: initialSelectedAudioAssetId,
    };

    let selectedAudioAsset = null;

    const setSelectedAsset = (asset) => {
        selectedAudioAsset = asset ?? null;
        audioSourceState.selectedAudioAssetId = asset?.id || '';
        return selectedAudioAsset;
    };

    return {
        getAudioSourceState: () => audioSourceState,
        getSelectedAsset: () => selectedAudioAsset,
        getSelectedAssetId: (fallback = '') => selectedAudioAsset?.id || fallback,
        getSelectedAssetLabel: (fallback = '') => selectedAudioAsset?.label || fallback,
        setSelectedAsset,
    };
};