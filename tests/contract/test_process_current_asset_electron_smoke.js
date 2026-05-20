const assert = require('assert');
const path = require('path');
const { spawn } = require('child_process');

const frontendRoot = path.resolve(__dirname, '..', '..', '3DAudioGraphs-main', 'frontend');
const rendererUrl = 'http://127.0.0.1:5173';
const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const electronExecutablePath = require(path.resolve(frontendRoot, 'node_modules', 'electron'));
const { _electron: electron } = require(path.resolve(frontendRoot, 'node_modules', 'playwright-core'));

const rendererStartupTimeoutMs = 30000;
const rendererPollIntervalMs = 250;
const smokeStepTimeoutMs = 180000;
const smokeStorageKey = '3d-audio-maker.process-current-asset.include-mfcc';

let viteProcess = null;
let startedLocalVite = false;
let viteLogBuffer = [];

function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function captureProcessOutput(childProcess) {
    const appendChunk = (chunk) => {
        const text = String(chunk || '');
        if (!text) return;
        viteLogBuffer = [...viteLogBuffer, text].slice(-40);
    };

    childProcess.stdout?.on('data', appendChunk);
    childProcess.stderr?.on('data', appendChunk);
}

async function isRendererReady() {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 1000);

    try {
        const response = await fetch(rendererUrl, { signal: controller.signal });
        return response.ok || (response.status >= 300 && response.status < 500);
    } catch (_error) {
        return false;
    } finally {
        clearTimeout(timeoutId);
    }
}

async function waitForRenderer() {
    const startedAt = Date.now();
    while ((Date.now() - startedAt) < rendererStartupTimeoutMs) {
        if (await isRendererReady()) {
            return true;
        }
        await delay(rendererPollIntervalMs);
    }

    throw new Error(`Timed out waiting for the Vite dev server at ${rendererUrl}.`);
}

async function ensureRendererServer() {
    if (await isRendererReady()) {
        console.log('Renderer ready: reusing existing Vite server.');
        return;
    }

    startedLocalVite = true;
    console.log('Renderer ready: starting local Vite server.');
    viteProcess = spawn(npmCommand, ['run', 'dev'], {
        cwd: frontendRoot,
        stdio: ['ignore', 'pipe', 'pipe'],
        shell: false,
    });
    captureProcessOutput(viteProcess);

    const viteExitedEarly = new Promise((_, reject) => {
        viteProcess.once('exit', (code, signal) => {
            reject(new Error(`Vite exited before it became ready (${signal || code || 'unknown'}).`));
        });
        viteProcess.once('error', reject);
    });

    await Promise.race([waitForRenderer(), viteExitedEarly]);
}

function terminateChild(childProcess) {
    if (!childProcess || childProcess.killed) return;
    childProcess.kill('SIGTERM');
}

async function readRendererSmokeState(page) {
    return page.evaluate(() => ({
        assetReady: document.body?.dataset?.wawSelectedAssetReady === 'true',
        assetId: document.body?.dataset?.wawSelectedAssetId || '',
        revisionId: document.body?.dataset?.wawSelectedRevisionId || '',
        hasMfcc: document.body?.dataset?.wawSelectedAssetHasMfcc === 'true',
        includeMfcc: document.body?.dataset?.wawProcessCurrentAssetIncludeMfcc === 'true',
        storedIncludeMfcc: globalThis.localStorage?.getItem('3d-audio-maker.process-current-asset.include-mfcc') || null,
    }));
}

async function resolveModeAudioPage(electronApp, initialPage = null) {
    const startedAt = Date.now();
    let seenUrls = [];

    while ((Date.now() - startedAt) < smokeStepTimeoutMs) {
        const candidatePages = [
            ...(initialPage ? [initialPage] : []),
            ...electronApp.windows(),
        ].filter((page, index, pages) => pages.indexOf(page) === index);

        for (const candidatePage of candidatePages) {
            if (!candidatePage || candidatePage.isClosed()) continue;

            try {
                const candidateUrl = candidatePage.url() || 'about:blank';
                seenUrls = [...new Set([...seenUrls, candidateUrl])].slice(-10);
                const hasModeAudioFolder = await candidatePage.locator('[data-waw-folder="mode-audio"]').count();
                if (hasModeAudioFolder > 0) {
                    return candidatePage;
                }
            } catch (_error) {
                // Ignore transient window churn while Electron finishes startup.
            }
        }

        await delay(250);
    }

    throw new Error(`Timed out waiting for the Mode Audio page. Seen URLs: ${seenUrls.join(', ') || 'none'}.`);
}

async function ensureModeAudioFolderExpanded(page) {
    await page.waitForSelector('[data-waw-folder="mode-audio"]', {
        state: 'attached',
        timeout: smokeStepTimeoutMs,
    });
    console.log('Renderer ready: Mode Audio folder marker attached.');
    const modeAudioFolderSelector = '[data-waw-folder="mode-audio"]';
    const folderIsClosed = await page.locator(modeAudioFolderSelector).evaluate((folderElement) => (
        folderElement.classList.contains('lil-closed')
    ));
    if (folderIsClosed) {
        await page.click(`${modeAudioFolderSelector} > .lil-title`);
    }
    await page.waitForFunction(
        (selector) => !document.querySelector(selector)?.classList.contains('lil-closed'),
        modeAudioFolderSelector,
        { timeout: smokeStepTimeoutMs },
    );
    console.log('Renderer ready: Mode Audio folder expanded.');
    await page.waitForSelector('[data-waw-control="process-current-asset"] button', {
        state: 'visible',
        timeout: smokeStepTimeoutMs,
    });
    console.log('Renderer ready: Process Current Asset button visible.');
}

