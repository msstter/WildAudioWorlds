const clampValue = (value, min, max) => Math.min(Math.max(value, min), max);

export const createFloatingPanelDragManager = ({
    windowObject = globalThis.window,
    documentObject = globalThis.document,
    bodyElement = globalThis.document?.body,
} = {}) => {
    if (!windowObject || !documentObject || !bodyElement) {
        throw new Error('Floating panel drag manager requires a window and document body.');
    }

    let activeDrag = null;

    const clampPanelPosition = (element, nextLeft, nextTop) => {
        const panelWidth = element.offsetWidth || Math.max(200, Number.parseFloat(element.style.width) || 0);
        const panelHeight = element.offsetHeight || Math.max(60, Number.parseFloat(element.style.height) || 0);
        const clampedLeft = clampValue(nextLeft, 0, Math.max(0, windowObject.innerWidth - panelWidth));
        const clampedTop = clampValue(nextTop, 0, Math.max(0, windowObject.innerHeight - panelHeight));
        return { left: clampedLeft, top: clampedTop };
    };

    const setPanelPosition = (element, nextLeft, nextTop) => {
        const { left, top } = clampPanelPosition(element, nextLeft, nextTop);
        element.style.left = `${left}px`;
        element.style.top = `${top}px`;
    };

    const startPanelDrag = (event, element, handleElement) => {
        if (event.button !== 0) return;

        const startLeft = Number.parseFloat(element.style.left) || 0;
        const startTop = Number.parseFloat(element.style.top) || 0;
        activeDrag = {
            pointerId: event.pointerId,
            element,
            handleElement,
            startPointerX: event.clientX,
            startPointerY: event.clientY,
            startLeft,
            startTop,
        };

        bodyElement.style.userSelect = 'none';
        handleElement.style.cursor = 'grabbing';
        handleElement.setPointerCapture?.(event.pointerId);
        event.preventDefault();
        event.stopPropagation();
    };

    const updatePanelDrag = (event) => {
        if (!activeDrag || event.pointerId !== activeDrag.pointerId) return;

        const deltaX = event.clientX - activeDrag.startPointerX;
        const deltaY = event.clientY - activeDrag.startPointerY;
        setPanelPosition(
            activeDrag.element,
            activeDrag.startLeft + deltaX,
            activeDrag.startTop + deltaY,
        );
        event.preventDefault();
    };

    const finishPanelDrag = (event) => {
        if (!activeDrag || (event && event.pointerId !== undefined && event.pointerId !== activeDrag.pointerId)) return;

        activeDrag.handleElement.releasePointerCapture?.(activeDrag.pointerId);
        activeDrag.handleElement.style.cursor = 'grab';
        bodyElement.style.userSelect = '';
        activeDrag = null;
    };

    const enablePanelDrag = (element, handleElement) => {
        handleElement.addEventListener('pointerdown', (event) => {
            startPanelDrag(event, element, handleElement);
        });
    };

    windowObject.addEventListener('pointermove', updatePanelDrag, { capture: true });
    windowObject.addEventListener('pointerup', finishPanelDrag, { capture: true });
    windowObject.addEventListener('pointercancel', finishPanelDrag, { capture: true });

    return {
        clampPanelPosition,
        enablePanelDrag,
        finishPanelDrag,
        setPanelPosition,
    };
};