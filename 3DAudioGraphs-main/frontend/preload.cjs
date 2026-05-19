const { contextBridge, ipcRenderer } = require('electron');

const invokeChannels = new Set([
    'backend-call:evaluate-readiness',
    'backend-call:get-action-metadata',
    'backend-call:show-open-dialog',
    'recorded-audio:import',
    'backend-call:run',
    'backend-call-monitor:open',
    'local-integration:get-state',
    'shell:open-companion',
]);

const sendChannels = new Set([
    'backend-call-monitor:update-state',
    'backend-call-monitor:clear-logs',
    'backend-call-monitor:ready',
]);

const onChannels = new Set([
    'backend-call:completed',
    'backend-call-monitor:state',
    'backend-call-monitor:logs',
    'backend-call-monitor:log-appended',
    'backend-call-monitor:call-started',
    'backend-call-monitor:call-finished',
    'backend-call-monitor:call-failed',
    'local-integration:event',
]);

function absolutePathToFileUrl(filePath = '') {
    const normalizedPath = String(filePath || '').trim().replace(/\\/g, '/');
    if (!normalizedPath) return null;

    const isUncPath = normalizedPath.startsWith('//');
    const encodedSegments = normalizedPath.split('/').map((segment, index) => {
        if (segment === '' && index === 0) return '';
        if (/^[A-Za-z]:$/.test(segment)) return segment;
        return encodeURIComponent(segment);
    });
    const encodedPath = encodedSegments.join('/');

    if (isUncPath) {
        return `file:${encodedPath}`;
    }

    if (encodedPath.startsWith('/')) {
        return `file://${encodedPath}`;
    }

    return `file:///${encodedPath}`;
}

const desktopBridge = {
    backend: {
        invoke(channel, ...args) {
            if (!invokeChannels.has(channel)) {
                throw new Error(`Blocked IPC invoke channel: ${channel}`);
            }
            return ipcRenderer.invoke(channel, ...args);
        },
        send(channel, ...args) {
            if (!sendChannels.has(channel)) {
                throw new Error(`Blocked IPC send channel: ${channel}`);
            }
            ipcRenderer.send(channel, ...args);
        },
        on(channel, listener) {
            if (!onChannels.has(channel) || typeof listener !== 'function') {
                return () => {};
            }

            const wrappedListener = (_event, ...args) => {
                listener(undefined, ...args);
            };

            ipcRenderer.on(channel, wrappedListener);
            return () => {
                ipcRenderer.removeListener(channel, wrappedListener);
            };
        },
    },
    buildAssetManifestUrl(folderPath = '') {
        const normalizedPath = String(folderPath || '').trim().replace(/[\\/]+$/, '');
        if (!normalizedPath) return null;
        const separator = normalizedPath.includes('\\') ? '\\' : '/';
        return absolutePathToFileUrl(`${normalizedPath}${separator}audio_assets_manifest.json`);
    },
};

contextBridge.exposeInMainWorld('desktopBridge', desktopBridge);