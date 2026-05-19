const { randomUUID } = require('crypto');
const { spawn, spawnSync } = require('child_process');
const { app, BrowserWindow, dialog, ipcMain, session } = require('electron');
const fs = require('fs');
const path = require('path');

const PRELOAD_ENTRY = path.join(__dirname, 'preload.cjs');
const SHARED_GRAPH_PATHS_MODULE = path.resolve(__dirname, '..', '..', 'packages', 'wild_audio_worlds', 'graph', 'backend_paths.cjs');
const SHARED_SESSION_COMMAND_CONTRACTS_MODULE = path.resolve(__dirname, '..', '..', 'packages', 'wild_audio_worlds', 'session', 'command_contracts.cjs');
const SHARED_SESSION_RECORDED_AUDIO_ERRORS_MODULE = path.resolve(__dirname, '..', '..', 'packages', 'wild_audio_worlds', 'session', 'recorded_audio_errors.cjs');
const LOCAL_INTEGRATION_BOOTSTRAP_MODULE = path.resolve(__dirname, '..', '..', 'services', 'local_integration', 'bootstrap_service.py');
const graphBackendPaths = fs.existsSync(SHARED_GRAPH_PATHS_MODULE)
    ? require(SHARED_GRAPH_PATHS_MODULE)
    : {
        resolveGraphProjectRoot: (frontendDir) => path.resolve(frontendDir, '..'),
        resolveBackendRunnerPath: (frontendDir) => path.join(path.resolve(frontendDir, '..'), 'backend', 'run_selection_analysis.py'),
        resolveRecordedAudioImportRunnerPath: (frontendDir) => path.join(path.resolve(frontendDir, '..'), 'backend', 'import_recorded_audio.py'),
    };
const sharedRecordedAudioErrors = fs.existsSync(SHARED_SESSION_RECORDED_AUDIO_ERRORS_MODULE)
    ? require(SHARED_SESSION_RECORDED_AUDIO_ERRORS_MODULE)
    : null;
