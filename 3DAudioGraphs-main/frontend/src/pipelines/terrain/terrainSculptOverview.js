const clampPct = (value) => Math.max(0, Math.min(100, Number(value) || 0));

const clampCanvasValue = (value, maxValue) => Math.max(0, Math.min(maxValue, value));

const shiftRangePct = (minPct, maxPct, deltaPct) => {
    const span = Math.max(0.1, maxPct - minPct);
    let nextMin = minPct + deltaPct;
    let nextMax = maxPct + deltaPct;

    if (nextMin < 0) {
        nextMax -= nextMin;
        nextMin = 0;
    }
    if (nextMax > 100) {
        nextMin -= (nextMax - 100);
        nextMax = 100;
    }

    nextMin = clampPct(Math.min(nextMin, 100 - span));
    nextMax = clampPct(Math.max(nextMin + 0.1, Math.min(100, nextMin + span)));
    return { minPct: nextMin, maxPct: nextMax };
};

const sampleGradient = (intensity) => {
    const clamped = Math.max(0, Math.min(1, intensity));
    const anchors = [
        { stop: 0.0, color: [7, 15, 26] },
        { stop: 0.2, color: [21, 50, 92] },
        { stop: 0.45, color: [35, 108, 171] },
        { stop: 0.68, color: [86, 196, 182] },
        { stop: 0.88, color: [244, 214, 116] },
        { stop: 1.0, color: [255, 245, 214] },
    ];

    let start = anchors[0];
    let end = anchors[anchors.length - 1];
    for (let index = 1; index < anchors.length; index++) {
        if (clamped <= anchors[index].stop) {
            start = anchors[index - 1];
            end = anchors[index];
            break;
        }
    }

    const localT = (clamped - start.stop) / Math.max(1e-6, end.stop - start.stop);
    return [0, 1, 2].map((channelIndex) => Math.round(
        start.color[channelIndex] + ((end.color[channelIndex] - start.color[channelIndex]) * localT),
    ));
};

const OVERVIEW_VISIBLE_MODES = new Set(['2D Spectrogram Overview', 'Both']);

