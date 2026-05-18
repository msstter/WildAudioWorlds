import * as THREE from 'three';

const SPHERE_SCALE_MIN = 0.3;
const SPHERE_SCALE_MAX = 4.0;
const LINE_THICKNESS_TO_WORLD = 0.06;
const FRAME_TIMING_COLUMN_NAMES = [
    'Frame_Index',
    'Time_Start_Sec',
    'Time_Center_Sec',
    'Time_End_Sec',
    'Sample_Start',
    'Sample_Center',
    'Sample_End',
];
const FRAME_TIMING_COLUMN_SET = new Set(FRAME_TIMING_COLUMN_NAMES);

export class Visualizer {
    constructor(scene) {
        this.scene = scene;
        this.isVisible = true;
        this.points        = [];
        this.frameRecords  = [];
        this.selectedFrameIndices = new Set();
        this.dataColumnsRaw = {};        // { columnName: number[] }
        this.dataColumnsNorm = {};       // { columnName: normalised number[] }
        this.modifierColumns = [];       // CSV columns available for modifiers (excludes XYZ)
        this._frameCenterTimesSec = [];
        this._hasExplicitFrameTiming = false;
        this._selectionHighlightColor = new THREE.Color('#ffd166');
        this._activeOnsetPulses = new Map();
        this._pulseNowMs = 0;
        this._pulseRevision = 0;
        this._prevPulseRevision = 0;

        // ── Existing line (stable base behavior) ───────────────────
        this.geometry = new THREE.BufferGeometry();
        this.material = new THREE.LineBasicMaterial({
            color: 0x00ffcc,
            linewidth: 2,
            vertexColors: true,
            transparent: true,
            opacity: 0.85,
        });
        this.line = new THREE.LineSegments(this.geometry, this.material);
        this.line.frustumCulled = false;
        this.scene.add(this.line);

        this.accumulatedGroup = new THREE.Group();
        this.scene.add(this.accumulatedGroup);

        // Overlay enhancer mesh for per-segment, data-baked thickness.
        this.lineEnhancerMesh = null;
        this._lineEnhancerUp = new THREE.Vector3(0, 1, 0);
        this._lineEnhancerDummy = new THREE.Object3D();
        this._lineEnhancerZeroMatrix = new THREE.Matrix4().makeScale(0, 0, 0);

        // ── InstancedMesh (built once loadData runs) ───────────────
        this.instancedMesh = null;

        // Settings reference (injected by main.js via setSettings)
        this.settings = null;

        // Audio waveform data for line breathing effect
        this.audioWaveform = null;

        // Per-frame tracking — reset when loadData() is called
        this._currentIndex        = 0;
        this._prevCurrentIndex    = undefined;
        this._prevNodeColorKey    = '';
        this._prevNodeScaleKey    = '';
        // Tracks which settings were active last frame so we can detect changes
        this._prevEnableDecay     = undefined;
        this._prevDecayTailLength = undefined;
        this._prevEnableDull      = undefined;
        this._prevDullTailLength  = undefined;
        this._prevDeconstructNode = undefined;
    }

    loadData(csvText) {
        const lines   = csvText.split('\n');
        const headers = lines[0].split(',').map(label => label.trim());
        const dataLines = lines.slice(1);

        let rawPoints  = [];
        let min = new THREE.Vector3( Infinity,  Infinity,  Infinity);
        let max = new THREE.Vector3(-Infinity, -Infinity, -Infinity);

        const numericColumns = headers.map(() => []);

        dataLines.forEach(line => {
            if (line.trim() === '') return;
            const parts = line.split(',').map(parseFloat);
            const [x, y, z] = parts;
            const pt = new THREE.Vector3(x, y, z);
            rawPoints.push(pt);
            min.min(pt);
            max.max(pt);

            for (let i = 0; i < headers.length; i++) {
                const v = parts[i];
                numericColumns[i].push(Number.isFinite(v) ? v : 0);
            }
        });

        // ── Normalise 3-D positions (unchanged logic) ──────────────
        const center = new THREE.Vector3().addVectors(min, max).multiplyScalar(0.5);
        const size   = new THREE.Vector3().subVectors(max, min);
        const maxDim = Math.max(size.x, size.y, size.z);
        const scale  = 100 / maxDim;

        this.points = rawPoints.map(pt => new THREE.Vector3(
            (pt.x - center.x) * scale,
            (pt.y - center.y) * scale,
            (pt.z - center.z) * scale
        ));

        // ── Normalise Volume + Pitch to [0, 1] ─────────────────────
        const normalise = arr => {
            const lo    = arr.reduce((a, b) => Math.min(a, b),  Infinity);
            const hi    = arr.reduce((a, b) => Math.max(a, b), -Infinity);
            const range = (hi - lo) || 1;
            return arr.map(v => (v - lo) / range);
        };

        this.dataColumnsRaw = {};
        this.dataColumnsNorm = {};
        this.selectedFrameIndices = new Set();
        this.clearOnsetPulses();
        headers.forEach((h, i) => {
            const raw = numericColumns[i] || [];
            this.dataColumnsRaw[h] = raw;
            this.dataColumnsNorm[h] = normalise(raw);
        });
        this.frameRecords = this._buildFrameRecords(headers, numericColumns, rawPoints.length);
        this._frameCenterTimesSec = this.frameRecords.map((record) => record.timeCenterSec);
        this.modifierColumns = headers.slice(3).filter((header) => !FRAME_TIMING_COLUMN_SET.has(header));

        // Clear prior active meshes before loading new data.
        this._disposeActiveMeshes();

        // ── Build InstancedMesh now that count is known ────────────
        this._buildInstancedMesh();
        this._buildLineEnhancerMesh();

        return {
            min,
            max,
            visualSize: size.clone().multiplyScalar(scale),
            axisLabels: headers,
            modifierColumns: this.modifierColumns.slice()
        };
    }

    clearData() {
        this.points = [];
        this.frameRecords = [];
        this.selectedFrameIndices = new Set();
        this.dataColumnsRaw = {};
        this.dataColumnsNorm = {};
        this.modifierColumns = [];
        this._frameCenterTimesSec = [];
        this._hasExplicitFrameTiming = false;
        this.audioWaveform = null;
        this._currentIndex = 0;
        this._prevCurrentIndex = undefined;
        this.clearOnsetPulses();
        this._disposeActiveMeshes();
    }