const sessionCommandContracts = fs.existsSync(SHARED_SESSION_COMMAND_CONTRACTS_MODULE)
    ? require(SHARED_SESSION_COMMAND_CONTRACTS_MODULE)
    : {
        DEFAULT_BACKEND_ANALYSIS_TYPE: 'slice-summary',
        normalizeBackendAnalysisType(value) {
            const normalized = typeof value === 'string' ? value.trim() : '';
            return normalized || this.DEFAULT_BACKEND_ANALYSIS_TYPE;
        },
        normalizeBackendSaveMode(analysisType, requestedSaveMode) {
            const normalizedAction = this.normalizeBackendAnalysisType(analysisType);
            const normalizedSaveMode = typeof requestedSaveMode === 'string' && requestedSaveMode.trim() !== ''
                ? requestedSaveMode.trim().toLowerCase()
                : 'json';

            if (normalizedAction === 'export-time-slice-audio' || normalizedAction === 'export-spectral-mask-audio') {
                return 'wav';
            }
            if (normalizedAction === 'bioacoustics-sync-workbook') {
                return 'xlsx';
            }
            if (normalizedAction === 'bioacoustics-import-workbook') {
                return normalizedSaveMode === 'json' ? 'json' : 'none';
            }
            return normalizedSaveMode === 'none' ? 'none' : 'json';
        },
        isBioacousticsAnalysisType(analysisType) {
            return typeof analysisType === 'string' && analysisType.startsWith('bioacoustics-');
        },
        isBioacousticsImportAnalysisType(analysisType) {
            return this.normalizeBackendAnalysisType(analysisType) === 'bioacoustics-import-workbook';
        },
        isBioacousticsSyncAnalysisType(analysisType) {
            return this.normalizeBackendAnalysisType(analysisType) === 'bioacoustics-sync-workbook';
        },
        normalizeBackendSelectionContract(selectionPayload) {
            const selection = selectionPayload && typeof selectionPayload === 'object' && !Array.isArray(selectionPayload)
                ? { ...selectionPayload }
                : {};
            return {
                ...selection,
                isReady: !!selection.isReady,
                frameRange: selection.frameRange && typeof selection.frameRange === 'object' && !Array.isArray(selection.frameRange)
                    ? { ...selection.frameRange }
                    : {},
                sampleRange: selection.sampleRange && typeof selection.sampleRange === 'object' && !Array.isArray(selection.sampleRange)
                    ? { ...selection.sampleRange }
                    : {},
                timeRangeSec: selection.timeRangeSec && typeof selection.timeRangeSec === 'object' && !Array.isArray(selection.timeRangeSec)
                    ? { ...selection.timeRangeSec }
                    : {},
                frequencyBinRange: selection.frequencyBinRange && typeof selection.frequencyBinRange === 'object' && !Array.isArray(selection.frequencyBinRange)
                    ? { ...selection.frequencyBinRange }
                    : {},
                amplitudePctRange: selection.amplitudePctRange && typeof selection.amplitudePctRange === 'object' && !Array.isArray(selection.amplitudePctRange)
                    ? { ...selection.amplitudePctRange }
                    : {},
            };
        },
        normalizeBackendRequestState(baseState, runOptions = {}) {
            const requestState = runOptions?.requestState && typeof runOptions.requestState === 'object' && !Array.isArray(runOptions.requestState)
                ? runOptions.requestState
                : baseState;
            const normalizedState = requestState && typeof requestState === 'object' && !Array.isArray(requestState)
                ? { ...requestState }
                : {};
            const requestBioState = normalizedState.bioacoustics && typeof normalizedState.bioacoustics === 'object' && !Array.isArray(normalizedState.bioacoustics)
                ? { ...normalizedState.bioacoustics }
                : {};
            const bioacousticsOptions = runOptions?.bioacousticsOptions && typeof runOptions.bioacousticsOptions === 'object' && !Array.isArray(runOptions.bioacousticsOptions)
                ? { ...runOptions.bioacousticsOptions }
                : {};

            return {
                asset: normalizedState.asset && typeof normalizedState.asset === 'object' && !Array.isArray(normalizedState.asset)
                    ? { ...normalizedState.asset }
                    : null,
                selection: this.normalizeBackendSelectionContract(normalizedState.selection),
                uiContext: normalizedState.uiContext && typeof normalizedState.uiContext === 'object' && !Array.isArray(normalizedState.uiContext)
                    ? { ...normalizedState.uiContext }
                    : {},
                bioacoustics: {
                    ...requestBioState,
                    ...bioacousticsOptions,
                },
            };
        },
        normalizeBackendAnalysisRequest(payload) {
            if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
                throw new TypeError('Selection analysis payload must be a JSON object.');
            }
            const normalizedPayload = { ...payload };
            const saveOptions = normalizedPayload.saveOptions && typeof normalizedPayload.saveOptions === 'object' && !Array.isArray(normalizedPayload.saveOptions)
                ? { ...normalizedPayload.saveOptions }
                : {};
            const callMeta = normalizedPayload.callMeta && typeof normalizedPayload.callMeta === 'object' && !Array.isArray(normalizedPayload.callMeta)
                ? { ...normalizedPayload.callMeta }
                : {};
            const analysisType = this.normalizeBackendAnalysisType(normalizedPayload.analysisType);

            return {
                analysisType,
                asset: normalizedPayload.asset && typeof normalizedPayload.asset === 'object' && !Array.isArray(normalizedPayload.asset)
                    ? { ...normalizedPayload.asset }
                    : {},
                selection: this.normalizeBackendSelectionContract(normalizedPayload.selection),
                uiContext: normalizedPayload.uiContext && typeof normalizedPayload.uiContext === 'object' && !Array.isArray(normalizedPayload.uiContext)
                    ? { ...normalizedPayload.uiContext }
                    : {},
                bioacoustics: normalizedPayload.bioacoustics && typeof normalizedPayload.bioacoustics === 'object' && !Array.isArray(normalizedPayload.bioacoustics)
                    ? { ...normalizedPayload.bioacoustics }
                    : {},
                saveOptions: {
                    ...saveOptions,
                    mode: this.normalizeBackendSaveMode(analysisType, saveOptions.mode || 'json'),
                    label: typeof saveOptions.label === 'string' ? saveOptions.label.trim() : '',
                },
                callMeta: {
                    ...callMeta,
                    requestId: typeof callMeta.requestId === 'string' ? callMeta.requestId.trim() : '',
                    requestedAt: typeof callMeta.requestedAt === 'string' ? callMeta.requestedAt.trim() : '',
                },
            };
        },
        buildBackendAnalysisRequest(baseState, runOptions = {}, overrides = {}) {
            const requestState = this.normalizeBackendRequestState(baseState, runOptions);
            return this.normalizeBackendAnalysisRequest({
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
        },
        getBackendErrorMetadataMap() {
            return {
                'backend-asset-missing': {
                    message: 'No audio asset is loaded for backend analysis.',
                },
                'backend-runner-missing': {
                    message: 'Backend runner is unavailable.',
                },
                'backend-request-build-failed': {
                    message: 'Failed to prepare the backend request payload.',
                },
                'backend-response-parse-failed': {
                    message: 'Failed to parse backend JSON response.',
                },
                'backend-analysis-failed': {
                    message: 'Backend analysis failed.',
                },
                'backend-analysis-exit': {
                    message: 'Backend analysis exited unexpectedly.',
                },
                'backend-no-payload': {
                    message: 'Backend analysis returned no payload.',
                },
                'backend-call-invoke-failed': {
                    message: 'Backend call failed.',
                },
            };
        },
        getBackendErrorMetadata(errorCode) {
            const normalizedErrorCode = typeof errorCode === 'string' && errorCode.trim() !== ''
                ? errorCode.trim()
                : 'backend-analysis-failed';
            return this.getBackendErrorMetadataMap()?.[normalizedErrorCode] || {
                message: normalizedErrorCode,
            };
        },
        enrichBackendFailure(failurePayload, { errorCode } = {}) {
            const base = failurePayload && typeof failurePayload === 'object' && !Array.isArray(failurePayload)
                ? { ...failurePayload }
                : {};
            const resolvedErrorCode = typeof (errorCode || base.errorCode) === 'string' && String(errorCode || base.errorCode).trim() !== ''
                ? String(errorCode || base.errorCode).trim()
                : 'backend-analysis-failed';
            const metadata = this.getBackendErrorMetadata(resolvedErrorCode);

            return {
                ...base,
                ok: false,
                errorCode: resolvedErrorCode,
                error: typeof base.error === 'string' && base.error.trim() !== ''
                    ? base.error.trim()
                    : (metadata.message || resolvedErrorCode),
            };
        },
        buildBackendFailure(errorCode, overrides = {}) {
            return this.enrichBackendFailure(overrides, { errorCode });
        },
        getRecordedAudioErrorMetadataMap() {
            return sharedRecordedAudioErrors?.getRecordedAudioErrorMetadataMap?.() || {};
        },
        getRecordedAudioErrorMetadata(errorCode) {
            const normalizedErrorCode = typeof errorCode === 'string' && errorCode.trim() !== ''
                ? errorCode.trim()
                : 'recorded-audio-import-failed';
            if (typeof sharedRecordedAudioErrors?.getRecordedAudioErrorMetadata === 'function') {
                return sharedRecordedAudioErrors.getRecordedAudioErrorMetadata(normalizedErrorCode);
            }
            return this.getRecordedAudioErrorMetadataMap()?.[normalizedErrorCode] || {
                message: normalizedErrorCode,
            };
        },
        enrichRecordedAudioFailure(failurePayload, { errorCode } = {}) {
            const base = failurePayload && typeof failurePayload === 'object' && !Array.isArray(failurePayload)
                ? { ...failurePayload }
                : {};
            const resolvedErrorCode = typeof (errorCode || base.errorCode) === 'string' && String(errorCode || base.errorCode).trim() !== ''
                ? String(errorCode || base.errorCode).trim()
                : 'recorded-audio-import-failed';
            const metadata = this.getRecordedAudioErrorMetadata(resolvedErrorCode);

            return {
                ...base,
                ok: false,
                errorCode: resolvedErrorCode,
                error: typeof base.error === 'string' && base.error.trim() !== ''
                    ? base.error.trim()
                    : (metadata.message || resolvedErrorCode),
            };
        },
        buildRecordedAudioFailure(errorCode, overrides = {}) {
            return this.enrichRecordedAudioFailure(overrides, { errorCode });
        },
        evaluateBackendActionReadiness(analysisType, { selection = null, bioacoustics = null } = {}) {
            const actionMetadata = this.getBackendActionMetadataMap?.()[this.normalizeBackendAnalysisType(analysisType)] || null;
            const readiness = actionMetadata?.readiness || {};
            const messages = readiness?.messages || {};
            const selectionState = selection && typeof selection === 'object' && !Array.isArray(selection) ? selection : {};
            const bioState = bioacoustics && typeof bioacoustics === 'object' && !Array.isArray(bioacoustics) ? bioacoustics : {};

            if (readiness.requiresSelectionReady && !selectionState.isReady) {
                return {
                    ready: false,
                    code: 'selection-not-ready',
                    message: messages.notReady || 'No ready selection is available.',
                };
            }

            if (typeof readiness.requiresBioacousticsStateField === 'string' && readiness.requiresBioacousticsStateField.trim() !== '') {
                const requiredField = readiness.requiresBioacousticsStateField.trim();
                if (!bioState[requiredField]) {
                    return {
                        ready: false,
                        code: 'bioacoustics-state-not-ready',
                        message: messages.notReady || 'The current Bioacoustics action is not ready.',
                    };
                }
            }

            if (readiness.requiresOnsetTimes && (!Array.isArray(bioState.onsetTimes) || bioState.onsetTimes.length === 0)) {
                return {
                    ready: false,
                    code: 'missing-onset-times',
                    message: messages.missingOnsetTimes || 'The current action requires onset times.',
                };
            }

            const workbookPath = typeof bioState.workbookPath === 'string' ? bioState.workbookPath.trim() : '';
            if (readiness.requiresWorkbookPath && !workbookPath && !(readiness.acceptsAutoDiscover && bioState.autoDiscover)) {
                return {
                    ready: false,
                    code: 'missing-workbook-path',
                    message: messages.missingWorkbookPath || 'The current action requires a workbook path.',
                };
            }

            const requiredOutputModes = Array.isArray(readiness.workbookPathRequiredForOutputModes)
                ? readiness.workbookPathRequiredForOutputModes.map((value) => String(value || '').trim().toLowerCase()).filter(Boolean)
                : [];
            if (requiredOutputModes.length > 0) {
                const outputMode = typeof bioState.outputMode === 'string' && bioState.outputMode.trim() !== ''
                    ? bioState.outputMode.trim().toLowerCase()
                    : (typeof readiness.defaultOutputMode === 'string' && readiness.defaultOutputMode.trim() !== ''
                        ? readiness.defaultOutputMode.trim().toLowerCase()
                        : 'duplicate');
                if (requiredOutputModes.includes(outputMode) && !workbookPath) {
                    return {
                        ready: false,
                        code: 'missing-workbook-path-for-output-mode',
                        message: messages.missingWorkbookPathForOutputMode || 'The current output mode requires a workbook path.',
                    };
                }
            }

            return {
                ready: true,
                code: 'ready',
                message: '',
            };
        },
        getBackendSaveModeMetadataMap() {
            return {
                json: {
                    label: 'Save JSON to data/exports/backend_calls',
                    artifactType: 'json-report',
                    artifactLabel: 'JSON Report',
                },
                wav: {
                    label: 'Save WAV to data/exports/backend_calls',
                    artifactType: 'wav-audio',
                    artifactLabel: 'WAV Audio',
                },
                xlsx: {
                    label: 'Write Workbook Output (.xlsx)',
                    artifactType: 'workbook-output',
                    artifactLabel: 'Workbook Output',
                },
                none: {
                    label: 'Do Not Save a File',
                    artifactType: 'none',
                    artifactLabel: 'No File',
                },
            };
        },
        enrichBackendSaveResult(saveResult, { mode } = {}) {
            const metadataMap = this.getBackendSaveModeMetadataMap();
            const base = saveResult && typeof saveResult === 'object' && !Array.isArray(saveResult)
                ? { ...saveResult }
                : {};
            const normalizedMode = typeof (mode !== undefined ? mode : base.mode) === 'string' && String(mode !== undefined ? mode : base.mode).trim() !== ''
                ? String(mode !== undefined ? mode : base.mode).trim().toLowerCase()
                : 'json';
            const metadata = metadataMap[normalizedMode] || {
                label: normalizedMode,
                artifactType: normalizedMode,
                artifactLabel: normalizedMode,
            };

            return {
                ...base,
                mode: normalizedMode,
                modeLabel: metadata.label,
                artifactType: metadata.artifactType,
                artifactLabel: metadata.artifactLabel,
            };
        },
        getBackendActionMetadataMap() {
            return {
                'slice-summary': {
                    label: 'Slice Summary',
                    help: 'Runs a concise backend overview on the current SpectroTerrain slice: RMS, spectral centroid, bandwidth, zero crossing rate, onset strength, and energy concentration inside the selected frequency band.',
                    saveModes: ['json', 'none'],
                    defaultSaveMode: 'json',
                    isBioacoustics: false,
                    showBioOutputMode: false,
                    readiness: {
                        requiresSelectionReady: true,
                        messages: {
                            notReady: 'No ready SpectroTerrain selection is available. Enable the terrain plane selections so they define a full 3D slice.',
                        },
                    },
                },
                'mfcc-profile': {
                    label: 'MFCC Profile',
                    help: 'Computes a 13-coefficient MFCC profile for the current slice and returns per-coefficient mean and standard deviation values.',
                    saveModes: ['json', 'none'],
                    defaultSaveMode: 'json',
                    isBioacoustics: false,
                    showBioOutputMode: false,
                    readiness: {
                        requiresSelectionReady: true,
                        messages: {
                            notReady: 'No ready SpectroTerrain selection is available. Enable the terrain plane selections so they define a full 3D slice.',
                        },
                    },
                },
                'spectral-shape': {
                    label: 'Spectral Shape',
                    help: 'Focuses on broader spectral character for the slice, including rolloff, flatness, and spectral contrast statistics.',
                    saveModes: ['json', 'none'],
                    defaultSaveMode: 'json',
                    isBioacoustics: false,
                    showBioOutputMode: false,
                    readiness: {
                        requiresSelectionReady: true,
                        messages: {
                            notReady: 'No ready SpectroTerrain selection is available. Enable the terrain plane selections so they define a full 3D slice.',
                        },
                    },
                },
                'export-time-slice-audio': {
                    label: 'Export Time Slice Audio',
                    help: 'Exports the selected full-clip time window as a WAV file. This first audio path uses the shared sculpt time range, but it does not yet apply the sculpted frequency or amplitude mask.',
                    saveModes: ['wav'],
                    defaultSaveMode: 'wav',
                    isBioacoustics: false,
                    showBioOutputMode: false,
                    readiness: {
                        requiresSelectionReady: true,
                        messages: {
                            notReady: 'No ready SpectroTerrain selection is available. Enable the terrain plane selections so they define a full 3D slice.',
                        },
                    },
                },
                'export-spectral-mask-audio': {
                    label: 'Export Sculpted Spectral Mask Audio',
                    help: 'Exports a WAV rebuilt from the selected full-clip time window after masking the STFT by the sculpted frequency and amplitude bounds.',
                    saveModes: ['wav'],
                    defaultSaveMode: 'wav',
                    isBioacoustics: false,
                    showBioOutputMode: false,
                    readiness: {
                        requiresSelectionReady: true,
                        messages: {
                            notReady: 'No ready SpectroTerrain selection is available. Enable the terrain plane selections so they define a full 3D slice.',
                        },
                    },
                },
                'bioacoustics-import-workbook': {
                    label: 'Bioacoustics: Import Workbook Onsets',
                    help: 'Loads onset times from a BioacousticsProject workbook for the currently selected audio file. The path field can point directly to an Excel workbook or to an audio/output folder root, and the handler will resolve the matching AudioData_OnsetFinder workbook from there.',
                    saveModes: ['none', 'json'],
                    defaultSaveMode: 'none',
                    isBioacoustics: true,
                    showBioOutputMode: false,
                    readiness: {
                        requiresBioacousticsStateField: 'canImport',
                        requiresWorkbookPath: true,
                        acceptsAutoDiscover: true,
                        messages: {
                            notReady: 'Bioacoustics import is waiting for a compatible asset.',
                            missingWorkbookPath: 'Bioacoustics import requires a workbook path.',
                        },
                    },
                },
                'bioacoustics-sync-workbook': {
                    label: 'Bioacoustics: Sync Workbook',
                    help: 'Writes the current Timbre onset list into a Bioacoustics-compatible workbook and regenerates the summary plus dyadic sheets. The path field can point to a source workbook or to a folder root whose data subfolder should receive or resolve the workbook.',
                    saveModes: ['xlsx'],
                    defaultSaveMode: 'xlsx',
                    isBioacoustics: true,
                    showBioOutputMode: true,
                    readiness: {
                        requiresBioacousticsStateField: 'canSync',
                        requiresOnsetTimes: true,
                        defaultOutputMode: 'duplicate',
                        workbookPathRequiredForOutputModes: ['duplicate', 'overwrite'],
                        messages: {
                            notReady: 'Bioacoustics workbook sync is waiting for onset times from the active Timbre target.',
                            missingOnsetTimes: 'Bioacoustics workbook sync requires onset times from the active Timbre target.',
                            missingWorkbookPathForOutputMode: 'Duplicate or overwrite workbook sync requires a source workbook path.',
                        },
                    },
                },
            };
        },
    };
const {
    DEFAULT_BACKEND_ANALYSIS_TYPE,
    buildBackendLogEventEntry: sessionBuildBackendLogEventEntry,
    buildBackendFailure,
    buildBackendAnalysisRequest,
    buildRecordedAudioFailure,
    enrichBackendLogEntry: sessionEnrichBackendLogEntry,
    enrichBackendFailure,
    enrichRecordedAudioFailure,
    enrichBackendSaveResult,
    evaluateBackendActionReadiness,
    formatBackendFailureForMonitor,
    formatBackendLogForMonitor: sessionFormatBackendLogForMonitor,
    getBackendActionMetadataMap,
    getBackendErrorMetadata,
    getBackendErrorMetadataMap,
    getBackendSaveModeMetadataMap,
    getRecordedAudioErrorMetadata,
    isBioacousticsAnalysisType,
    isBioacousticsImportAnalysisType,
    isBioacousticsSyncAnalysisType,
    normalizeBackendAnalysisType,
    normalizeBackendRequestState,
    normalizeBackendSaveMode,
} = sessionCommandContracts;

const formatBackendLogForMonitor = typeof sessionFormatBackendLogForMonitor === 'function'
    ? sessionFormatBackendLogForMonitor
    : (logEntry = {}) => {
        const entry = logEntry && typeof logEntry === 'object' && !Array.isArray(logEntry)
            ? { ...logEntry }
            : {};
        const level = typeof entry.level === 'string' && entry.level.trim() !== ''
            ? entry.level.trim().toLowerCase()
            : 'info';
        const scope = typeof entry.scope === 'string' && entry.scope.trim() !== ''
            ? entry.scope.trim()
            : 'bridge';
        const detailSections = typeof entry.details === 'string' && entry.details.trim() !== ''
            ? [{ key: 'details', label: 'Details', value: entry.details.trim() }]
            : entry.details && typeof entry.details === 'object' && !Array.isArray(entry.details)
                ? Object.keys(entry.details).map((fieldKey) => {
                    const rawValue = entry.details[fieldKey];
                    const value = typeof rawValue === 'string'
                        ? rawValue.trim()
                        : (typeof rawValue === 'number' || typeof rawValue === 'boolean')
                            ? String(rawValue)
                            : rawValue && typeof rawValue === 'object'
                                ? JSON.stringify(rawValue, null, 2)
                                : '';
                    return value
                        ? { key: fieldKey, label: fieldKey, value }
                        : null;
                }).filter(Boolean)
                : [];

        return {
            kind: 'backend-log',
            scopeLabel: scope,
            levelLabel: level.toUpperCase(),
            detailSections,
        };
    };

const enrichBackendLogEntry = typeof sessionEnrichBackendLogEntry === 'function'
    ? sessionEnrichBackendLogEntry
    : (logEntry = {}) => {
        const entry = logEntry && typeof logEntry === 'object' && !Array.isArray(logEntry)
            ? { ...logEntry }
            : {};
        const level = typeof entry.level === 'string' && entry.level.trim() !== ''
            ? entry.level.trim().toLowerCase()
            : 'info';
        const scope = typeof entry.scope === 'string' && entry.scope.trim() !== ''
            ? entry.scope.trim()
            : 'bridge';
        const message = typeof entry.message === 'string' ? entry.message.trim() : '';

        return {
            ...entry,
            level,
            scope,
            message,
            formattedLog: formatBackendLogForMonitor({
                ...entry,
                level,
                scope,
                message,
            }),
        };
    };

const buildBackendLogEventEntry = typeof sessionBuildBackendLogEventEntry === 'function'
    ? sessionBuildBackendLogEventEntry
    : (eventCode, context = {}, overrides = {}) => {
        const nextOverrides = overrides && typeof overrides === 'object' && !Array.isArray(overrides)
            ? { ...overrides }
            : {};
        const nextContext = context && typeof context === 'object' && !Array.isArray(context)
            ? context
            : {};
        const defaultEventMap = {
            'backend-call-started': {
                scope: 'bridge',
                level: 'info',
                message: `Running ${nextContext.analysisType || 'backend action'} for ${nextContext.assetLabel || 'current asset'}.`,
            },
            'backend-call-completed-saved': {
                scope: 'bridge',
                level: 'info',
                message: `Completed ${nextContext.analysisType || 'backend action'}. Saved ${nextContext.artifactLabel || 'output'}.`,
            },
            'backend-call-completed-unsaved': {
                scope: 'bridge',
                level: 'info',
                message: `Completed ${nextContext.analysisType || 'backend action'}. No file was saved.`,
            },
            'backend-call-failed': {
                scope: 'bridge',
                level: 'error',
                message: nextContext.failure?.error || 'Backend analysis failed.',
            },
            'backend-call-stderr': {
                scope: 'backend-stderr',
                level: 'warn',
                message: nextContext.stderrText || 'Backend emitted stderr output.',
            },
        };
        const defaultEntry = defaultEventMap[eventCode] || {
            scope: 'bridge',
            level: 'info',
            message: eventCode,
        };

        return {
            eventCode,
            scope: nextOverrides.scope !== undefined ? nextOverrides.scope : defaultEntry.scope,
            level: nextOverrides.level !== undefined ? nextOverrides.level : defaultEntry.level,
            message: typeof nextOverrides.message === 'string' && nextOverrides.message.trim() !== ''
                ? nextOverrides.message.trim()
                : defaultEntry.message,
            details: nextOverrides.details !== undefined ? nextOverrides.details : null,
        };
    };

let mainWindow;
let backendMonitorWindow = null;
let backendCallStateCache = null;
let backendCallLogsCache = [];
let cachedBackendPythonCommand = null;
let localIntegrationSessionCache = null;

const BACKEND_CALL_LOG_LIMIT = 200;
const LOCAL_INTEGRATION_HOST_SHELL_ID = `shell-graph-${randomUUID()}`;
const LOCAL_INTEGRATION_HOST_STARTED_AT = new Date().toISOString();

// Use dedicated GPU more aggressively.
app.commandLine.appendSwitch('force_high_performance_gpu');

function getProjectRoot() {
    return graphBackendPaths.resolveGraphProjectRoot(__dirname);
}

function getWorkspaceRoot() {
    return path.resolve(getProjectRoot(), '..');
}

function isDevMode() {
    return !app.isPackaged;
}

function getRendererBaseUrl() {
    return (process.env.ELECTRON_RENDERER_URL || 'http://localhost:5173').replace(/\/$/, '');
}

function loadWindowEntry(windowRef, htmlFile = 'index.html') {
    if (isDevMode()) {
        const url = htmlFile === 'index.html'
            ? getRendererBaseUrl()
            : `${getRendererBaseUrl()}/${htmlFile}`;
        return windowRef.loadURL(url);
    }

    return windowRef.loadFile(path.join(__dirname, 'dist-renderer', htmlFile));
}

function buildWindowOptions(overrides = {}) {
    return {
        width: 1400,
        height: 900,
        webPreferences: {
            preload: PRELOAD_ENTRY,
            nodeIntegration: false,
            contextIsolation: true,
        },
        ...overrides,
    };
}

function trimBackendCallLogs() {
    if (backendCallLogsCache.length <= BACKEND_CALL_LOG_LIMIT) return;
    backendCallLogsCache = backendCallLogsCache.slice(-BACKEND_CALL_LOG_LIMIT);
}

function sendToBackendMonitor(channel, payload) {
    if (!backendMonitorWindow || backendMonitorWindow.isDestroyed()) return;
    backendMonitorWindow.webContents.send(channel, payload);
}

function sendToMainWindow(channel, payload) {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    mainWindow.webContents.send(channel, payload);
}

function appendBackendLog({ level = 'info', scope = 'bridge', message = '', details = null } = {}) {
    const entry = enrichBackendLogEntry({
        id: randomUUID(),
        timestamp: new Date().toISOString(),
        level,
        scope,
        message,
        details,
    });

    backendCallLogsCache.push(entry);
    trimBackendCallLogs();
    sendToBackendMonitor('backend-call-monitor:log-appended', entry);
    return entry;
}

function appendBackendEventLog(eventCode, context = {}, overrides = {}) {
    return appendBackendLog(buildBackendLogEventEntry(eventCode, context, overrides));
}

function setBackendCallState(nextState) {
    backendCallStateCache = nextState && typeof nextState === 'object' ? nextState : null;
    sendToBackendMonitor('backend-call-monitor:state', backendCallStateCache);
}

function withFormattedBackendFailure(failurePayload, { errorCode } = {}) {
    const failure = enrichBackendFailure(failurePayload, { errorCode });
    if (typeof formatBackendFailureForMonitor !== 'function') {
        return failure;
    }

    return {
        ...failure,
        formattedFailure: formatBackendFailureForMonitor(failure, {
            errorCode: failure.errorCode,
        }),
    };
}

function resolvePythonEnvironmentRoot(command) {
    if (!path.isAbsolute(command)) return null;

    const executableDir = path.dirname(command);
    const executableDirName = path.basename(executableDir).toLowerCase();
    if (executableDirName === 'scripts' || executableDirName === 'bin') {
        return path.dirname(executableDir);
    }

    return executableDir;
}

function buildBackendPythonEnv(command) {
    const nextEnv = {
        ...process.env,
        PYTHONUNBUFFERED: '1',
    };

    if (process.platform !== 'win32' || !path.isAbsolute(command)) {
        return nextEnv;
    }

    const envRoot = resolvePythonEnvironmentRoot(command);
    if (!envRoot) {
        return nextEnv;
    }

    const pathEntries = [
        path.join(envRoot, 'Library', 'mingw-w64', 'bin'),
        path.join(envRoot, 'Library', 'usr', 'bin'),
        path.join(envRoot, 'Library', 'bin'),
        path.join(envRoot, 'Scripts'),
        envRoot,
    ].filter((entry, index, entries) => fs.existsSync(entry) && entries.indexOf(entry) === index);

    if (pathEntries.length === 0) {
        return nextEnv;
    }

    const pathKey = Object.keys(nextEnv).find((key) => key.toLowerCase() === 'path') || 'Path';
    const currentPath = typeof nextEnv[pathKey] === 'string' ? nextEnv[pathKey] : '';
    nextEnv[pathKey] = [...pathEntries, currentPath].filter(Boolean).join(path.delimiter);
    return nextEnv;
}

function resolveBackendPythonCommand() {
    if (cachedBackendPythonCommand) {
        return cachedBackendPythonCommand;
    }

    const projectRoot = getProjectRoot();
    const explicitCommand = process.env.BACKEND_PYTHON;
    const fileCandidates = [
        explicitCommand,
        process.platform === 'win32'
            ? path.join(projectRoot, '.conda-backend', 'python.exe')
            : path.join(projectRoot, '.conda-backend', 'bin', 'python'),
        path.join(projectRoot, '.venv', 'bin', 'python'),
        path.join(projectRoot, '.venv', 'Scripts', 'python.exe'),
    ].filter(Boolean);

    const canRunBackendModules = (command) => {
        try {
            const result = spawnSync(command, ['-c', 'import librosa, numpy, soundfile'], {
                cwd: projectRoot,
                env: buildBackendPythonEnv(command),
                stdio: 'ignore',
                timeout: 10000,
            });
            return result.status === 0;
        } catch (_error) {
            return false;
        }
    };

    for (const candidate of fileCandidates) {
        if (!path.isAbsolute(candidate)) continue;
        if (fs.existsSync(candidate) && canRunBackendModules(candidate)) {
            cachedBackendPythonCommand = candidate;
            return cachedBackendPythonCommand;
        }
    }

    if (explicitCommand && !path.isAbsolute(explicitCommand) && canRunBackendModules(explicitCommand)) {
        cachedBackendPythonCommand = explicitCommand;
        return cachedBackendPythonCommand;
    }

    const fallbackCandidates = process.platform === 'win32'
        ? ['python']
        : ['python3', 'python'];
    for (const candidate of fallbackCandidates) {
        if (canRunBackendModules(candidate)) {
            cachedBackendPythonCommand = candidate;
            return cachedBackendPythonCommand;
        }
    }

    cachedBackendPythonCommand = process.platform === 'win32' ? 'python' : 'python3';
    return cachedBackendPythonCommand;
}

function resolveBackendRunnerPath() {
    return graphBackendPaths.resolveBackendRunnerPath(__dirname);
}

function resolveRecordedAudioImportRunnerPath() {
    return graphBackendPaths.resolveRecordedAudioImportRunnerPath(__dirname);
}

function resolveLocalIntegrationBootstrapPath() {
    return LOCAL_INTEGRATION_BOOTSTRAP_MODULE;
}

function sanitizeFileComponent(value, fallback = 'recorded-audio') {
    const sanitized = String(value || '')
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
    return sanitized || fallback;
}

function formatFileTimestamp(date = new Date()) {
    const parts = [
        date.getFullYear(),
        `${date.getMonth() + 1}`.padStart(2, '0'),
        `${date.getDate()}`.padStart(2, '0'),
        `${date.getHours()}`.padStart(2, '0'),
        `${date.getMinutes()}`.padStart(2, '0'),
        `${date.getSeconds()}`.padStart(2, '0'),
    ];
    return `${parts[0]}${parts[1]}${parts[2]}-${parts[3]}${parts[4]}${parts[5]}`;
}

function toNodeBuffer(value) {
    if (value instanceof ArrayBuffer) {
        return Buffer.from(value);
    }
    if (ArrayBuffer.isView(value)) {
        return Buffer.from(value.buffer, value.byteOffset, value.byteLength);
    }
    return null;
}

function buildLocalIntegrationSessionPayload({
    launchReason = 'service-bootstrap',
    asset = null,
    selection = null,
} = {}) {
    const currentState = backendCallStateCache && typeof backendCallStateCache === 'object' && !Array.isArray(backendCallStateCache)
        ? backendCallStateCache
        : {};
    const currentAsset = asset && typeof asset === 'object' && !Array.isArray(asset)
        ? asset
        : (currentState.asset && typeof currentState.asset === 'object' && !Array.isArray(currentState.asset)
            ? currentState.asset
            : {});
    const currentSelection = selection && typeof selection === 'object' && !Array.isArray(selection)
        ? selection
        : (currentState.selection && typeof currentState.selection === 'object' && !Array.isArray(currentState.selection)
            ? currentState.selection
            : {});
    const currentUiContext = currentState.uiContext && typeof currentState.uiContext === 'object' && !Array.isArray(currentState.uiContext)
        ? currentState.uiContext
        : {};

    return {
        sessionId: localIntegrationSessionCache?.sessionId || '',
        mode: 'standalone',
        hostShell: {
            shellId: LOCAL_INTEGRATION_HOST_SHELL_ID,
            shellType: 'audio-graphs',
            startedAt: LOCAL_INTEGRATION_HOST_STARTED_AT,
            version: app.getVersion(),
        },
        asset: {
            assetId: currentAsset.id || '',
            assetLabel: currentAsset.label || '',
            sourceAudioPath: typeof currentAsset.audioUrl === 'string' ? currentAsset.audioUrl : '',
            sourceKind: typeof currentAsset.audioUrl === 'string' && currentAsset.audioUrl.trim() !== ''
                ? 'frontend-audio-asset'
                : 'unknown',
            activeRevisionId: currentAsset.revisionId || currentAsset.id || '',
        },
        transportState: {
            playheadSec: Number(currentUiContext.playbackTimeSec || 0),
            selectionWindow: currentSelection,
        },
        launchContext: {
            originatingShell: 'audio-graphs',
            launchReason,
            requestedCompanion: '',
            requestedByShellId: LOCAL_INTEGRATION_HOST_SHELL_ID,
        },
        peers: [{
            shellId: LOCAL_INTEGRATION_HOST_SHELL_ID,
            shellType: 'audio-graphs',
            status: 'attached',
            attachedAt: LOCAL_INTEGRATION_HOST_STARTED_AT,
            lastSeenAt: new Date().toISOString(),
        }],
    };
}

function runLocalIntegrationServiceCommand(command, payload, {
    launchReason = command,
    asset = null,
    selection = null,
    onStderrLine = null,
} = {}) {
    return new Promise((resolve, reject) => {
        const bootstrapPath = resolveLocalIntegrationBootstrapPath();
        if (!fs.existsSync(bootstrapPath)) {
            reject(new Error(`Local integration service bootstrap not found: ${bootstrapPath}`));
            return;
        }

        const pythonCommand = resolveBackendPythonCommand();
        const child = spawn(pythonCommand, [bootstrapPath], {
            cwd: getWorkspaceRoot(),
            env: buildBackendPythonEnv(pythonCommand),
        });

        let stdout = '';
        let stderr = '';

        child.stdout.on('data', (chunk) => {
            stdout += chunk.toString();
        });

        child.stderr.on('data', (chunk) => {
            const text = chunk.toString();
            stderr += text;
            if (typeof onStderrLine === 'function') {
                for (const line of text.split(/\r?\n/)) {
                    const trimmed = line.trim();
                    if (trimmed) {
                        onStderrLine(trimmed);
                    }
                }
            }
        });

        child.on('error', (error) => {
            error.stderr = stderr;
            reject(error);
        });

        child.on('close', (code) => {
            let parsed = null;
            try {
                parsed = stdout.trim() ? JSON.parse(stdout) : null;
            } catch (parseError) {
                parseError.stdout = stdout;
                parseError.stderr = stderr;
                reject(parseError);
                return;
            }

            if (parsed?.session && typeof parsed.session === 'object') {
                localIntegrationSessionCache = {
                    ...(localIntegrationSessionCache || {}),
                    ...parsed.session,
                };
            }

            if (code !== 0 || parsed?.ok === false) {
                const error = new Error(parsed?.error || `Local integration service command failed: ${command}`);
                error.payload = parsed || null;
                error.stderr = stderr;
                error.stdout = stdout;
                reject(error);
                return;
            }

            resolve(parsed || {
                ok: true,
                session: localIntegrationSessionCache,
            });
        });

        child.stdin.write(JSON.stringify({
            command,
            workspaceRoot: getWorkspaceRoot(),
            projectRoot: getProjectRoot(),
            session: buildLocalIntegrationSessionPayload({
                launchReason,
                asset,
                selection,
            }),
            payload,
        }));
        child.stdin.end();
    });
}

async function ensureLocalIntegrationSession({
    launchReason = 'service-bootstrap',
    asset = null,
    selection = null,
} = {}) {
    if (localIntegrationSessionCache?.sessionId) {
        return localIntegrationSessionCache;
    }

    const bootstrapResult = await runLocalIntegrationServiceCommand('service/bootstrap', {}, {
        launchReason,
        asset,
        selection,
    });
    return bootstrapResult?.session || localIntegrationSessionCache;
}

function runBackendSelectionAnalysis(requestPayload) {
    return new Promise((resolve, reject) => {
        void (async () => {
            try {
                await ensureLocalIntegrationSession({
                    launchReason: 'backend-call-bootstrap',
                    asset: requestPayload?.asset || null,
                    selection: requestPayload?.selection || null,
                });
                const integrationResponse = await runLocalIntegrationServiceCommand('backend-call/run', requestPayload, {
                    launchReason: 'backend-call-run',
                    asset: requestPayload?.asset || null,
                    selection: requestPayload?.selection || null,
                    onStderrLine: (stderrText) => {
                        appendBackendEventLog('backend-call-stderr', {
                            stderrText,
                        });
                    },
                });
                const response = integrationResponse?.response || null;
                if (response?.ok === false) {
                    const failure = enrichBackendFailure(response, {
                        errorCode: response?.errorCode || 'backend-analysis-failed',
                    });
                    const error = new Error(failure.error);
                    error.payload = failure;
                    error.errorCode = failure.errorCode;
                    reject(error);
                    return;
                }

                resolve(response || buildBackendFailure('backend-no-payload'));
            } catch (error) {
                reject(error);
            }
        })();
    });
}

function runRecordedAudioImport(requestPayload) {
    return new Promise((resolve, reject) => {
        void (async () => {
            try {
                await ensureLocalIntegrationSession({
                    launchReason: 'recorded-audio-bootstrap',
                });
                const integrationResponse = await runLocalIntegrationServiceCommand('recorded-audio/import', requestPayload, {
                    launchReason: 'recorded-audio-import',
                });
                const response = integrationResponse?.response || null;
                if (response?.ok === false) {
                    const failure = enrichRecordedAudioFailure(response, {
                        errorCode: response?.errorCode || 'recorded-audio-import-failed',
                    });
                    const error = new Error(failure.error || getRecordedAudioErrorMetadata('recorded-audio-import-failed').message);
                    error.payload = failure;
                    error.errorCode = failure.errorCode;
                    reject(error);
                    return;
                }

                resolve(response || { ok: true });
            } catch (error) {
                reject(error);
            }
        })();
    });
}

function createBackendMonitorWindow() {
    if (backendMonitorWindow && !backendMonitorWindow.isDestroyed()) {
        backendMonitorWindow.focus();
        return backendMonitorWindow;
    }

    backendMonitorWindow = new BrowserWindow(buildWindowOptions({
        width: 760,
        height: 880,
        minWidth: 620,
        minHeight: 720,
        title: 'Backend Call Monitor',
        autoHideMenuBar: true,
    }));

    loadWindowEntry(backendMonitorWindow, 'backend-call-monitor.html');

    backendMonitorWindow.on('closed', () => {
        backendMonitorWindow = null;
    });

    backendMonitorWindow.webContents.on('did-finish-load', () => {
        sendToBackendMonitor('backend-call-monitor:state', backendCallStateCache);
        sendToBackendMonitor('backend-call-monitor:logs', backendCallLogsCache);
    });

    return backendMonitorWindow;
}

ipcMain.handle('backend-call-monitor:open', async () => {
    createBackendMonitorWindow();
    return { ok: true };
});

ipcMain.handle('backend-call:get-action-metadata', async () => {
    return {
        ok: true,
        defaultActionType: DEFAULT_BACKEND_ANALYSIS_TYPE,
        actions: getBackendActionMetadataMap(),
        errors: getBackendErrorMetadataMap(),
        saveModes: getBackendSaveModeMetadataMap(),
    };
});

ipcMain.handle('backend-call:show-open-dialog', async (event, dialogOptions = {}) => {
    const browserWindow = BrowserWindow.fromWebContents(event.sender) || mainWindow || undefined;
    const requestedProperties = Array.isArray(dialogOptions?.properties) && dialogOptions.properties.length > 0
        ? dialogOptions.properties
        : ['openFile'];
    const isDirectorySelection = requestedProperties.includes('openDirectory');
    const result = await dialog.showOpenDialog(browserWindow, {
        title: typeof dialogOptions?.title === 'string' && dialogOptions.title.trim() !== ''
            ? dialogOptions.title.trim()
            : isDirectorySelection ? 'Choose Folder' : 'Choose Workbook',
        properties: requestedProperties,
        filters: Array.isArray(dialogOptions?.filters) && dialogOptions.filters.length > 0
            ? dialogOptions.filters
            : isDirectorySelection
                ? []
            : [
                { name: 'Excel Files', extensions: ['xlsx', 'xls'] },
                { name: 'All Files', extensions: ['*'] },
            ],
        defaultPath: typeof dialogOptions?.defaultPath === 'string' && dialogOptions.defaultPath.trim() !== ''
            ? dialogOptions.defaultPath
            : undefined,
    });

    return {
        canceled: !!result.canceled,
        filePaths: Array.isArray(result.filePaths) ? result.filePaths : [],
    };
});

ipcMain.handle('recorded-audio:import', async (_event, requestPayload = {}) => {
    const audioBuffer = toNodeBuffer(requestPayload?.audioBuffer);
    if (!audioBuffer || audioBuffer.length === 0) {
        return buildRecordedAudioFailure('recorded-audio-missing-buffer');
    }

    const requestedLabel = typeof requestPayload?.assetLabel === 'string'
        ? requestPayload.assetLabel.trim()
        : '';
    const safeStem = sanitizeFileComponent(requestPayload?.fileStem || requestedLabel, 'recorded-audio');
    const finalStem = `${safeStem}-${formatFileTimestamp()}`;
    const projectRoot = getProjectRoot();
    const sampleAudioDir = path.join(projectRoot, 'data', 'sample_audio');
    const savedAudioPath = path.join(sampleAudioDir, `${finalStem}.wav`);

    fs.mkdirSync(sampleAudioDir, { recursive: true });
    fs.writeFileSync(savedAudioPath, audioBuffer);

    appendBackendEventLog('recorded-audio-saved', {
        savedAudioPath,
    }, {
        details: {
            includeMfcc: requestPayload?.includeMfcc !== false,
        },
    });

    try {
        const response = await runRecordedAudioImport({
            audioPath: savedAudioPath,
            assetLabel: requestedLabel || finalStem,
            includeMfcc: requestPayload?.includeMfcc !== false,
            projectRoot,
        });

        appendBackendEventLog('recorded-audio-imported', {
            assetLabel: response?.asset?.label || finalStem,
        }, {
            details: {
                assetId: response?.asset?.id || null,
                savedAudioPath,
            },
        });
        return response;
    } catch (error) {
        const failure = error?.payload
            ? enrichRecordedAudioFailure(error.payload, {
                errorCode: error?.payload?.errorCode || error?.errorCode || 'recorded-audio-import-failed',
            })
            : buildRecordedAudioFailure(error?.errorCode || 'recorded-audio-import-failed', {
                error: error?.message || undefined,
                stderr: error?.stderr || '',
                stdout: error?.stdout || '',
            });
        appendBackendEventLog('recorded-audio-failed', {
            failure,
        }, {
            details: failure.details || failure.stderr || failure.traceback || failure.stdout || null,
        });
        return failure;
    }
});

ipcMain.on('backend-call-monitor:update-state', (_event, nextState) => {
    setBackendCallState(nextState);
});

ipcMain.on('backend-call-monitor:clear-logs', () => {
    backendCallLogsCache = [];
    sendToBackendMonitor('backend-call-monitor:logs', backendCallLogsCache);
});

ipcMain.on('backend-call-monitor:ready', (event) => {
    event.sender.send('backend-call-monitor:state', backendCallStateCache);
    event.sender.send('backend-call-monitor:logs', backendCallLogsCache);
});

ipcMain.handle('backend-call:run', async (_event, runOptions = {}) => {
    const analysisType = normalizeBackendAnalysisType(runOptions.analysisType || DEFAULT_BACKEND_ANALYSIS_TYPE);
    const requestState = normalizeBackendRequestState(backendCallStateCache, runOptions);
    const requestAsset = requestState.asset;
    const requestSelection = requestState.selection;
    const requestBioacoustics = requestState.bioacoustics;

    if (!requestAsset?.audioUrl) {
        const failure = withFormattedBackendFailure(buildBackendFailure('backend-asset-missing'));
        appendBackendEventLog('backend-call-failed', {
            failure,
        });
        sendToMainWindow('backend-call:completed', failure);
        return failure;
    }

    const readiness = evaluateBackendActionReadiness(analysisType, {
        selection: requestSelection,
        bioacoustics: requestBioacoustics,
    });
    if (!readiness.ready) {
        const failure = withFormattedBackendFailure({
            error: readiness.message || 'The backend action is not ready to run.',
        }, {
            errorCode: 'backend-analysis-failed',
        });
        appendBackendEventLog('backend-call-failed', {
            failure,
        });
        sendToMainWindow('backend-call:completed', failure);
        return failure;
    }

    let requestPayload;
    try {
        requestPayload = buildBackendAnalysisRequest(requestState, {
            analysisType,
            saveMode: runOptions.saveMode,
            saveLabel: runOptions.saveLabel,
        }, {
            requestId: typeof runOptions.requestId === 'string' && runOptions.requestId.trim() !== ''
                ? runOptions.requestId.trim()
                : randomUUID(),
            requestedAt: new Date().toISOString(),
        });
    } catch (error) {
        const failure = withFormattedBackendFailure(buildBackendFailure('backend-request-build-failed', {
            error: error?.message || undefined,
        }));
        appendBackendEventLog('backend-call-failed', {
            failure,
        }, {
            details: failure.details || null,
        });
        sendToMainWindow('backend-call:completed', failure);
        return failure;
    }

    appendBackendEventLog('backend-call-started', {
        analysisType: requestPayload.analysisType,
        assetLabel: requestPayload.asset.label || requestPayload.asset.id || 'current asset',
    }, {
        details: {
            requestId: requestPayload.callMeta.requestId,
            saveMode: requestPayload.saveOptions.mode,
        },
    });
    sendToBackendMonitor('backend-call-monitor:call-started', requestPayload);

    try {
        const response = await runBackendSelectionAnalysis(requestPayload);
        if (response?.ok === false) {
            const failure = withFormattedBackendFailure(response, {
                errorCode: response?.errorCode || 'backend-analysis-failed',
            });
            appendBackendEventLog('backend-call-failed', {
                failure,
            }, {
                details: failure.details || failure.stderr || failure.traceback || failure.stdout || null,
            });
            sendToBackendMonitor('backend-call-monitor:call-failed', failure);
            sendToMainWindow('backend-call:completed', failure);
            return failure;
        }

        const saveResult = enrichBackendSaveResult(response?.saveResult || {});
        const completedResponse = {
            ...response,
            saveResult,
        };
        appendBackendEventLog(saveResult.saved ? 'backend-call-completed-saved' : 'backend-call-completed-unsaved', {
            analysisType: requestPayload.analysisType,
            artifactLabel: saveResult.artifactLabel || 'output',
        }, {
            details: {
                requestId: requestPayload.callMeta.requestId,
                saved: saveResult.saved || false,
                saveMode: saveResult.modeLabel || saveResult.mode || null,
                artifact: saveResult.artifactLabel || null,
                savePath: saveResult.path || null,
            },
        });
        sendToBackendMonitor('backend-call-monitor:call-finished', completedResponse);
        sendToMainWindow('backend-call:completed', completedResponse);
        return completedResponse;
    } catch (error) {
        const failure = error?.payload
            ? withFormattedBackendFailure(error.payload, {
                errorCode: error?.payload?.errorCode || error?.errorCode || 'backend-analysis-failed',
            })
            : withFormattedBackendFailure(buildBackendFailure(error?.errorCode || 'backend-analysis-failed', {
                error: error?.message || undefined,
                stderr: error?.stderr || '',
            }));
        appendBackendEventLog('backend-call-failed', {
            failure,
        }, {
            details: failure.details || failure.stderr || failure.traceback || failure.stdout || null,
        });
        sendToBackendMonitor('backend-call-monitor:call-failed', failure);
        sendToMainWindow('backend-call:completed', failure);
        return failure;
    }
});

function createWindow() {
    mainWindow = new BrowserWindow(buildWindowOptions());

    if (isDevMode()) {
        // Load from Vite dev server during development
        loadWindowEntry(mainWindow);
        mainWindow.webContents.openDevTools();
    } else {
        // Load from built dist in production
        loadWindowEntry(mainWindow);
    }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

function configureMediaPermissions() {
    const defaultSession = session.defaultSession;
    if (!defaultSession) return;

    const isAllowedPermission = (permission, details = {}) => {
        if (permission === 'pointerLock') {
            return true;
        }

        if (permission !== 'media') {
            return false;
        }

        const mediaTypes = Array.isArray(details?.mediaTypes) ? details.mediaTypes : [];
        return mediaTypes.length === 0 || mediaTypes.includes('audio');
    };

    defaultSession.setPermissionCheckHandler((_webContents, permission, _requestingOrigin, details) => {
        return isAllowedPermission(permission, details);
    });

    defaultSession.setPermissionRequestHandler((_webContents, permission, callback, details) => {
        callback(isAllowedPermission(permission, details));
    });
}

app.on('ready', () => {
    configureMediaPermissions();
    createWindow();
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (mainWindow === null) {
        createWindow();
    }
});
