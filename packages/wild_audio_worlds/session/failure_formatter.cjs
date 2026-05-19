const {
    enrichBackendFailure,
    getBackendErrorMetadata,
} = require('./error_metadata.cjs');

const MONITOR_FAILURE_FIELDS = [
    { key: 'errorCode', label: 'Error Code' },
    { key: 'error', label: 'Error' },
    { key: 'exitCode', label: 'Exit Code' },
    { key: 'stderr', label: 'Standard Error' },
    { key: 'stdout', label: 'Standard Output' },
    { key: 'traceback', label: 'Traceback' },
    { key: 'details', label: 'Details' },
];

function normalizeFailureFieldValue(value) {
    if (typeof value === 'string') {
        const trimmed = value.trim();
        return trimmed || '';
    }

    if (typeof value === 'number' || typeof value === 'boolean') {
        return String(value);
    }

    if (value && typeof value === 'object') {
        return JSON.stringify(value, null, 2);
    }

    return '';
}

function formatBackendFailureForMonitor(failurePayload, { errorCode } = {}) {
    const failure = enrichBackendFailure(failurePayload, { errorCode });
    const metadata = getBackendErrorMetadata(failure.errorCode);
    const metadataMessage = typeof metadata.message === 'string' ? metadata.message.trim() : '';
    const summary = metadataMessage && metadataMessage !== failure.error
        ? metadataMessage
        : '';

    return {
        kind: 'backend-failure',
        summary,
        sections: MONITOR_FAILURE_FIELDS.map(({ key, label }) => {
            const value = normalizeFailureFieldValue(failure[key]);
            return value
                ? { key, label, value }
                : null;
        }).filter(Boolean),
    };
}

module.exports = {
    formatBackendFailureForMonitor,
};