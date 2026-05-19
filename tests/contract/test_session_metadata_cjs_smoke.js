const assert = require('assert');
const path = require('path');

const analysisTypes = require(path.resolve(__dirname, '..', '..', 'packages', 'wild_audio_worlds', 'session', 'analysis_types.cjs'));
const commandContracts = require(path.resolve(__dirname, '..', '..', 'packages', 'wild_audio_worlds', 'session', 'command_contracts.cjs'));
const errorMetadata = require(path.resolve(__dirname, '..', '..', 'packages', 'wild_audio_worlds', 'session', 'error_metadata.cjs'));
const resultMetadata = require(path.resolve(__dirname, '..', '..', 'packages', 'wild_audio_worlds', 'session', 'result_metadata.cjs'));

const readiness = analysisTypes.evaluateBackendActionReadiness('bioacoustics-sync-workbook', {
    bioacoustics: {
        canSync: true,
        onsetTimes: [0.1],
        outputMode: 'duplicate',
        workbookPath: '',
    },
});

assert.strictEqual(readiness.ready, false);
assert.strictEqual(readiness.message, 'Duplicate or overwrite workbook sync requires a source workbook path.');

const enrichedSaveResult = resultMetadata.enrichBackendSaveResult({
    mode: 'json',
    saved: true,
});

assert.deepStrictEqual(enrichedSaveResult, {
    mode: 'json',
    saved: true,
    modeLabel: 'Save JSON to data/exports/backend_calls',
    artifactType: 'json-report',
    artifactLabel: 'JSON Report',
});

const enrichedFailure = errorMetadata.buildBackendFailure('backend-call-invoke-failed', {
    stderr: 'demo stderr',
});

assert.deepStrictEqual(enrichedFailure, {
    ok: false,
    errorCode: 'backend-call-invoke-failed',
    error: 'Backend call failed.',
    stderr: 'demo stderr',
});

const formattedFailure = commandContracts.formatBackendFailureForMonitor({
    errorCode: 'backend-response-parse-failed',
    error: 'Failed to parse backend JSON response. Unexpected token < in JSON at position 0.',
    stderr: 'backend stderr',
    traceback: 'Traceback line 1\nTraceback line 2',
});

assert.deepStrictEqual(formattedFailure, {
    kind: 'backend-failure',
    summary: 'Failed to parse backend JSON response.',
    sections: [
        {
            key: 'errorCode',
            label: 'Error Code',
            value: 'backend-response-parse-failed',
        },
        {
            key: 'error',
            label: 'Error',
            value: 'Failed to parse backend JSON response. Unexpected token < in JSON at position 0.',
        },
        {
            key: 'stderr',
            label: 'Standard Error',
            value: 'backend stderr',
        },
        {
            key: 'traceback',
            label: 'Traceback',
            value: 'Traceback line 1\nTraceback line 2',
        },
    ],
});

const enrichedLogEntry = commandContracts.enrichBackendLogEntry({
    level: 'error',
    scope: 'bridge',
    message: 'Completed slice-summary. No file was saved.',
    details: {
        requestId: 'req-123',
        saveMode: 'Do Not Save a File',
        saved: false,
    },
});

assert.deepStrictEqual(enrichedLogEntry.formattedLog, {
    kind: 'backend-log',
    scopeLabel: 'Electron Bridge',
    levelLabel: 'Error',
    detailSections: [
        {
            key: 'requestId',
            label: 'Request ID',
            value: 'req-123',
        },
        {
            key: 'saveMode',
            label: 'Save Mode',
            value: 'Do Not Save a File',
        },
        {
            key: 'saved',
            label: 'Saved',
            value: 'false',
        },
    ],
});

const startedLogEvent = commandContracts.buildBackendLogEventEntry('backend-call-started', {
    analysisType: 'slice-summary',
    assetLabel: 'Demo Asset',
}, {
    details: {
        requestId: 'req-123',
        saveMode: 'json',
    },
});

assert.deepStrictEqual(startedLogEvent, {
    eventCode: 'backend-call-started',
    scope: 'bridge',
    level: 'info',
    message: 'Running slice-summary for Demo Asset.',
    details: {
        requestId: 'req-123',
        saveMode: 'json',
    },
});

const failedLogEvent = commandContracts.buildBackendLogEventEntry('backend-call-failed', {
    failure: {
        error: 'Backend analysis returned no payload.',
    },
});

assert.deepStrictEqual(failedLogEvent, {
    eventCode: 'backend-call-failed',
    scope: 'bridge',
    level: 'error',
    message: 'Backend analysis returned no payload.',
    details: null,
});

const savedRecordedAudioLogEvent = commandContracts.buildBackendLogEventEntry('recorded-audio-saved', {
    savedAudioPath: '/tmp/demo.wav',
}, {
    details: {
        includeMfcc: true,
    },
});

assert.deepStrictEqual(savedRecordedAudioLogEvent, {
    eventCode: 'recorded-audio-saved',
    scope: 'recorded-audio',
    level: 'info',
    message: 'Saved recorded microphone audio to /tmp/demo.wav.',
    details: {
        includeMfcc: true,
    },
});

const failedRecordedAudioLogEvent = commandContracts.buildBackendLogEventEntry('recorded-audio-failed', {
    failure: {
        error: 'Recorded audio import failed with exit code 1.',
    },
});

assert.deepStrictEqual(failedRecordedAudioLogEvent, {
    eventCode: 'recorded-audio-failed',
    scope: 'recorded-audio',
    level: 'error',
    message: 'Recorded audio import failed with exit code 1.',
    details: null,
});

const missingRecordedAudioFailure = commandContracts.buildRecordedAudioFailure('recorded-audio-missing-buffer');

assert.deepStrictEqual(missingRecordedAudioFailure, {
    ok: false,
    errorCode: 'recorded-audio-missing-buffer',
    error: 'Recorded audio import is missing WAV audio data.',
});

const runnerMissingRecordedAudioFailure = commandContracts.buildRecordedAudioFailure('recorded-audio-runner-missing', {
    details: {
        backendRunnerPath: '/tmp/import_recorded_audio.py',
    },
});

assert.deepStrictEqual(runnerMissingRecordedAudioFailure, {
    ok: false,
    errorCode: 'recorded-audio-runner-missing',
    error: 'Recorded audio import runner is unavailable.',
    details: {
        backendRunnerPath: '/tmp/import_recorded_audio.py',
    },
});