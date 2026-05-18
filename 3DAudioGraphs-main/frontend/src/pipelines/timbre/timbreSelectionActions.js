import {
    createSelectionGroupId,
    createSelectionGroupRecord,
    deleteSelectionGroup,
    loadSelectionGroupsFromStorage,
    mergeSelectionIntoGroup,
    normalizeSelectionGroupRecord,
    persistSelectionGroupsToStorage,
    renameSelectionGroup,
    reorderSelectionGroupsWithinAsset,
    removeSelectionFromGroup,
    replaceSelectionGroupInstanceIds,
    splitSelectionGroup,
} from '../../shared/selection/groupStore.js';

const TIMBRE_SELECTION_GROUP_STORAGE_KEY = '3daudio_timbre_selection_groups_v1';

const formatTimbreSelectionGroupSource = (sourceType) => {
    if (sourceType === 'auto:windows') return 'Auto from windows';
    if (sourceType === 'auto:onsets') return 'Auto from onset segments';
    return 'Saved from current selection';
};

export const createTimbreSelectionActions = ({
    storageKey = TIMBRE_SELECTION_GROUP_STORAGE_KEY,
    normalizeSelectionIds,
    getSelectedAsset,
    getCurrentSelectionSummary,
    getSelectedInstanceIds,
    getCurrentSelectionAnalysisState,
    buildSelectionAnalysisForIds,
    clearPlaneSelections,
    setSelectedInstanceIds,
    jumpToAnalysisTarget,
    confirmDeleteGroup,
    renderSelectionPanel,
    onSelectionGroupsCommitted,
    storage = globalThis.localStorage,
    cryptoObject = globalThis.crypto,
    nowFactory = () => new Date().toISOString(),
} = {}) => {
    const createGroupId = () => createSelectionGroupId({ cryptoObject });

    const normalizeGroupRecord = (candidate) => normalizeSelectionGroupRecord(candidate, {
        normalizeSelectionIds,
        createGroupId,
        nowFactory,
    });

    let groupRecords = loadSelectionGroupsFromStorage(storageKey, {
        storage,
        normalizeSelectionGroupRecord: normalizeGroupRecord,
    });
    let activePanelTabId = 'current';
    let inlineLabelTabId = 'current';
    let inlineLabelValue = '';

    const getSelectedAssetId = () => getSelectedAsset?.()?.id || '';
    const getSelectedAssetLabel = () => getSelectedAsset?.()?.label || '';

    const persistGroupRecords = () => {
        persistSelectionGroupsToStorage(storageKey, groupRecords, { storage });
    };

    const getCurrentAssetGroups = () => {
        const assetId = getSelectedAssetId();
        return groupRecords.filter((group) => group.assetId === assetId);
    };

    const getGroupById = (groupId) => groupRecords.find((group) => group.id === groupId) || null;

    const ensureActivePanelTab = () => {
        if (activePanelTabId === 'current') return;
        const group = getGroupById(activePanelTabId);
        if (!group || group.assetId !== getSelectedAssetId()) {
            activePanelTabId = 'current';
        }
    };

    const getDefaultInlineLabel = (tabId = activePanelTabId) => {
        if (tabId === 'current') {
            return `Group ${getCurrentAssetGroups().length + 1}`;
        }
        return getGroupById(tabId)?.label || 'Saved Group';
    };

    const syncInlineLabelState = (tabId = activePanelTabId) => {
        const fallbackLabel = getDefaultInlineLabel(tabId);
        if (inlineLabelTabId !== tabId) {
            inlineLabelTabId = tabId;
            inlineLabelValue = fallbackLabel;
            return fallbackLabel;
        }

        if (!inlineLabelValue.trim()) {
            inlineLabelValue = fallbackLabel;
        }
        return fallbackLabel;
    };

    const setInlineLabel = (nextValue, tabId = activePanelTabId) => {
        inlineLabelTabId = tabId;
        inlineLabelValue = typeof nextValue === 'string' ? nextValue : '';
    };

    const getInlineLabelValue = () => inlineLabelValue;

    const commitGroupRecords = (nextGroups, { activeTabId = activePanelTabId } = {}) => {
        groupRecords = nextGroups
            .map(normalizeGroupRecord)
            .filter(Boolean);
        activePanelTabId = activeTabId;
        persistGroupRecords();
        onSelectionGroupsCommitted?.(groupRecords);
    };

    const createGroupRecord = ({ label, instanceIds, sourceType = 'manual' }) => {
        return createSelectionGroupRecord({
            label,
            assetId: getSelectedAssetId(),
            assetLabel: getSelectedAssetLabel(),
            sourceType,
            instanceIds,
        }, {
            normalizeSelectionIds,
            normalizeSelectionGroupRecord: normalizeGroupRecord,
            createGroupId,
            nowFactory,
        });
    };

    const getGroupAnalysis = (groupId) => {
        const group = getGroupById(groupId);
        if (!group || group.assetId !== getSelectedAssetId()) return null;
        return buildSelectionAnalysisForIds?.(group.instanceIds) || null;
    };

    const saveCurrentSelectionAsNewGroup = (labelOverride = null) => {
        const summary = getCurrentSelectionSummary?.();
        if (!summary) return;

        const fallbackLabel = `Group ${getCurrentAssetGroups().length + 1}`;
        const label = typeof labelOverride === 'string' && labelOverride.trim() !== ''
            ? labelOverride.trim()
            : fallbackLabel;
        if (!label) return;

        const nextGroup = createGroupRecord({
            label,
            instanceIds: summary.selectedRecords.map((entry) => entry.instanceId),
        });
        if (!nextGroup) return;

        commitGroupRecords([...groupRecords, nextGroup], { activeTabId: nextGroup.id });
        setInlineLabel(nextGroup.label, nextGroup.id);
        renderSelectionPanel?.();
    };

    const overwriteGroupFromCurrent = (groupId) => {
        const summary = getCurrentSelectionSummary?.();
        if (!summary) return;

        const nextGroups = replaceSelectionGroupInstanceIds(
            groupRecords,
            groupId,
            summary.selectedRecords.map((entry) => entry.instanceId),
            {
                normalizeSelectionGroupRecord: normalizeGroupRecord,
                nowFactory,
            },
        );
        commitGroupRecords(nextGroups, { activeTabId: groupId });
        renderSelectionPanel?.();
    };

    const loadGroupIntoCurrent = (groupId, { merge = false } = {}) => {
        const group = getGroupById(groupId);
        if (!group || group.assetId !== getSelectedAssetId()) return;

        if (!merge) {
            clearPlaneSelections?.();
            setSelectedInstanceIds?.(group.instanceIds);
            return;
        }

        setSelectedInstanceIds?.([...(getSelectedInstanceIds?.() || []), ...group.instanceIds]);
    };

    const renameGroup = (groupId, labelOverride = null) => {
        const group = getGroupById(groupId);
        if (!group) return;

        const nextLabel = typeof labelOverride === 'string' && labelOverride.trim() !== ''
            ? labelOverride.trim()
            : group.label;
        if (!nextLabel) return;

        const nextGroups = renameSelectionGroup(groupRecords, groupId, nextLabel, {
            normalizeSelectionGroupRecord: normalizeGroupRecord,
            nowFactory,
        });
        commitGroupRecords(nextGroups, { activeTabId: groupId });
        setInlineLabel(nextLabel, groupId);
        renderSelectionPanel?.();
    };

    const deleteGroup = async (groupId) => {
        const group = getGroupById(groupId);
        if (!group) return;
        if (!(await confirmDeleteGroup?.(group.label))) return;

        commitGroupRecords(deleteSelectionGroup(groupRecords, groupId), { activeTabId: 'current' });
        renderSelectionPanel?.();
    };

    const moveGroupWithinAsset = (groupId, direction) => {
        const assetId = getSelectedAssetId();
        if (!assetId) return;

        const nextGroups = reorderSelectionGroupsWithinAsset(groupRecords, assetId, groupId, direction);
        if (nextGroups === groupRecords) return;

        commitGroupRecords(nextGroups, { activeTabId: groupId });
        renderSelectionPanel?.();
    };

    const mergeCurrentIntoGroup = (groupId) => {
        const nextGroups = mergeSelectionIntoGroup(groupRecords, groupId, getSelectedInstanceIds?.(), {
            normalizeSelectionIds,
            normalizeSelectionGroupRecord: normalizeGroupRecord,
            nowFactory,
        });
        if (nextGroups === groupRecords) return;

        commitGroupRecords(nextGroups, { activeTabId: groupId });
        renderSelectionPanel?.();
    };

    const removeCurrentFromGroup = (groupId) => {
        const nextGroups = removeSelectionFromGroup(groupRecords, groupId, getSelectedInstanceIds?.(), {
            normalizeSelectionGroupRecord: normalizeGroupRecord,
            nowFactory,
        });
        if (nextGroups === groupRecords) return;

        commitGroupRecords(nextGroups, { activeTabId: groupId });
        renderSelectionPanel?.();
    };

    const splitGroupByCurrentSelection = (groupId) => {
        const splitResult = splitSelectionGroup(groupRecords, groupId, getSelectedInstanceIds?.(), {
            createSelectionGroupRecord: ({ label, instanceIds, sourceType, assetId, assetLabel }) => createSelectionGroupRecord({
                label,
                instanceIds,
                sourceType,
                assetId,
                assetLabel,
            }, {
                normalizeSelectionIds,
                normalizeSelectionGroupRecord: normalizeGroupRecord,
                createGroupId,
                nowFactory,
            }),
            normalizeSelectionGroupRecord: normalizeGroupRecord,
            nowFactory,
        });
        if (!splitResult) return;

        commitGroupRecords(splitResult.nextGroups, { activeTabId: splitResult.createdGroup.id });
        setInlineLabel(splitResult.createdGroup.label, splitResult.createdGroup.id);
        renderSelectionPanel?.();
    };

    const jumpToGroup = (groupId) => {
        const analysis = getGroupAnalysis(groupId);
        if (!analysis) return;
        jumpToAnalysisTarget?.(analysis);
    };

    const autoSaveGroupsFromWindows = () => {
        const selectionAnalysis = getCurrentSelectionAnalysisState?.();
        const windows = (selectionAnalysis?.contiguousWindows || [])
            .filter((window) => Array.isArray(window.pointIndices) && window.pointIndices.length > 0);
        if (windows.length === 0) return;

        const createdGroups = windows
            .map((window, index) => createGroupRecord({
                label: `Window ${index + 1}`,
                instanceIds: window.pointIndices,
                sourceType: 'auto:windows',
            }))
            .filter(Boolean);
        if (createdGroups.length === 0) return;

        commitGroupRecords([...groupRecords, ...createdGroups], { activeTabId: createdGroups[0].id });
        renderSelectionPanel?.();
    };

    const buildAutoGroupsFromOnsets = () => {
        const selectionAnalysis = getCurrentSelectionAnalysisState?.();
        const onsetIds = new Set((selectionAnalysis?.onsetEvents || []).map((event) => event.pointIndex));
        const groups = [];

        for (const window of selectionAnalysis?.contiguousWindows || []) {
            if (!Array.isArray(window.pointIndices) || window.pointIndices.length === 0) continue;

            const onsetLocalIndices = window.pointIndices
                .map((pointIndex, localIndex) => (onsetIds.has(pointIndex) ? localIndex : null))
                .filter((localIndex) => Number.isInteger(localIndex));

            if (onsetLocalIndices.length === 0) continue;

            for (let segmentIndex = 0; segmentIndex < onsetLocalIndices.length; segmentIndex++) {
                const startLocalIndex = onsetLocalIndices[segmentIndex];
                const endLocalIndex = onsetLocalIndices[segmentIndex + 1] ?? window.pointIndices.length;
                const pointIndices = window.pointIndices.slice(startLocalIndex, endLocalIndex);
                if (pointIndices.length > 0) {
                    groups.push(pointIndices);
                }
            }
        }

        return groups;
    };

    const autoSaveGroupsFromOnsets = () => {
        const onsetGroups = buildAutoGroupsFromOnsets();
        if (onsetGroups.length === 0) return;

        const createdGroups = onsetGroups
            .map((pointIndices, index) => createGroupRecord({
                label: `Onset ${index + 1}`,
                instanceIds: pointIndices,
                sourceType: 'auto:onsets',
            }))
            .filter(Boolean);
        if (createdGroups.length === 0) return;

        commitGroupRecords([...groupRecords, ...createdGroups], { activeTabId: createdGroups[0].id });
        renderSelectionPanel?.();
    };

    return {
        autoSaveGroupsFromOnsets,
        autoSaveGroupsFromWindows,
        deleteGroup,
        ensureActivePanelTab,
        formatGroupSource: formatTimbreSelectionGroupSource,
        getActivePanelTabId: () => activePanelTabId,
        getCurrentAssetGroups,
        getGroupAnalysis,
        getGroupById,
        getInlineLabelValue,
        jumpToGroup,
        loadGroupIntoCurrent,
        mergeCurrentIntoGroup,
        moveGroupWithinAsset,
        overwriteGroupFromCurrent,
        removeCurrentFromGroup,
        renameGroup,
        saveCurrentSelectionAsNewGroup,
        setActivePanelTabId: (tabId) => {
            activePanelTabId = typeof tabId === 'string' && tabId.trim() !== '' ? tabId : 'current';
        },
        setInlineLabel,
        splitGroupByCurrentSelection,
        syncInlineLabelState,
    };
};