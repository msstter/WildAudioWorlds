export const PROCESS_CURRENT_ASSET_INCLUDE_MFCC_STORAGE_KEY = '3d-audio-maker.process-current-asset.include-mfcc';

const normalizeStoredProcessCurrentAssetIncludeMfcc = (value) => {
    if (typeof value === 'boolean') return value;

    const normalizedValue = String(value || '').trim().toLowerCase();
    if (normalizedValue === 'true') return true;
    if (normalizedValue === 'false') return false;
    return null;
};

export const readStoredProcessCurrentAssetIncludeMfcc = ({
    storageObject = globalThis.localStorage,
    fallbackValue = true,
} = {}) => {
    try {
        if (!storageObject || typeof storageObject.getItem !== 'function') {
            return fallbackValue;
        }

        const storedValue = normalizeStoredProcessCurrentAssetIncludeMfcc(
            storageObject.getItem(PROCESS_CURRENT_ASSET_INCLUDE_MFCC_STORAGE_KEY),
        );
        return typeof storedValue === 'boolean' ? storedValue : fallbackValue;
    } catch (_error) {
        return fallbackValue;
    }
};

export const writeStoredProcessCurrentAssetIncludeMfcc = (includeMfcc, {
    storageObject = globalThis.localStorage,
} = {}) => {
    try {
        if (!storageObject || typeof storageObject.setItem !== 'function') {
            return false;
        }

        storageObject.setItem(
            PROCESS_CURRENT_ASSET_INCLUDE_MFCC_STORAGE_KEY,
            includeMfcc ? 'true' : 'false',
        );
        return true;
    } catch (_error) {
        return false;
    }
};

export const buildProcessCurrentAssetRequest = ({
    assetSnapshot = null,
    includeMfcc = true,
    fallbackLabel = 'Current Asset',
} = {}) => {
    if (!assetSnapshot?.audioUrl) return null;

    const safeFallbackLabel = String(fallbackLabel || '').trim() || 'Current Asset';
    return {
        assetLabel: assetSnapshot.label || safeFallbackLabel,
        includeMfcc: !!includeMfcc,
        requestAsset: assetSnapshot,
    };
};