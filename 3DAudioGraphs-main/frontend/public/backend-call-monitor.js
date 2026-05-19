const ipcRenderer = globalThis.desktopBridge?.backend ?? null;
const BIO_HANDLER_PREFERENCES_KEY = '3daudio_backend_monitor_bio_handler_v1';

const elements = {
    connectionStatus: document.getElementById('connection-status'),
    analysisType: document.getElementById('analysis-type'),
    analysisHelp: document.getElementById('analysis-help'),
    saveMode: document.getElementById('save-mode'),
    saveLabel: document.getElementById('save-label'),
    bioHandlerSection: document.getElementById('bio-handler-section'),
    bioStatus: document.getElementById('bio-status'),
    bioWorkbookPath: document.getElementById('bio-workbook-path'),
    bioWorkbookBrowseBtn: document.getElementById('bio-workbook-browse-btn'),
    bioOutputModeField: document.getElementById('bio-output-mode-field'),
    bioOutputMode: document.getElementById('bio-output-mode'),
    bioFactTarget: document.getElementById('bio-fact-target'),
    bioFactOnsets: document.getElementById('bio-fact-onsets'),
    bioFactImported: document.getElementById('bio-fact-imported'),
    runCallBtn: document.getElementById('run-call-btn'),
    clearLogsBtn: document.getElementById('clear-logs-btn'),
    selectionStatus: document.getElementById('selection-status'),
    factAsset: document.getElementById('fact-asset'),
    factMode: document.getElementById('fact-mode'),
    factSelectionModel: document.getElementById('fact-selection-model'),
    factCurrentTarget: document.getElementById('fact-current-target'),
    factSource: document.getElementById('fact-source'),
    factPlanes: document.getElementById('fact-planes'),
    factVisibleFrames: document.getElementById('fact-visible-frames'),
    factSliceFrames: document.getElementById('fact-slice-frames'),
    factTime: document.getElementById('fact-time'),
    factFrequency: document.getElementById('fact-frequency'),
    factAmplitude: document.getElementById('fact-amplitude'),
    factPlayback: document.getElementById('fact-playback'),
    requestPreview: document.getElementById('request-preview'),
    resultPreview: document.getElementById('result-preview'),
    callLog: document.getElementById('call-log'),
    logCount: document.getElementById('log-count'),
};

const viewState = {
    actionCatalog: {},
    defaultActionType: '',
    errorCatalog: {},
    saveModeCatalog: {},
    currentState: null,
    logs: [],
    latestResult: null,
    isRunning: false,
    canonicalReadiness: {
        ready: false,
        pending: !!ipcRenderer,
        message: ipcRenderer
            ? 'Loading canonical backend readiness...'
            : 'Open this page through the desktop app to run backend calls.',
        selectionStatusMessage: '',
    },
    canonicalReadinessRequestId: 0,
    canonicalReadinessTimer: null,
};

const MONITOR_FAILURE_FIELDS = [
    { key: 'errorCode', label: 'Error Code' },
    { key: 'error', label: 'Error' },
    { key: 'exitCode', label: 'Exit Code' },
    { key: 'stderr', label: 'Standard Error' },
    { key: 'stdout', label: 'Standard Output' },
    { key: 'traceback', label: 'Traceback' },
    { key: 'details', label: 'Details' },
];