    _buildFrameRecords(headers, numericColumns, rowCount) {
        const headerIndexByName = new Map(headers.map((header, index) => [header, index]));
        const hasExplicitTiming = FRAME_TIMING_COLUMN_NAMES.every((columnName) => headerIndexByName.has(columnName));
        this._hasExplicitFrameTiming = hasExplicitTiming;

        const getColumn = (columnName) => {
            const columnIndex = headerIndexByName.get(columnName);
            return Number.isInteger(columnIndex) ? (numericColumns[columnIndex] || []) : [];
        };

        const frameIndices = getColumn('Frame_Index');
        const timeStartsSec = getColumn('Time_Start_Sec');
        const timeCentersSec = getColumn('Time_Center_Sec');
        const timeEndsSec = getColumn('Time_End_Sec');
        const sampleStarts = getColumn('Sample_Start');
        const sampleCenters = getColumn('Sample_Center');
        const sampleEnds = getColumn('Sample_End');

        return Array.from({ length: rowCount }, (_, rowIndex) => ({
            rowIndex,
            frameIndex: hasExplicitTiming && Number.isFinite(frameIndices[rowIndex])
                ? Math.round(frameIndices[rowIndex])
                : rowIndex,
            timeStartSec: hasExplicitTiming && Number.isFinite(timeStartsSec[rowIndex])
                ? timeStartsSec[rowIndex]
                : null,
            timeCenterSec: hasExplicitTiming && Number.isFinite(timeCentersSec[rowIndex])
                ? timeCentersSec[rowIndex]
                : null,
            timeEndSec: hasExplicitTiming && Number.isFinite(timeEndsSec[rowIndex])
                ? timeEndsSec[rowIndex]
                : null,
            sampleStart: hasExplicitTiming && Number.isFinite(sampleStarts[rowIndex])
                ? Math.round(sampleStarts[rowIndex])
                : null,
            sampleCenter: hasExplicitTiming && Number.isFinite(sampleCenters[rowIndex])
                ? Math.round(sampleCenters[rowIndex])
                : null,
            sampleEnd: hasExplicitTiming && Number.isFinite(sampleEnds[rowIndex])
                ? Math.round(sampleEnds[rowIndex])
                : null,
        }));
    }

    hasFrameTiming() {
        return this._hasExplicitFrameTiming && this._frameCenterTimesSec.length === this.points.length;
    }

    getFrameRecordAtIndex(index) {
        if (!this.frameRecords.length) return null;
        const safeIndex = Math.max(0, Math.min(this.frameRecords.length - 1, Math.round(index)));
        return this.frameRecords[safeIndex] || null;
    }

    getFrameRecordForInstanceId(instanceId) {
        return this.getFrameRecordAtIndex(instanceId);
    }

    setSelectedFrameIndices(indices) {
        const nextSelected = new Set();
        for (const index of indices || []) {
            if (!Number.isFinite(index)) continue;
            const rounded = Math.round(index);
            if (rounded < 0 || rounded >= this.points.length) continue;
            nextSelected.add(rounded);
        }
        this.selectedFrameIndices = nextSelected;
        this.clearOnsetPulses();

        if (!this.instancedMesh) return;
        const enableDull = this.settings ? this.settings.enableDull : false;
        const dullTailLength = this.settings ? Math.max(1, Math.floor(this.settings.dullTailLength)) : 120;
        this._refreshColors(this._currentIndex, enableDull, dullTailLength);
    }

    clearOnsetPulses() {
        if (!this._activeOnsetPulses.size) return;
        this._activeOnsetPulses.clear();
        this._pulseRevision += 1;
    }

    triggerOnsetPulse(frameIndex, nowMs = performance.now()) {
        if (!Number.isFinite(frameIndex)) return;
        const roundedFrameIndex = Math.round(frameIndex);
        if (roundedFrameIndex < 0 || roundedFrameIndex >= this.points.length) return;

        const durationMs = Math.max(16, Number(this.settings?.nodeFlashDurationMs) || 180);
        this._activeOnsetPulses.set(roundedFrameIndex, {
            startMs: nowMs,
            endMs: nowMs + durationMs,
        });
        this._pulseRevision += 1;
    }

    _pruneExpiredOnsetPulses(nowMs = this._pulseNowMs) {
        let removedAny = false;
        for (const [frameIndex, pulse] of this._activeOnsetPulses.entries()) {
            if (pulse.endMs <= nowMs) {
                this._activeOnsetPulses.delete(frameIndex);
                removedAny = true;
            }
        }
        if (removedAny) this._pulseRevision += 1;
    }

    _onsetPulseIntensityAt(frameIndex, nowMs = this._pulseNowMs) {
        if (!this.settings?.enableNodeFlash) return 0;

        const pulse = this._activeOnsetPulses.get(frameIndex);
        if (!pulse) return 0;

        const durationMs = Math.max(1, pulse.endMs - pulse.startMs);
        const remainingRatio = (pulse.endMs - nowMs) / durationMs;
        return Math.max(0, Math.min(1, remainingRatio));
    }

    getFrameTimeAtIndex(index, fallbackDurationSec = 0) {
        if (this.points.length === 0) return 0;

        const safeIndex = Math.max(0, Math.min(this.points.length - 1, Math.round(index)));
        if (this.hasFrameTiming()) {
            return this._frameCenterTimesSec[safeIndex] ?? 0;
        }

        if (Number.isFinite(fallbackDurationSec) && fallbackDurationSec > 0) {
            const denominator = Math.max(1, this.points.length - 1);
            return (safeIndex / denominator) * fallbackDurationSec;
        }

        return 0;
    }

