const {
    DEFAULT_BACKEND_ANALYSIS_TYPE,
    evaluateBackendActionReadiness,
    getBackendActionMetadataMap,
    normalizeBackendAnalysisType,
    normalizeBackendSaveMode,
} = require('./analysis_types.cjs');
const {
    normalizeBackendSelectionContract,
    normalizeReadySelectionForRequest,
} = require('./selection_contracts.cjs');
const {
    enrichBackendSaveResult,
    getBackendSaveModeMetadataMap,
} = require('./result_metadata.cjs');

const DEFAULT_BACKEND_SAVE_MODE = 'json';

function mappingOrEmpty(value) {
    return value && typeof value === 'object' && !Array.isArray(value)
        ? { ...value }
        : {};
}

function normalizeBackendRequestState(baseState, runOptions = {}) {
    const requestState = runOptions?.requestState && typeof runOptions.requestState === 'object' && !Array.isArray(runOptions.requestState)
        ? runOptions.requestState
        : baseState;
    const normalizedState = mappingOrEmpty(requestState);
    const requestBioState = mappingOrEmpty(normalizedState.bioacoustics);
    const bioacousticsOptions = mappingOrEmpty(runOptions?.bioacousticsOptions);
    const asset = normalizedState.asset && typeof normalizedState.asset === 'object' && !Array.isArray(normalizedState.asset)
        ? { ...normalizedState.asset }
        : null;

    return {
        asset,
        selection: normalizeBackendSelectionContract(normalizedState.selection),
        uiContext: mappingOrEmpty(normalizedState.uiContext),
        bioacoustics: {
            ...requestBioState,
            ...bioacousticsOptions,
        },
    };
}

function normalizeBackendAnalysisRequest(payload) {
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
        throw new TypeError('Selection analysis payload must be a JSON object.');
    }

    const normalizedPayload = mappingOrEmpty(payload);
    const saveOptions = mappingOrEmpty(normalizedPayload.saveOptions);
    const callMeta = mappingOrEmpty(normalizedPayload.callMeta);
    const analysisType = normalizeBackendAnalysisType(normalizedPayload.analysisType);
    const asset = mappingOrEmpty(normalizedPayload.asset);
    const selection = normalizeBackendSelectionContract(normalizedPayload.selection);

    return {
        analysisType,
        asset,
        selection: selection.isReady
            ? normalizeReadySelectionForRequest(asset, selection)
            : selection,
        uiContext: mappingOrEmpty(normalizedPayload.uiContext),
        bioacoustics: mappingOrEmpty(normalizedPayload.bioacoustics),
        saveOptions: {
            ...saveOptions,
            mode: normalizeBackendSaveMode(analysisType, saveOptions.mode || DEFAULT_BACKEND_SAVE_MODE),
            label: typeof saveOptions.label === 'string' ? saveOptions.label.trim() : '',
        },
        callMeta: {
            ...callMeta,
            requestId: typeof callMeta.requestId === 'string' ? callMeta.requestId.trim() : '',
            requestedAt: typeof callMeta.requestedAt === 'string' ? callMeta.requestedAt.trim() : '',
        },
    };
}

function buildBackendAnalysisRequest(baseState, runOptions = {}, overrides = {}) {
    const requestState = normalizeBackendRequestState(baseState, runOptions);
    return normalizeBackendAnalysisRequest({
        ...requestState,
        analysisType: runOptions?.analysisType,
        saveOptions: {
            mode: runOptions?.saveMode,
            label: runOptions?.saveLabel,
        },
        callMeta: {
            requestId: overrides.requestId || runOptions?.requestId || '',
            requestedAt: overrides.requestedAt || runOptions?.requestedAt || '',
        },
    });
}

module.exports = {
    DEFAULT_BACKEND_ANALYSIS_TYPE,
    DEFAULT_BACKEND_SAVE_MODE,
    buildBackendAnalysisRequest,
    enrichBackendSaveResult,
    evaluateBackendActionReadiness,
    getBackendActionMetadataMap,
    getBackendSaveModeMetadataMap,
    normalizeBackendAnalysisRequest,
    normalizeBackendAnalysisType,
    normalizeBackendRequestState,
    normalizeBackendSaveMode,
    normalizeBackendSelectionContract,
};