const loadBioHandlerPreferences = () => {
    try {
        const raw = globalThis.localStorage?.getItem(BIO_HANDLER_PREFERENCES_KEY);
        if (!raw) return {};
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (_error) {
        return {};
    }
};

const persistBioHandlerPreferences = () => {
    try {
        globalThis.localStorage?.setItem(BIO_HANDLER_PREFERENCES_KEY, JSON.stringify({
            workbookPath: elements.bioWorkbookPath.value.trim(),
            outputMode: elements.bioOutputMode.value,
        }));
    } catch (_error) {
        // Ignore preference persistence failures.
    }
};

const bioHandlerPreferences = loadBioHandlerPreferences();
elements.bioWorkbookPath.value = typeof bioHandlerPreferences.workbookPath === 'string'
    ? bioHandlerPreferences.workbookPath
    : '';
elements.bioOutputMode.value = typeof bioHandlerPreferences.outputMode === 'string' && bioHandlerPreferences.outputMode.trim() !== ''
    ? bioHandlerPreferences.outputMode
    : 'duplicate';

const getActionCatalog = () => viewState.actionCatalog && typeof viewState.actionCatalog === 'object'
    ? viewState.actionCatalog
    : {};

const getOrderedActionEntries = () => Object.entries(getActionCatalog());

const getCurrentActionType = () => {
    const selectedType = elements.analysisType.value;
    if (selectedType && getActionCatalog()[selectedType]) {
        return selectedType;
    }

    if (viewState.defaultActionType && getActionCatalog()[viewState.defaultActionType]) {
        return viewState.defaultActionType;
    }

    return getOrderedActionEntries()[0]?.[0] || '';
};

const getCurrentActionConfig = () => {
    const actionType = getCurrentActionType();
    return actionType ? getActionCatalog()[actionType] || null : null;
};

const getSaveModeCatalog = () => viewState.saveModeCatalog && typeof viewState.saveModeCatalog === 'object'
    ? viewState.saveModeCatalog
    : {};

const getErrorCatalog = () => viewState.errorCatalog && typeof viewState.errorCatalog === 'object'
    ? viewState.errorCatalog
    : {};

const getSharedErrorMessage = (errorCode, fallback = '') => {
    const normalizedErrorCode = typeof errorCode === 'string' ? errorCode.trim() : '';
    if (normalizedErrorCode && typeof getErrorCatalog()[normalizedErrorCode]?.message === 'string' && getErrorCatalog()[normalizedErrorCode].message.trim() !== '') {
        return getErrorCatalog()[normalizedErrorCode].message.trim();
    }
    return fallback;
};

const normalizeFailurePreviewValue = (value) => {
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
};

const buildFallbackFailureDisplay = (failurePayload) => ({
    kind: 'backend-failure',
    summary: '',
    sections: MONITOR_FAILURE_FIELDS.map(({ key, label }) => {
        const value = normalizeFailurePreviewValue(failurePayload?.[key]);
        return value
            ? { key, label, value }
            : null;
    }).filter(Boolean),
});

const formatStructuredFailurePreview = (formattedFailure, failurePayload = null) => {
    const summary = typeof formattedFailure?.summary === 'string' && formattedFailure.summary.trim() !== ''
        ? formattedFailure.summary.trim()
        : '';
    const sections = Array.isArray(formattedFailure?.sections) && formattedFailure.sections.length > 0
        ? formattedFailure.sections
        : buildFallbackFailureDisplay(failurePayload).sections;

    if (!summary && sections.length === 0) {
        return typeof failurePayload?.error === 'string' && failurePayload.error.trim() !== ''
            ? failurePayload.error.trim()
            : 'Backend call failed.';
    }

    return [
        summary,
        ...sections.map((section) => `${section.label}\n${section.value}`),
    ].filter(Boolean).join('\n\n');
};

const formatLatestResultPreview = (latestResult) => {
    if (!latestResult) {
        return 'No backend calls yet.';
    }

    if (latestResult?.formattedFailure || latestResult?.ok === false) {
        return formatStructuredFailurePreview(latestResult.formattedFailure, latestResult);
    }

    return JSON.stringify(latestResult, null, 2);
};

const normalizeLogDetailSections = (entry) => {
    if (Array.isArray(entry?.formattedLog?.detailSections) && entry.formattedLog.detailSections.length > 0) {
        return entry.formattedLog.detailSections.filter((section) => section && typeof section === 'object');
    }

    if (typeof entry?.details === 'string' && entry.details.trim() !== '') {
        return [{
            key: 'details',
            label: 'Details',
            value: entry.details.trim(),
        }];
    }

    if (entry?.details && typeof entry.details === 'object' && !Array.isArray(entry.details)) {
        return Object.keys(entry.details).map((fieldKey) => {
            const rawValue = entry.details[fieldKey];
            const value = typeof rawValue === 'string'
                ? rawValue.trim()
                : (typeof rawValue === 'number' || typeof rawValue === 'boolean')
                    ? String(rawValue)
                    : rawValue && typeof rawValue === 'object'
                        ? JSON.stringify(rawValue, null, 2)
                        : '';
            return value
                ? {
                    key: fieldKey,
                    label: fieldKey,
                    value,
                }
                : null;
        }).filter(Boolean);
    }

    return [];
};

const getCurrentBioState = () => viewState.currentState?.bioacoustics || null;

const getBioacousticsOptions = () => ({
    workbookPath: elements.bioWorkbookPath.value.trim(),
    outputMode: elements.bioOutputMode.value,
});

const getCanonicalReadinessState = () => viewState.canonicalReadiness && typeof viewState.canonicalReadiness === 'object'
    ? viewState.canonicalReadiness
    : {
        ready: false,
        pending: !!ipcRenderer,
        message: ipcRenderer
            ? 'Loading canonical backend readiness...'
            : 'Open this page through the desktop app to run backend calls.',
        selectionStatusMessage: '',
    };

const buildCanonicalReadinessRequest = () => {
    const actionConfig = getCurrentActionConfig();
    return {
        analysisType: getCurrentActionType(),
        bioacousticsState: actionConfig?.isBioacoustics
            ? (viewState.currentState?.bioacoustics || null)
            : undefined,
        bioacousticsOptions: actionConfig?.isBioacoustics
            ? getBioacousticsOptions()
            : undefined,
    };
};

const refreshCanonicalReadiness = async () => {
    const requestId = ++viewState.canonicalReadinessRequestId;
    if (!ipcRenderer) {
        viewState.canonicalReadiness = {
            ready: false,
            pending: false,
            message: 'Open this page through the desktop app to run backend calls.',
            selectionStatusMessage: '',
        };
        renderAll();
        return;
    }

    const actionConfig = getCurrentActionConfig();
    if (!actionConfig) {
        viewState.canonicalReadiness = {
            ready: false,
            pending: false,
            message: 'Loading backend action metadata...',
            selectionStatusMessage: '',
        };
        renderAll();
        return;
    }

    viewState.canonicalReadiness = {
        ...getCanonicalReadinessState(),
        ready: false,
        pending: true,
        message: 'Loading canonical backend readiness...',
    };
    renderAll();

    try {
        const response = await ipcRenderer.invoke('backend-call:evaluate-readiness', buildCanonicalReadinessRequest());
        if (requestId !== viewState.canonicalReadinessRequestId) {
            return;
        }
        viewState.canonicalReadiness = {
            ready: !!response?.readiness?.ready,
            pending: false,
            message: typeof response?.readiness?.message === 'string'
                ? response.readiness.message.trim()
                : '',
            selectionStatusMessage: typeof response?.selectionStatusMessage === 'string'
                ? response.selectionStatusMessage.trim()
                : '',
        };
    } catch (error) {
        if (requestId !== viewState.canonicalReadinessRequestId) {
            return;
        }
        viewState.canonicalReadiness = {
            ready: false,
            pending: false,
            message: error?.message || 'Failed to evaluate backend readiness from canonical session state.',
            selectionStatusMessage: '',
        };
    }

    renderAll();
};

const scheduleCanonicalReadinessRefresh = () => {
    if (viewState.canonicalReadinessTimer) {
        globalThis.clearTimeout(viewState.canonicalReadinessTimer);
    }
    viewState.canonicalReadinessTimer = globalThis.setTimeout(() => {
        viewState.canonicalReadinessTimer = null;
        void refreshCanonicalReadiness();
    }, 40);
};

const evaluateActionReadiness = () => {
    if (!ipcRenderer) {
        return {
            ready: false,
            message: 'Open this page through the desktop app to run backend calls.',
        };
    }

    const actionConfig = getCurrentActionConfig();
    if (!actionConfig) {
        return {
            ready: false,
            message: 'Loading backend action metadata...',
        };
    }

    if (viewState.isRunning) {
        return {
            ready: false,
            message: 'Backend call already in progress.',
        };
    }

    const readinessSnapshot = getCanonicalReadinessState();
    if (readinessSnapshot.pending) {
        return {
            ready: false,
            message: 'Loading canonical backend readiness...',
        };
    }

    if (!readinessSnapshot.ready) {
        return {
            ready: false,
            message: readinessSnapshot.message || 'The current action is not ready.',
        }
    }

    return {
        ready: true,
        message: '',
    };
};

const syncActionOptions = () => {
    const actionEntries = getOrderedActionEntries();
    const previousValue = elements.analysisType.value;

    elements.analysisType.replaceChildren();
    if (actionEntries.length === 0) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = ipcRenderer
            ? 'Loading backend actions...'
            : 'Open through the desktop app';
        elements.analysisType.appendChild(option);
        elements.analysisType.value = '';
        elements.analysisType.disabled = true;
        return;
    }

    for (const [analysisType, config] of actionEntries) {
        const option = document.createElement('option');
        option.value = analysisType;
        option.textContent = config?.label || analysisType;
        elements.analysisType.appendChild(option);
    }

    const nextValue = getActionCatalog()[previousValue]
        ? previousValue
        : (viewState.defaultActionType && getActionCatalog()[viewState.defaultActionType]
            ? viewState.defaultActionType
            : actionEntries[0][0]);
    elements.analysisType.value = nextValue;
    elements.analysisType.disabled = false;
};

