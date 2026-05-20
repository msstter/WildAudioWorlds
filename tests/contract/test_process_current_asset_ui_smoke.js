const assert = require('assert');
const path = require('path');
const { pathToFileURL } = require('url');

function createMemoryStorage(initialEntries = {}) {
    const entries = new Map(Object.entries(initialEntries));
    return {
        getItem(key) {
            return entries.has(key) ? entries.get(key) : null;
        },
        setItem(key, value) {
            entries.set(key, String(value));
        },
        removeItem(key) {
            entries.delete(key);
        },
    };
}

async function main() {
    const modulePath = path.resolve(
        __dirname,
        '..',
        '..',
        '3DAudioGraphs-main',
        'frontend',
        'src',
        'app',
        'processCurrentAssetControl.js',
    );
    const processCurrentAssetControl = await import(pathToFileURL(modulePath).href);
    const {
        PROCESS_CURRENT_ASSET_INCLUDE_MFCC_STORAGE_KEY,
        buildProcessCurrentAssetRequest,
        readStoredProcessCurrentAssetIncludeMfcc,
        writeStoredProcessCurrentAssetIncludeMfcc,
    } = processCurrentAssetControl;

    const storage = createMemoryStorage();
    assert.strictEqual(readStoredProcessCurrentAssetIncludeMfcc({ storageObject: storage }), true);

    assert.strictEqual(writeStoredProcessCurrentAssetIncludeMfcc(false, { storageObject: storage }), true);
    assert.strictEqual(storage.getItem(PROCESS_CURRENT_ASSET_INCLUDE_MFCC_STORAGE_KEY), 'false');
    assert.strictEqual(readStoredProcessCurrentAssetIncludeMfcc({ storageObject: storage }), false);

    const firstAssetSnapshot = {
        id: 'asset-1',
        label: 'First Asset',
        revisionId: 'asset-1-rev-1',
        audioUrl: './audio_assets/first-asset.wav',
    };
    assert.deepStrictEqual(buildProcessCurrentAssetRequest({
        assetSnapshot: firstAssetSnapshot,
        includeMfcc: readStoredProcessCurrentAssetIncludeMfcc({ storageObject: storage }),
    }), {
        assetLabel: 'First Asset',
        includeMfcc: false,
        requestAsset: firstAssetSnapshot,
    });

    const secondAssetSnapshot = {
        id: 'asset-2',
        label: 'Second Asset',
        revisionId: 'asset-2-rev-4',
        audioUrl: './audio_assets/second-asset.wav',
    };
    assert.deepStrictEqual(buildProcessCurrentAssetRequest({
        assetSnapshot: secondAssetSnapshot,
        includeMfcc: readStoredProcessCurrentAssetIncludeMfcc({ storageObject: storage }),
    }), {
        assetLabel: 'Second Asset',
        includeMfcc: false,
        requestAsset: secondAssetSnapshot,
    });

    assert.strictEqual(writeStoredProcessCurrentAssetIncludeMfcc(true, { storageObject: storage }), true);
    assert.strictEqual(storage.getItem(PROCESS_CURRENT_ASSET_INCLUDE_MFCC_STORAGE_KEY), 'true');
    assert.deepStrictEqual(buildProcessCurrentAssetRequest({
        assetSnapshot: secondAssetSnapshot,
        includeMfcc: readStoredProcessCurrentAssetIncludeMfcc({ storageObject: storage }),
    }), {
        assetLabel: 'Second Asset',
        includeMfcc: true,
        requestAsset: secondAssetSnapshot,
    });

    const invalidStorage = createMemoryStorage({
        [PROCESS_CURRENT_ASSET_INCLUDE_MFCC_STORAGE_KEY]: 'unexpected-value',
    });
    assert.strictEqual(
        readStoredProcessCurrentAssetIncludeMfcc({ storageObject: invalidStorage, fallbackValue: false }),
        false,
    );
    assert.strictEqual(buildProcessCurrentAssetRequest({ assetSnapshot: null, includeMfcc: true }), null);
}

main().catch((error) => {
    console.error(error);
    process.exit(1);
});