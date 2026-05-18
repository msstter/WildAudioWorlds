export const createAppInitialization = ({
    applyInitialState,
    bindRuntimeEvents,
    startAnimationLoop,
    loadInitialAudioAssets,
} = {}) => {
    let initialized = false;

    return {
        initialize: () => {
            if (initialized) return;
            initialized = true;

            applyInitialState?.();
            bindRuntimeEvents?.();
            startAnimationLoop?.();
            void loadInitialAudioAssets?.();
        },
    };
};