const ipcRenderer = globalThis.desktopBridge?.backend ?? null;
const BIO_HANDLER_PREFERENCES_KEY = '3daudio_backend_monitor_bio_handler_v1';

const SAVE_MODE_LABELS = {
    json: 'Save JSON to data/exports/backend_calls',
    wav: 'Save WAV to data/exports/backend_calls',
    xlsx: 'Write Workbook Output (.xlsx)',
    none: 'Do Not Save a File',
};

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
    currentState: null,
    logs: [],
    latestResult: null,
    isRunning: false,
};

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
const getCurrentBioState = () => viewState.currentState?.bioacoustics || null;

const getBioacousticsOptions = () => ({
    workbookPath: elements.bioWorkbookPath.value.trim(),
    outputMode: elements.bioOutputMode.value,
});

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
        option.textContent = SAVE_MODE_LABELS[saveMode] || saveMode;
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
    bioacoustics: getCurrentActionConfig().isBioacoustics
        ? {
            ...(viewState.currentState?.bioacoustics || {}),
            ...getBioacousticsOptions(),
        }
        : (viewState.currentState?.bioacoustics || null),
    uiContext: viewState.currentState?.uiContext || null,
});

const isActionReady = () => {
    if (!ipcRenderer || viewState.isRunning) return false;

    const actionConfig = getCurrentActionConfig();
    if (!actionConfig) return false;
    if (!actionConfig.isBioacoustics) {
        return !!viewState.currentState?.selection?.isReady;
    }

    const bioState = getCurrentBioState();
    if (elements.analysisType.value === 'bioacoustics-import-workbook') {
        return !!bioState?.canImport && !!elements.bioWorkbookPath.value.trim();
    }

    const outputMode = elements.bioOutputMode.value;
    const needsSourceWorkbook = outputMode === 'duplicate' || outputMode === 'overwrite';
    return !!bioState?.canSync && (!needsSourceWorkbook || !!elements.bioWorkbookPath.value.trim());
};

const renderBioHandler = () => {
    const actionConfig = getCurrentActionConfig();
    const bioState = getCurrentBioState();
    const showBioHandler = !!actionConfig.isBioacoustics;

    elements.bioHandlerSection.style.display = showBioHandler ? 'grid' : 'none';
    if (!showBioHandler) return;

    elements.bioOutputModeField.style.display = actionConfig.showBioOutputMode ? '' : 'none';
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
        meta.textContent = `${toText(entry.timestamp, 'n/a')} | ${toText(entry.scope, 'bridge')} | ${toText(entry.level, 'info').toUpperCase()}`;

        const message = document.createElement('div');
        message.className = 'log-message';
        message.textContent = toText(entry.message, '');

        root.appendChild(meta);
        root.appendChild(message);

        if (entry.details) {
            const details = document.createElement('div');
            details.className = 'log-details';
            details.textContent = typeof entry.details === 'string'
                ? entry.details
                : JSON.stringify(entry.details, null, 2);
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
    elements.selectionStatus.textContent = getCurrentActionConfig()?.isBioacoustics
        ? (getCurrentBioState()?.statusMessage || 'Waiting for a Bioacoustics handler snapshot.')
        : (selection?.statusMessage || 'Waiting for a selection snapshot.');
    renderBioHandler();
    renderFacts();
    elements.requestPreview.textContent = JSON.stringify(buildRequestPreview(), null, 2);
    elements.resultPreview.textContent = viewState.latestResult
        ? JSON.stringify(viewState.latestResult, null, 2)
        : 'No backend calls yet.';
    elements.runCallBtn.disabled = !isActionReady();
    elements.runCallBtn.textContent = viewState.isRunning ? 'Running...' : 'Run Backend Call';
    renderLogs();
};

elements.analysisType.addEventListener('change', renderAll);
elements.saveMode.addEventListener('change', renderAll);
elements.saveLabel.addEventListener('input', renderAll);
elements.bioWorkbookPath.addEventListener('input', () => {
    persistBioHandlerPreferences();
    renderAll();
});
elements.bioOutputMode.addEventListener('change', () => {
    persistBioHandlerPreferences();
    renderAll();
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
            bioacousticsOptions: getCurrentActionConfig().isBioacoustics
                ? getBioacousticsOptions()
                : undefined,
        });
        viewState.latestResult = response;
    } catch (error) {
        viewState.latestResult = {
            ok: false,
            error: error?.message || 'Backend call failed.',
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
    } catch (_error) {
        viewState.actionCatalog = {};
        viewState.defaultActionType = '';
    }

    renderAll();
};

if (ipcRenderer) {
    ipcRenderer.on('backend-call-monitor:state', (_event, nextState) => {
        viewState.currentState = nextState || null;
        renderAll();
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