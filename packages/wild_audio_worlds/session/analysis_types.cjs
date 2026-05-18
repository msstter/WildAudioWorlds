const registry = require('./analysis_types.json');

const BACKEND_ANALYSIS_TYPE_CONFIGS = registry && typeof registry.actions === 'object' && registry.actions
    ? registry.actions
    : {};
const DEFAULT_BACKEND_ANALYSIS_TYPE = typeof registry?.default === 'string' && registry.default.trim() !== ''
    ? registry.default.trim()
    : 'slice-summary';

function cloneObject(value) {
    return value && typeof value === 'object' && !Array.isArray(value)
        ? { ...value }
        : {};
}

function normalizeBackendAnalysisType(value) {
    const normalized = typeof value === 'string' ? value.trim() : '';
    return normalized || DEFAULT_BACKEND_ANALYSIS_TYPE;
}

function getBackendAnalysisTypeConfig(analysisType) {
    const normalized = normalizeBackendAnalysisType(analysisType);
    const config = BACKEND_ANALYSIS_TYPE_CONFIGS[normalized];
    return config && typeof config === 'object' ? cloneObject(config) : null;
}

function isBioacousticsAnalysisType(analysisType) {
    return getBackendAnalysisTypeConfig(analysisType)?.group === 'bioacoustics';
}

function isBioacousticsImportAnalysisType(analysisType) {
    return getBackendAnalysisTypeConfig(analysisType)?.operation === 'import-workbook';
}

function isBioacousticsSyncAnalysisType(analysisType) {
    return getBackendAnalysisTypeConfig(analysisType)?.operation === 'sync-workbook';
}

function normalizeBackendSaveMode(analysisType, requestedSaveMode) {
    const normalizedSaveMode = typeof requestedSaveMode === 'string' && requestedSaveMode.trim() !== ''
        ? requestedSaveMode.trim().toLowerCase()
        : '';
    const config = getBackendAnalysisTypeConfig(analysisType);
    const allowedSaveModes = Array.isArray(config?.allowedSaveModes) ? config.allowedSaveModes : [];

    if (allowedSaveModes.includes(normalizedSaveMode)) {
        return normalizedSaveMode;
    }

    const defaultSaveMode = typeof config?.defaultSaveMode === 'string' && config.defaultSaveMode.trim() !== ''
        ? config.defaultSaveMode.trim().toLowerCase()
        : 'json';
    return defaultSaveMode;
}

function getBackendActionMetadata(analysisType) {
    const normalized = normalizeBackendAnalysisType(analysisType);
    const config = getBackendAnalysisTypeConfig(normalized);
    if (!config) {
        return null;
    }

    const ui = cloneObject(config.ui);
    const allowedSaveModes = Array.isArray(config.allowedSaveModes)
        ? [...config.allowedSaveModes]
        : [];
    const defaultSaveMode = typeof config.defaultSaveMode === 'string' && config.defaultSaveMode.trim() !== ''
        ? config.defaultSaveMode.trim().toLowerCase()
        : 'json';

    return {
        label: typeof ui.label === 'string' && ui.label.trim() !== '' ? ui.label.trim() : normalized,
        help: typeof ui.help === 'string' && ui.help.trim() !== '' ? ui.help.trim() : 'No description available.',
        saveModes: allowedSaveModes.length > 0 ? allowedSaveModes : [defaultSaveMode],
        defaultSaveMode,
        isBioacoustics: config.group === 'bioacoustics',
        showBioOutputMode: !!ui.showBioOutputMode,
    };
}

function getBackendActionMetadataMap() {
    const metadataMap = {};
    for (const analysisType of Object.keys(BACKEND_ANALYSIS_TYPE_CONFIGS)) {
        const metadata = getBackendActionMetadata(analysisType);
        if (metadata) {
            metadataMap[analysisType] = metadata;
        }
    }
    return metadataMap;
}

module.exports = {
    BACKEND_ANALYSIS_TYPE_CONFIGS,
    DEFAULT_BACKEND_ANALYSIS_TYPE,
    getBackendActionMetadata,
    getBackendActionMetadataMap,
    getBackendAnalysisTypeConfig,
    isBioacousticsAnalysisType,
    isBioacousticsImportAnalysisType,
    isBioacousticsSyncAnalysisType,
    normalizeBackendAnalysisType,
    normalizeBackendSaveMode,
};