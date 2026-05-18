const clampUnit = (value) => Math.min(Math.max(value, 0), 1);

export const createTransportMarkerLayer = ({
    progressElement,
    documentObject = globalThis.document,
} = {}) => {
    let hostElement = null;
    let layerElement = null;

    const ensureLayerElement = () => {
        if (layerElement) return layerElement;
        if (!progressElement?.parentElement || !documentObject) return null;

        const wrapper = documentObject.createElement('div');
        wrapper.style.position = 'relative';
        wrapper.style.display = 'flex';
        wrapper.style.flex = '1 1 auto';
        wrapper.style.alignItems = 'center';
        wrapper.style.minWidth = '0';

        progressElement.parentElement.insertBefore(wrapper, progressElement);
        wrapper.appendChild(progressElement);
        progressElement.style.width = '100%';
        progressElement.style.flex = '1 1 auto';

        const markerLayer = documentObject.createElement('div');
        markerLayer.style.position = 'absolute';
        markerLayer.style.inset = '0';
        markerLayer.style.display = 'none';
        markerLayer.style.pointerEvents = 'none';
        wrapper.appendChild(markerLayer);

        hostElement = wrapper;
        layerElement = markerLayer;
        return layerElement;
    };

    const clearMarkers = () => {
        const markerLayer = ensureLayerElement();
        if (!markerLayer) return null;
        markerLayer.replaceChildren();
        markerLayer.style.display = 'none';
        return markerLayer;
    };

    const renderMarkers = ({
        visible = false,
        markers = [],
        durationSec = 0,
        markerColor = 'rgba(34, 211, 238, 0.92)',
        markerShadow = '0 0 10px rgba(34, 211, 238, 0.45)',
        titleForMarker = () => '',
        onMarkerClick = () => {},
    } = {}) => {
        const markerLayer = ensureLayerElement();
        if (!markerLayer) return null;

        markerLayer.replaceChildren();
        markerLayer.style.display = visible ? 'block' : 'none';
        if (!visible || !Number.isFinite(durationSec) || durationSec <= 0) return markerLayer;

        for (const markerData of markers) {
            if (!Number.isFinite(markerData?.timeSec)) continue;

            const marker = documentObject.createElement('button');
            marker.type = 'button';
            marker.style.position = 'absolute';
            marker.style.left = `${clampUnit(markerData.timeSec / durationSec) * 100}%`;
            marker.style.top = '0';
            marker.style.bottom = '0';
            marker.style.width = '12px';
            marker.style.transform = 'translateX(-50%)';
            marker.style.padding = '0';
            marker.style.border = 'none';
            marker.style.background = 'transparent';
            marker.style.cursor = 'pointer';
            marker.style.pointerEvents = 'auto';
            marker.style.zIndex = '1';

            const markerTitle = titleForMarker(markerData) || '';
            marker.title = markerTitle;
            marker.setAttribute('aria-label', markerTitle);

            const markerLine = documentObject.createElement('span');
            markerLine.style.position = 'absolute';
            markerLine.style.left = '50%';
            markerLine.style.top = '18%';
            markerLine.style.bottom = '18%';
            markerLine.style.width = '2px';
            markerLine.style.transform = 'translateX(-50%)';
            markerLine.style.borderRadius = '999px';
            markerLine.style.background = markerColor;
            markerLine.style.boxShadow = markerShadow;
            marker.appendChild(markerLine);

            marker.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                onMarkerClick(markerData, event);
            });

            markerLayer.appendChild(marker);
        }

        return markerLayer;
    };

    return {
        clearMarkers,
        ensureLayerElement,
        getHostElement: () => hostElement,
        getLayerElement: () => layerElement ?? ensureLayerElement(),
        renderMarkers,
    };
};