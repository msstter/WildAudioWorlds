const registry = require('./log_events.json');
const {
    normalizeBackendLogLevel,
    normalizeBackendLogScope,
} = require('./log_metadata.cjs');

const DEFAULT_BACKEND_LOG_EVENT_CODE = 'backend-call-failed';
const BACKEND_LOG_EVENT_METADATA = registry && typeof registry.events === 'object' && registry.events
    ? registry.events
    : {};

function cloneObject(value) {
    return value && typeof value === 'object' && !Array.isArray(value)
        ? { ...value }
        : {};
}

function normalizeBackendLogEventCode(value, fallback = DEFAULT_BACKEND_LOG_EVENT_CODE) {
    const normalized = typeof value === 'string' ? value.trim() : '';
    return normalized || fallback;
}

function getBackendLogEventMetadata(eventCode) {
    const normalizedEventCode = normalizeBackendLogEventCode(eventCode);
    const metadata = BACKEND_LOG_EVENT_METADATA[normalizedEventCode];
    if (metadata && typeof metadata === 'object') {
        return cloneObject(metadata);
    }

    return {
        scope: 'bridge',
        level: 'info',
        fallbackMessage: normalizedEventCode,
    };
}

function getBackendLogEventMetadataMap() {
    const metadataMap = {};
    for (const eventCode of Object.keys(BACKEND_LOG_EVENT_METADATA)) {
        metadataMap[eventCode] = getBackendLogEventMetadata(eventCode);
    }
    return metadataMap;
}

function getContextValue(context, pathExpression) {
    if (!pathExpression || typeof pathExpression !== 'string') {
        return undefined;
    }

    const pathSegments = pathExpression.split('.').map((segment) => segment.trim()).filter(Boolean);
    let current = context;
    for (const segment of pathSegments) {
        if (!current || typeof current !== 'object' || Array.isArray(current) || !(segment in current)) {
            return undefined;
        }
        current = current[segment];
    }
    return current;
}

function normalizeTemplateValue(value) {
    if (typeof value === 'string') {
        const trimmed = value.trim();
        return trimmed || '';
    }

    if (typeof value === 'number' || typeof value === 'boolean') {
        return String(value);
    }

    return '';
}

function formatBackendLogEventMessage(eventCode, context = {}, overrideMessage = '') {
    const metadata = getBackendLogEventMetadata(eventCode);
    const explicitMessage = normalizeTemplateValue(overrideMessage);
    if (explicitMessage) {
        return explicitMessage;
    }

    if (typeof metadata.messagePath === 'string' && metadata.messagePath.trim() !== '') {
        const value = normalizeTemplateValue(getContextValue(context, metadata.messagePath));
        if (value) {
            return value;
        }
    }

    if (typeof metadata.messageTemplate === 'string' && metadata.messageTemplate.includes('{')) {
        const renderedMessage = metadata.messageTemplate.replace(/\{([^{}]+)\}/g, (_match, token) => {
            const value = normalizeTemplateValue(getContextValue(context, token.trim()));
            return value;
        }).replace(/\s+/g, ' ').trim();
        if (renderedMessage) {
            return renderedMessage;
        }
    }

    return normalizeTemplateValue(metadata.fallbackMessage) || normalizeBackendLogEventCode(eventCode);
}

function buildBackendLogEventEntry(eventCode, context = {}, overrides = {}) {
    const metadata = getBackendLogEventMetadata(eventCode);
    const normalizedEventCode = normalizeBackendLogEventCode(eventCode);
    const nextOverrides = overrides && typeof overrides === 'object' && !Array.isArray(overrides)
        ? { ...overrides }
        : {};

    return {
        eventCode: normalizedEventCode,
        scope: normalizeBackendLogScope(nextOverrides.scope !== undefined ? nextOverrides.scope : metadata.scope),
        level: normalizeBackendLogLevel(nextOverrides.level !== undefined ? nextOverrides.level : metadata.level),
        message: formatBackendLogEventMessage(normalizedEventCode, context, nextOverrides.message),
        details: nextOverrides.details !== undefined ? nextOverrides.details : null,
    };
}

module.exports = {
    BACKEND_LOG_EVENT_METADATA,
    DEFAULT_BACKEND_LOG_EVENT_CODE,
    buildBackendLogEventEntry,
    formatBackendLogEventMessage,
    getBackendLogEventMetadata,
    getBackendLogEventMetadataMap,
    normalizeBackendLogEventCode,
};