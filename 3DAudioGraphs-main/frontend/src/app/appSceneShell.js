import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js';
import { createFloatingPanelDragManager } from '../shared/ui/floatingPanel.js';

export const BASE_BACKGROUND_COLOR = '#000000';
export const BASE_FOG_DENSITY = 0.002;
export const BASE_FOG_COLOR = '#000000';

const createTimbreSelectionBadge = (documentObject) => {
    const badge = documentObject.createElement('div');
    badge.dataset.fpvPointerLockBlocker = 'true';
    badge.style.cssText = [
        'position:absolute',
        'left:12px',
        'top:72px',
        'max-width:min(420px, calc(100vw - 24px))',
        'padding:10px 12px',
        'border:1px solid rgba(56, 189, 248, 0.35)',
        'border-radius:8px',
        'background:rgba(8, 11, 17, 0.9)',
        'color:#e5e7eb',
        'font-family:monospace',
        'font-size:12px',
        'line-height:1.45',
        'box-shadow:0 10px 32px rgba(0, 0, 0, 0.35)',
        'z-index:22',
        'display:none',
        'pointer-events:auto',
    ].join(';');

    const header = documentObject.createElement('div');
    header.style.cssText = [
        'display:flex',
        'justify-content:space-between',
        'align-items:center',
        'margin-bottom:8px',
        'cursor:grab',
        'user-select:none',
    ].join(';');

    const title = documentObject.createElement('div');
    title.style.cssText = 'font-weight:bold;color:#67e8f9;';
    title.textContent = 'Selection --';

    const dragHint = documentObject.createElement('div');
    dragHint.style.cssText = 'color:#64748b;font-size:10px;letter-spacing:0.08em;text-transform:uppercase;';
    dragHint.textContent = 'Drag';

    const meta = documentObject.createElement('div');
    meta.style.cssText = 'color:#cbd5e1;';
    meta.textContent = 'Click a visible timbre node.';

    const range = documentObject.createElement('div');
    range.style.cssText = 'color:#94a3b8;';
    range.textContent = 'Shift-click to add or remove nodes.';

    const stats = documentObject.createElement('div');
    stats.style.cssText = 'color:#64748b;';
    stats.textContent = 'Plane selection inactive | Export and playback actions unlock once nodes are selected.';

    header.appendChild(title);
    header.appendChild(dragHint);
    badge.appendChild(header);
    badge.appendChild(meta);
    badge.appendChild(range);
    badge.appendChild(stats);
    badge.addEventListener('pointerdown', (event) => {
        event.stopPropagation();
    });

    return {
        badge,
        header,
        title,
        meta,
        range,
        stats,
    };
};

const createTimbreSelectionPanel = (documentObject) => {
    const panel = documentObject.createElement('div');
    panel.dataset.fpvPointerLockBlocker = 'true';
    panel.style.cssText = [
        'position:absolute',
        'left:12px',
        'top:188px',
        'width:min(360px, calc(100vw - 24px))',
        'padding:10px 12px',
        'border:1px solid rgba(148, 163, 184, 0.28)',
        'border-radius:8px',
        'background:rgba(8, 11, 17, 0.9)',
        'color:#e5e7eb',
        'font-family:monospace',
        'font-size:12px',
        'line-height:1.45',
        'z-index:21',
        'display:none',
        'pointer-events:auto',
        'box-shadow:0 10px 32px rgba(0, 0, 0, 0.35)',
    ].join(';');

    const header = documentObject.createElement('div');
    header.style.cssText = [
        'display:flex',
        'justify-content:space-between',
        'align-items:center',
        'margin-bottom:8px',
        'cursor:grab',
        'user-select:none',
    ].join(';');

    const headerText = documentObject.createElement('div');
    headerText.style.cssText = 'display:grid;gap:2px;';

    const title = documentObject.createElement('div');
    title.style.cssText = 'font-weight:bold;color:#fde68a;';
    title.textContent = 'Node Selection';

    const subtitle = documentObject.createElement('div');
    subtitle.style.cssText = 'color:#94a3b8;font-size:11px;';
    subtitle.textContent = 'Current + saved node groups';

    const dragHint = documentObject.createElement('div');
    dragHint.style.cssText = 'color:#64748b;font-size:10px;letter-spacing:0.08em;text-transform:uppercase;';
    dragHint.textContent = 'Drag';

    const tabBar = documentObject.createElement('div');
    tabBar.style.cssText = 'display:flex;gap:6px;overflow-x:auto;padding-bottom:4px;margin-bottom:8px;';

    const body = documentObject.createElement('div');
    body.style.cssText = 'display:grid;gap:8px;';

    headerText.appendChild(title);
    headerText.appendChild(subtitle);
    header.appendChild(headerText);
    header.appendChild(dragHint);
    panel.appendChild(header);
    panel.appendChild(tabBar);
    panel.appendChild(body);
    panel.addEventListener('pointerdown', (event) => {
        event.stopPropagation();
    });

    return {
        panel,
        header,
        subtitle,
        tabBar,
        body,
    };
};

