export const createTimbreController = ({
    analysisState,
    trajectoryVisualizer,
    transportMarkers,
    getCurrentSelectionSummary,
    getSelectedInstanceIds,
    ensureActiveSelectionPanelTab,
    getActiveSelectionPanelTabId,
    getGroupById,
    getSelectedAsset,
    buildSelectionAnalysisForIds,
    updateSelectionBadge,
    updateSelectionPlaybackMask,
    formatTimestamp,
    isTerrainMode,
    getShowTransportOnsetMarkers,
    getTrajectoryDurationSec,
    seekToTimeSec,
    highlightOnset,
    onAnalysisUpdated,
    nowFactory = () => globalThis.performance?.now?.() ?? Date.now(),
} = {}) => {
    const getCurrentAnalysisSnapshot = () => {
        const summary = getCurrentSelectionSummary?.();
        if (!summary) return null;

        return {
            selectedRecords: summary.selectedRecords,
            summary,
            contiguousWindows: analysisState.contiguousWindows,
            onsetEvents: analysisState.onsetEvents,
            interOnsetIntervals: analysisState.interOnsetIntervals,
            onsetMethod: analysisState.onsetMethod,
        };
    };

    const getActiveAnalysisSnapshot = () => {
        ensureActiveSelectionPanelTab?.();
        if (getActiveSelectionPanelTabId?.() === 'current') {
            const currentAnalysis = getCurrentAnalysisSnapshot();
            return currentAnalysis
                ? {
                    kind: 'current',
                    label: 'Current Selection',
                    instanceIds: [...(getSelectedInstanceIds?.() || [])],
                    analysis: currentAnalysis,
                }
                : null;
        }

        const group = getGroupById?.(getActiveSelectionPanelTabId?.());
        const selectedAssetId = getSelectedAsset?.()?.id || '';
        if (!group || group.assetId !== selectedAssetId) return null;

        const analysis = buildSelectionAnalysisForIds?.(group.instanceIds);
        if (!analysis?.summary) return null;

        return {
            kind: 'group',
            label: group.label,
            instanceIds: [...group.instanceIds],
            analysis,
            group,
        };
    };

    const invalidateOnsetProgress = ({ clearPulses = true, adoptCurrentTimeSec = null } = {}) => {
        if (clearPulses) trajectoryVisualizer?.clearOnsetPulses?.();
        analysisState.lastPlaybackTimeSec = Number.isFinite(adoptCurrentTimeSec) ? adoptCurrentTimeSec : null;
    };

    const updateTransportOnsetMarkers = () => {
        const markerLayer = transportMarkers?.ensureLayerElement?.();
        if (!markerLayer) return;

        const activeAnalysisTarget = getActiveAnalysisSnapshot();
        const durationSec = getTrajectoryDurationSec?.() || 0;
        const onsetEvents = activeAnalysisTarget?.analysis?.onsetEvents || [];
        const shouldShowMarkers = !isTerrainMode?.() && !!getShowTransportOnsetMarkers?.() && durationSec > 0 && onsetEvents.length > 0;

        const markerColor = activeAnalysisTarget?.kind === 'group'
            ? 'rgba(250, 204, 21, 0.92)'
            : 'rgba(34, 211, 238, 0.92)';
        const markerShadow = activeAnalysisTarget?.kind === 'group'
            ? '0 0 10px rgba(250, 204, 21, 0.45)'
            : '0 0 10px rgba(34, 211, 238, 0.45)';

        transportMarkers.renderMarkers({
            visible: shouldShowMarkers,
            markers: onsetEvents,
            durationSec,
            markerColor,
            markerShadow,
            titleForMarker: (event) => `${activeAnalysisTarget?.label || 'Selection'} | ${formatTimestamp?.(event.timeSec) || 'n/a'} | Click to highlight related nodes`,
            onMarkerClick: (event) => {
                if (!activeAnalysisTarget?.analysis) return;

                if (Number.isFinite(event.timeSec)) {
                    seekToTimeSec?.(event.timeSec);
                    invalidateOnsetProgress({ clearPulses: false, adoptCurrentTimeSec: event.timeSec });
                }

                highlightOnset?.(activeAnalysisTarget.analysis, event, {
                    nowMs: nowFactory(),
                    clearExistingPulses: true,
                });
            },
        });
    };

    const rebuildSelectionAnalysis = ({ adoptCurrentTimeSec = null } = {}) => {
        const nextAnalysis = buildSelectionAnalysisForIds?.(getSelectedInstanceIds?.(), { includeSelectionSources: true });
        if (!nextAnalysis) return null;

        analysisState.contiguousWindows = nextAnalysis.contiguousWindows;
        analysisState.onsetEvents = nextAnalysis.onsetEvents;
        analysisState.interOnsetIntervals = nextAnalysis.interOnsetIntervals;
        analysisState.onsetMethod = nextAnalysis.onsetMethod;
        invalidateOnsetProgress({ clearPulses: true, adoptCurrentTimeSec });
        updateSelectionBadge?.();
        updateSelectionPlaybackMask?.();
        updateTransportOnsetMarkers();
        onAnalysisUpdated?.(nextAnalysis);
        return nextAnalysis;
    };

    return {
        getActiveAnalysisSnapshot,
        getCurrentAnalysisSnapshot,
        invalidateOnsetProgress,
        rebuildSelectionAnalysis,
        updateTransportOnsetMarkers,
    };
};