const syncSaveModeOptions = () => {
    const actionConfig = getCurrentActionConfig();
    if (!actionConfig) {
        elements.saveMode.disabled = true;
        return;
    }

    const allowedSaveModes = Array.isArray(actionConfig.saveModes) && actionConfig.saveModes.length > 0
        ? actionConfig.saveModes
        : ['json', 'none'];
    const previousValue = elements.saveMode.value;

    elements.saveMode.replaceChildren();
    for (const saveMode of allowedSaveModes) {
        const option = document.createElement('option');
        option.value = saveMode;
        option.textContent = getSaveModeCatalog()[saveMode]?.label || saveMode;
        elements.saveMode.appendChild(option);
    }

    elements.saveMode.value = allowedSaveModes.includes(previousValue)
        ? previousValue
        : (actionConfig.defaultSaveMode || allowedSaveModes[0]);
    elements.saveMode.disabled = false;
    elements.saveLabel.placeholder = elements.saveMode.value === 'wav'
        ? 'Optional export label'
        : elements.saveMode.value === 'xlsx'
            ? 'Optional workbook label'
            : 'Optional result label';
};

const toText = (value, fallback = 'n/a') => {
    if (value === null || value === undefined || value === '') return fallback;
    return String(value);
};

const formatTimeRange = (range) => {
    if (!range) return 'n/a';
    return `${Number(range.start || 0).toFixed(3)}s -> ${Number(range.end || 0).toFixed(3)}s (${Number(range.duration || 0).toFixed(3)}s)`;
};

