const assert = require('assert');
const path = require('path');

const contracts = require(path.resolve(__dirname, '..', '..', 'packages', 'wild_audio_worlds', 'session', 'selection_contracts.cjs'));

const readySelection = contracts.normalizeReadySelectionForRequest(
    {
        analysisClipDurationSec: 3.0,
        analysisFftNfft: 32,
    },
    {
        isReady: true,
        timeRangeSec: {
            start: -1,
            end: 4,
        },
        frequencyBinRange: {
            startBin: -5,
            endBin: 99,
            totalBins: 64,
        },
        amplitudePctRange: {
            min: -10,
            max: 120,
        },
    },
);

assert.deepStrictEqual(readySelection.timeRangeSec, {
    start: 0,
    end: 3,
    duration: 3,
});
assert.deepStrictEqual(readySelection.frequencyBinRange, {
    startBin: 0,
    endBin: 31,
    totalBins: 32,
});
assert.deepStrictEqual(readySelection.amplitudePctRange, {
    min: 0,
    max: 100,
});