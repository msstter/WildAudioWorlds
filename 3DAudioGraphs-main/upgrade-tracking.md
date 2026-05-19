# Upgrade Tracking

Last updated: 2026-05-19

## Frontend package updates

- `frontend/package.json`
  - `three`: `^0.158.0` -> `^0.184.0`
  - `electron`: `^42.0.1` -> `^42.1.0`
  - `vite`: `^8.0.11` -> `^8.0.13`
- `frontend/package-lock.json`
  - Refreshed by `npm install` to capture the updated dependency tree.

## App function updates

- No additional dependency version changes were required after the 2026-05-19 refresh.
- Source-level frontend follow-up work did happen after the dependency bump as the cross-app integration continued.
- `frontend/main.cjs` and `frontend/preload.cjs`
  - Added canonical backend-readiness IPC and shared canonical request-context loading so backend analysis and readiness checks now use service-owned session state.
- `frontend/public/backend-call-monitor.js`
  - Backend monitor action gating now queries canonical readiness from Electron main instead of relying on pushed monitor-snapshot state for selection readiness.
- `frontend/src/main.js`, `frontend/index.html`, `frontend/src/styles/transport.css`, `frontend/src/app/recordingControls.js`, and `frontend/src/app/cameraControlPanel.js`
  - Added always-visible `LIVE` and `CAM` transport launchers and minimal modal-open plumbing so the live-source and camera-control workflows are discoverable from the main shell.

## Validation

- `npm install --dry-run`: reported the frontend dependencies as up to date after the refresh.
- `npm run build`: passed successfully on 2026-05-18 and again on 2026-05-19 after the renderer integration follow-up work.
- `node --check src/main.js && node --check src/app/recordingControls.js && node --check src/app/cameraControlPanel.js`: passed on 2026-05-19.
- Build note: Vite still reports a chunk-size warning for the main renderer bundle exceeding 500 kB after minification (`index-B19HM9Ky.js` at 954.28 kB in the latest build). This did not block the build.

## Next tracking entries

- Add function-level notes here if a future dependency bump requires code updates.
- Record any file paths touched by those changes alongside the package version that triggered them.
- If the renderer chunk-size warning becomes actionable work, note the split strategy or bundle-shaping change here alongside the build output that motivated it.