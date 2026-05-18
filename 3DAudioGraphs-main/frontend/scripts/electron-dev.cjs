const { spawn } = require('child_process');

const rendererUrl = 'http://127.0.0.1:5173';
const rendererStartupTimeoutMs = 30000;
const rendererPollIntervalMs = 250;

const npmCommand = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const electronCommand = process.platform === 'win32' ? 'electron.cmd' : 'electron';

let viteProcess = null;
let electronProcess = null;
let startedLocalVite = false;
let shuttingDown = false;

function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
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

function spawnProcess(command, args, options = {}) {
    return spawn(command, args, {
        stdio: 'inherit',
        shell: false,
        ...options,
    });
}

function terminateChild(childProcess) {
    if (!childProcess || childProcess.killed) return;
    childProcess.kill('SIGTERM');
}

function exitFromChild(code, signal) {
    if (typeof code === 'number') {
        process.exit(code);
    }

    if (signal) {
        process.kill(process.pid, signal);
        return;
    }

    process.exit(1);
}

function shutdown() {
    if (shuttingDown) return;
    shuttingDown = true;
    terminateChild(electronProcess);
    if (startedLocalVite) {
        terminateChild(viteProcess);
    }
}

process.on('SIGINT', () => {
    shutdown();
    process.exit(130);
});

process.on('SIGTERM', () => {
    shutdown();
    process.exit(143);
});

async function ensureRendererServer() {
    if (await isRendererReady()) {
        console.log(`Reusing existing Vite dev server at ${rendererUrl}.`);
        return;
    }

    startedLocalVite = true;
    viteProcess = spawnProcess(npmCommand, ['run', 'dev']);

    const viteExitedEarly = new Promise((resolve, reject) => {
        viteProcess.once('exit', (code, signal) => {
            reject(new Error(`Vite exited before it became ready (${signal || code || 'unknown'}).`));
        });
        viteProcess.once('error', reject);
    });

    await Promise.race([waitForRenderer(), viteExitedEarly]);
}

async function main() {
    try {
        await ensureRendererServer();
    } catch (error) {
        shutdown();
        console.error(error?.message || 'Failed to start the Vite dev server.');
        process.exit(1);
        return;
    }

    electronProcess = spawnProcess(electronCommand, ['.'], {
        env: {
            ...process.env,
            ELECTRON_RENDERER_URL: rendererUrl,
        },
    });

    electronProcess.once('error', (error) => {
        shutdown();
        console.error(error?.message || 'Failed to launch Electron.');
        process.exit(1);
    });

    electronProcess.once('exit', (code, signal) => {
        shutdown();
        exitFromChild(code, signal);
    });
}

main();