    getFrameIndexAtTime(timeSec, fallbackDurationSec = 0) {
        if (this.points.length === 0) return 0;

        const safeTimeSec = Number.isFinite(timeSec) ? Math.max(0, timeSec) : 0;
        if (this.hasFrameTiming()) {
            const times = this._frameCenterTimesSec;
            const lastIndex = times.length - 1;
            if (lastIndex <= 0) return 0;
            if (safeTimeSec <= times[0]) return 0;
            if (safeTimeSec >= times[lastIndex]) return lastIndex;

            let low = 0;
            let high = lastIndex;
            while (low < high) {
                const mid = Math.floor((low + high) / 2);
                if (times[mid] < safeTimeSec) {
                    low = mid + 1;
                } else {
                    high = mid;
                }
            }

            if (low <= 0) return 0;
            const previous = low - 1;
            return Math.abs(times[low] - safeTimeSec) <= Math.abs(safeTimeSec - times[previous])
                ? low
                : previous;
        }

        if (Number.isFinite(fallbackDurationSec) && fallbackDurationSec > 0) {
            const progress = Math.max(0, Math.min(1, safeTimeSec / fallbackDurationSec));
            return Math.max(0, Math.min(this.points.length - 1, Math.floor(progress * this.points.length)));
        }

        return 0;
    }

    syncToTime(timeSec, fallbackDurationSec = 0) {
        if (this.points.length === 0) return;
        if (!this.isVisible) return;

        const currentIndex = this.getFrameIndexAtTime(timeSec, fallbackDurationSec);
        const count = this.points.length;
        const exactProgress = Math.max(0, Math.min(1, (currentIndex + 0.5) / count));
        this.syncToProgress(exactProgress);
    }

    _normalisedColumn(columnName) {
        if (columnName && this.dataColumnsNorm[columnName]) return this.dataColumnsNorm[columnName];
        const first = this.modifierColumns[0];
        if (first && this.dataColumnsNorm[first]) return this.dataColumnsNorm[first];
        return new Array(this.points.length).fill(0);
    }

    _nodeScaleAt(i) {
        const s = this.settings || {};
        if (!s.showNodeScale) return 1;
        const data = this._normalisedColumn(s.nodeScaleDataColumn);
        const lo = Number.isFinite(s.nodeScaleMin) ? s.nodeScaleMin : SPHERE_SCALE_MIN;
        const hi = Number.isFinite(s.nodeScaleMax) ? s.nodeScaleMax : SPHERE_SCALE_MAX;
        return lo + (data[i] ?? 0) * (hi - lo);
    }

    _brightnessAt(i) {
        const s = this.settings || {};
        if (!s.showNodeBrightness) return 0.5;
        const data = this._normalisedColumn(s.nodeBrightnessDataColumn);
        const lo = Number.isFinite(s.nodeBrightnessMin) ? s.nodeBrightnessMin : 0.3;
        const hi = Number.isFinite(s.nodeBrightnessMax) ? s.nodeBrightnessMax : 0.7;
        return lo + (data[i] ?? 0) * (hi - lo);
    }

    _hueColorAt(i) {
        const s = this.settings || {};
        const low = new THREE.Color(s.hueLowColor ?? '#3a4dff');
        const high = new THREE.Color(s.hueHighColor ?? '#ff4a3a');
        const t = Math.min(1, Math.max(0, s.showNodeHueRotation ? (this._normalisedColumn(s.nodeHueDataColumn)[i] ?? 0) : 0.5));

        // Interpolate in HSL hue-space (not RGB) so the gradient stays vivid.
        const lHsl = { h: 0, s: 0, l: 0 };
        const hHsl = { h: 0, s: 0, l: 0 };
        low.getHSL(lHsl);
        high.getHSL(hHsl);

        let deltaHue = hHsl.h - lHsl.h;
        if (deltaHue > 0.5) deltaHue -= 1;
        if (deltaHue < -0.5) deltaHue += 1;

        const hue = (lHsl.h + deltaHue * t + 1) % 1;
        const sat = lHsl.s + (hHsl.s - lHsl.s) * t;
        return new THREE.Color().setHSL(hue, sat, 0.5);
    }

    _nodeColorKey(s) {
        return JSON.stringify([
            s?.showNodeBrightness,
            s?.nodeBrightnessDataColumn,
            s?.nodeBrightnessMin,
            s?.nodeBrightnessMax,
            s?.showNodeHueRotation,
            s?.nodeHueDataColumn,
            s?.hueLowColor,
            s?.hueHighColor,
            s?.enableDull,
            s?.dullTailLength,
            s?.dullColor,
            s?.enableNodeFlash,
            s?.nodeFlashColor,
            s?.nodeFlashBrightness,
        ]);
    }

    _nodeScaleKey(s) {
        return JSON.stringify([
            s?.showNodeScale,
            s?.nodeScaleDataColumn,
            s?.nodeScaleMin,
            s?.nodeScaleMax,
        ]);
    }

    _disposeObject3D(obj) {
        if (!obj) return;
        if (obj.parent) obj.parent.remove(obj);
        obj.traverse((child) => {
            if (child.geometry && typeof child.geometry.dispose === 'function') {
                child.geometry.dispose();
            }
            if (child.material) {
                if (Array.isArray(child.material)) {
                    child.material.forEach((m) => m?.dispose?.());
                } else if (typeof child.material.dispose === 'function') {
                    child.material.dispose();
                }
            }
        });
    }

    _disposeActiveMeshes() {
        if (this.instancedMesh) {
            this._disposeObject3D(this.instancedMesh);
            this.instancedMesh = null;
        }
        if (this.lineEnhancerMesh) {
            this._disposeObject3D(this.lineEnhancerMesh);
            this.lineEnhancerMesh = null;
        }
        this.geometry.setFromPoints([]);
        if (this.geometry.hasAttribute('color')) this.geometry.deleteAttribute('color');
    }

