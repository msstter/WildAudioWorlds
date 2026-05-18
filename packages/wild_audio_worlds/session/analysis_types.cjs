const registry = require('./analysis_types.json');

const BACKEND_ANALYSIS_TYPE_CONFIGS = registry && typeof registry.actions === 'object' && registry.actions
    ? registry.actions
    : {};
const DEFAULT_BACKEND_ANALYSIS_TYPE = typeof registry?.default === 'string' && registry.default.trim() !== ''
    ? registry.default.trim()
    : 'slice-summary';

function normalizeBackendAnalysisType(value) {
    const normalized = typeof value === 'string' ? value.trim() : '';
    return normalized || DEFAULT_BACKEND_ANALYSIS_TYPE;
}

function getBackendAnalysisTypeConfig(analysisType) {
    const normalized = normalizeBackendAnalysisType(analysisType);
    const config = BACKEND_ANALYSIS_TYPE_CONFIGS[normalized];
    return config && typeof config === 'object' ? config : null;
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

module.exports = {
    BACKEND_ANALYSIS_TYPE_CONFIGS,
    DEFAULT_BACKEND_ANALYSIS_TYPE,
    getBackendAnalysisTypeConfig,
    isBioacousticsAnalysisType,
    isBioacousticsImportAnalysisType,
    isBioacousticsSyncAnalysisType,
    normalizeBackendAnalysisType,
    normalizeBackendSaveMode,
};