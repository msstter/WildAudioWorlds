import * as THREE from 'three';
import { CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js';

const MAX_TRACK_EXTENSION_MULTIPLIER = 5.5;
const MIN_FREQUENCY_OVERHANG = 8;
const MIN_AMPLITUDE_OVERHANG = 6;

export const createTerrainAxes = ({
    scene,
    labelRenderer,
    terrainVisualizer,
    settings,
    isTerrainMode,
    terrainStretchSettings,
    terrainScaleBoundsFromSettings,
    formatTerrainAxisValue,
} = {}) => {
    let terrainAxesObject = null;
    let terrainAxesMaterial = null;
    let terrainAxisLabelGroup = null;
    let terrainAxisLabelEntries = [];

    const cleanupLabelEntries = (entries) => {
        for (const entry of entries) {
            if (entry?.div?.parentNode) {
                entry.div.parentNode.removeChild(entry.div);
            }
        }
    };

    const disposeAxes = () => {
        if (terrainAxesObject) {
            cleanupLabelEntries(terrainAxisLabelEntries);
            scene.remove(terrainAxesObject);
            terrainAxesObject.traverse((child) => {
                if (child.geometry) child.geometry.dispose();
                if (child.material) child.material.dispose();
            });
            terrainAxesObject.clear?.();
            terrainAxesObject = null;
            terrainAxesMaterial = null;
            terrainAxisLabelEntries = [];
        }

        if (terrainAxisLabelGroup) {
            terrainAxisLabelGroup.parent?.remove(terrainAxisLabelGroup);
            terrainAxisLabelGroup.clear?.();
            terrainAxisLabelGroup = null;
        }
    };

    const applyGraphSettings = () => {
        const inTerrainMode = isTerrainMode();
        const showLines = settings.terrainShowAxesLines && inTerrainMode;
        const showText = settings.showLabels && settings.terrainShowAxesText && inTerrainMode;

        if (terrainAxesObject) {
            terrainAxesObject.visible = showLines;
            if (terrainAxesMaterial) terrainAxesMaterial.color.set(settings.terrainAxesColor);
        }
        if (terrainAxisLabelGroup) terrainAxisLabelGroup.visible = showText;
        for (const entry of terrainAxisLabelEntries) {
            if (entry.label) entry.label.visible = showText;
        }
    };

    const buildAxes = () => {
        for (const node of labelRenderer.domElement.querySelectorAll('.axis-label[data-axis-pipeline="terrain"]')) {
            node.remove();
        }

        disposeAxes();

        const { width: terrainWidth, height: terrainHeight, zDepth } = terrainVisualizer.getTerrainWorldBounds();
        const stretch = terrainStretchSettings();
        const width = terrainWidth * stretch.x;
        const height = terrainHeight * stretch.y;
        const depth = zDepth * stretch.z;
        const halfWidth = width / 2;
        const halfHeight = height / 2;
        const halfDepth = depth / 2;
        const terrainScaleBounds = terrainScaleBoundsFromSettings();
        const totalFrameCount = Math.max(0, terrainVisualizer.getFrameDataCount?.() ?? 0);
        const alignedFrameWindow = terrainVisualizer.getAlignedFrameWindow?.() || {
            start: 0,
            endExclusive: Math.max(1, Math.round(settings.terrainTimeDepth || 180)),
        };
        const currentWindowFrameSpan = Math.max(
            1,
            Math.round(Math.abs((terrainScaleBounds.timeMax ?? 0) - (terrainScaleBounds.timeMin ?? 0))),
        );
        const framesBeforeWindow = Math.max(0, Math.round(alignedFrameWindow.start || 0));
        const framesAfterWindow = totalFrameCount > 0
            ? Math.max(0, totalFrameCount - Math.max(framesBeforeWindow, Math.round(alignedFrameWindow.endExclusive || 0)))
            : 0;
        const rawPastMultiplier = framesBeforeWindow / currentWindowFrameSpan;
        const rawFutureMultiplier = framesAfterWindow / currentWindowFrameSpan;
        const dominantTrackMultiplier = Math.max(rawPastMultiplier, rawFutureMultiplier, 1);
        const trackCompression = dominantTrackMultiplier > MAX_TRACK_EXTENSION_MULTIPLIER
            ? (MAX_TRACK_EXTENSION_MULTIPLIER / dominantTrackMultiplier)
            : 1;
        const pastDepth = depth * rawPastMultiplier * trackCompression;
        const futureDepth = depth * rawFutureMultiplier * trackCompression;
        const planeOverhangX = Math.max(MIN_FREQUENCY_OVERHANG, width * 0.08);
        const planeOverhangY = Math.max(MIN_AMPLITUDE_OVERHANG, height * 0.12);
        const floorHalfWidth = halfWidth + planeOverhangX;
        const playheadHalfWidth = halfWidth + planeOverhangX;
        const playheadMinY = -halfHeight;
        const playheadMaxY = halfHeight + planeOverhangY;
        const frontZ = halfDepth;
        const backZ = -halfDepth;
        const trackFrontZ = frontZ + futureDepth;
        const trackBackZ = backZ - pastDepth;

        const boxGeometry = new THREE.BoxGeometry(width, height, depth);
        const edges = new THREE.EdgesGeometry(boxGeometry);
        boxGeometry.dispose();
        const material = new THREE.LineBasicMaterial({ color: settings.terrainAxesColor });
        terrainAxesMaterial = material;
        const box = new THREE.LineSegments(edges, material);

        const terrainAxesRoot = new THREE.Group();
        terrainAxesRoot.position.set(0, height / 2, -depth / 2);
        terrainAxesRoot.add(box);

        const guidePoints = [];
        const addGuideSegment = (startX, startY, startZ, endX, endY, endZ) => {
            guidePoints.push(
                new THREE.Vector3(startX, startY, startZ),
                new THREE.Vector3(endX, endY, endZ),
            );
        };

        // Extend the floor Frequency x Time plane into a larger track so the terrain slab reads as a moving playhead area.
        addGuideSegment(-floorHalfWidth, -halfHeight, trackFrontZ, floorHalfWidth, -halfHeight, trackFrontZ);
        addGuideSegment(floorHalfWidth, -halfHeight, trackFrontZ, floorHalfWidth, -halfHeight, trackBackZ);
        addGuideSegment(floorHalfWidth, -halfHeight, trackBackZ, -floorHalfWidth, -halfHeight, trackBackZ);
        addGuideSegment(-floorHalfWidth, -halfHeight, trackBackZ, -floorHalfWidth, -halfHeight, trackFrontZ);

        // Add top and bottom time rails so the current terrain slab feels mounted on a larger progress track.
        addGuideSegment(-halfWidth, halfHeight, frontZ, -halfWidth, halfHeight, trackFrontZ);
        addGuideSegment(halfWidth, halfHeight, frontZ, halfWidth, halfHeight, trackFrontZ);
        addGuideSegment(-halfWidth, halfHeight, backZ, -halfWidth, halfHeight, trackBackZ);
        addGuideSegment(halfWidth, halfHeight, backZ, halfWidth, halfHeight, trackBackZ);
        addGuideSegment(-halfWidth, -halfHeight, frontZ, -halfWidth, -halfHeight, trackFrontZ);
        addGuideSegment(halfWidth, -halfHeight, frontZ, halfWidth, -halfHeight, trackFrontZ);
        addGuideSegment(-halfWidth, -halfHeight, backZ, -halfWidth, -halfHeight, trackBackZ);
        addGuideSegment(halfWidth, -halfHeight, backZ, halfWidth, -halfHeight, trackBackZ);
        addGuideSegment(0, -halfHeight, trackFrontZ, 0, -halfHeight, trackBackZ);

        // Enlarge the Frequency x Amplitude playhead face slightly beyond the slab so the cross-section reads as the active view area.
        addGuideSegment(-playheadHalfWidth, playheadMinY, frontZ, playheadHalfWidth, playheadMinY, frontZ);
        addGuideSegment(playheadHalfWidth, playheadMinY, frontZ, playheadHalfWidth, playheadMaxY, frontZ);
        addGuideSegment(playheadHalfWidth, playheadMaxY, frontZ, -playheadHalfWidth, playheadMaxY, frontZ);
        addGuideSegment(-playheadHalfWidth, playheadMaxY, frontZ, -playheadHalfWidth, playheadMinY, frontZ);

        if (guidePoints.length > 0) {
            const guideGeometry = new THREE.BufferGeometry().setFromPoints(guidePoints);
            const guideLines = new THREE.LineSegments(guideGeometry, material);
            terrainAxesRoot.add(guideLines);
        }

        terrainAxesObject = terrainAxesRoot;
        terrainAxisLabelGroup = new THREE.Group();
        terrainAxisLabelGroup.position.copy(terrainAxesRoot.position);
        scene.add(terrainAxesRoot);
        scene.add(terrainAxisLabelGroup);

        terrainAxisLabelEntries = [];
        const createLabel = (text, type, x, y, z) => {
            const div = document.createElement('div');
            div.className = 'axis-label';
            div.dataset.axisPipeline = 'terrain';
            div.textContent = text;
            const label = new CSS2DObject(div);
            label.position.set(x, y, z);
            terrainAxisLabelGroup.add(label);
            terrainAxisLabelEntries.push({ div, type, label });
        };

        createLabel(`${settings.terrainAxesTextFreq}: Low (${formatTerrainAxisValue(terrainScaleBounds.frequencyMin)})`, 'freq', -playheadHalfWidth, playheadMinY, frontZ);
        createLabel(`${settings.terrainAxesTextFreq}: High (${formatTerrainAxisValue(terrainScaleBounds.frequencyMax)})`, 'freq', playheadHalfWidth, playheadMinY, frontZ);
        createLabel(`${settings.terrainAxesTextAmp}: Low (${formatTerrainAxisValue(terrainScaleBounds.amplitudeMin)})`, 'amp', -playheadHalfWidth, playheadMinY, frontZ);
        createLabel(`${settings.terrainAxesTextAmp}: High (${formatTerrainAxisValue(terrainScaleBounds.amplitudeMax)})`, 'amp', -playheadHalfWidth, playheadMaxY, frontZ);

        if (totalFrameCount > 1) {
            createLabel(`${settings.terrainAxesTextTime}: Clip End (${formatTerrainAxisValue(totalFrameCount - 1)})`, 'time-end', playheadHalfWidth, playheadMinY, trackFrontZ);
            createLabel(`${settings.terrainAxesTextTime}: Clip Start (0)`, 'time-start', playheadHalfWidth, playheadMinY, trackBackZ);
        } else {
            createLabel(`${settings.terrainAxesTextTime}: Now (${formatTerrainAxisValue(terrainScaleBounds.timeMin)})`, 'time', playheadHalfWidth, playheadMinY, frontZ);
            createLabel(`${settings.terrainAxesTextTime}: Past (${formatTerrainAxisValue(terrainScaleBounds.timeMax)})`, 'time', playheadHalfWidth, playheadMinY, backZ);
        }

        applyGraphSettings();
    };

    return {
        applyGraphSettings,
        buildAxes,
    };
};