    accumulateCurrentView() {
        const snapshot = new THREE.Group();
        let hasContent = false;

        const linePos = this.geometry.getAttribute('position');
        if (linePos && linePos.count > 0) {
            const lineGeometry = this.geometry.clone();
            const lineMaterial = this.material.clone();
            const line = new THREE.LineSegments(lineGeometry, lineMaterial);
            line.frustumCulled = false;
            snapshot.add(line);
            hasContent = true;
        }

        if (this.lineEnhancerMesh && this.lineEnhancerMesh.visible) {
            const enhancer = this.lineEnhancerMesh.clone();
            enhancer.geometry = this.lineEnhancerMesh.geometry.clone();
            enhancer.material = this.lineEnhancerMesh.material.clone();
            enhancer.instanceMatrix = this.lineEnhancerMesh.instanceMatrix.clone();
            if (this.lineEnhancerMesh.instanceColor) {
                enhancer.instanceColor = this.lineEnhancerMesh.instanceColor.clone();
            }
            enhancer.count = this.lineEnhancerMesh.count;
            snapshot.add(enhancer);
            hasContent = true;
        }

        if (this.instancedMesh) {
            const nodes = this.instancedMesh.clone();
            nodes.geometry = this.instancedMesh.geometry.clone();
            nodes.material = this.instancedMesh.material.clone();
            nodes.instanceMatrix = this.instancedMesh.instanceMatrix.clone();
            if (this.instancedMesh.instanceColor) {
                nodes.instanceColor = this.instancedMesh.instanceColor.clone();
            }
            nodes.count = this.instancedMesh.count;
            snapshot.add(nodes);
            hasContent = true;
        }

        if (hasContent) {
            this.accumulatedGroup.add(snapshot);
        }
    }

    clearAccumulatedView() {
        const children = [...this.accumulatedGroup.children];
        for (const child of children) {
            this._disposeObject3D(child);
        }
        this.accumulatedGroup.clear();
    }

    _buildInstancedMesh() {
        const count = this.points.length;

        const sphereGeo = new THREE.SphereGeometry(1, 8, 8);
        const sphereMat = new THREE.MeshStandardMaterial({
            transparent: true,
            roughness:   0.2,
            metalness:   0.8,
        });

        this.instancedMesh = new THREE.InstancedMesh(sphereGeo, sphereMat, count);
        this.instancedMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
        this.instancedMesh.frustumCulled = false;

        const dummy = new THREE.Object3D();

        for (let i = 0; i < count; i++) {
            const pt = this.points[i];

            dummy.position.set(pt.x, pt.y, pt.z);
            dummy.scale.setScalar(0);
            dummy.updateMatrix();
            this.instancedMesh.setMatrixAt(i, dummy.matrix);

            this.instancedMesh.setColorAt(i, new THREE.Color('#ffffff'));
        }

        this.instancedMesh.instanceMatrix.needsUpdate = true;
        this.instancedMesh.instanceColor.needsUpdate  = true;

        this.scene.add(this.instancedMesh);
    }

    _buildLineEnhancerMesh() {
        if (this.lineEnhancerMesh) {
            this.scene.remove(this.lineEnhancerMesh);
            this.lineEnhancerMesh.geometry.dispose();
            this.lineEnhancerMesh.material.dispose();
            this.lineEnhancerMesh = null;
        }

        const segmentCount = Math.max(0, this.points.length - 1);
        const safeCount = Math.max(1, segmentCount);

        const geo = new THREE.CylinderGeometry(1, 1, 1, 8, 1, true);
        const mat = new THREE.MeshBasicMaterial({
            color: 0x00ffcc,
            transparent: true,
            opacity: 0.9,
            depthTest: false,
            depthWrite: false,
        });

        this.lineEnhancerMesh = new THREE.InstancedMesh(geo, mat, safeCount);
        this.lineEnhancerMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
        this.lineEnhancerMesh.frustumCulled = false;
        this.lineEnhancerMesh.visible = false;
        this.lineEnhancerMesh.renderOrder = 10;

        for (let i = 0; i < safeCount; i++) {
            this.lineEnhancerMesh.setMatrixAt(i, this._lineEnhancerZeroMatrix);
            this.lineEnhancerMesh.setColorAt(i, new THREE.Color('#ffffff'));
        }
        this.lineEnhancerMesh.instanceMatrix.needsUpdate = true;
        if (this.lineEnhancerMesh.instanceColor) {
            this.lineEnhancerMesh.instanceColor.needsUpdate = true;
        }

        this.scene.add(this.lineEnhancerMesh);
    }

    setSettings(settings) {
        this.settings = settings;
    }

    setVisible(visible) {
        this.isVisible = !!visible;
        this.line.visible = this.isVisible;
        this.accumulatedGroup.visible = this.isVisible;
        if (this.lineEnhancerMesh) this.lineEnhancerMesh.visible = this.isVisible;
        if (this.instancedMesh) this.instancedMesh.visible = this.isVisible;
    }

    setAudioWaveform(waveform) {
        this.audioWaveform = waveform;
    }

    setRenderOrders({ line, lineEnhancer, nodes }) {
        if (typeof line === 'number') this.line.renderOrder = line;
        if (this.lineEnhancerMesh && typeof lineEnhancer === 'number') this.lineEnhancerMesh.renderOrder = lineEnhancer;
        if (this.instancedMesh && typeof nodes === 'number') this.instancedMesh.renderOrder = nodes;
    }

    setViewportSize(width, height) {
        // Kept for API compatibility from main.js; no-op for mesh-based enhancer.
        void width;
        void height;
    }

    _lineThicknessAt(i) {
        const s = this.settings || {};
        const lo = Number.isFinite(s.lineThicknessMin) ? s.lineThicknessMin : 1;
        const hi = Number.isFinite(s.lineThicknessMax) ? s.lineThicknessMax : 6;
        if (!s.showLineThickness) return (lo + hi) * 0.5;
        const data = this._normalisedColumn(s.lineThicknessDataColumn);
        return lo + (data[i] ?? 0) * (hi - lo);
    }

    _lineBrightnessAt(i) {
        const s = this.settings || {};
        if (!s.showLineBrightness) return 0.55;
        const data = this._normalisedColumn(s.lineBrightnessDataColumn);
        const lo = Number.isFinite(s.lineBrightnessMin) ? s.lineBrightnessMin : 0.3;
        const hi = Number.isFinite(s.lineBrightnessMax) ? s.lineBrightnessMax : 0.8;
        return lo + (data[i] ?? 0) * (hi - lo);
    }

