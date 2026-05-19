const registry = require('./result_metadata.json');

const DEFAULT_BACKEND_SAVE_MODE = 'json';
const BACKEND_SAVE_MODE_METADATA = registry && typeof registry.saveModes === 'object' && registry.saveModes
    ? registry.saveModes
    : {};

function cloneObject(value) {
    return value && typeof value === 'object' && !Array.isArray(value)
        ? { ...value }
        : {};
}

function normalizeBackendSaveModeKey(value) {
    const normalized = typeof value === 'string' ? value.trim().toLowerCase() : '';
    return normalized || DEFAULT_BACKEND_SAVE_MODE;
}

function getBackendSaveModeMetadata(mode) {
    const normalizedMode = normalizeBackendSaveModeKey(mode);
    const metadata = BACKEND_SAVE_MODE_METADATA[normalizedMode];
    if (metadata && typeof metadata === 'object') {
        return cloneObject(metadata);
    }

    return {
        label: normalizedMode,
        artifactType: normalizedMode,
        artifactLabel: normalizedMode,
    };
}

function getBackendSaveModeMetadataMap() {
    const metadataMap = {};
    for (const mode of Object.keys(BACKEND_SAVE_MODE_METADATA)) {
        metadataMap[mode] = getBackendSaveModeMetadata(mode);
    }
    return metadataMap;
}

function enrichBackendSaveResult(saveResult, { mode } = {}) {
    const base = saveResult && typeof saveResult === 'object' && !Array.isArray(saveResult)
        ? { ...saveResult }
        : {};
    const normalizedMode = normalizeBackendSaveModeKey(mode !== undefined ? mode : base.mode);
    const metadata = getBackendSaveModeMetadata(normalizedMode);

    return {
        ...base,
        mode: normalizedMode,
        modeLabel: typeof metadata.label === 'string' ? metadata.label : normalizedMode,
        artifactType: typeof metadata.artifactType === 'string' ? metadata.artifactType : normalizedMode,
        artifactLabel: typeof metadata.artifactLabel === 'string' ? metadata.artifactLabel : normalizedMode,
    };
}

module.exports = {
    BACKEND_SAVE_MODE_METADATA,
    DEFAULT_BACKEND_SAVE_MODE,
    enrichBackendSaveResult,
    getBackendSaveModeMetadata,
    getBackendSaveModeMetadataMap,
    normalizeBackendSaveModeKey,
};