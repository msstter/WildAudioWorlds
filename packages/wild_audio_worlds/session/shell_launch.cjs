const path = require('path');

const SHELL_LAUNCH_ARG_MAP = Object.freeze(require(path.resolve(__dirname, 'shell_launch_args.json')));

function textOrEmpty(value) {
    return String(value || '').trim();
}

function buildShellLaunchCliArgs(launchRequest = {}) {
    const request = launchRequest && typeof launchRequest === 'object' && !Array.isArray(launchRequest)
        ? launchRequest
        : {};
    const cliArgs = [];
    for (const [fieldName, flag] of Object.entries(SHELL_LAUNCH_ARG_MAP)) {
        const value = textOrEmpty(request[fieldName]);
        if (value) {
            cliArgs.push(flag, value);
        }
    }
    return cliArgs;
}

function parseShellLaunchCliArgs(argv = []) {
    const rawArgv = Array.isArray(argv) ? [...argv] : [];
    const parsed = {};
    const remainingArgv = [];

    for (let index = 0; index < rawArgv.length; index += 1) {
        const token = textOrEmpty(rawArgv[index]);
        let matchedField = '';
        let matchedValue = '';
        let consumedExtra = false;

        for (const [fieldName, flag] of Object.entries(SHELL_LAUNCH_ARG_MAP)) {
            if (token === flag) {
                matchedField = fieldName;
                matchedValue = textOrEmpty(rawArgv[index + 1]);
                consumedExtra = index + 1 < rawArgv.length;
                break;
            }

            const prefixedFlag = `${flag}=`;
            if (token.startsWith(prefixedFlag)) {
                matchedField = fieldName;
                matchedValue = textOrEmpty(token.slice(prefixedFlag.length));
                break;
            }
        }

        if (matchedField) {
            if (matchedValue) {
                parsed[matchedField] = matchedValue;
            }
            if (consumedExtra) {
                index += 1;
            }
            continue;
        }

        remainingArgv.push(rawArgv[index]);
    }

    return {
        launchRequest: parsed.sessionId ? parsed : null,
        remainingArgv,
    };
}

module.exports = {
    SHELL_LAUNCH_ARG_MAP,
    buildShellLaunchCliArgs,
    parseShellLaunchCliArgs,
};