export const createTerrainSculptOverviewController = ({
    panel,
    canvas,
    meta,
    status,
    footer,
    terrainVisualizer,
    settings,
    isTerrainMode,
    getSelectedAsset,
    getPlaybackTimeSec,
    getDurationSec,
    ensureTerrainPlaneSelectionSettings,
    getCurrentSelectionTargetLabel,
    getRenderedSliceLabel,
    applyOverviewSelection,
    onInteractionTargetChange,
} = {}) => {
    const context = canvas?.getContext?.('2d');
    let dragState = null;
    let cachedAssetId = '';
    let cachedFrameCount = 0;
    let cachedSourceBinCount = 0;
    let cachedBitmap = null;

    const clearBitmapCache = () => {
        cachedBitmap = null;
        cachedAssetId = '';
        cachedFrameCount = 0;
        cachedSourceBinCount = 0;
    };

    const getPanelState = () => {
        const planeSelections = ensureTerrainPlaneSelectionSettings?.();
        return {
            planeSelections,
            asset: getSelectedAsset?.() || null,
            frameCount: terrainVisualizer?.getFrameDataCount?.() || 0,
            visibleWindow: terrainVisualizer?.getAlignedFrameWindow?.() || { start: 0, endExclusive: 0 },
            playbackTimeSec: getPlaybackTimeSec?.() || 0,
            durationSec: getDurationSec?.() || 0,
        };
    };

    const shouldShow = (planeSelections) => !!(
        panel &&
        canvas &&
        context &&
        isTerrainMode?.() &&
        planeSelections?.enabled &&
        OVERVIEW_VISIBLE_MODES.has(planeSelections?.overviewMode)
    );

    const ensureCanvasSize = () => {
        if (!canvas) return { width: 0, height: 0, dpr: 1 };
        const rect = canvas.getBoundingClientRect();
        const dpr = Math.max(1, globalThis.window?.devicePixelRatio || 1);
        const width = Math.max(240, Math.round(rect.width * dpr));
        const height = Math.max(160, Math.round(rect.height * dpr));
        if (canvas.width !== width || canvas.height !== height) {
            canvas.width = width;
            canvas.height = height;
        }
        return { width, height, dpr };
    };

    const getSourceBinCount = (frameCount) => {
        if (frameCount <= 0) return 0;
        const firstRow = terrainVisualizer?.getFrameDataRowAt?.(0);
        return ArrayBuffer.isView(firstRow) ? firstRow.length : 0;
    };

    const ensureBitmap = ({ asset, frameCount } = {}) => {
        const sourceBinCount = getSourceBinCount(frameCount);
        const assetId = asset?.id || '';
        if (
            cachedBitmap &&
            cachedAssetId === assetId &&
            cachedFrameCount === frameCount &&
            cachedSourceBinCount === sourceBinCount
        ) {
            return cachedBitmap;
        }

        if (frameCount <= 0 || sourceBinCount <= 0) {
            clearBitmapCache();
            return null;
        }

        const bitmapHeight = Math.min(256, Math.max(64, sourceBinCount));
        const bitmapCanvas = document.createElement('canvas');
        bitmapCanvas.width = Math.max(1, frameCount);
        bitmapCanvas.height = bitmapHeight;
        const bitmapContext = bitmapCanvas.getContext('2d');
        const imageData = bitmapContext.createImageData(bitmapCanvas.width, bitmapCanvas.height);
        const pixelData = imageData.data;

        let intensityMax = 0;
        for (let frameIndex = 0; frameIndex < frameCount; frameIndex++) {
            const frameRow = terrainVisualizer?.getFrameDataRowAt?.(frameIndex);
            if (!ArrayBuffer.isView(frameRow)) continue;
            for (let binIndex = 0; binIndex < frameRow.length; binIndex++) {
                intensityMax = Math.max(intensityMax, Number(frameRow[binIndex]) || 0);
            }
        }

        const safeMax = Math.max(1, intensityMax);
        for (let frameIndex = 0; frameIndex < frameCount; frameIndex++) {
            const frameRow = terrainVisualizer?.getFrameDataRowAt?.(frameIndex);
            if (!ArrayBuffer.isView(frameRow)) continue;

            for (let yIndex = 0; yIndex < bitmapHeight; yIndex++) {
                const normalizedY = bitmapHeight <= 1 ? 0 : (yIndex / (bitmapHeight - 1));
                const sourceBinIndex = Math.max(
                    0,
                    Math.min(sourceBinCount - 1, Math.round((1 - normalizedY) * (sourceBinCount - 1))),
                );
                const intensity = Math.max(0, (Number(frameRow[sourceBinIndex]) || 0) / safeMax);
                const [red, green, blue] = sampleGradient(intensity);
                const pixelOffset = ((yIndex * bitmapCanvas.width) + frameIndex) * 4;
                pixelData[pixelOffset + 0] = red;
                pixelData[pixelOffset + 1] = green;
                pixelData[pixelOffset + 2] = blue;
                pixelData[pixelOffset + 3] = 255;
            }
        }

        bitmapContext.putImageData(imageData, 0, 0);
        cachedBitmap = bitmapCanvas;
        cachedAssetId = assetId;
        cachedFrameCount = frameCount;
        cachedSourceBinCount = sourceBinCount;
        return cachedBitmap;
    };

    const drawMessage = (width, height, message) => {
        context.clearRect(0, 0, width, height);
        context.fillStyle = '#061018';
        context.fillRect(0, 0, width, height);
        context.fillStyle = '#9fb2c7';
        context.font = `${Math.max(14, Math.round(height * 0.06))}px monospace`;
        context.textAlign = 'center';
        context.textBaseline = 'middle';
        context.fillText(message, width * 0.5, height * 0.5);
    };

    const selectionRectFromState = (planeSelections, width, height) => {
        const timeMinPct = clampPct(planeSelections?.fullClipTimeMinPct ?? 0);
        const timeMaxPct = clampPct(planeSelections?.fullClipTimeMaxPct ?? 100);
        const frequencyMinPct = clampPct(planeSelections?.xz?.axis1MinPct ?? 0);
        const frequencyMaxPct = clampPct(planeSelections?.xz?.axis1MaxPct ?? 100);

        const x = (Math.min(timeMinPct, timeMaxPct) / 100) * width;
        const rectWidth = Math.max(1, (Math.abs(timeMaxPct - timeMinPct) / 100) * width);
        const top = ((100 - Math.max(frequencyMinPct, frequencyMaxPct)) / 100) * height;
        const bottom = ((100 - Math.min(frequencyMinPct, frequencyMaxPct)) / 100) * height;
        return {
            timeMinPct: Math.min(timeMinPct, timeMaxPct),
            timeMaxPct: Math.max(timeMinPct, timeMaxPct),
            frequencyMinPct: Math.min(frequencyMinPct, frequencyMaxPct),
            frequencyMaxPct: Math.max(frequencyMinPct, frequencyMaxPct),
            x,
            y: top,
            width: rectWidth,
            height: Math.max(1, bottom - top),
        };
    };

    const detectDragMode = (pointerX, pointerY, selectionRect) => {
        const threshold = 10;
        const insideX = pointerX >= selectionRect.x && pointerX <= (selectionRect.x + selectionRect.width);
        const insideY = pointerY >= selectionRect.y && pointerY <= (selectionRect.y + selectionRect.height);
        if (!insideX || !insideY) return 'new';

        const nearLeft = Math.abs(pointerX - selectionRect.x) <= threshold;
        const nearRight = Math.abs(pointerX - (selectionRect.x + selectionRect.width)) <= threshold;
        const nearTop = Math.abs(pointerY - selectionRect.y) <= threshold;
        const nearBottom = Math.abs(pointerY - (selectionRect.y + selectionRect.height)) <= threshold;

        if (nearLeft && nearTop) return 'corner-top-left';
        if (nearRight && nearTop) return 'corner-top-right';
        if (nearLeft && nearBottom) return 'corner-bottom-left';
        if (nearRight && nearBottom) return 'corner-bottom-right';
        if (nearLeft) return 'left';
        if (nearRight) return 'right';
        if (nearTop) return 'top';
        if (nearBottom) return 'bottom';
        return 'move';
    };

    const canvasPointToPcts = (pointerX, pointerY, width, height) => ({
        timePct: clampPct((clampCanvasValue(pointerX, width) / Math.max(1, width)) * 100),
        frequencyPct: clampPct(100 - ((clampCanvasValue(pointerY, height) / Math.max(1, height)) * 100)),
    });

    const applyDragSelection = (pointerX, pointerY) => {
        if (!dragState) return;
        const { width, height } = dragState.canvasBounds;
        const pointerPcts = canvasPointToPcts(pointerX, pointerY, width, height);
        const startSelection = dragState.startSelection;
        let nextSelection = {
            timeMinPct: startSelection.timeMinPct,
            timeMaxPct: startSelection.timeMaxPct,
            frequencyMinPct: startSelection.frequencyMinPct,
            frequencyMaxPct: startSelection.frequencyMaxPct,
        };

        if (dragState.mode === 'move') {
            const deltaTimePct = pointerPcts.timePct - dragState.startPointerPcts.timePct;
            const deltaFrequencyPct = pointerPcts.frequencyPct - dragState.startPointerPcts.frequencyPct;
            const shiftedTime = shiftRangePct(startSelection.timeMinPct, startSelection.timeMaxPct, deltaTimePct);
            const shiftedFrequency = shiftRangePct(startSelection.frequencyMinPct, startSelection.frequencyMaxPct, deltaFrequencyPct);
            nextSelection = {
                timeMinPct: shiftedTime.minPct,
                timeMaxPct: shiftedTime.maxPct,
                frequencyMinPct: shiftedFrequency.minPct,
                frequencyMaxPct: shiftedFrequency.maxPct,
            };
        } else if (dragState.mode === 'new') {
            nextSelection = {
                timeMinPct: Math.min(dragState.startPointerPcts.timePct, pointerPcts.timePct),
                timeMaxPct: Math.max(dragState.startPointerPcts.timePct, pointerPcts.timePct),
                frequencyMinPct: Math.min(dragState.startPointerPcts.frequencyPct, pointerPcts.frequencyPct),
                frequencyMaxPct: Math.max(dragState.startPointerPcts.frequencyPct, pointerPcts.frequencyPct),
            };
        } else {
            if (dragState.mode.includes('left')) nextSelection.timeMinPct = Math.min(pointerPcts.timePct, startSelection.timeMaxPct - 0.1);
            if (dragState.mode.includes('right')) nextSelection.timeMaxPct = Math.max(pointerPcts.timePct, startSelection.timeMinPct + 0.1);
            if (dragState.mode.includes('top')) nextSelection.frequencyMaxPct = Math.max(pointerPcts.frequencyPct, startSelection.frequencyMinPct + 0.1);
            if (dragState.mode.includes('bottom')) nextSelection.frequencyMinPct = Math.min(pointerPcts.frequencyPct, startSelection.frequencyMaxPct - 0.1);
            if (dragState.mode === 'left') nextSelection.timeMaxPct = startSelection.timeMaxPct;
            if (dragState.mode === 'right') nextSelection.timeMinPct = startSelection.timeMinPct;
            if (dragState.mode === 'top') nextSelection.frequencyMinPct = startSelection.frequencyMinPct;
            if (dragState.mode === 'bottom') nextSelection.frequencyMaxPct = startSelection.frequencyMaxPct;
        }

        applyOverviewSelection?.({
            timeMinPct: clampPct(Math.min(nextSelection.timeMinPct, nextSelection.timeMaxPct)),
            timeMaxPct: clampPct(Math.max(nextSelection.timeMinPct, nextSelection.timeMaxPct)),
            frequencyMinPct: clampPct(Math.min(nextSelection.frequencyMinPct, nextSelection.frequencyMaxPct)),
            frequencyMaxPct: clampPct(Math.max(nextSelection.frequencyMinPct, nextSelection.frequencyMaxPct)),
        });
    };

    const render = () => {
        if (!panel || !canvas || !context) return;
        const { planeSelections, asset, frameCount, visibleWindow, playbackTimeSec, durationSec } = getPanelState();
        const visible = shouldShow(planeSelections);
        panel.style.display = visible ? 'block' : 'none';
        if (!visible) return;

        const { width, height } = ensureCanvasSize();
        const bitmap = ensureBitmap({ asset, frameCount });
        const selectionRect = selectionRectFromState(planeSelections, width, height);
        const currentTargetLabel = getCurrentSelectionTargetLabel?.() || 'Full Sculpt Mask';
        const renderedSliceLabel = getRenderedSliceLabel?.() || 'Waiting for SpectroTerrain frame data';

        meta.textContent = asset
            ? `${asset.label || asset.id || 'Current asset'} | Full clip frames ${frameCount} | Rendered slice: ${renderedSliceLabel}`
            : 'Load an audio asset to inspect the full-clip spectrogram.';
        if (status) {
            status.textContent = `Target: ${currentTargetLabel} | Blue: Full Sculpt Mask | White: 3D Window`;
        }
        footer.textContent = 'Drag inside the rectangle to move it, drag an edge to trim it, or drag a new box.';

        if (!bitmap) {
            drawMessage(width, height, asset ? 'No FFT terrain data loaded.' : 'Load an audio asset to draw the overview.');
            return;
        }

        context.clearRect(0, 0, width, height);
        context.drawImage(bitmap, 0, 0, width, height);

        const visibleStartPct = frameCount > 1 ? (visibleWindow.start / Math.max(1, frameCount - 1)) * 100 : 0;
        const visibleEndPct = frameCount > 1 ? ((Math.max(visibleWindow.start, visibleWindow.endExclusive - 1)) / Math.max(1, frameCount - 1)) * 100 : 100;
        const visibleX = (Math.min(visibleStartPct, visibleEndPct) / 100) * width;
        const visibleWidth = Math.max(1, (Math.abs(visibleEndPct - visibleStartPct) / 100) * width);
        context.fillStyle = 'rgba(255, 255, 255, 0.08)';
        context.fillRect(visibleX, 0, visibleWidth, height);

        if (durationSec > 0) {
            const playbackPct = clampPct((playbackTimeSec / durationSec) * 100);
            const playbackX = (playbackPct / 100) * width;
            context.strokeStyle = 'rgba(255, 255, 255, 0.75)';
            context.lineWidth = 1.5;
            context.beginPath();
            context.moveTo(playbackX, 0);
            context.lineTo(playbackX, height);
            context.stroke();
        }

        context.fillStyle = 'rgba(8, 17, 28, 0.24)';
        context.strokeStyle = '#93c5fd';
        context.lineWidth = 2;
        context.fillRect(selectionRect.x, selectionRect.y, selectionRect.width, selectionRect.height);
        context.strokeRect(selectionRect.x, selectionRect.y, selectionRect.width, selectionRect.height);

        const handles = [
            [selectionRect.x, selectionRect.y],
            [selectionRect.x + selectionRect.width, selectionRect.y],
            [selectionRect.x, selectionRect.y + selectionRect.height],
            [selectionRect.x + selectionRect.width, selectionRect.y + selectionRect.height],
        ];
        context.fillStyle = '#e0f2fe';
        for (const [handleX, handleY] of handles) {
            context.fillRect(handleX - 3, handleY - 3, 6, 6);
        }
    };

    const handlePointerDown = (event) => {
        const { planeSelections } = getPanelState();
        if (!shouldShow(planeSelections)) return;

        const rect = canvas.getBoundingClientRect();
        const pointerX = (event.clientX - rect.left) * ((canvas.width || rect.width) / Math.max(1, rect.width));
        const pointerY = (event.clientY - rect.top) * ((canvas.height || rect.height) / Math.max(1, rect.height));
        const selectionRect = selectionRectFromState(planeSelections, canvas.width || rect.width, canvas.height || rect.height);
        dragState = {
            mode: detectDragMode(pointerX, pointerY, selectionRect),
            canvasBounds: {
                width: canvas.width || rect.width,
                height: canvas.height || rect.height,
            },
            startPointerPcts: canvasPointToPcts(pointerX, pointerY, canvas.width || rect.width, canvas.height || rect.height),
            startSelection: {
                timeMinPct: selectionRect.timeMinPct,
                timeMaxPct: selectionRect.timeMaxPct,
                frequencyMinPct: selectionRect.frequencyMinPct,
                frequencyMaxPct: selectionRect.frequencyMaxPct,
            },
        };

        onInteractionTargetChange?.({ source: '2d-overview' });

        canvas.setPointerCapture?.(event.pointerId);
        event.preventDefault();
        event.stopPropagation();
    };

    const handlePointerMove = (event) => {
        if (!dragState) return;
        const rect = canvas.getBoundingClientRect();
        const pointerX = (event.clientX - rect.left) * ((canvas.width || rect.width) / Math.max(1, rect.width));
        const pointerY = (event.clientY - rect.top) * ((canvas.height || rect.height) / Math.max(1, rect.height));
        applyDragSelection(pointerX, pointerY);
        event.preventDefault();
        event.stopPropagation();
    };

    const finishPointerDrag = (event) => {
        if (!dragState) return;
        canvas.releasePointerCapture?.(event.pointerId);
        dragState = null;
        onInteractionTargetChange?.({ source: '2d-overview' });
        render();
    };

    canvas?.addEventListener?.('pointerdown', handlePointerDown);
    canvas?.addEventListener?.('pointermove', handlePointerMove);
    canvas?.addEventListener?.('pointerup', finishPointerDrag);
    canvas?.addEventListener?.('pointercancel', finishPointerDrag);

    return {
        clearBitmapCache,
        render,
        refreshData: () => {
            clearBitmapCache();
            render();
        },
        syncVisibility: () => {
            render();
        },
    };
};