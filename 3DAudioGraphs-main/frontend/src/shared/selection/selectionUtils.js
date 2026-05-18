export const normalizeSelectionIds = (selectionIds, { maxIndexExclusive = null } = {}) => {
    const hasIndexConstraint = Number.isFinite(maxIndexExclusive);

    return Array.from(new Set((selectionIds || [])
        .filter((selectionId) => Number.isFinite(selectionId))
        .map((selectionId) => Math.round(selectionId))))
        .filter((selectionId) => selectionId >= 0 && (!hasIndexConstraint || selectionId < maxIndexExclusive))
        .sort((a, b) => a - b);
};