const createTerrainHelperBadge = (documentObject) => {
    const badge = documentObject.createElement('div');
    badge.textContent = '2D Helper: Idle';
    badge.style.cssText = [
        'position:absolute',
        'top:12px',
        'right:12px',
        'max-width:min(420px, calc(100vw - 24px))',
        'padding:4px 8px',
        'border:1px solid #4b5563',
        'border-radius:4px',
        'background:rgba(31, 41, 55, 0.78)',
        'color:#d1d5db',
        'font-family:monospace',
        'font-size:11px',
        'line-height:1.4',
        'display:none',
        'pointer-events:none',
        'z-index:24',
    ].join(';');
    return badge;
};

const createTerrainSculptOverviewPanel = (documentObject) => {
    const panel = documentObject.createElement('div');
    panel.dataset.fpvPointerLockBlocker = 'true';
    panel.style.cssText = [
        'position:absolute',
        'left:calc(50vw - 320px)',
        'top:108px',
        'width:min(680px, calc(100vw - 24px))',
        'padding:10px 12px 12px',
        'border:1px solid rgba(110, 182, 255, 0.28)',
        'border-radius:10px',
        'background:rgba(7, 12, 18, 0.92)',
        'color:#e5e7eb',
        'font-family:monospace',
        'font-size:12px',
        'line-height:1.45',
        'z-index:23',
        'display:none',
        'pointer-events:auto',
        'box-shadow:0 18px 42px rgba(0, 0, 0, 0.4)',
    ].join(';');

    const header = documentObject.createElement('div');
    header.style.cssText = [
        'display:flex',
        'justify-content:space-between',
        'align-items:flex-start',
        'gap:12px',
        'margin-bottom:8px',
        'cursor:grab',
        'user-select:none',
    ].join(';');

    const headerText = documentObject.createElement('div');
    headerText.style.cssText = 'display:grid;gap:2px;';

    const title = documentObject.createElement('div');
    title.style.cssText = 'font-weight:bold;color:#93c5fd;';
    title.textContent = '2D High-Level Sculpt View';

    const meta = documentObject.createElement('div');
    meta.style.cssText = 'color:#94a3b8;font-size:11px;';
    meta.textContent = 'Whole-file Frequency x Time view for the Full Sculpt Mask. The rendered 3D terrain slice is shown separately as a local view window.';

    const dragHint = documentObject.createElement('div');
    dragHint.style.cssText = 'color:#64748b;font-size:10px;letter-spacing:0.08em;text-transform:uppercase;';
    dragHint.textContent = 'Drag';

    const canvas = documentObject.createElement('canvas');
    canvas.style.cssText = [
        'display:block',
        'width:100%',
        'height:280px',
        'border-radius:8px',
        'border:1px solid rgba(255, 255, 255, 0.08)',
        'background:linear-gradient(180deg, rgba(7, 14, 22, 0.96), rgba(3, 7, 12, 0.96))',
        'cursor:crosshair',
    ].join(';');

    const status = documentObject.createElement('div');
    status.style.cssText = [
        'margin-top:8px',
        'padding:6px 8px',
        'border:1px solid rgba(147, 197, 253, 0.18)',
        'border-radius:7px',
        'background:rgba(9, 18, 28, 0.72)',
        'color:#cbd5e1',
        'font-size:11px',
        'line-height:1.45',
    ].join(';');
    status.textContent = 'Target: Full Sculpt Mask | Blue: Full Sculpt Mask | White: 3D Window';

    const footer = documentObject.createElement('div');
    footer.style.cssText = 'margin-top:8px;color:#64748b;font-size:11px;';
    footer.textContent = 'Drag to move, trim, or redraw the shared mask.';

    headerText.appendChild(title);
    headerText.appendChild(meta);
    header.appendChild(headerText);
    header.appendChild(dragHint);
    panel.appendChild(header);
    panel.appendChild(canvas);
    panel.appendChild(status);
    panel.appendChild(footer);
    panel.addEventListener('pointerdown', (event) => {
        event.stopPropagation();
    });

    return {
        panel,
        header,
        title,
        meta,
        canvas,
        status,
        footer,
    };
};