const formatFrameRange = (range) => {
    if (!range) return 'n/a';
    return `${toText(range.startFrame)} -> ${toText(range.endFrame)} (${toText(range.frameCount)} frames)`;
};

const formatBinRange = (range) => {
    if (!range) return 'n/a';
    return `${toText(range.startBin)} -> ${toText(range.endBin)} of ${toText(range.totalBins)}`;
};

const formatPctRange = (range) => {
    if (!range) return 'n/a';
    return `${Number(range.min || 0).toFixed(1)}% -> ${Number(range.max || 0).toFixed(1)}%`;
};

const buildRequestPreview = () => ({
    analysisType: getCurrentActionType(),
    saveOptions: {
        mode: elements.saveMode.value,
        label: elements.saveLabel.value.trim(),
    },
    asset: viewState.currentState?.asset || null,
    selection: viewState.currentState?.selection || null,
    bioacoustics: getCurrentActionConfig()?.isBioacoustics
        ? {
            ...(viewState.currentState?.bioacoustics || {}),
            ...getBioacousticsOptions(),
        }
        : (viewState.currentState?.bioacoustics || null),
    uiContext: viewState.currentState?.uiContext || null,
});

const isActionReady = () => {
    return evaluateActionReadiness().ready;
};

const renderBioHandler = () => {
    const actionConfig = getCurrentActionConfig();
    const bioState = getCurrentBioState();
    const showBioHandler = !!actionConfig?.isBioacoustics;

    elements.bioHandlerSection.style.display = showBioHandler ? 'grid' : 'none';
    if (!showBioHandler) return;

    elements.bioOutputModeField.style.display = actionConfig?.showBioOutputMode ? '' : 'none';
    elements.bioStatus.textContent = bioState?.statusMessage || 'Waiting for Bioacoustics handler state from the main window.';
    elements.bioFactTarget.textContent = `${toText(bioState?.targetLabel, 'Current Selection')} | ${toText(bioState?.targetKind, 'current')}`;
    elements.bioFactOnsets.textContent = `${toText(bioState?.onsetCount, 0)} current onset${Number(bioState?.onsetCount || 0) === 1 ? '' : 's'} | ${toText(bioState?.importedOnsetCount, 0)} imported onset${Number(bioState?.importedOnsetCount || 0) === 1 ? '' : 's'}`;
    elements.bioFactImported.textContent = bioState?.importedWorkbookPath
        ? `${bioState.importedWorkbookPath}\n${toText(bioState?.importedMatchedFileName, 'Matched file unavailable')}`
        : 'No workbook imported yet for the current asset.';
};

