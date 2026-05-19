const assert = require('assert');
const path = require('path');

const analysisTypes = require(path.resolve(__dirname, '..', '..', 'packages', 'wild_audio_worlds', 'session', 'analysis_types.cjs'));
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