export const createAppSceneShell = ({
    documentObject = document,
    windowObject = window,
} = {}) => {
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(BASE_FOG_COLOR, BASE_FOG_DENSITY);
    scene.background = new THREE.Color(BASE_BACKGROUND_COLOR);

    const camera = new THREE.PerspectiveCamera(75, windowObject.innerWidth / windowObject.innerHeight, 0.1, 5000);
    camera.position.set(70, 70, 100);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(windowObject.innerWidth, windowObject.innerHeight);
    renderer.domElement.tabIndex = 0;
    documentObject.body.appendChild(renderer.domElement);

    const labelRenderer = new CSS2DRenderer();
    labelRenderer.setSize(windowObject.innerWidth, windowObject.innerHeight);
    labelRenderer.domElement.style.position = 'absolute';
    labelRenderer.domElement.style.top = '0px';
    labelRenderer.domElement.style.pointerEvents = 'none';
    documentObject.body.appendChild(labelRenderer.domElement);

    const fpsMeter = documentObject.createElement('div');
    fpsMeter.textContent = 'FPS --';
    fpsMeter.style.cssText = [
        'position:absolute',
        'top:12px',
        'left:12px',
        'padding:4px 8px',
        'border:1px solid #333',
        'border-radius:4px',
        'background:rgba(0, 0, 0, 0.7)',
        'color:#88ffcc',
        'font-family:monospace',
        'font-size:11px',
        'display:none',
        'z-index:25',
    ].join(';');
    documentObject.body.appendChild(fpsMeter);

    const terrainHelperBadge = createTerrainHelperBadge(documentObject);
    documentObject.body.appendChild(terrainHelperBadge);

    const badgeParts = createTimbreSelectionBadge(documentObject);
    documentObject.body.appendChild(badgeParts.badge);

    const panelParts = createTimbreSelectionPanel(documentObject);
    documentObject.body.appendChild(panelParts.panel);

    const terrainOverviewParts = createTerrainSculptOverviewPanel(documentObject);
    documentObject.body.appendChild(terrainOverviewParts.panel);

    const floatingPanelDragManager = createFloatingPanelDragManager();
    floatingPanelDragManager.enablePanelDrag(badgeParts.badge, badgeParts.header);
    floatingPanelDragManager.enablePanelDrag(panelParts.panel, panelParts.header);
    floatingPanelDragManager.enablePanelDrag(terrainOverviewParts.panel, terrainOverviewParts.header);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 1.5);
    directionalLight.position.set(50, 100, 80);
    scene.add(directionalLight);

    return {
        scene,
        camera,
        renderer,
        labelRenderer,
        fpsMeter,
        controls,
        ambientLight,
        directionalLight,
        floatingPanelDragManager,
        elements: {
            terrainHelperBadge,
            timbreSelectionBadge: badgeParts.badge,
            timbreSelectionTitle: badgeParts.title,
            timbreSelectionMeta: badgeParts.meta,
            timbreSelectionRange: badgeParts.range,
            timbreSelectionStats: badgeParts.stats,
            timbreSelectionPanel: panelParts.panel,
            timbreSelectionPanelSubtitle: panelParts.subtitle,
            timbreSelectionPanelTabBar: panelParts.tabBar,
            timbreSelectionPanelBody: panelParts.body,
            terrainSculptOverviewPanel: terrainOverviewParts.panel,
            terrainSculptOverviewHeader: terrainOverviewParts.header,
            terrainSculptOverviewTitle: terrainOverviewParts.title,
            terrainSculptOverviewMeta: terrainOverviewParts.meta,
            terrainSculptOverviewCanvas: terrainOverviewParts.canvas,
            terrainSculptOverviewStatus: terrainOverviewParts.status,
            terrainSculptOverviewFooter: terrainOverviewParts.footer,
        },
    };
};