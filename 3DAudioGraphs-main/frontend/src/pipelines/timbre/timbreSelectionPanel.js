export const createTimbreSelectionPanel = ({
    elements,
    isTerrainMode,
    shouldShowBadge,
    shouldShowPanel,
    getCurrentSelectionSummary,
    getCurrentAssetGroups,
    getGroupById,
    ensureActiveTab,
    getActiveTabId,
    setActiveTabId,
    getActiveLassoDraw,
    planeSelectionMeta,
    syncInlineLabelState,
    getInlineLabelValue,
    setInlineLabel,
    formatSelectionTimestamp,
    formatSelectionScalar,
    getCurrentAnalysisState,
    buildSelectionAnalysisForIds,
    getSelectedAssetLabel,
    formatGroupSource,
    updateTransportOnsetMarkers,
    actions,
} = {}) => {
    const createActionButton = (label, onClick, { disabled = false, accent = false, danger = false } = {}) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = label;
        button.disabled = disabled;
        button.style.padding = '6px 8px';
        button.style.borderRadius = '6px';
        button.style.border = `1px solid ${danger ? '#7f1d1d' : accent ? '#164e63' : '#334155'}`;
        button.style.background = disabled
            ? 'rgba(30, 41, 59, 0.45)'
            : danger
                ? 'rgba(127, 29, 29, 0.25)'
                : accent
                    ? 'rgba(8, 145, 178, 0.18)'
                    : 'rgba(15, 23, 42, 0.9)';
        button.style.color = disabled ? '#64748b' : '#e2e8f0';
        button.style.cursor = disabled ? 'default' : 'pointer';
        button.style.fontFamily = 'inherit';
        button.style.fontSize = '11px';
        if (!disabled) {
            button.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                Promise.resolve(onClick?.()).catch((error) => {
                    console.error('Node selection panel action failed:', error);
                });
            });
        }
        return button;
    };

    const renderPanel = () => {
        const {
            panel,
            panelSubtitle,
            panelTabBar,
            panelBody,
        } = elements;

        if (!shouldShowPanel?.()) {
            panel.style.display = 'none';
            updateTransportOnsetMarkers?.();
            return;
        }

        ensureActiveTab?.();
        panel.style.display = 'block';

        const activeLassoDraw = getActiveLassoDraw?.();
        const currentAssetGroups = getCurrentAssetGroups?.() || [];
        panelSubtitle.textContent = activeLassoDraw
            ? `Drawing ${planeSelectionMeta?.[activeLassoDraw.planeKey]?.label || 'Lasso'}`
            : `${currentAssetGroups.length} saved group${currentAssetGroups.length === 1 ? '' : 's'}`;

        panelTabBar.replaceChildren();
        panelBody.replaceChildren();

        const createTabButton = (label, tabId) => {
            const button = document.createElement('button');
            const isActive = getActiveTabId?.() === tabId;
            button.type = 'button';
            button.textContent = label;
            button.style.padding = '5px 9px';
            button.style.borderRadius = '999px';
            button.style.border = `1px solid ${isActive ? '#0ea5e9' : '#334155'}`;
            button.style.background = isActive ? 'rgba(14, 165, 233, 0.18)' : 'rgba(15, 23, 42, 0.85)';
            button.style.color = isActive ? '#e0f2fe' : '#cbd5e1';
            button.style.cursor = 'pointer';
            button.style.fontFamily = 'inherit';
            button.style.fontSize = '11px';
            button.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                setActiveTabId?.(tabId);
                renderPanel();
            });
            return button;
        };

        const appendInfoLine = (label, value) => {
            const line = document.createElement('div');
            line.style.color = '#cbd5e1';
            line.textContent = `${label}: ${value}`;
            panelBody.appendChild(line);
        };

        const appendButtonGrid = (...buttons) => {
            const grid = document.createElement('div');
            grid.style.display = 'grid';
            grid.style.gridTemplateColumns = 'repeat(2, minmax(0, 1fr))';
            grid.style.gap = '6px';
            for (const button of buttons) {
                if (button) grid.appendChild(button);
            }
            panelBody.appendChild(grid);
        };

        const appendInlineLabelEditor = ({
            labelText,
            inputValue,
            inputPlaceholder,
            buttonText,
            onSubmit,
            disabled = false,
        }) => {
            const wrapper = document.createElement('div');
            wrapper.style.display = 'grid';
            wrapper.style.gap = '6px';

            const label = document.createElement('div');
            label.style.color = '#94a3b8';
            label.style.fontSize = '11px';
            label.textContent = labelText;

            const row = document.createElement('div');
            row.style.display = 'grid';
            row.style.gridTemplateColumns = 'minmax(0, 1fr) auto';
            row.style.gap = '6px';

            const input = document.createElement('input');
            input.type = 'text';
            input.value = inputValue;
            input.placeholder = inputPlaceholder;
            input.disabled = disabled;
            input.style.padding = '7px 9px';
            input.style.border = '1px solid #475569';
            input.style.borderRadius = '7px';
            input.style.background = disabled ? 'rgba(15, 23, 42, 0.55)' : '#020617';
            input.style.color = disabled ? '#64748b' : '#f8fafc';
            input.style.fontFamily = 'inherit';
            input.style.fontSize = '12px';
            input.addEventListener('pointerdown', (event) => {
                event.stopPropagation();
            });
            input.addEventListener('input', () => {
                setInlineLabel?.(input.value);
            });
            input.addEventListener('keydown', (event) => {
                if (event.key !== 'Enter' || disabled) return;
                event.preventDefault();
                Promise.resolve(onSubmit?.(input.value)).catch((error) => {
                    console.error('Node selection inline label action failed:', error);
                });
            });

            row.appendChild(input);
            row.appendChild(createActionButton(buttonText, () => onSubmit?.(input.value), { disabled, accent: true }));
            wrapper.appendChild(label);
            wrapper.appendChild(row);
            panelBody.appendChild(wrapper);
        };

        const currentSummary = getCurrentSelectionSummary?.();
        panelTabBar.appendChild(createTabButton(`Current${currentSummary ? ` (${currentSummary.selectedRecords.length})` : ''}`, 'current'));
        for (const group of currentAssetGroups) {
            panelTabBar.appendChild(createTabButton(`${group.label} (${group.instanceIds.length})`, group.id));
        }

        if (getActiveTabId?.() === 'current') {
            const defaultLabel = syncInlineLabelState?.('current');
            const currentAnalysisState = getCurrentAnalysisState?.();
            appendInfoLine('Selection', currentSummary ? `${currentSummary.selectedRecords.length} nodes` : 'None');
            appendInfoLine('Frames', currentSummary ? `${currentSummary.frameMin}-${currentSummary.frameMax}` : 'n/a');
            appendInfoLine('Time', currentSummary ? `${formatSelectionTimestamp?.(currentSummary.timeMin)} -> ${formatSelectionTimestamp?.(currentSummary.timeMax)}` : 'n/a');
            appendInfoLine('Analysis', currentSummary
                ? `${currentAnalysisState?.onsetMethod} | ${currentAnalysisState?.onsetEvents?.length || 0} onsets | ${currentAnalysisState?.interOnsetIntervals?.length || 0} IOIs`
                : 'n/a');
            if (activeLassoDraw) {
                appendInfoLine('Lasso', `${planeSelectionMeta?.[activeLassoDraw.planeKey]?.label || activeLassoDraw.planeKey} | ${activeLassoDraw.points.length} points`);
            }

            appendInlineLabelEditor({
                labelText: 'New group label',
                inputValue: getInlineLabelValue?.() || '',
                inputPlaceholder: defaultLabel,
                buttonText: 'Save Group',
                onSubmit: (nextLabel) => actions?.saveCurrentSelectionAsNewGroup?.(nextLabel),
                disabled: !currentSummary,
            });

            appendButtonGrid(
                createActionButton('Auto Tabs: Windows', actions?.autoSaveGroupsFromWindows, {
                    disabled: (currentAnalysisState?.contiguousWindows?.length || 0) === 0,
                    accent: true,
                }),
                createActionButton('Auto Tabs: Onsets', actions?.autoSaveGroupsFromOnsets, {
                    disabled: (currentAnalysisState?.onsetEvents?.length || 0) === 0,
                    accent: true,
                }),
            );
            appendButtonGrid(
                createActionButton('Export Audio', actions?.exportCurrentSelectionAsAudioClip, {
                    disabled: !currentSummary,
                    accent: true,
                }),
                createActionButton('Export Onsets + IOI', actions?.exportCurrentSelectionAsIoiCsv, {
                    disabled: !currentSummary,
                }),
            );
            appendButtonGrid(
                createActionButton('Export Onsets + IOI 2', actions?.exportCurrentSelectionAsBioacousticsWorkbook, {
                    disabled: !currentSummary,
                    accent: true,
                }),
            );
            updateTransportOnsetMarkers?.();
            return;
        }

        const activeGroup = getGroupById?.(getActiveTabId?.());
        if (!activeGroup) {
            setActiveTabId?.('current');
            renderPanel();
            return;
        }

        const groupAnalysis = buildSelectionAnalysisForIds?.(activeGroup.instanceIds);
        const groupSummary = groupAnalysis?.summary;
        const defaultLabel = syncInlineLabelState?.(activeGroup.id);
        const groupSelectionSet = new Set(activeGroup.instanceIds);
        const overlappingCurrentNodes = currentSummary
            ? currentSummary.selectedRecords
                .map((entry) => entry.instanceId)
                .filter((instanceId) => groupSelectionSet.has(instanceId))
            : [];
        const canMergeCurrentIntoGroup = currentSummary
            ? currentSummary.selectedRecords.some((entry) => !groupSelectionSet.has(entry.instanceId))
            : false;
        const canRemoveCurrentFromGroup = overlappingCurrentNodes.length > 0 && overlappingCurrentNodes.length < activeGroup.instanceIds.length;
        const activeGroupIndex = currentAssetGroups.findIndex((group) => group.id === activeGroup.id);

        appendInfoLine('Group', activeGroup.label);
        appendInfoLine('Source', formatGroupSource?.(activeGroup.sourceType));
        appendInfoLine('Nodes', `${activeGroup.instanceIds.length}`);
        appendInfoLine('Frames', groupSummary ? `${groupSummary.frameMin}-${groupSummary.frameMax}` : 'n/a');
        appendInfoLine('Time', groupSummary ? `${formatSelectionTimestamp?.(groupSummary.timeMin)} -> ${formatSelectionTimestamp?.(groupSummary.timeMax)}` : 'n/a');
        appendInfoLine('Analysis', groupSummary ? `${groupAnalysis?.onsetMethod} | ${groupAnalysis?.onsetEvents?.length || 0} onsets | ${groupAnalysis?.interOnsetIntervals?.length || 0} IOIs` : 'n/a');
        appendInfoLine('Overlap', currentSummary ? `${overlappingCurrentNodes.length} current nodes intersect this tab` : 'No current selection');

        appendInlineLabelEditor({
            labelText: 'Group label',
            inputValue: getInlineLabelValue?.() || '',
            inputPlaceholder: defaultLabel,
            buttonText: 'Apply Name',
            onSubmit: (nextLabel) => actions?.renameGroup?.(activeGroup.id, nextLabel),
        });

        appendButtonGrid(
            createActionButton('Load Group', () => actions?.loadGroupIntoCurrent?.(activeGroup.id), { accent: true }),
            createActionButton('Merge Into Current', () => actions?.loadGroupIntoCurrent?.(activeGroup.id, { merge: true })),
            createActionButton('Overwrite From Current', () => actions?.overwriteGroupFromCurrent?.(activeGroup.id), { disabled: !currentSummary }),
        );
        appendButtonGrid(
            createActionButton('Jump To Group', () => actions?.jumpToGroup?.(activeGroup.id), { accent: true }),
            createActionButton('Export Audio', () => actions?.exportGroupAsAudioClip?.(activeGroup.id), { accent: true }),
        );
        appendButtonGrid(
            createActionButton('Export Onsets + IOI', () => actions?.exportGroupAsIoiCsv?.(activeGroup.id)),
            createActionButton('Merge Current Into Tab', () => actions?.mergeCurrentIntoGroup?.(activeGroup.id), {
                disabled: !currentSummary || !canMergeCurrentIntoGroup,
            }),
        );
        appendButtonGrid(
            createActionButton('Export Onsets + IOI 2', () => actions?.exportGroupAsBioacousticsWorkbook?.(activeGroup.id), {
                accent: true,
            }),
        );
        appendButtonGrid(
            createActionButton('Delete Current Nodes', () => actions?.removeCurrentFromGroup?.(activeGroup.id), {
                disabled: !canRemoveCurrentFromGroup,
            }),
            createActionButton('Split Current Nodes', () => actions?.splitGroupByCurrentSelection?.(activeGroup.id), {
                disabled: !canRemoveCurrentFromGroup,
            }),
        );
        appendButtonGrid(
            createActionButton('Move Tab Left', () => actions?.moveGroupWithinAsset?.(activeGroup.id, -1), {
                disabled: activeGroupIndex <= 0,
            }),
            createActionButton('Move Tab Right', () => actions?.moveGroupWithinAsset?.(activeGroup.id, 1), {
                disabled: activeGroupIndex < 0 || activeGroupIndex >= currentAssetGroups.length - 1,
            }),
        );
        appendButtonGrid(
            createActionButton('Delete Group', () => actions?.deleteGroup?.(activeGroup.id), { danger: true }),
        );
        updateTransportOnsetMarkers?.();
    };

    const updateBadge = () => {
        const {
            badge,
            badgeTitle,
            badgeMeta,
            badgeRange,
            badgeStats,
        } = elements;

        if (isTerrainMode?.()) {
            badge.style.display = 'none';
            renderPanel();
            return;
        }

        badge.style.display = shouldShowBadge?.() ? 'block' : 'none';

        const summary = getCurrentSelectionSummary?.();
        const activeLassoDraw = getActiveLassoDraw?.();
        if (!summary) {
            badgeTitle.textContent = 'Selection --';
            badgeMeta.textContent = 'Click a visible timbre node.';
            badgeRange.textContent = actions?.isSelectionPlaybackMaskEnabled?.()
                ? 'Mask To Selection is enabled. Select nodes to isolate playback.'
                : 'Shift-click to add or remove nodes.';
            if (activeLassoDraw) {
                badgeStats.textContent = `Drawing lasso on ${planeSelectionMeta?.[activeLassoDraw.planeKey]?.label || activeLassoDraw.planeKey} | ${activeLassoDraw.points.length} point${activeLassoDraw.points.length === 1 ? '' : 's'}`;
            } else {
                badgeStats.textContent = 'Plane selection inactive | Export and playback actions unlock once nodes are selected.';
            }
            renderPanel();
            return;
        }

        const currentAnalysisState = getCurrentAnalysisState?.();
        const assetLabel = getSelectedAssetLabel?.() || 'Current asset';

        badgeTitle.textContent = `Selection ${summary.selectedRecords.length} node${summary.selectedRecords.length === 1 ? '' : 's'}`;
        badgeMeta.textContent = `${assetLabel} | Frames ${summary.frameMin}-${summary.frameMax} | Time ${formatSelectionTimestamp?.(summary.timeMin)} -> ${formatSelectionTimestamp?.(summary.timeMax)}`;
        badgeRange.textContent = `Windows ${currentAnalysisState?.contiguousWindows?.length || 0} | Onsets ${currentAnalysisState?.onsetEvents?.length || 0} | IOIs ${currentAnalysisState?.interOnsetIntervals?.length || 0} | ${currentAnalysisState?.onsetMethod || 'n/a'} | Mask ${actions?.isSelectionPlaybackMaskEnabled?.() ? 'On' : 'Off'}`;
        badgeStats.textContent = `Duration ${formatSelectionScalar?.(summary.durationSec)}s | Bounds X ${formatSelectionScalar?.(summary.pointBounds.minX)}-${formatSelectionScalar?.(summary.pointBounds.maxX)} | Y ${formatSelectionScalar?.(summary.pointBounds.minY)}-${formatSelectionScalar?.(summary.pointBounds.maxY)} | Z ${formatSelectionScalar?.(summary.pointBounds.minZ)}-${formatSelectionScalar?.(summary.pointBounds.maxZ)} | Manual ${summary.manualCount} | Box ${summary.boxCount}`;
        renderPanel();
    };

    return {
        renderPanel,
        updateBadge,
    };
};