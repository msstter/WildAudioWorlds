const { randomUUID } = require('crypto');
const { spawn, spawnSync } = require('child_process');
const { app, BrowserWindow, dialog, ipcMain, session } = require('electron');
const fs = require('fs');
const path = require('path');

const PRELOAD_ENTRY = path.join(__dirname, 'preload.cjs');
const SHARED_GRAPH_PATHS_MODULE = path.resolve(__dirname, '..', '..', 'packages', 'wild_audio_worlds', 'graph', 'backend_paths.cjs');
const SHARED_SESSION_COMMAND_CONTRACTS_MODULE = path.resolve(__dirname, '..', '..', 'packages', 'wild_audio_worlds', 'session', 'command_contracts.cjs');
const graphBackendPaths = fs.existsSync(SHARED_GRAPH_PATHS_MODULE)
    ? require(SHARED_GRAPH_PATHS_MODULE)
    : {
        resolveGraphProjectRoot: (frontendDir) => path.resolve(frontendDir, '..'),
        resolveBackendRunnerPath: (frontendDir) => path.join(path.resolve(frontendDir, '..'), 'backend', 'run_selection_analysis.py'),
        resolveRecordedAudioImportRunnerPath: (frontendDir) => path.join(path.resolve(frontendDir, '..'), 'backend', 'import_recorded_audio.py'),
    };
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
    };
const {
    DEFAULT_BACKEND_ANALYSIS_TYPE,
    buildBackendAnalysisRequest,
    isBioacousticsAnalysisType,
    isBioacousticsImportAnalysisType,
    isBioacousticsSyncAnalysisType,
    normalizeBackendAnalysisType,
    normalizeBackendRequestState,
    normalizeBackendSaveMode,
} = sessionCommandContracts;

let mainWindow;
let backendMonitorWindow = null;
let backendCallStateCache = null;
let backendCallLogsCache = [];
let cachedBackendPythonCommand = null;

const BACKEND_CALL_LOG_LIMIT = 200;

// Use dedicated GPU more aggressively.
app.commandLine.appendSwitch('force_high_performance_gpu');

function getProjectRoot() {
    return graphBackendPaths.resolveGraphProjectRoot(__dirname);
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
    const entry = {
        id: randomUUID(),
        timestamp: new Date().toISOString(),
        level,
        scope,
        message,
        details,
    };

    backendCallLogsCache.push(entry);
    trimBackendCallLogs();
    sendToBackendMonitor('backend-call-monitor:log-appended', entry);
    return entry;
}