async function setMfccToggleState(page, expectedValue) {
    const toggleSelector = '[data-waw-control="process-current-asset-include-mfcc"] input';
    await page.waitForSelector(toggleSelector, { state: 'visible', timeout: smokeStepTimeoutMs });
    const currentValue = await page.isChecked(toggleSelector);
    if (currentValue !== expectedValue) {
        await page.click(toggleSelector);
    }

    await page.waitForFunction(
        (nextValue) => document.body?.dataset?.wawProcessCurrentAssetIncludeMfcc === String(nextValue),
        expectedValue,
        { timeout: 5000 },
    );

    const state = await readRendererSmokeState(page);
    assert.strictEqual(state.includeMfcc, expectedValue);
    assert.strictEqual(state.storedIncludeMfcc, expectedValue ? 'true' : 'false');
}

async function processCurrentAssetAndWaitForRevision(page, previousRevisionId, expectedHasMfcc) {
    await page.click('[data-waw-control="process-current-asset"] button');

    await page.waitForFunction(
        ({ previousRevisionId: priorRevision, expectedHasMfcc: nextHasMfcc }) => {
            const bodyDataset = document.body?.dataset;
            return bodyDataset?.wawSelectedAssetReady === 'true'
                && !!bodyDataset?.wawSelectedRevisionId
                && bodyDataset.wawSelectedRevisionId !== priorRevision
                && bodyDataset.wawSelectedAssetHasMfcc === String(nextHasMfcc);
        },
        {
            previousRevisionId,
            expectedHasMfcc,
        },
        {
            timeout: smokeStepTimeoutMs,
        },
    );

    const nextState = await readRendererSmokeState(page);
    assert.ok(nextState.assetReady);
    assert.ok(nextState.assetId);
    assert.notStrictEqual(nextState.revisionId, previousRevisionId);
    assert.strictEqual(nextState.hasMfcc, expectedHasMfcc);
    return nextState.revisionId;
}

async function main() {
    let electronApp = null;

    try {
        await ensureRendererServer();
        console.log('Renderer ready: launching Electron app.');

        electronApp = await electron.launch({
            executablePath: electronExecutablePath,
            args: [frontendRoot],
            env: {
                ...process.env,
                ELECTRON_RENDERER_URL: rendererUrl,
                ELECTRON_ENABLE_LOGGING: '1',
                ELECTRON_ENABLE_STACK_DUMPING: '1',
                WAW_ELECTRON_SMOKE_TEST: '1',
            },
            timeout: smokeStepTimeoutMs,
        });
        console.log('Renderer ready: Electron app launched.');

        const electronProcess = electronApp.process?.();
        electronProcess?.stdout?.on('data', (chunk) => {
            const text = String(chunk || '').trim();
            if (text) console.log(`[electron stdout] ${text}`);
        });
        electronProcess?.stderr?.on('data', (chunk) => {
            const text = String(chunk || '').trim();
            if (text) console.error(`[electron stderr] ${text}`);
        });
        electronProcess?.once('exit', (code, signal) => {
            console.log(`Electron process exited: ${signal || code || 'unknown'}.`);
        });

        const initialPage = await electronApp.firstWindow();
        console.log('Renderer ready: acquired first Electron window.');
        const page = await resolveModeAudioPage(electronApp, initialPage);
        console.log('Renderer ready: resolved live Mode Audio page.');
        page.on('console', (message) => {
            if (message.type() === 'error') {
                console.error(`[renderer console] ${message.text()}`);
            }
        });
        page.on('pageerror', (error) => {
            console.error(`[renderer pageerror] ${error && error.stack ? error.stack : error}`);
        });
        page.on('crash', () => {
            console.error('Renderer page crashed.');
        });
        page.on('close', () => {
            console.error('Renderer page closed.');
        });
        console.log(`Renderer ready: window URL is ${page.url() || 'about:blank'}.`);
        await ensureModeAudioFolderExpanded(page);
        console.log('Renderer ready: Mode Audio controls became visible.');
        await page.waitForFunction(
            () => document.body?.dataset?.wawSelectedAssetReady === 'true',
            null,
            { timeout: smokeStepTimeoutMs },
        );
        console.log('Renderer ready: initial asset loaded.');

        const initialState = await readRendererSmokeState(page);
        assert.ok(initialState.assetReady);
        assert.ok(initialState.revisionId);

        await setMfccToggleState(page, false);
        const revisionWithoutMfcc = await processCurrentAssetAndWaitForRevision(
            page,
            initialState.revisionId,
            false,
        );
        console.log('Renderer ready: processed current asset without MFCC.');

        await setMfccToggleState(page, true);
        await processCurrentAssetAndWaitForRevision(
            page,
            revisionWithoutMfcc,
            true,
        );
        console.log('Renderer ready: processed current asset with MFCC.');
        console.log('Electron smoke passed.');
    } catch (error) {
        if (viteLogBuffer.length > 0) {
            console.error('Captured Vite output:\n', viteLogBuffer.join(''));
        }
        throw error;
    } finally {
        if (electronApp) {
            await electronApp.close().catch(() => {});
        }
        if (startedLocalVite) {
            terminateChild(viteProcess);
        }
    }
}

main().catch((error) => {
    console.error(error);
    process.exit(1);
});