    _lineHueColorAt(i) {
        const s = this.settings || {};
        if (!s.showLineHueRotation) {
            return new THREE.Color(s.lineColor ?? '#00ffcc');
        }
        const low = new THREE.Color(s.lineHueLowColor ?? '#3a4dff');
        const high = new THREE.Color(s.lineHueHighColor ?? '#ff4a3a');
        const t = Math.min(1, Math.max(0, this._normalisedColumn(s.lineHueDataColumn)[i] ?? 0));

        const lHsl = { h: 0, s: 0, l: 0 };
        const hHsl = { h: 0, s: 0, l: 0 };
        low.getHSL(lHsl);
        high.getHSL(hHsl);

        let deltaHue = hHsl.h - lHsl.h;
        if (deltaHue > 0.5) deltaHue -= 1;
        if (deltaHue < -0.5) deltaHue += 1;

        const hue = (lHsl.h + deltaHue * t + 1) % 1;
        const sat = lHsl.s + (hHsl.s - lHsl.s) * t;
        const lgt = this._lineBrightnessAt(i);
        return new THREE.Color().setHSL(hue, sat, Math.min(1, Math.max(0, lgt)));
    }

    _segmentBreakThreshold(points) {
        if (!Array.isArray(points) || points.length < 3) return Infinity;

        const segmentLengths = [];
        for (let i = 1; i < points.length; i++) {
            segmentLengths.push(points[i].distanceTo(points[i - 1]));
        }

        segmentLengths.sort((a, b) => a - b);
        const percentile = (ratio) => {
            const lastIndex = segmentLengths.length - 1;
            const index = Math.max(0, Math.min(lastIndex, Math.floor(lastIndex * ratio)));
            return segmentLengths[index];
        };

        const q1 = percentile(0.25);
        const median = percentile(0.5);
        const q3 = percentile(0.75);
        const p95 = percentile(0.95);
        const iqr = Math.max(0, q3 - q1);

        // UMAP paths can contain rare giant jumps between otherwise smooth runs.
        // Use a robust fence instead of an average-based threshold so a single
        // discontinuity does not keep itself visible.
        return Math.max(0.5, q3 + (iqr * 8), p95 * 1.75, median * 12);
    }

    // Switches node shading between lit (Standard) and unlit (Basic) at runtime.
    setNodeShadingMode(mode) {
        if (!this.instancedMesh) return;

        const oldMat = this.instancedMesh.material;
        const wantsBasic = mode === 'Basic';

        if (wantsBasic && oldMat && oldMat.isMeshBasicMaterial) return;
        if (!wantsBasic && oldMat && oldMat.isMeshStandardMaterial) return;

        const opacity = (oldMat && typeof oldMat.opacity === 'number') ? oldMat.opacity : 1;
        let newMat;

        if (wantsBasic) {
            newMat = new THREE.MeshBasicMaterial({
                transparent: true,
                opacity,
            });
        } else {
            newMat = new THREE.MeshStandardMaterial({
                transparent: true,
                opacity,
                roughness: 0.2,
                metalness: 0.8,
            });
        }

        this.instancedMesh.material = newMat;
        if (oldMat && typeof oldMat.dispose === 'function') oldMat.dispose();
    }

    // Returns color for node i given its age (distance from playhead)
    _nodeColor(i, distance, enableDull, dullTailLength) {
        const s = this.settings;
        const c = this._hueColorAt(i);
        const hsl = { h: 0, s: 0, l: 0 };
        c.getHSL(hsl);
        hsl.l = Math.min(1, Math.max(0, this._brightnessAt(i)));
        let color = new THREE.Color().setHSL(hsl.h, hsl.s, hsl.l);

        if (this.selectedFrameIndices.has(i)) {
            color = color.clone().lerp(this._selectionHighlightColor, 0.82);
        }

        if (enableDull && distance > 0) {
            const t = Math.max(0, 1 - distance / dullTailLength);
            const dullTarget = new THREE.Color(s?.dullColor ?? '#111111');
            color = dullTarget.lerp(color, t);
        }

        const pulseIntensity = this._onsetPulseIntensityAt(i);
        if (pulseIntensity > 0) {
            const flashColor = new THREE.Color(s?.nodeFlashColor ?? '#fff1a8');
            const flashBrightness = Math.max(0, Number(s?.nodeFlashBrightness) || 1);
            const flashMix = Math.max(0, Math.min(1, pulseIntensity * flashBrightness));
            color = color.clone().lerp(flashColor, flashMix);

            const pulseHsl = { h: 0, s: 0, l: 0 };
            color.getHSL(pulseHsl);
            pulseHsl.l = Math.min(1, pulseHsl.l + (0.18 * flashMix));
            color = new THREE.Color().setHSL(pulseHsl.h, pulseHsl.s, pulseHsl.l);
        }

        return color;
    }

    // Full colour refresh — used when nodeColor picker changes
    _refreshColors(currentIndex, enableDull, dullTailLength) {
        if (!this.instancedMesh) return;
        const count = this.points.length;
        for (let i = 0; i < count; i++) {
            const c = this._nodeColor(i, currentIndex - i, enableDull, dullTailLength);
            this.instancedMesh.setColorAt(i, c);
        }
        this.instancedMesh.instanceColor.needsUpdate = true;
        this._prevNodeColorKey = this._nodeColorKey(this.settings);
    }

