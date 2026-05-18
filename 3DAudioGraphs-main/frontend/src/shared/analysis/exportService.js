import { encodeAudioDataAsWavBlob } from './exportPayloads.js';
import { formatCsvCell, sanitizeFileLabel, triggerFileSave } from '../ui/fileSave.js';

export const buildSelectionExportFileStem = (label, {
    assetLabel = '',
    assetId = '',
    fallback = 'selection',
    sanitizeLabel = sanitizeFileLabel,
} = {}) => {
    const assetStem = sanitizeLabel(assetLabel || assetId || 'asset', 'asset');
    const targetStem = sanitizeLabel(label, fallback);
    return `${assetStem}_${targetStem}`;
};

const createCsvBlob = (csvMatrix, formatCell = formatCsvCell) => {
    if (!csvMatrix) return null;
    const rows = (csvMatrix.rows || []).map((row) => row.map(formatCell).join(','));
    return new Blob([[csvMatrix.header.join(','), ...rows].join('\n') + '\n'], { type: 'text/csv;charset=utf-8' });
};

export const createSelectionExportService = ({
    buildExportFileStem = (label, fallback = 'selection') => buildSelectionExportFileStem(label, { fallback }),
    buildAnalysisPayload,
    buildAnalysisCsvMatrix,
    buildAnalysisIoiCsvMatrix,
    buildAudioDataForAnalysis,
    getCurrentAnalysis,
    getGroupRecord,
    getGroupAnalysis,
    formatCell = formatCsvCell,
    saveFile = triggerFileSave,
    encodeAudioData = encodeAudioDataAsWavBlob,
} = {}) => {
    const exportAnalysisAsJson = async (analysis, { label = 'Selection', suggestedStem = buildExportFileStem(label) } = {}) => {
        const payload = typeof buildAnalysisPayload === 'function'
            ? buildAnalysisPayload(analysis, { label })
            : null;
        if (!payload) return;

        const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: 'application/json' });
        await saveFile(blob, 'json', {
            suggestedName: `${suggestedStem}.json`,
            description: 'Selection Export',
        });
    };

    const exportAnalysisAsCsv = async (analysis, { label = 'Selection', suggestedStem = buildExportFileStem(label) } = {}) => {
        const csvMatrix = typeof buildAnalysisCsvMatrix === 'function'
            ? buildAnalysisCsvMatrix(analysis, { label })
            : null;
        const blob = createCsvBlob(csvMatrix, formatCell);
        if (!blob) return;

        await saveFile(blob, 'csv', {
            suggestedName: `${suggestedStem}.csv`,
            description: 'Selection CSV',
        });
    };

    const exportAnalysisAsIoiCsv = async (analysis, { label = 'Selection', suggestedStem = buildExportFileStem(`${label}-ioi`, 'ioi') } = {}) => {
        const csvMatrix = typeof buildAnalysisIoiCsvMatrix === 'function'
            ? buildAnalysisIoiCsvMatrix(analysis, { label })
            : null;
        const blob = createCsvBlob(csvMatrix, formatCell);
        if (!blob) return;

        await saveFile(blob, 'csv', {
            suggestedName: `${suggestedStem}.csv`,
            description: 'Onset / IOI CSV',
        });
    };

    const exportAnalysisAsAudioClip = async (analysis, { label = 'Selection', suggestedStem = buildExportFileStem(`${label}-clip`, 'clip') } = {}) => {
        const audioData = typeof buildAudioDataForAnalysis === 'function'
            ? await buildAudioDataForAnalysis(analysis, { label })
            : null;
        if (!audioData) return;

        const blob = encodeAudioData(audioData);
        await saveFile(blob, 'wav', {
            suggestedName: `${suggestedStem}.wav`,
            description: 'Selected Audio Clip',
        });
    };

    const exportCurrentSelectionAsJson = async () => {
        const analysis = typeof getCurrentAnalysis === 'function' ? getCurrentAnalysis() : null;
        if (!analysis) return;
        await exportAnalysisAsJson(analysis, {
            label: 'Current Selection',
            suggestedStem: buildExportFileStem('current-selection'),
        });
    };

    const exportCurrentSelectionAsCsv = async () => {
        const analysis = typeof getCurrentAnalysis === 'function' ? getCurrentAnalysis() : null;
        if (!analysis) return;
        await exportAnalysisAsCsv(analysis, {
            label: 'Current Selection',
            suggestedStem: buildExportFileStem('current-selection'),
        });
    };

    const exportCurrentSelectionAsIoiCsv = async () => {
        const analysis = typeof getCurrentAnalysis === 'function' ? getCurrentAnalysis() : null;
        if (!analysis) return;
        await exportAnalysisAsIoiCsv(analysis, {
            label: 'Current Selection',
            suggestedStem: buildExportFileStem('current-selection-ioi', 'ioi'),
        });
    };

    const exportCurrentSelectionAsAudioClip = async () => {
        const analysis = typeof getCurrentAnalysis === 'function' ? getCurrentAnalysis() : null;
        if (!analysis) return;
        await exportAnalysisAsAudioClip(analysis, {
            label: 'Current Selection',
            suggestedStem: buildExportFileStem('current-selection-clip', 'clip'),
        });
    };

    const exportSelectionGroupAsAudioClip = async (groupId) => {
        const group = typeof getGroupRecord === 'function' ? getGroupRecord(groupId) : null;
        const analysis = typeof getGroupAnalysis === 'function' ? getGroupAnalysis(groupId) : null;
        if (!group || !analysis?.summary) return;

        await exportAnalysisAsAudioClip(analysis, {
            label: group.label,
            suggestedStem: buildExportFileStem(`${group.label}-clip`, 'clip'),
        });
    };

    const exportSelectionGroupAsIoiCsv = async (groupId) => {
        const group = typeof getGroupRecord === 'function' ? getGroupRecord(groupId) : null;
        const analysis = typeof getGroupAnalysis === 'function' ? getGroupAnalysis(groupId) : null;
        if (!group || !analysis?.summary) return;

        await exportAnalysisAsIoiCsv(analysis, {
            label: group.label,
            suggestedStem: buildExportFileStem(`${group.label}-ioi`, 'ioi'),
        });
    };

    return {
        buildExportFileStem,
        exportAnalysisAsJson,
        exportAnalysisAsCsv,
        exportAnalysisAsIoiCsv,
        exportAnalysisAsAudioClip,
        exportCurrentSelectionAsJson,
        exportCurrentSelectionAsCsv,
        exportCurrentSelectionAsIoiCsv,
        exportCurrentSelectionAsAudioClip,
        exportSelectionGroupAsAudioClip,
        exportSelectionGroupAsIoiCsv,
    };
};