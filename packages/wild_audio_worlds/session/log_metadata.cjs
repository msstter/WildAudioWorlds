const registry = require('./log_metadata.json');

const DEFAULT_BACKEND_LOG_SCOPE = 'bridge';
const DEFAULT_BACKEND_LOG_LEVEL = 'info';

const BACKEND_LOG_SCOPE_METADATA = registry && typeof registry.scopes === 'object' && registry.scopes
    ? registry.scopes
    : {};
const BACKEND_LOG_LEVEL_METADATA = registry && typeof registry.levels === 'object' && registry.levels
    ? registry.levels
    : {};
const BACKEND_LOG_DETAIL_FIELD_METADATA = registry && typeof registry.detailFields === 'object' && registry.detailFields
    ? registry.detailFields
    : {};

function cloneObject(value) {
    return value && typeof value === 'object' && !Array.isArray(value)
        ? { ...value }
        : {};
}

function normalizeBackendLogScope(value, fallback = DEFAULT_BACKEND_LOG_SCOPE) {
    const normalized = typeof value === 'string' ? value.trim() : '';
    return normalized || fallback;
}

function normalizeBackendLogLevel(value, fallback = DEFAULT_BACKEND_LOG_LEVEL) {
    const normalized = typeof value === 'string' ? value.trim().toLowerCase() : '';
    return normalized || fallback;
}

function getBackendLogScopeMetadata(scope) {
    const normalizedScope = normalizeBackendLogScope(scope);
    const metadata = BACKEND_LOG_SCOPE_METADATA[normalizedScope];
    if (metadata && typeof metadata === 'object') {
        return cloneObject(metadata);
    }

    return {
        label: normalizedScope,
    };
}

function getBackendLogScopeMetadataMap() {
    const metadataMap = {};
    for (const scope of Object.keys(BACKEND_LOG_SCOPE_METADATA)) {
        metadataMap[scope] = getBackendLogScopeMetadata(scope);
    }
    return metadataMap;
}

function getBackendLogLevelMetadata(level) {
    const normalizedLevel = normalizeBackendLogLevel(level);
    const metadata = BACKEND_LOG_LEVEL_METADATA[normalizedLevel];
    if (metadata && typeof metadata === 'object') {
        return cloneObject(metadata);
    }

    return {
        label: normalizedLevel.toUpperCase(),
    };
}

function getBackendLogLevelMetadataMap() {
    const metadataMap = {};
    for (const level of Object.keys(BACKEND_LOG_LEVEL_METADATA)) {
        metadataMap[level] = getBackendLogLevelMetadata(level);
    }
    return metadataMap;
}

function humanizeBackendLogFieldKey(fieldKey) {
    const normalizedFieldKey = typeof fieldKey === 'string' ? fieldKey.trim() : '';
    if (!normalizedFieldKey) {
        return 'Details';
    }

    return normalizedFieldKey
        .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
        .replace(/[_-]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .replace(/^./, (value) => value.toUpperCase());
}

function getBackendLogDetailFieldMetadata(fieldKey) {
    const normalizedFieldKey = typeof fieldKey === 'string' ? fieldKey.trim() : '';
    const metadata = normalizedFieldKey ? BACKEND_LOG_DETAIL_FIELD_METADATA[normalizedFieldKey] : null;
    if (metadata && typeof metadata === 'object') {
        return cloneObject(metadata);
    }

    return {
        label: humanizeBackendLogFieldKey(normalizedFieldKey),
    };
}

function normalizeBackendLogDetailValue(value) {
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

function formatBackendLogDetailSections(details) {
    if (typeof details === 'string') {
        const value = normalizeBackendLogDetailValue(details);
        return value
            ? [{
                key: 'details',
                label: getBackendLogDetailFieldMetadata('details').label,
                value,
            }]
            : [];
    }

    if (details && typeof details === 'object' && !Array.isArray(details)) {
        return Object.keys(details).map((fieldKey) => {
            const value = normalizeBackendLogDetailValue(details[fieldKey]);
            return value
                ? {
                    key: fieldKey,
                    label: getBackendLogDetailFieldMetadata(fieldKey).label,
                    value,
                }
                : null;
        }).filter(Boolean);
    }

    const value = normalizeBackendLogDetailValue(details);
    return value
        ? [{
            key: 'details',
            label: getBackendLogDetailFieldMetadata('details').label,
            value,
        }]
        : [];
}

function formatBackendLogForMonitor(logEntry) {
    const base = cloneObject(logEntry);
    const normalizedScope = normalizeBackendLogScope(base.scope);
    const normalizedLevel = normalizeBackendLogLevel(base.level);

    return {
        kind: 'backend-log',
        scopeLabel: getBackendLogScopeMetadata(normalizedScope).label,
        levelLabel: getBackendLogLevelMetadata(normalizedLevel).label,
        detailSections: formatBackendLogDetailSections(base.details),
    };
}

function enrichBackendLogEntry(logEntry) {
    const base = cloneObject(logEntry);
    const normalizedScope = normalizeBackendLogScope(base.scope);
    const normalizedLevel = normalizeBackendLogLevel(base.level);
    const normalizedMessage = typeof base.message === 'string' ? base.message.trim() : '';

    return {
        ...base,
        scope: normalizedScope,
        level: normalizedLevel,
        message: normalizedMessage,
        formattedLog: formatBackendLogForMonitor({
            ...base,
            scope: normalizedScope,
            level: normalizedLevel,
            message: normalizedMessage,
        }),
    };
}

module.exports = {
    BACKEND_LOG_DETAIL_FIELD_METADATA,
    BACKEND_LOG_LEVEL_METADATA,
    BACKEND_LOG_SCOPE_METADATA,
    DEFAULT_BACKEND_LOG_LEVEL,
    DEFAULT_BACKEND_LOG_SCOPE,
    enrichBackendLogEntry,
    formatBackendLogForMonitor,
    getBackendLogLevelMetadata,
    getBackendLogLevelMetadataMap,
    getBackendLogScopeMetadata,
    getBackendLogScopeMetadataMap,
    normalizeBackendLogLevel,
    normalizeBackendLogScope,
};