function setBackendCallState(nextState) {
    backendCallStateCache = nextState && typeof nextState === 'object' ? nextState : null;
    sendToBackendMonitor('backend-call-monitor:state', backendCallStateCache);
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

function runBackendSelectionAnalysis(requestPayload) {
    return new Promise((resolve, reject) => {
        const backendRunnerPath = resolveBackendRunnerPath();
        if (!fs.existsSync(backendRunnerPath)) {
            reject(new Error(`Backend runner not found: ${backendRunnerPath}`));
            return;
        }

        const pythonCommand = resolveBackendPythonCommand();
        const child = spawn(pythonCommand, [backendRunnerPath], {
            cwd: getProjectRoot(),
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
            const trimmed = text.trim();
            if (trimmed) {
                appendBackendLog({
                    level: 'warn',
                    scope: 'backend-stderr',
                    message: trimmed,
                });
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
                parseError.message = `Failed to parse backend JSON response: ${parseError.message}`;
                parseError.stdout = stdout;
                parseError.stderr = stderr;
                reject(parseError);
                return;
            }

            if (parsed?.ok === false) {
                const error = new Error(parsed.error || `Backend analysis failed with exit code ${code}.`);
                error.payload = parsed;
                error.stderr = stderr;
                reject(error);
                return;
            }

            if (code !== 0 && !parsed) {
                const error = new Error(`Backend analysis exited with code ${code}.`);
                error.stdout = stdout;
                error.stderr = stderr;
                reject(error);
                return;
            }

            resolve(parsed || {
                ok: false,
                error: 'Backend analysis returned no payload.',
                stderr,
            });
        });

        child.stdin.write(JSON.stringify(requestPayload));
        child.stdin.end();
    });
}

function runRecordedAudioImport(requestPayload) {
    return new Promise((resolve, reject) => {
        const backendRunnerPath = resolveRecordedAudioImportRunnerPath();
        if (!fs.existsSync(backendRunnerPath)) {
            reject(new Error(`Recorded audio import runner not found: ${backendRunnerPath}`));
            return;
        }

        const pythonCommand = resolveBackendPythonCommand();
        const child = spawn(pythonCommand, [backendRunnerPath], {
            cwd: getProjectRoot(),
            env: buildBackendPythonEnv(pythonCommand),
        });

        let stdout = '';
        let stderr = '';

        child.stdout.on('data', (chunk) => {
            stdout += chunk.toString();
        });

        child.stderr.on('data', (chunk) => {
            stderr += chunk.toString();
        });

        child.on('error', (error) => {
            reject(error);
        });

        child.on('close', (code) => {
            const outputLines = stdout.trim().split(/\r?\n/).filter(Boolean);
            let response = null;

            if (outputLines.length > 0) {
                try {
                    response = JSON.parse(outputLines[outputLines.length - 1]);
                } catch (_error) {
                    response = null;
                }
            }

            if (code === 0 && response?.ok !== false) {
                resolve(response || { ok: true });
                return;
            }

            const failure = response || {
                ok: false,
                error: `Recorded audio import failed with exit code ${code}.`,
                stderr,
                stdout,
            };
            const error = new Error(failure.error || 'Recorded audio import failed.');
            error.payload = failure;
            reject(error);
        });

        child.stdin.end(JSON.stringify(requestPayload));
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
        return {
            ok: false,
            error: 'Recorded audio import is missing WAV audio data.',
        };
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

    appendBackendLog({
        level: 'info',
        scope: 'recorded-audio',
        message: `Saved recorded microphone audio to ${savedAudioPath}.`,
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

        appendBackendLog({
            level: 'info',
            scope: 'recorded-audio',
            message: `Imported recorded audio as ${response?.asset?.label || finalStem}.`,
            details: {
                assetId: response?.asset?.id || null,
                savedAudioPath,
            },
        });
        return response;
    } catch (error) {
        const failure = error?.payload || {
            ok: false,
            error: error?.message || 'Recorded audio import failed.',
        };
        appendBackendLog({
            level: 'error',
            scope: 'recorded-audio',
            message: failure.error,
            details: failure.stderr || failure.traceback || null,
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
        const failure = {
            ok: false,
            error: 'No audio asset is loaded for backend analysis.',
        };
        appendBackendLog({ level: 'error', scope: 'bridge', message: failure.error });
        sendToMainWindow('backend-call:completed', failure);
        return failure;
    }

    if (!isBioacousticsAnalysisType(analysisType) && !requestSelection?.isReady) {
        const failure = {
            ok: false,
            error: 'No ready SpectroTerrain selection is available. Enable the terrain plane selections so they define a full 3D slice.',
        };
        appendBackendLog({ level: 'error', scope: 'bridge', message: failure.error });
        sendToMainWindow('backend-call:completed', failure);
        return failure;
    }

    if (isBioacousticsImportAnalysisType(analysisType)
        && !requestBioacoustics?.workbookPath
        && !requestBioacoustics?.autoDiscover) {
        const failure = {
            ok: false,
            error: 'Bioacoustics import requires a workbook path.',
        };
        appendBackendLog({ level: 'error', scope: 'bridge', message: failure.error });
        sendToMainWindow('backend-call:completed', failure);
        return failure;
    }

    if (isBioacousticsSyncAnalysisType(analysisType)) {
        const onsetTimes = Array.isArray(requestBioacoustics?.onsetTimes) ? requestBioacoustics.onsetTimes : [];
        const outputMode = typeof requestBioacoustics?.outputMode === 'string' && requestBioacoustics.outputMode.trim() !== ''
            ? requestBioacoustics.outputMode.trim().toLowerCase()
            : 'duplicate';
        if (onsetTimes.length === 0) {
            const failure = {
                ok: false,
                error: 'Bioacoustics workbook sync requires onset times from the active Timbre target.',
            };
            appendBackendLog({ level: 'error', scope: 'bridge', message: failure.error });
            sendToMainWindow('backend-call:completed', failure);
            return failure;
        }
        if ((outputMode === 'duplicate' || outputMode === 'overwrite') && !requestBioacoustics?.workbookPath) {
            const failure = {
                ok: false,
                error: 'Duplicate or overwrite workbook sync requires a source workbook path.',
            };
            appendBackendLog({ level: 'error', scope: 'bridge', message: failure.error });
            sendToMainWindow('backend-call:completed', failure);
            return failure;
        }
    }

    const requestPayload = buildBackendAnalysisRequest(requestState, {
        analysisType,
        saveMode: runOptions.saveMode,
        saveLabel: runOptions.saveLabel,
    }, {
        requestId: typeof runOptions.requestId === 'string' && runOptions.requestId.trim() !== ''
            ? runOptions.requestId.trim()
            : randomUUID(),
        requestedAt: new Date().toISOString(),
    });

    appendBackendLog({
        level: 'info',
        scope: 'bridge',
        message: `Running ${requestPayload.analysisType} for ${requestPayload.asset.label || requestPayload.asset.id || 'current asset'}.`,
        details: {
            requestId: requestPayload.callMeta.requestId,
            saveMode: requestPayload.saveOptions.mode,
        },
    });
    sendToBackendMonitor('backend-call-monitor:call-started', requestPayload);

    try {
        const response = await runBackendSelectionAnalysis(requestPayload);
        appendBackendLog({
            level: 'info',
            scope: 'bridge',
            message: `Completed ${requestPayload.analysisType}.`,
            details: {
                requestId: requestPayload.callMeta.requestId,
                saved: response?.saveResult?.saved || false,
                savePath: response?.saveResult?.path || null,
            },
        });
        sendToBackendMonitor('backend-call-monitor:call-finished', response);
        sendToMainWindow('backend-call:completed', response);
        return response;
    } catch (error) {
        const failure = error?.payload || {
            ok: false,
            error: error?.message || 'Backend analysis failed.',
            stderr: error?.stderr || '',
        };
        appendBackendLog({
            level: 'error',
            scope: 'bridge',
            message: failure.error,
            details: failure.stderr || failure.traceback || null,
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