const renderFacts = () => {
    const currentState = viewState.currentState;
    const selection = currentState?.selection || null;
    const uiContext = currentState?.uiContext || null;

    elements.factAsset.textContent = currentState?.asset?.label || 'No asset loaded';
    elements.factMode.textContent = uiContext?.visualizationMode || 'n/a';
    elements.factSelectionModel.textContent = selection?.selectionModel || 'n/a';
    elements.factCurrentTarget.textContent = selection?.currentTarget || 'n/a';
    elements.factSource.textContent = selection?.source || 'n/a';
    elements.factPlanes.textContent = Array.isArray(selection?.activeSelectionSpaces) && selection.activeSelectionSpaces.length > 0
        ? selection.activeSelectionSpaces.join(' | ')
        : 'No active Selection Spaces';
    elements.factVisibleFrames.textContent = selection?.renderWindowLabel || formatFrameRange(selection?.visibleFrameWindow);
    elements.factSliceFrames.textContent = formatFrameRange(selection?.frameRange);
    elements.factTime.textContent = formatTimeRange(selection?.timeRangeSec);
    elements.factFrequency.textContent = formatBinRange(selection?.frequencyBinRange);
    elements.factAmplitude.textContent = formatPctRange(selection?.amplitudePctRange);
    elements.factPlayback.textContent = `${Number(uiContext?.playbackTimeSec || 0).toFixed(3)}s | Time Depth ${toText(uiContext?.terrainTimeDepth)} | Bins ${toText(uiContext?.terrainFrequencyBins)}`;
};

