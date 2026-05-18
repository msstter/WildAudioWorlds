const path = require('path');

function resolveGraphProjectRoot(frontendDir) {
    return path.resolve(frontendDir, '..');
}

function resolveBackendRunnerPath(frontendDir) {
    return path.join(resolveGraphProjectRoot(frontendDir), 'backend', 'run_selection_analysis.py');
}

function resolveRecordedAudioImportRunnerPath(frontendDir) {
    return path.join(resolveGraphProjectRoot(frontendDir), 'backend', 'import_recorded_audio.py');
}

module.exports = {
    resolveGraphProjectRoot,
    resolveBackendRunnerPath,
    resolveRecordedAudioImportRunnerPath,
};