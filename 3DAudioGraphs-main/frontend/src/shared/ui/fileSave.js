export const sanitizeFileLabel = (value, fallback = 'selection') => {
    const sanitizedValue = String(value || '')
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '');
    return sanitizedValue || fallback;
};

export const formatCsvCell = (value) => {
    const stringValue = value == null ? '' : String(value);
    return /[",\n]/.test(stringValue)
        ? `"${stringValue.replace(/"/g, '""')}"`
        : stringValue;
};

export const triggerFileSave = async (blob, ext, {
    suggestedName = `recording.${ext}`,
    description = 'Recording',
    windowObject = globalThis.window,
    documentObject = globalThis.document,
    urlObject = globalThis.URL,
} = {}) => {
    const mimeType = blob.type || 'application/octet-stream';
    if (windowObject?.showSaveFilePicker) {
        try {
            const handle = await windowObject.showSaveFilePicker({
                suggestedName,
                types: [{ description, accept: { [mimeType]: [`.${ext}`] } }],
            });
            const writable = await handle.createWritable();
            await writable.write(blob);
            await writable.close();
            return;
        } catch (error) {
            if (error?.name === 'AbortError') return;
        }
    }

    const url = urlObject.createObjectURL(blob);
    const anchor = documentObject.createElement('a');
    anchor.href = url;
    anchor.download = suggestedName;
    anchor.click();
    setTimeout(() => urlObject.revokeObjectURL(url), 10000);
};