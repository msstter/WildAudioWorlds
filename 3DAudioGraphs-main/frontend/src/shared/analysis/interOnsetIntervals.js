export const buildInterOnsetIntervals = (onsetEvents) => {
    const interOnsetIntervals = [];

    for (let onsetIndex = 1; onsetIndex < onsetEvents.length; onsetIndex++) {
        const previousEvent = onsetEvents[onsetIndex - 1];
        const currentEvent = onsetEvents[onsetIndex];
        interOnsetIntervals.push({
            onsetIndex,
            fromPointIndex: previousEvent.pointIndex,
            toPointIndex: currentEvent.pointIndex,
            fromTimeSec: previousEvent.timeSec,
            toTimeSec: currentEvent.timeSec,
            intervalSec: Math.max(0, currentEvent.timeSec - previousEvent.timeSec),
        });
    }

    return interOnsetIntervals;
};