const renderLogs = () => {
    elements.callLog.replaceChildren();
    const entries = [...viewState.logs].reverse();

    for (const entry of entries) {
        const root = document.createElement('div');
        root.className = 'log-entry';
        root.dataset.level = entry.level || 'info';

        const meta = document.createElement('div');
        meta.className = 'log-meta';
        meta.textContent = `${toText(entry.timestamp, 'n/a')} | ${toText(entry?.formattedLog?.scopeLabel, toText(entry.scope, 'bridge'))} | ${toText(entry?.formattedLog?.levelLabel, toText(entry.level, 'info').toUpperCase())}`;

        const message = document.createElement('div');
        message.className = 'log-message';
        message.textContent = toText(entry.message, '');

        root.appendChild(meta);
        root.appendChild(message);

        const detailSections = normalizeLogDetailSections(entry);
        if (detailSections.length > 0) {
            const details = document.createElement('div');
            details.className = 'log-details';

            for (const section of detailSections) {
                const detailSection = document.createElement('div');
                detailSection.className = 'log-detail-section';

                const label = document.createElement('div');
                label.className = 'log-detail-label';
                label.textContent = toText(section.label, 'Details');

                const value = document.createElement('div');
                value.className = 'log-detail-value';
                value.textContent = toText(section.value, '');

                detailSection.appendChild(label);
                detailSection.appendChild(value);
                details.appendChild(detailSection);
            }

            root.appendChild(details);
        }

        elements.callLog.appendChild(root);
    }

    elements.logCount.textContent = `${viewState.logs.length} entr${viewState.logs.length === 1 ? 'y' : 'ies'}`;
};

const renderAll = () => {
    syncActionOptions();
    syncSaveModeOptions();
    elements.analysisHelp.textContent = getCurrentActionConfig()?.help || (ipcRenderer
        ? 'Loading backend action metadata...'
        : 'Open this page through the desktop app to load backend actions.');
    elements.saveLabel.disabled = elements.saveMode.value === 'none';
    if (elements.saveLabel.disabled) {
        elements.saveLabel.value = '';
    }

    elements.connectionStatus.textContent = ipcRenderer
        ? 'Electron bridge connected. The monitor receives the current rendered slice plus the live Full Sculpt Mask snapshot from the main window.'
        : 'Electron bridge unavailable. Open this page through the desktop app to run backend calls.';

    const selection = viewState.currentState?.selection || null;
    const readiness = evaluateActionReadiness();
    const canonicalReadiness = getCanonicalReadinessState();
    elements.selectionStatus.textContent = readiness.ready
        ? (getCurrentActionConfig()?.isBioacoustics
            ? (getCurrentBioState()?.statusMessage || 'Waiting for a Bioacoustics handler snapshot.')
            : (canonicalReadiness.selectionStatusMessage || selection?.statusMessage || 'Waiting for a selection snapshot.'))
        : readiness.message;
    renderBioHandler();
    renderFacts();
    elements.requestPreview.textContent = JSON.stringify(buildRequestPreview(), null, 2);
    elements.resultPreview.textContent = formatLatestResultPreview(viewState.latestResult);
    elements.runCallBtn.disabled = !isActionReady();
    elements.runCallBtn.textContent = viewState.isRunning ? 'Running...' : 'Run Backend Call';
    renderLogs();
};

elements.analysisType.addEventListener('change', () => {
    renderAll();
    scheduleCanonicalReadinessRefresh();
});
elements.saveMode.addEventListener('change', renderAll);
elements.saveLabel.addEventListener('input', renderAll);
elements.bioWorkbookPath.addEventListener('input', () => {
    persistBioHandlerPreferences();
    renderAll();
    scheduleCanonicalReadinessRefresh();
});
elements.bioOutputMode.addEventListener('change', () => {
    persistBioHandlerPreferences();
    renderAll();
    scheduleCanonicalReadinessRefresh();
});

elements.bioWorkbookBrowseBtn.addEventListener('click', async () => {
    if (!ipcRenderer) return;

    const response = await ipcRenderer.invoke('backend-call:show-open-dialog', {
        title: 'Choose Bioacoustics Workbook Or Folder',
        properties: ['openFile', 'openDirectory'],
        filters: [
            { name: 'Excel Files', extensions: ['xlsx', 'xls'] },
            { name: 'All Files', extensions: ['*'] },
        ],
        defaultPath: elements.bioWorkbookPath.value.trim() || undefined,
    });
    if (!response || response.canceled || !Array.isArray(response.filePaths) || response.filePaths.length === 0) {
        return;
    }

    elements.bioWorkbookPath.value = response.filePaths[0];
    persistBioHandlerPreferences();
    renderAll();
});

