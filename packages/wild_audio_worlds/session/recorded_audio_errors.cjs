const registry = require('./recorded_audio_errors.json');

const DEFAULT_RECORDED_AUDIO_ERROR_CODE = 'recorded-audio-import-failed';
const RECORDED_AUDIO_ERROR_METADATA = registry && typeof registry.errors === 'object' && registry.errors
    ? registry.errors
    : {};

function cloneObject(value) {
    return value && typeof value === 'object' && !Array.isArray(value)
        ? { ...value }
        : {};
}

function normalizeRecordedAudioErrorCode(value, fallback = DEFAULT_RECORDED_AUDIO_ERROR_CODE) {
    const normalized = typeof value === 'string' ? value.trim() : '';
    return normalized || fallback;
}

function getRecordedAudioErrorMetadata(errorCode) {
    const normalizedErrorCode = normalizeRecordedAudioErrorCode(errorCode);
    const metadata = RECORDED_AUDIO_ERROR_METADATA[normalizedErrorCode];
    if (metadata && typeof metadata === 'object') {
        return cloneObject(metadata);
    }

    return {
        message: normalizedErrorCode,
    };
}

function getRecordedAudioErrorMetadataMap() {
    const metadataMap = {};
    for (const errorCode of Object.keys(RECORDED_AUDIO_ERROR_METADATA)) {
        metadataMap[errorCode] = getRecordedAudioErrorMetadata(errorCode);
    }
    return metadataMap;
}

function enrichRecordedAudioFailure(failurePayload, { errorCode } = {}) {
    const base = failurePayload && typeof failurePayload === 'object' && !Array.isArray(failurePayload)
        ? { ...failurePayload }
        : {};
    const resolvedErrorCode = normalizeRecordedAudioErrorCode(errorCode !== undefined ? errorCode : base.errorCode);
    const metadata = getRecordedAudioErrorMetadata(resolvedErrorCode);
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

function buildRecordedAudioFailure(errorCode, overrides = {}) {
    return enrichRecordedAudioFailure(overrides, { errorCode });
}

module.exports = {
    DEFAULT_RECORDED_AUDIO_ERROR_CODE,
    RECORDED_AUDIO_ERROR_METADATA,
    buildRecordedAudioFailure,
    enrichRecordedAudioFailure,
    getRecordedAudioErrorMetadata,
    getRecordedAudioErrorMetadataMap,
    normalizeRecordedAudioErrorCode,
};