    syncToProgress(progress) {
        if (this.points.length === 0) return;
        if (!this.isVisible) return;

        const count        = this.points.length;
        const currentIndex = Math.max(0, Math.min(count - 1, Math.floor(progress * count)));
        this._currentIndex = currentIndex;
        this._pulseNowMs = performance.now();
        this._pruneExpiredOnsetPulses(this._pulseNowMs);

        const s               = this.settings;
        const enableDecay     = s ? s.enableDecay     : false;
        const decayTailLength = s ? Math.max(1, Math.floor(s.decayTailLength)) : 60;
        const enableDull      = s ? s.enableDull      : false;
        const dullTailLength  = s ? Math.max(1, Math.floor(s.dullTailLength))  : 120;
        const deconstructLine = s ? s.deconstructiveLine  : false;
        const deconstructNode = s ? s.deconstructiveNodes : false;

        // ── Visibility toggles ─────────────────────────────────────
        const showLine = s ? s.showLine : true;
        const useScaleEnhancer = !!(s?.enableLineScaleEnhancer);
        this.line.visible = showLine && !useScaleEnhancer;
        if (this.lineEnhancerMesh) this.lineEnhancerMesh.visible = false;
        if (this.instancedMesh) this.instancedMesh.visible = s ? s.showNodes : true;

        // ── Node colour parameters changed → full refresh ──────────
        const pulseStateChanged = this._pulseRevision !== this._prevPulseRevision;
        const pulseActive = !!s?.enableNodeFlash && this._activeOnsetPulses.size > 0;
        const nodeColorChanged = (!!s && this._nodeColorKey(s) !== this._prevNodeColorKey) || pulseStateChanged || pulseActive;
        const nodeScaleChanged = !!s && this._nodeScaleKey(s) !== this._prevNodeScaleKey;
        if (nodeColorChanged) {
            this._refreshColors(currentIndex, enableDull, dullTailLength);
        }

        // ── Line ───────────────────────────────────────────────────
        const enableLineDecay     = s?.enableLineDecay     ?? false;
        const lineDecayTailLength = Math.max(1, Math.floor(s?.lineDecayTailLength ?? 60));
        const enableLineDull      = s?.enableLineDull      ?? false;
        const lineDullTailLength  = Math.max(1, Math.floor(s?.lineDullTailLength  ?? 120));

        let drawnPoints;
        let drawnStartIndex = 0;
        if (deconstructLine) {
            const end = enableLineDecay
                ? Math.min(this.points.length, currentIndex + lineDecayTailLength)
                : this.points.length;
            drawnStartIndex = currentIndex;
            drawnPoints = this.points.slice(currentIndex, end);
        } else {
            const start = enableLineDecay
                ? Math.max(0, currentIndex - lineDecayTailLength)
                : 0;
            drawnStartIndex = start;
            drawnPoints = this.points.slice(start, currentIndex);
        }

        if (drawnPoints.length > 1) {
            // Apply waveform breathing effect if enabled
            let visualPoints = drawnPoints;
            if (s?.enableLineBreathing && this.audioWaveform) {
                visualPoints = this._applyLineBreathingEffect(drawnPoints, drawnStartIndex);
            }

            const breakThreshold = this._segmentBreakThreshold(drawnPoints);
            const dullCol = new THREE.Color(s?.lineDullColor ?? '#111111');
            const sourceCount = Math.max(1, drawnPoints.length - 1);

            const colorForVisualIndex = (vi) => {
                const sourceT = visualPoints.length > 1 ? vi / (visualPoints.length - 1) : 0;
                const sourceIndex = drawnStartIndex + Math.min(
                    drawnPoints.length - 1,
                    Math.round(sourceT * sourceCount)
                );
                const base = this._lineHueColorAt(sourceIndex);
                const bhsl = { h: 0, s: 0, l: 0 };
                base.getHSL(bhsl);
                bhsl.l = Math.min(1, Math.max(0, this._lineBrightnessAt(sourceIndex)));
                const brightBase = new THREE.Color().setHSL(bhsl.h, bhsl.s, bhsl.l);
                const age = deconstructLine ? vi : (drawnPoints.length - 1 - vi);
                return (enableLineDull && age > 0)
                    ? dullCol.clone().lerp(brightBase, Math.max(0, 1 - age / lineDullTailLength))
                    : brightBase;
            };

            const segmentPoints = [];
            const segmentColors = [];
            for (let vi = 0; vi < visualPoints.length - 1; vi++) {
                const p0 = visualPoints[vi];
                const p1 = visualPoints[vi + 1];
                if (p0.distanceTo(p1) > breakThreshold) continue;

                const c0 = colorForVisualIndex(vi);
                const c1 = colorForVisualIndex(vi + 1);
                segmentPoints.push(p0, p1);
                segmentColors.push(c0.r, c0.g, c0.b, c1.r, c1.g, c1.b);
            }

            this.geometry.setFromPoints(segmentPoints);
            if (segmentColors.length > 0) {
                this.geometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(segmentColors), 3));
            } else if (this.geometry.hasAttribute('color')) {
                this.geometry.deleteAttribute('color');
            }
            this.material.color.set(s?.lineColor ?? '#00ffcc');
            this.material.needsUpdate = true;

