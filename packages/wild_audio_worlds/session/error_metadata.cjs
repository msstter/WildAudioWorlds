const registry = require('./error_metadata.json');

const DEFAULT_BACKEND_ERROR_CODE = 'backend-analysis-failed';
const BACKEND_ERROR_METADATA = registry && typeof registry.errors === 'object' && registry.errors
    ? registry.errors
    : {};

function cloneObject(value) {
    return value && typeof value === 'object' && !Array.isArray(value)
        ? { ...value }
        : {};
}

function normalizeBackendErrorCode(value, fallback = DEFAULT_BACKEND_ERROR_CODE) {
    const normalized = typeof value === 'string' ? value.trim() : '';
    return normalized || fallback;
}

function getBackendErrorMetadata(errorCode) {
    const normalizedErrorCode = normalizeBackendErrorCode(errorCode);
    const metadata = BACKEND_ERROR_METADATA[normalizedErrorCode];
    if (metadata && typeof metadata === 'object') {
        return cloneObject(metadata);
    }

    return {
        message: normalizedErrorCode,
    };
}

function getBackendErrorMetadataMap() {
    const metadataMap = {};
    for (const errorCode of Object.keys(BACKEND_ERROR_METADATA)) {
        metadataMap[errorCode] = getBackendErrorMetadata(errorCode);
    }
    return metadataMap;
}

function enrichBackendFailure(failurePayload, { errorCode } = {}) {
    const base = failurePayload && typeof failurePayload === 'object' && !Array.isArray(failurePayload)
        ? { ...failurePayload }
        : {};
    const resolvedErrorCode = normalizeBackendErrorCode(errorCode !== undefined ? errorCode : base.errorCode);
    const metadata = getBackendErrorMetadata(resolvedErrorCode);
    const errorMessage = typeof base.error === 'string' && base.error.trim() !== ''
        ? base.error.trim()
        : (typeof metadata.message === 'string' && metadata.message.trim() !== ''
            ? metadata.message.trim()
            : resolvedErrorCode);

    return {
        ...base,
        ok: false,
        errorCode: resolvedErrorCode,
        error: errorMessage,
    };
}

function buildBackendFailure(errorCode, overrides = {}) {
    return enrichBackendFailure(overrides, { errorCode });
}

module.exports = {
    BACKEND_ERROR_METADATA,
    DEFAULT_BACKEND_ERROR_CODE,
    buildBackendFailure,
    enrichBackendFailure,
    getBackendErrorMetadata,
    getBackendErrorMetadataMap,
    normalizeBackendErrorCode,
};