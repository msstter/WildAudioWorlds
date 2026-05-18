const applyStyles = (element, styles) => {
    Object.assign(element.style, styles);
    return element;
};

const defaultRequestFrame = (callback) => {
    if (typeof globalThis.requestAnimationFrame === 'function') {
        return globalThis.requestAnimationFrame(callback);
    }
    return setTimeout(callback, 0);
};

export const createDialogService = ({
    documentObject = globalThis.document,
    bodyElement = globalThis.document?.body,
    requestFrame = defaultRequestFrame,
} = {}) => {
    if (!documentObject || !bodyElement) {
        throw new Error('Dialog service requires a document body.');
    }

    const overlay = applyStyles(documentObject.createElement('div'), {
        position: 'fixed',
        inset: '0',
        display: 'none',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(2, 6, 23, 0.72)',
        zIndex: '60',
        pointerEvents: 'auto',
    });

    const card = applyStyles(documentObject.createElement('div'), {
        width: 'min(420px, calc(100vw - 32px))',
        padding: '16px',
        border: '1px solid #334155',
        borderRadius: '10px',
        background: '#0b1220',
        boxShadow: '0 18px 48px rgba(0, 0, 0, 0.42)',
        color: '#e2e8f0',
        fontFamily: 'monospace',
    });

    const titleElement = applyStyles(documentObject.createElement('div'), {
        fontSize: '14px',
        fontWeight: 'bold',
        color: '#fde68a',
    });

    const messageElement = applyStyles(documentObject.createElement('div'), {
        marginTop: '6px',
        color: '#cbd5e1',
        fontSize: '12px',
        lineHeight: '1.45',
    });

    const inputElement = applyStyles(documentObject.createElement('input'), {
        width: '100%',
        marginTop: '12px',
        padding: '8px 10px',
        border: '1px solid #475569',
        borderRadius: '7px',
        background: '#020617',
        color: '#f8fafc',
        fontFamily: 'inherit',
        fontSize: '12px',
    });
    inputElement.type = 'text';

    const actionsElement = applyStyles(documentObject.createElement('div'), {
        display: 'flex',
        justifyContent: 'flex-end',
        gap: '8px',
        marginTop: '14px',
    });

    const cancelButton = applyStyles(documentObject.createElement('button'), {
        padding: '7px 10px',
        border: '1px solid #475569',
        borderRadius: '7px',
        background: 'rgba(15, 23, 42, 0.9)',
        color: '#cbd5e1',
        cursor: 'pointer',
        fontFamily: 'inherit',
        fontSize: '12px',
    });
    cancelButton.type = 'button';

    const confirmButton = applyStyles(documentObject.createElement('button'), {
        padding: '7px 10px',
        border: '1px solid #0f766e',
        borderRadius: '7px',
        background: 'rgba(15, 118, 110, 0.25)',
        color: '#ecfeff',
        cursor: 'pointer',
        fontFamily: 'inherit',
        fontSize: '12px',
    });
    confirmButton.type = 'button';

    actionsElement.appendChild(cancelButton);
    actionsElement.appendChild(confirmButton);
    card.appendChild(titleElement);
    card.appendChild(messageElement);
    card.appendChild(inputElement);
    card.appendChild(actionsElement);
    overlay.appendChild(card);
    bodyElement.appendChild(overlay);

    let activeDialog = null;

    const closeActiveDialog = (result = null) => {
        if (!activeDialog) return;

        const { resolve, keydownHandler } = activeDialog;
        activeDialog = null;
        documentObject.removeEventListener('keydown', keydownHandler, true);
        overlay.style.display = 'none';
        inputElement.value = '';
        cancelButton.onclick = null;
        confirmButton.onclick = null;
        resolve(result);
    };

    card.addEventListener('pointerdown', (event) => {
        event.stopPropagation();
    });
    overlay.addEventListener('pointerdown', (event) => {
        if (event.target === overlay) {
            closeActiveDialog(null);
        }
    });

    const openDialog = ({
        title = '',
        message = '',
        defaultValue = '',
        confirmLabel = 'OK',
        cancelLabel = 'Cancel',
        mode = 'text',
        danger = false,
    } = {}) => new Promise((resolve) => {
        if (activeDialog) {
            closeActiveDialog(null);
        }

        const submit = () => {
            if (mode === 'confirm') {
                closeActiveDialog(true);
                return;
            }
            closeActiveDialog(inputElement.value);
        };
        const cancel = () => {
            closeActiveDialog(null);
        };
        const keydownHandler = (event) => {
            if (!activeDialog) return;
            if (event.key === 'Escape') {
                event.preventDefault();
                cancel();
                return;
            }
            if (event.key === 'Enter') {
                event.preventDefault();
                submit();
            }
        };

        activeDialog = { resolve, keydownHandler };
        titleElement.textContent = title;
        messageElement.textContent = message;
        inputElement.value = defaultValue;
        inputElement.style.display = mode === 'confirm' ? 'none' : '';
        cancelButton.textContent = cancelLabel;
        confirmButton.textContent = confirmLabel;
        confirmButton.style.borderColor = danger ? '#b91c1c' : '#0f766e';
        confirmButton.style.background = danger ? 'rgba(185, 28, 28, 0.26)' : 'rgba(15, 118, 110, 0.25)';
        cancelButton.onclick = cancel;
        confirmButton.onclick = submit;
        overlay.style.display = 'flex';
        documentObject.addEventListener('keydown', keydownHandler, true);

        requestFrame(() => {
            if (mode === 'confirm') {
                confirmButton.focus();
                return;
            }
            inputElement.focus();
            inputElement.select();
        });
    });

    const promptText = async ({
        title = '',
        message = '',
        defaultValue = '',
        confirmLabel = 'OK',
        cancelLabel = 'Cancel',
        fallbackValue = defaultValue,
    } = {}) => {
        const response = await openDialog({
            title,
            message,
            defaultValue,
            confirmLabel,
            cancelLabel,
            mode: 'text',
        });
        if (response === null) return null;
        const trimmed = response.trim();
        return trimmed || fallbackValue;
    };

    const confirm = async ({
        title = '',
        message = '',
        confirmLabel = 'Confirm',
        cancelLabel = 'Cancel',
        danger = false,
    } = {}) => {
        const response = await openDialog({
            title,
            message,
            confirmLabel,
            cancelLabel,
            mode: 'confirm',
            danger,
        });
        return response === true;
    };

    return {
        closeActiveDialog,
        confirm,
        openDialog,
        overlay,
        promptText,
    };
};