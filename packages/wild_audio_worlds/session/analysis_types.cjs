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

function getBackendActionReadinessConfig(analysisType) {
    const config = getBackendAnalysisTypeConfig(analysisType);
    if (!config) {
        return null;
    }

    const readiness = cloneObject(config.readiness);
    const messages = cloneObject(readiness.messages);
    return {
        ...readiness,
        workbookPathRequiredForOutputModes: Array.isArray(readiness.workbookPathRequiredForOutputModes)
            ? [...readiness.workbookPathRequiredForOutputModes]
            : [],
        messages,
    };
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
        readiness: getBackendActionReadinessConfig(normalized),
    };
}

function evaluateBackendActionReadiness(analysisType, { selection = null, bioacoustics = null } = {}) {
    const readiness = getBackendActionReadinessConfig(analysisType);
    if (!readiness) {
        return {
            ready: false,
            code: 'unknown-action',
            message: 'Backend action metadata is unavailable.',
        };
    }

    const selectionState = selection && typeof selection === 'object' && !Array.isArray(selection) ? selection : {};
    const bioState = bioacoustics && typeof bioacoustics === 'object' && !Array.isArray(bioacoustics) ? bioacoustics : {};
    const messages = cloneObject(readiness.messages);

    if (readiness.requiresSelectionReady && !selectionState.isReady) {
        return {
            ready: false,
            code: 'selection-not-ready',
            message: typeof messages.notReady === 'string' && messages.notReady.trim() !== ''
                ? messages.notReady.trim()
                : 'The current action requires a ready selection.',
        };
    }

    if (typeof readiness.requiresBioacousticsStateField === 'string' && readiness.requiresBioacousticsStateField.trim() !== '') {
        const requiredField = readiness.requiresBioacousticsStateField.trim();
        if (!bioState[requiredField]) {
            return {
                ready: false,
                code: 'bioacoustics-state-not-ready',
                message: typeof messages.notReady === 'string' && messages.notReady.trim() !== ''
                    ? messages.notReady.trim()
                    : 'The current Bioacoustics action is not ready.',
            };
        }
    }

    if (readiness.requiresOnsetTimes) {
        const onsetTimes = Array.isArray(bioState.onsetTimes) ? bioState.onsetTimes : [];
        if (onsetTimes.length === 0) {
            return {
                ready: false,
                code: 'missing-onset-times',
                message: typeof messages.missingOnsetTimes === 'string' && messages.missingOnsetTimes.trim() !== ''
                    ? messages.missingOnsetTimes.trim()
                    : 'The current action requires onset times.',
            };
        }
    }

    const workbookPath = typeof bioState.workbookPath === 'string' ? bioState.workbookPath.trim() : '';
    if (readiness.requiresWorkbookPath && !workbookPath) {
        const autoDiscover = !!bioState.autoDiscover;
        if (!(readiness.acceptsAutoDiscover && autoDiscover)) {
            return {
                ready: false,
                code: 'missing-workbook-path',
                message: typeof messages.missingWorkbookPath === 'string' && messages.missingWorkbookPath.trim() !== ''
                    ? messages.missingWorkbookPath.trim()
                    : 'The current action requires a workbook path.',
            };
        }
    }

    const requiredOutputModes = Array.isArray(readiness.workbookPathRequiredForOutputModes)
        ? readiness.workbookPathRequiredForOutputModes.map((value) => String(value || '').trim().toLowerCase()).filter(Boolean)
        : [];
    if (requiredOutputModes.length > 0) {
        const defaultOutputMode = typeof readiness.defaultOutputMode === 'string' && readiness.defaultOutputMode.trim() !== ''
            ? readiness.defaultOutputMode.trim().toLowerCase()
            : 'duplicate';
        const outputMode = typeof bioState.outputMode === 'string' && bioState.outputMode.trim() !== ''
            ? bioState.outputMode.trim().toLowerCase()
            : defaultOutputMode;
        if (requiredOutputModes.includes(outputMode) && !workbookPath) {
            return {
                ready: false,
                code: 'missing-workbook-path-for-output-mode',
                message: typeof messages.missingWorkbookPathForOutputMode === 'string' && messages.missingWorkbookPathForOutputMode.trim() !== ''
                    ? messages.missingWorkbookPathForOutputMode.trim()
                    : 'The current output mode requires a workbook path.',
            };
        }
    }

    return {
        ready: true,
        code: 'ready',
        message: '',
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
    getBackendActionReadinessConfig,
    getBackendAnalysisTypeConfig,
    evaluateBackendActionReadiness,
    isBioacousticsAnalysisType,
    isBioacousticsImportAnalysisType,
    isBioacousticsSyncAnalysisType,
    normalizeBackendAnalysisType,
    normalizeBackendSaveMode,
};