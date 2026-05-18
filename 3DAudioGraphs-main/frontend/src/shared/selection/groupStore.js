export const createSelectionGroupId = ({ cryptoObject = globalThis.crypto } = {}) => {
    if (cryptoObject?.randomUUID) return cryptoObject.randomUUID();
    return `group-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
};

const defaultNowFactory = () => new Date().toISOString();

export const normalizeSelectionGroupRecord = (candidate, {
    normalizeSelectionIds,
    createGroupId = () => createSelectionGroupId(),
    defaultLabel = 'Saved Group',
    defaultSourceType = 'manual',
    nowFactory = defaultNowFactory,
} = {}) => {
    const instanceIds = typeof normalizeSelectionIds === 'function'
        ? normalizeSelectionIds(candidate?.instanceIds)
        : [];
    if (instanceIds.length === 0) return null;

    const label = typeof candidate?.label === 'string' && candidate.label.trim() !== ''
        ? candidate.label.trim()
        : defaultLabel;
    const assetId = typeof candidate?.assetId === 'string' ? candidate.assetId : '';
    const assetLabel = typeof candidate?.assetLabel === 'string' ? candidate.assetLabel : '';
    const sourceType = typeof candidate?.sourceType === 'string' && candidate.sourceType.trim() !== ''
        ? candidate.sourceType.trim()
        : defaultSourceType;
    const createdAt = typeof candidate?.createdAt === 'string' && candidate.createdAt.trim() !== ''
        ? candidate.createdAt
        : nowFactory();

    return {
        id: typeof candidate?.id === 'string' && candidate.id.trim() !== '' ? candidate.id : createGroupId(),
        label,
        assetId,
        assetLabel,
        sourceType,
        instanceIds,
        createdAt,
        updatedAt: nowFactory(),
    };
};

export const loadSelectionGroupsFromStorage = (storageKey, {
    storage = globalThis.localStorage,
    normalizeSelectionGroupRecord,
} = {}) => {
    try {
        const stored = storage?.getItem?.(storageKey);
        if (!stored) return [];
        const parsed = JSON.parse(stored);
        if (!Array.isArray(parsed) || typeof normalizeSelectionGroupRecord !== 'function') return [];
        return parsed
            .map(normalizeSelectionGroupRecord)
            .filter(Boolean);
    } catch {
        return [];
    }
};

export const persistSelectionGroupsToStorage = (storageKey, groupRecords, {
    storage = globalThis.localStorage,
} = {}) => {
    storage?.setItem?.(storageKey, JSON.stringify(groupRecords));
};

export const createSelectionGroupRecord = ({
    label,
    instanceIds,
    sourceType = 'manual',
    assetId = '',
    assetLabel = '',
} = {}, {
    normalizeSelectionIds,
    normalizeSelectionGroupRecord,
    createGroupId = () => createSelectionGroupId(),
    nowFactory = defaultNowFactory,
} = {}) => {
    const normalizedIds = typeof normalizeSelectionIds === 'function'
        ? normalizeSelectionIds(instanceIds)
        : [];
    if (normalizedIds.length === 0 || typeof normalizeSelectionGroupRecord !== 'function') return null;

    const now = nowFactory();
    return normalizeSelectionGroupRecord({
        id: createGroupId(),
        label,
        assetId,
        assetLabel,
        sourceType,
        instanceIds: normalizedIds,
        createdAt: now,
        updatedAt: now,
    });
};

const replaceGroupRecord = (groupRecords, groupId, nextRecordFactory) => {
    let replaced = false;
    const nextGroups = groupRecords.map((groupRecord) => {
        if (groupRecord.id !== groupId) return groupRecord;
        replaced = true;
        return nextRecordFactory(groupRecord);
    });
    return replaced ? nextGroups : groupRecords;
};

export const renameSelectionGroup = (groupRecords, groupId, nextLabel, {
    normalizeSelectionGroupRecord,
    nowFactory = defaultNowFactory,
} = {}) => {
    if (typeof normalizeSelectionGroupRecord !== 'function') return groupRecords;
    if (typeof nextLabel !== 'string' || nextLabel.trim() === '') return groupRecords;

    const trimmedLabel = nextLabel.trim();
    return replaceGroupRecord(groupRecords, groupId, (groupRecord) => normalizeSelectionGroupRecord({
        ...groupRecord,
        label: trimmedLabel,
        updatedAt: nowFactory(),
    }) || groupRecord);
};

export const replaceSelectionGroupInstanceIds = (groupRecords, groupId, nextInstanceIds, {
    normalizeSelectionGroupRecord,
    nowFactory = defaultNowFactory,
} = {}) => {
    if (typeof normalizeSelectionGroupRecord !== 'function') return groupRecords;

    return replaceGroupRecord(groupRecords, groupId, (groupRecord) => normalizeSelectionGroupRecord({
        ...groupRecord,
        instanceIds: nextInstanceIds,
        updatedAt: nowFactory(),
    }) || groupRecord);
};

export const deleteSelectionGroup = (groupRecords, groupId) => groupRecords.filter((groupRecord) => groupRecord.id !== groupId);

export const reorderSelectionGroupsWithinAsset = (groupRecords, assetId, groupId, direction) => {
    if (!assetId) return groupRecords;

    const currentAssetGroups = groupRecords.filter((groupRecord) => groupRecord.assetId === assetId);
    const currentIndex = currentAssetGroups.findIndex((groupRecord) => groupRecord.id === groupId);
    const targetIndex = currentIndex + direction;
    if (currentIndex < 0 || targetIndex < 0 || targetIndex >= currentAssetGroups.length) return groupRecords;

    const reorderedGroups = [...currentAssetGroups];
    const [movedGroup] = reorderedGroups.splice(currentIndex, 1);
    reorderedGroups.splice(targetIndex, 0, movedGroup);

    const assetRecordPositions = [];
    for (let recordIndex = 0; recordIndex < groupRecords.length; recordIndex++) {
        if (groupRecords[recordIndex].assetId === assetId) {
            assetRecordPositions.push(recordIndex);
        }
    }

    const nextGroups = groupRecords.slice();
    assetRecordPositions.forEach((recordIndex, assetIndex) => {
        nextGroups[recordIndex] = reorderedGroups[assetIndex];
    });

    return nextGroups;
};

export const mergeSelectionIntoGroup = (groupRecords, groupId, selectionIds, {
    normalizeSelectionIds,
    normalizeSelectionGroupRecord,
    nowFactory = defaultNowFactory,
} = {}) => {
    const groupRecord = groupRecords.find((entry) => entry.id === groupId);
    if (!groupRecord || typeof normalizeSelectionIds !== 'function') return groupRecords;

    const nextInstanceIds = normalizeSelectionIds([...(groupRecord.instanceIds || []), ...(selectionIds || [])]);
    if (nextInstanceIds.length === (groupRecord.instanceIds || []).length) return groupRecords;

    return replaceSelectionGroupInstanceIds(groupRecords, groupId, nextInstanceIds, {
        normalizeSelectionGroupRecord,
        nowFactory,
    });
};

export const removeSelectionFromGroup = (groupRecords, groupId, selectionIds, {
    normalizeSelectionGroupRecord,
    nowFactory = defaultNowFactory,
} = {}) => {
    const groupRecord = groupRecords.find((entry) => entry.id === groupId);
    if (!groupRecord) return groupRecords;

    const selectedSet = new Set(selectionIds || []);
    const nextInstanceIds = (groupRecord.instanceIds || []).filter((instanceId) => !selectedSet.has(instanceId));
    if (nextInstanceIds.length === 0 || nextInstanceIds.length === (groupRecord.instanceIds || []).length) return groupRecords;

    return replaceSelectionGroupInstanceIds(groupRecords, groupId, nextInstanceIds, {
        normalizeSelectionGroupRecord,
        nowFactory,
    });
};

export const splitSelectionGroup = (groupRecords, groupId, selectionIds, {
    createSelectionGroupRecord,
    normalizeSelectionGroupRecord,
    nowFactory = defaultNowFactory,
} = {}) => {
    const groupRecord = groupRecords.find((entry) => entry.id === groupId);
    if (!groupRecord || typeof createSelectionGroupRecord !== 'function') return null;

    const selectedSet = new Set(selectionIds || []);
    const splitInstanceIds = (groupRecord.instanceIds || []).filter((instanceId) => selectedSet.has(instanceId));
    const remainingInstanceIds = (groupRecord.instanceIds || []).filter((instanceId) => !selectedSet.has(instanceId));
    if (splitInstanceIds.length === 0 || remainingInstanceIds.length === 0) return null;

    const createdGroup = createSelectionGroupRecord({
        label: `${groupRecord.label} Split`,
        instanceIds: splitInstanceIds,
        sourceType: groupRecord.sourceType,
        assetId: groupRecord.assetId,
        assetLabel: groupRecord.assetLabel,
    });
    if (!createdGroup) return null;

    const nextGroups = replaceSelectionGroupInstanceIds(groupRecords, groupId, remainingInstanceIds, {
        normalizeSelectionGroupRecord,
        nowFactory,
    }).slice();
    const activeGroupIndex = nextGroups.findIndex((entry) => entry.id === groupId);
    nextGroups.splice(activeGroupIndex + 1, 0, createdGroup);

    return {
        nextGroups,
        createdGroup,
    };
};