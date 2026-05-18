export const DEFAULT_KEYBOARD_HOTKEYS = {
    togglePlayPause: 'Space',
    toggleFullscreen: 'KeyF',
    seekForward: 'ArrowRight',
    seekBackward: 'ArrowLeft',
    toggleRecordControl: 'KeyR',
    playFromBeginning: 'KeyB',
    toggleSpeedMenu: 'KeyS',
    toggleFpvMode: 'KeyY',
    fpvMoveForward: 'KeyW',
    fpvMoveBackward: 'KeyS',
    fpvMoveLeft: 'KeyA',
    fpvMoveRight: 'KeyD',
    fpvMoveUp: 'Space',
    fpvMoveDown: 'KeyC',
    fpvSprint: 'ShiftLeft',
    fpvPlayPause: 'KeyE',
    captureCameraKeyframe: 'KeyK',
    nextCameraKeyframe: 'ArrowUp',
    previousCameraKeyframe: 'ArrowDown',
    toggleSidebarOrCloseMenus: 'Escape',
};

export const DEFAULT_POINTER_BINDINGS = {
    pointerVerticalScrollAction: 'Zoom Camera',
    pointerVerticalScrollFlipDirection: false,
    pointerShiftVerticalScrollAction: 'Seek Playback',
    pointerShiftVerticalScrollFlipDirection: false,
    pointerMouseHorizontalScrollAction: 'Seek Playback',
    pointerMouseHorizontalScrollFlipDirection: false,
    pointerTrackpadHorizontalScrollAction: 'Disabled',
    pointerTrackpadHorizontalScrollFlipDirection: false,
    pointerLeftMouseButtonAction: 'Rotate Camera',
    pointerMiddleMouseButtonAction: 'Zoom Camera',
    pointerRightMouseButtonAction: 'Pan Camera',
};

export const DEFAULT_INPUT_BINDINGS = {
    ...DEFAULT_KEYBOARD_HOTKEYS,
    ...DEFAULT_POINTER_BINDINGS,
};

const POINTER_SCROLL_ACTIONS = ['Zoom Camera', 'Seek Playback', 'Disabled'];
const POINTER_HORIZONTAL_SCROLL_ACTIONS = ['Seek Playback', 'Disabled'];
const POINTER_MOUSE_BUTTON_ACTIONS = ['Rotate Camera', 'Zoom Camera', 'Pan Camera', 'Disabled'];

export const POINTER_SCROLL_BINDING_META = [
    {
        key: 'pointerVerticalScrollAction',
        flipKey: 'pointerVerticalScrollFlipDirection',
        label: 'Vertical Scroll',
        detail: 'Mouse wheel / trackpad two-finger up-down',
        options: POINTER_SCROLL_ACTIONS,
    },
    {
        key: 'pointerShiftVerticalScrollAction',
        flipKey: 'pointerShiftVerticalScrollFlipDirection',
        label: 'Shift + Vertical Scroll',
        detail: 'Held Shift + wheel / trackpad two-finger up-down',
        options: POINTER_SCROLL_ACTIONS,
    },
    {
        key: 'pointerMouseHorizontalScrollAction',
        flipKey: 'pointerMouseHorizontalScrollFlipDirection',
        label: 'Mouse Horizontal Scroll',
        detail: 'Horizontal wheel / tilt wheel',
        options: POINTER_HORIZONTAL_SCROLL_ACTIONS,
    },
    {
        key: 'pointerTrackpadHorizontalScrollAction',
        flipKey: 'pointerTrackpadHorizontalScrollFlipDirection',
        label: 'Trackpad Horizontal Scroll',
        detail: 'Trackpad two-finger left-right',
        options: POINTER_HORIZONTAL_SCROLL_ACTIONS,
    },
];

export const POINTER_MOUSE_BUTTON_BINDING_META = [
    {
        key: 'pointerLeftMouseButtonAction',
        label: 'Left Mouse Drag',
        detail: 'Canvas drag with the primary mouse button',
        options: POINTER_MOUSE_BUTTON_ACTIONS,
    },
    {
        key: 'pointerMiddleMouseButtonAction',
        label: 'Middle Mouse Drag',
        detail: 'Canvas drag with the middle mouse button',
        options: POINTER_MOUSE_BUTTON_ACTIONS,
    },
    {
        key: 'pointerRightMouseButtonAction',
        label: 'Right Mouse Drag',
        detail: 'Canvas drag with the secondary mouse button',
        options: POINTER_MOUSE_BUTTON_ACTIONS,
    },
];