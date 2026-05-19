const assert = require('assert');
const path = require('path');

const shellLaunch = require(path.resolve(__dirname, '..', '..', 'packages', 'wild_audio_worlds', 'session', 'shell_launch.cjs'));

const launchRequest = {
    sessionId: 'waw-session-demo',
    manifestPath: '/tmp/demo/session_manifest.json',
    serviceEndpoint: '/tmp/demo/bootstrap_service.py',
    originatingShell: 'audio-graphs',
    launchReason: 'open-companion',
};

const cliArgs = shellLaunch.buildShellLaunchCliArgs(launchRequest);

assert.deepStrictEqual(cliArgs, [
    '--waw-session-id', 'waw-session-demo',
    '--waw-manifest-path', '/tmp/demo/session_manifest.json',
    '--waw-service-endpoint', '/tmp/demo/bootstrap_service.py',
    '--waw-origin-shell', 'audio-graphs',
    '--waw-launch-reason', 'open-companion',
]);

const parsed = shellLaunch.parseShellLaunchCliArgs([
    'electron',
    'main.cjs',
    ...cliArgs,
    '--inspect',
]);

assert.deepStrictEqual(parsed, {
    launchRequest,
    remainingArgv: [
        'electron',
        'main.cjs',
        '--inspect',
    ],
});