            if (useScaleEnhancer && showLine && this.lineEnhancerMesh) {
                const segmentCount = Math.max(0, this.points.length - 1);
                const visibleSegStart = drawnStartIndex;
                const visibleSegEnd = drawnStartIndex + drawnPoints.length - 2;

                for (let si = 0; si < segmentCount; si++) {
                    if (si < visibleSegStart || si > visibleSegEnd) {
                        this.lineEnhancerMesh.setMatrixAt(si, this._lineEnhancerZeroMatrix);
                        continue;
                    }

                    const p0orig = this.points[si];
                    const p1orig = this.points[si + 1];
                    if (p0orig.distanceTo(p1orig) > breakThreshold) {
                        this.lineEnhancerMesh.setMatrixAt(si, this._lineEnhancerZeroMatrix);
                        continue;
                    }

                    // Apply waveform breathing offsets to segment endpoints
                    let p0 = p0orig.clone();
                    let p1 = p1orig.clone();
                    if (s?.enableLineBreathing && this.audioWaveform) {
                        const waveOffset0 = this._getWaveformOffset(si);
                        const waveOffset1 = this._getWaveformOffset(si + 1);
                        const baseDir = new THREE.Vector3().subVectors(p1orig, p0orig).normalize();
                        const perp = this._getPerpendicularVector(baseDir);
                        p0.addScaledVector(perp, waveOffset0);
                        p1.addScaledVector(perp, waveOffset1);
                    }

                    const dir = new THREE.Vector3().subVectors(p1, p0);
                    const len = dir.length();
                    if (len <= 1e-6) {
                        this.lineEnhancerMesh.setMatrixAt(si, this._lineEnhancerZeroMatrix);
                        continue;
                    }

                    const mid = new THREE.Vector3().addVectors(p0, p1).multiplyScalar(0.5);
                    const radius = Math.max(0.01, this._lineThicknessAt(si) * LINE_THICKNESS_TO_WORLD);

                    this._lineEnhancerDummy.position.copy(mid);
                    this._lineEnhancerDummy.quaternion.setFromUnitVectors(this._lineEnhancerUp, dir.normalize());
                    this._lineEnhancerDummy.scale.set(radius, len, radius);
                    this._lineEnhancerDummy.updateMatrix();
                    this.lineEnhancerMesh.setMatrixAt(si, this._lineEnhancerDummy.matrix);

                    const localIndex = si - drawnStartIndex;
                    const sourceIndex = si;
                    const base = this._lineHueColorAt(sourceIndex);
                    const bhsl = { h: 0, s: 0, l: 0 };
                    base.getHSL(bhsl);
                    bhsl.l = Math.min(1, Math.max(0, this._lineBrightnessAt(sourceIndex)));
                    const brightBase = new THREE.Color().setHSL(bhsl.h, bhsl.s, bhsl.l);
                    const age = deconstructLine ? localIndex : (drawnPoints.length - 1 - localIndex);
                    const segColor = (enableLineDull && age > 0)
                        ? dullCol.clone().lerp(brightBase, Math.max(0, 1 - age / lineDullTailLength))
                        : brightBase;
                    this.lineEnhancerMesh.setColorAt(si, segColor);
                }

                this.lineEnhancerMesh.instanceMatrix.needsUpdate = true;
                if (this.lineEnhancerMesh.instanceColor) {
                    this.lineEnhancerMesh.instanceColor.needsUpdate = true;
                }
                this.lineEnhancerMesh.visible = true;
            } else {
                if (this.lineEnhancerMesh) this.lineEnhancerMesh.visible = false;
            }
        } else {
            this.geometry.setFromPoints([]);
            if (this.geometry.hasAttribute('color')) this.geometry.deleteAttribute('color');
            if (this.lineEnhancerMesh) this.lineEnhancerMesh.visible = false;
        }

        if (!this.instancedMesh || (s && !s.showNodes)) return;

        // ── Detect conditions that require a full rebuild ──────────
        const prevIndex       = this._prevCurrentIndex;
        const rewound         = prevIndex !== undefined && currentIndex < prevIndex;
        const settingsChanged = this._prevEnableDecay     !== enableDecay     ||
                                this._prevDecayTailLength !== decayTailLength ||
                                this._prevEnableDull      !== enableDull      ||
                                this._prevDullTailLength  !== dullTailLength  ||
                                this._prevDeconstructNode !== deconstructNode ||
                                nodeScaleChanged;

        const dummy      = new THREE.Object3D();
        const zeroMatrix = new THREE.Matrix4().makeScale(0, 0, 0);
        let   matrixDirty = false;
        let   colorDirty  = false;

        // Set the scale matrix for a single revealed node
        const setMatrix = (i) => {
            const dist = currentIndex - i;
            let scale;
            if (deconstructNode) {
                // Deconstructive: full until playhead, then decay/disappear
                if (dist <= 0) {
                    scale = this._nodeScaleAt(i);
                } else if (enableDecay) {
                    scale = dist >= decayTailLength ? 0 : this._nodeScaleAt(i) * (1 - dist / decayTailLength);
                } else {
                    scale = 0; // instant removal as playhead passes
                }
            } else {
                // Constructive: permanent by default; optionally decay
                if (enableDecay) {
                    scale = dist >= decayTailLength ? 0 : this._nodeScaleAt(i) * (1 - dist / decayTailLength);
                } else {
                    scale = this._nodeScaleAt(i); // stays forever
                }
            }
            const pt = this.points[i];
            dummy.position.set(pt.x, pt.y, pt.z);
            dummy.scale.setScalar(Math.max(0, scale));
            dummy.updateMatrix();
            this.instancedMesh.setMatrixAt(i, dummy.matrix);
            matrixDirty = true;
        };

        // Set the colour for a single revealed node
        const setColor = (i) => {
            const c = this._nodeColor(i, currentIndex - i, enableDull, dullTailLength);
            this.instancedMesh.setColorAt(i, c);
            colorDirty = true;
        };

        if (rewound || settingsChanged) {
            // Full rebuild — touch every instance
            for (let i = 0; i < count; i++) {
                if (i > currentIndex) {
                    // Future nodes
                    if (deconstructNode) {
                        const pt = this.points[i];
                        dummy.position.set(pt.x, pt.y, pt.z);
                        dummy.scale.setScalar(this._nodeScaleAt(i));
                        dummy.updateMatrix();
                        this.instancedMesh.setMatrixAt(i, dummy.matrix);
                        setColor(i);
                    } else {
                        this.instancedMesh.setMatrixAt(i, zeroMatrix);
                    }
                    matrixDirty = true;
                } else {
                    setMatrix(i);
                    setColor(i);
                }
            }
        } else if (deconstructNode) {
            // Deconstructive incremental: remove nodes as playhead passes them
            const from = prevIndex !== undefined ? prevIndex : currentIndex;
            for (let i = from; i <= currentIndex; i++) {
                setMatrix(i);
                setColor(i);
            }
            // Refresh the fade-out zone
            if (enableDecay) {
                const zoneStart  = Math.max(0, currentIndex - decayTailLength);
                const justExited = currentIndex - decayTailLength - 1;
                if (justExited >= 0) {
                    this.instancedMesh.setMatrixAt(justExited, zeroMatrix);
                    matrixDirty = true;
                }
                for (let i = zoneStart; i < currentIndex; i++) setMatrix(i);
            }
            if (enableDull) {
                const zoneStart = Math.max(0, currentIndex - dullTailLength);
                for (let i = zoneStart; i < currentIndex; i++) setColor(i);
            }
        } else {
            // Constructive incremental: reveal new nodes, maintain transition zones
            const revealFrom = prevIndex !== undefined ? prevIndex + 1 : 0;
            for (let i = revealFrom; i <= currentIndex; i++) {
                setMatrix(i);
                setColor(i);
            }
            // Decay transition zone
            if (enableDecay) {
                const zoneStart  = Math.max(0, currentIndex - decayTailLength);
                const justExited = currentIndex - decayTailLength - 1;
                if (justExited >= 0) {
                    this.instancedMesh.setMatrixAt(justExited, zeroMatrix);
                    matrixDirty = true;
                }
                for (let i = zoneStart; i < currentIndex; i++) setMatrix(i);
            }
            // Dull transition zone
            if (enableDull) {
                const zoneStart = Math.max(0, currentIndex - dullTailLength);
                for (let i = zoneStart; i < currentIndex; i++) setColor(i);
            }
        }

        if (matrixDirty) this.instancedMesh.instanceMatrix.needsUpdate = true;
        if (colorDirty)  this.instancedMesh.instanceColor.needsUpdate  = true;

        this._prevCurrentIndex    = currentIndex;
        this._prevEnableDecay     = enableDecay;
        this._prevDecayTailLength = decayTailLength;
        this._prevEnableDull      = enableDull;
        this._prevDullTailLength  = dullTailLength;
        this._prevDeconstructNode = deconstructNode;
        this._prevNodeScaleKey    = this._nodeScaleKey(s);
        this._prevPulseRevision   = this._pulseRevision;
    }

    applyBreathing(amplitude) {
        if (!this.instancedMesh || amplitude < 0.01 || !this.settings) return;
        if (!this.settings.showNodes || !this.settings.enableBreathing || this.settings.jitterIntensity <= 0) return;

        const currentIndex    = this._currentIndex;
        if (currentIndex === undefined || currentIndex < 0) return;

        const s               = this.settings;
        const enableDecay     = s.enableDecay;
        const decayTailLength = Math.max(1, Math.floor(s.decayTailLength));
        const deconstructNode = s.deconstructiveNodes;
        const count           = this.points.length;

        const maxBreathingNodes = Math.max(0, Math.floor(this.settings.maxBreathingNodes ?? 120));
        if (maxBreathingNodes === 0) return;

        // Cap the breathing window: if no decay, jitter only the nearest N nodes for performance
        const breathWindow = enableDecay
            ? Math.min(decayTailLength, maxBreathingNodes)
            : Math.min(maxBreathingNodes, currentIndex + 1);

        const dummy  = new THREE.Object3D();
        const t      = Date.now() * 0.001;
        const jitter = amplitude * s.jitterIntensity;

        const start = deconstructNode
            ? Math.max(0, currentIndex - (enableDecay ? decayTailLength : 0))
            : Math.max(0, currentIndex - breathWindow);
        const end = deconstructNode
            ? Math.min(count - 1, currentIndex + breathWindow)
            : currentIndex;

        for (let i = start; i <= end; i++) {
            const dist = currentIndex - i;
            let scale  = this._nodeScaleAt(i);

            if (deconstructNode) {
                if (dist <= 0) {
                    // future/current node in deconstructive mode — full scale
                } else if (enableDecay) {
                    if (dist >= decayTailLength) continue;
                    scale *= (1 - dist / decayTailLength);
                } else {
                    continue; // already hidden
                }
            } else {
                if (enableDecay) {
                    if (dist >= decayTailLength) continue;
                    scale *= (1 - dist / decayTailLength);
                }
                // else: permanent, full scale
            }
            if (scale <= 0) continue;

            const phase = i * 0.4;
            const ox = Math.sin(t * 3.1 + phase)        * jitter;
            const oy = Math.cos(t * 2.7 + phase * 1.3)  * jitter;
            const oz = Math.sin(t * 2.3 + phase * 0.7)  * jitter;

            const pt = this.points[i];
            dummy.position.set(pt.x + ox, pt.y + oy, pt.z + oz);
            dummy.scale.setScalar(scale);
            dummy.updateMatrix();
            this.instancedMesh.setMatrixAt(i, dummy.matrix);
        }

        this.instancedMesh.instanceMatrix.needsUpdate = true;
    }

    _getPerpendicularVector(dir) {
        let perp = new THREE.Vector3(0, 0, 1);
        if (Math.abs(dir.y) < 0.9) {
            perp.set(0, 1, 0).cross(dir).normalize();
        } else {
            perp.set(1, 0, 0).cross(dir).normalize();
        }
        return perp;
    }

    _getWaveformOffset(pointIndex) {
        if (!this.audioWaveform) return 0;
        const s = this.settings;
        const amplitude = Math.max(0, s?.lineBreathingAmplitude ?? 1.0);
        const waveformIndex = Math.floor((pointIndex / this.points.length) * this.audioWaveform.length);
        const waveValue = this.audioWaveform[Math.max(0, Math.min(waveformIndex, this.audioWaveform.length - 1))];
        return waveValue * amplitude * 0.5;
    }

    _applyLineBreathingEffect(points, startIndex) {
        // Subdivide line segments and apply waveform-based breathing
        if (!this.audioWaveform || points.length < 2) return points;
        
        const s = this.settings;
        if (!s?.enableLineBreathing) return points;
        
        const amplitude = Math.max(0, s.lineBreathingAmplitude ?? 1.0);
        if (amplitude <= 0) return points;
        
        const subdivisions = 6; // Create 6 intermediate points between each segment
        const subdivisionPoints = [];
        
        for (let i = 0; i < points.length - 1; i++) {
            const p0 = points[i];
            const p1 = points[i + 1];
            
            // Add original point with waveform offset
            const originalIndex = startIndex + i;
            const waveOffset0 = this._getWaveformOffset(originalIndex);
            const dir0 = i > 0 
                ? new THREE.Vector3().subVectors(p1, points[i - 1]).normalize()
                : new THREE.Vector3().subVectors(p1, p0).normalize();
            const perp0 = this._getPerpendicularVector(dir0);
            const breathedP0 = p0.clone().addScaledVector(perp0, waveOffset0);
            subdivisionPoints.push(breathedP0);
            
            // Subdivide segment with waveform offsets
            for (let j = 1; j <= subdivisions; j++) {
                const t = j / (subdivisions + 1);
                const interpPt = new THREE.Vector3().lerpVectors(p0, p1, t);
                const interpIndex = originalIndex + t;
                const waveOffset = this._getWaveformOffset(interpIndex);
                
                const dir = new THREE.Vector3().subVectors(p1, p0).normalize();
                const perp = this._getPerpendicularVector(dir);
                const breathedPt = interpPt.clone().addScaledVector(perp, waveOffset);
                subdivisionPoints.push(breathedPt);
            }
        }
        
        // Add final point with waveform offset
        const finalIndex = startIndex + points.length - 1;
        const waveOffsetFinal = this._getWaveformOffset(finalIndex);
        const dirFinal = new THREE.Vector3().subVectors(points[points.length - 1], points[points.length - 2]).normalize();
        const perpFinal = this._getPerpendicularVector(dirFinal);
        const breathedFinal = points[points.length - 1].clone().addScaledVector(perpFinal, waveOffsetFinal);
        subdivisionPoints.push(breathedFinal);
        
        return subdivisionPoints;
    }
}