elements.clearLogsBtn.addEventListener('click', () => {
    viewState.logs = [];
    renderLogs();
    ipcRenderer?.send('backend-call-monitor:clear-logs');
});

elements.runCallBtn.addEventListener('click', async () => {
    if (!ipcRenderer || viewState.isRunning) return;

    viewState.isRunning = true;
    viewState.latestResult = {
        status: 'running',
        preview: buildRequestPreview(),
    };
    renderAll();

    try {
        const response = await ipcRenderer.invoke('backend-call:run', {
            analysisType: getCurrentActionType(),
            saveMode: elements.saveMode.value,
            saveLabel: elements.saveLabel.value.trim(),
            bioacousticsOptions: getCurrentActionConfig()?.isBioacoustics
                ? getBioacousticsOptions()
                : undefined,
        });
        viewState.latestResult = response;
    } catch (error) {
        const errorCode = typeof error?.errorCode === 'string' && error.errorCode.trim() !== ''
            ? error.errorCode.trim()
            : 'backend-call-invoke-failed';
        const failure = {
            ok: false,
            errorCode,
            error: getSharedErrorMessage(errorCode, error?.message || 'Backend call failed.'),
        };
        viewState.latestResult = {
            ...failure,
            formattedFailure: buildFallbackFailureDisplay(failure),
        };
    } finally {
        viewState.isRunning = false;
        renderAll();
    }
});

const loadActionMetadata = async () => {
    if (!ipcRenderer) {
        viewState.actionCatalog = {};
        viewState.defaultActionType = '';
        viewState.errorCatalog = {};
        viewState.saveModeCatalog = {};
        renderAll();
        return;
    }

    try {
        const response = await ipcRenderer.invoke('backend-call:get-action-metadata');
        viewState.actionCatalog = response?.actions && typeof response.actions === 'object'
            ? response.actions
            : {};
        viewState.defaultActionType = typeof response?.defaultActionType === 'string'
            ? response.defaultActionType
            : '';
        viewState.errorCatalog = response?.errors && typeof response.errors === 'object'
            ? response.errors
            : {};
        viewState.saveModeCatalog = response?.saveModes && typeof response.saveModes === 'object'
            ? response.saveModes
            : {};
    } catch (_error) {
        viewState.actionCatalog = {};
        viewState.defaultActionType = '';
        viewState.errorCatalog = {};
        viewState.saveModeCatalog = {};
    }

    renderAll();
    scheduleCanonicalReadinessRefresh();
};

if (ipcRenderer) {
    ipcRenderer.on('backend-call-monitor:state', (_event, nextState) => {
        viewState.currentState = nextState || null;
        renderAll();
        scheduleCanonicalReadinessRefresh();
    });

    ipcRenderer.on('backend-call-monitor:logs', (_event, logEntries) => {
        viewState.logs = Array.isArray(logEntries) ? logEntries : [];
        renderAll();
    });

    ipcRenderer.on('backend-call-monitor:log-appended', (_event, entry) => {
        if (!entry) return;
        viewState.logs.push(entry);
        renderLogs();
    });

    ipcRenderer.on('backend-call-monitor:call-started', (_event, requestPayload) => {
        viewState.isRunning = true;
        viewState.latestResult = {
            status: 'running',
            requestPayload,
        };
        renderAll();
    });

    ipcRenderer.on('backend-call-monitor:call-finished', (_event, response) => {
        viewState.isRunning = false;
        viewState.latestResult = response;
        renderAll();
    });

    ipcRenderer.on('backend-call-monitor:call-failed', (_event, response) => {
        viewState.isRunning = false;
        viewState.latestResult = response;
        renderAll();
    });

    ipcRenderer.send('backend-call-monitor:ready');
    void loadActionMetadata();
}

renderAll();