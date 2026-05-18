"""Generate 3D Flower Raster plots from the extractor workbook.

Stage 1 — Cylindrical Skeleton
-------------------------------
Every dyad from every audio file is mapped into a 3D cylindrical space:

*  **Radial (r)**:  interval duration in ms (i_l on the "long" side,
   i_s mirrored 180° on the "short" side).
*  **Angular (θ)**:  each file *f* at index *i* of *N* total files gets
   a base angle  θ_f = i × (180 / N)  degrees.  The short-interval
   mirror is placed at θ_f + 180°.
*  **Vertical (z)**:  Cycle Duration cd_k (ms) — **not** a rank index.

Stage 2 — Volumetric Flower
----------------------------
*  **Mesh3d skin** with ``alphahull`` wraps a non-convex surface around
   each file's point cloud, creating a solid 3D sculpture of rhythm.
*  **Signature Mode (single file)**: the 2D profile is replicated across
   N discrete angular steps (default 32) from 0°–360°, producing a
   lathe-like solid of revolution.
*  **Group Mode**: files are assigned to named groups (e.g. by species,
   culture, or recording site).  Each group receives an equal angular
   sector of the flower and its constituent files are lathe-revolved
   within that sector, keeping group data spatially clustered.
   Additional Excel workbooks can be merged in via ``EXTRA_SOURCES``.

Pipeline role
~~~~~~~~~~~~~
- Input:  ``Cross_Species_Rhythm_Data.xlsx`` (+ optional extra workbooks)
- Output: HTML and/or PNG in ``Raster_Plots/<dataset>/``
- Called as Step 3b by ``main.py``
"""

import os
import sys
import fnmatch

import numpy as np
import pandas as pd


# =====================================================================
# 1. CONFIGURATION
# =====================================================================

excel_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "Cross_Species_Rhythm_Data.xlsx")
output_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "Raster_Plots")

PLOT_DATASETS = ("raw", "stable")

# 3D-specific settings — Stage 1 (skeleton)
RASTER_3D_ENABLED = False
RASTER_3D_FORMAT = "html"          # "html", "png", or "both"
RASTER_3D_DOT_SIZE = 2.5
RASTER_3D_PETAL_OPACITY = 0.70
RASTER_3D_COLORMAP = "rainbow"     # rainbow | cool | warm | pastel
RASTER_3D_BG_COLOR = "#ffffff"
RASTER_3D_SHOW_LABELS = True
RASTER_3D_SHOW_STEMS = True        # translucent petal mid-planes
RASTER_3D_ELEVATION = 25           # static PNG camera elevation (deg)
RASTER_3D_AZIMUTH = -60            # static PNG camera azimuth (deg)
RASTER_3D_FIG_WIDTH = 1200         # pixels for both formats
RASTER_3D_FIG_HEIGHT = 900

# Stage 2 (volumetric)
RASTER_3D_MESH_ENABLED = True      # add Mesh3d alphahull skin
RASTER_3D_MESH_OPACITY = 0.6       # mesh transparency
RASTER_3D_ALPHAHULL = 7            # alphahull concavity (lower = tighter)
RASTER_3D_SHOW_SKELETON = True     # show skeleton dots under the mesh
RASTER_3D_LATHE_STEPS = 32         # angular steps for lathe replication

# Group mode (replaces old split-flower)
RASTER_3D_GROUP_MODE = False        # enable grouped angular layout
RASTER_3D_GROUPS = {}               # {"Group Name": ["pattern1*", "pattern2*"], ...}
RASTER_3D_EXTRA_SOURCES = []        # list of additional .xlsx workbook paths

# ------------------------------------------------------------------
# GUI CONFIG OVERRIDE
# ------------------------------------------------------------------
_config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "pipeline_config.json")
if os.path.isfile(_config_path):
    import json as _json
    with open(_config_path) as _f:
        _cfg = _json.load(_f).get("plot_generator", {})
    excel_path = _cfg.get("excel_path", excel_path)
    output_folder = _cfg.get("output_folder", output_folder)
    PLOT_DATASETS = tuple(_cfg.get("PLOT_DATASETS", list(PLOT_DATASETS)))
    RASTER_3D_ENABLED     = _cfg.get("RASTER_3D_ENABLED", RASTER_3D_ENABLED)
    RASTER_3D_FORMAT      = _cfg.get("RASTER_3D_FORMAT", RASTER_3D_FORMAT)
    RASTER_3D_DOT_SIZE    = _cfg.get("RASTER_3D_DOT_SIZE", RASTER_3D_DOT_SIZE)
    RASTER_3D_PETAL_OPACITY = _cfg.get("RASTER_3D_PETAL_OPACITY", RASTER_3D_PETAL_OPACITY)
    RASTER_3D_COLORMAP    = _cfg.get("RASTER_3D_COLORMAP", RASTER_3D_COLORMAP)
    RASTER_3D_BG_COLOR    = _cfg.get("RASTER_3D_BG_COLOR", RASTER_3D_BG_COLOR)
    RASTER_3D_SHOW_LABELS = _cfg.get("RASTER_3D_SHOW_LABELS", RASTER_3D_SHOW_LABELS)
    RASTER_3D_SHOW_STEMS  = _cfg.get("RASTER_3D_SHOW_STEMS", RASTER_3D_SHOW_STEMS)
    RASTER_3D_ELEVATION   = _cfg.get("RASTER_3D_ELEVATION", RASTER_3D_ELEVATION)
    RASTER_3D_AZIMUTH     = _cfg.get("RASTER_3D_AZIMUTH", RASTER_3D_AZIMUTH)
    RASTER_3D_FIG_WIDTH   = _cfg.get("RASTER_3D_FIG_WIDTH", RASTER_3D_FIG_WIDTH)
    RASTER_3D_FIG_HEIGHT  = _cfg.get("RASTER_3D_FIG_HEIGHT", RASTER_3D_FIG_HEIGHT)
    # Stage 2
    RASTER_3D_MESH_ENABLED   = _cfg.get("RASTER_3D_MESH_ENABLED", RASTER_3D_MESH_ENABLED)
    RASTER_3D_MESH_OPACITY   = _cfg.get("RASTER_3D_MESH_OPACITY", RASTER_3D_MESH_OPACITY)
    RASTER_3D_ALPHAHULL      = _cfg.get("RASTER_3D_ALPHAHULL", RASTER_3D_ALPHAHULL)
    RASTER_3D_SHOW_SKELETON  = _cfg.get("RASTER_3D_SHOW_SKELETON", RASTER_3D_SHOW_SKELETON)
    RASTER_3D_LATHE_STEPS    = _cfg.get("RASTER_3D_LATHE_STEPS", RASTER_3D_LATHE_STEPS)
    # Group mode
    RASTER_3D_GROUP_MODE     = _cfg.get("RASTER_3D_GROUP_MODE", RASTER_3D_GROUP_MODE)
    RASTER_3D_GROUPS         = _cfg.get("RASTER_3D_GROUPS", RASTER_3D_GROUPS)
    RASTER_3D_EXTRA_SOURCES  = _cfg.get("RASTER_3D_EXTRA_SOURCES", RASTER_3D_EXTRA_SOURCES)
    del _json, _f, _cfg


os.makedirs(output_folder, exist_ok=True)


# =====================================================================
# 2. COLOUR PALETTES
# =====================================================================

_PALETTES = {
    "rainbow": [
        "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
        "#42d4f4", "#f032e6", "#bfef45", "#fabed4", "#469990",
        "#dcbeff", "#9A6324", "#fffac8", "#800000", "#aaffc3",
        "#808000", "#ffd8b1", "#000075", "#a9a9a9", "#e6beff",
    ],
    "cool": [
        "#1f77b4", "#17becf", "#2ca02c", "#98df8a", "#9467bd",
        "#c5b0d5", "#8c564b", "#c49c94", "#7f7f7f", "#c7c7c7",
        "#393b79", "#5254a3", "#6b6ecf", "#9c9ede", "#637939",
        "#8ca252", "#b5cf6b", "#cedb9c", "#8c6d31", "#bd9e39",
    ],
    "warm": [
        "#e6194b", "#f58231", "#ffe119", "#fabebe", "#ff6f61",
        "#d2691e", "#e77c8e", "#c0392b", "#f39c12", "#e74c3c",
        "#ff4500", "#ff8c00", "#ffa07a", "#cd5c5c", "#dc143c",
        "#db7093", "#ff1493", "#ff69b4", "#c71585", "#b22222",
    ],
    "pastel": [
        "#aec6cf", "#ffb7b2", "#b5ead7", "#ffdac1", "#e2f0cb",
        "#c7ceea", "#f0e6ef", "#fdfd96", "#ff9aa2", "#b2cefe",
        "#d4a5a5", "#a0d2db", "#e8d5b7", "#c3b1e1", "#b5e7a0",
        "#ffc3a0", "#ffccf9", "#d5aaff", "#85e3ff", "#bffcc6",
    ],
}


def _get_petal_colors(n):
    """Return *n* hex colours from the active palette, cycling if needed."""
    pal = _PALETTES.get(RASTER_3D_COLORMAP, _PALETTES["rainbow"])
    return [pal[i % len(pal)] for i in range(n)]


# =====================================================================
# 3. DATA LOADING
# =====================================================================

def load_plot_datasets(workbook_path, selected_datasets):
    """Load dyadic sheets that are available for plotting."""
    dataset_sheets = {
        "raw":    "Dyadic Events (For Plots)",
        "stable": "Dyadic Events (Stable Rhythms)",
    }
    loaded = []
    workbook = pd.ExcelFile(workbook_path)
    for ds_name in selected_datasets:
        sheet = dataset_sheets[ds_name]
        if sheet not in workbook.sheet_names:
            print(f"  Skipping {ds_name} — sheet '{sheet}' not found.")
            continue
        df = pd.read_excel(workbook_path, sheet_name=sheet)
        if df.empty:
            print(f"  Skipping {ds_name} — sheet '{sheet}' is empty.")
            continue
        loaded.append((ds_name, df))
    return loaded


def _merge_extra_sources(base_datasets, extra_paths, selected_datasets):
    """Load matching sheets from extra workbooks and merge rows into
    the base datasets so all files end up in a single DataFrame per
    dataset name (raw / stable)."""
    if not extra_paths:
        return base_datasets

    dataset_sheets = {
        "raw":    "Dyadic Events (For Plots)",
        "stable": "Dyadic Events (Stable Rhythms)",
    }

    # Build a lookup: ds_name → DataFrame
    merged = {ds: df.copy() for ds, df in base_datasets}

    for wb_path in extra_paths:
        if not os.path.isfile(wb_path):
            print(f"  Extra source not found, skipping: {wb_path}")
            continue
        print(f"  Merging extra source: {wb_path}")
        try:
            wb = pd.ExcelFile(wb_path)
        except Exception as exc:
            print(f"    Could not open: {exc}")
            continue
        for ds_name in selected_datasets:
            sheet = dataset_sheets.get(ds_name)
            if sheet and sheet in wb.sheet_names:
                extra_df = pd.read_excel(wb_path, sheet_name=sheet)
                if extra_df.empty:
                    continue
                if ds_name in merged:
                    merged[ds_name] = pd.concat(
                        [merged[ds_name], extra_df], ignore_index=True)
                else:
                    merged[ds_name] = extra_df

    return list(merged.items())


# =====================================================================
# 3b. GROUP ASSIGNMENT
# =====================================================================

def _assign_groups(filenames, group_patterns):
    """Assign each filename to a group using fnmatch patterns.

    *group_patterns* is ``{"Group A": ["pat1*", "pat2*"], ...}``.
    Files not matching any pattern go into an "Ungrouped" bucket.

    Returns an ordered list of ``(group_name, [filenames])`` preserving
    the order groups appear in *group_patterns*.
    """
    assigned = {}       # group_name → [filename, ...]
    group_order = []    # to preserve insertion order
    used = set()

    for gname, patterns in group_patterns.items():
        members = []
        for fname in filenames:
            for pat in patterns:
                if fnmatch.fnmatch(fname, pat):
                    members.append(fname)
                    used.add(fname)
                    break
        if members:
            assigned[gname] = members
            group_order.append(gname)

    # Anything left goes to "Ungrouped"
    leftover = [f for f in filenames if f not in used]
    if leftover:
        assigned["Ungrouped"] = leftover
        group_order.append("Ungrouped")

    return [(g, assigned[g]) for g in group_order]


# =====================================================================
# 4. CYLINDRICAL → CARTESIAN TRANSFORM
# =====================================================================

def _cylindrical_to_cartesian(radii, z_vals, theta_rad):
    """Convert cylindrical (r, θ, z) to Cartesian (x, y, z)."""
    x = radii * np.cos(theta_rad)
    y = radii * np.sin(theta_rad)
    return x, y, z_vals


# =====================================================================
# 4b. LATHE REPLICATION (Stage 2)
# =====================================================================

def _lathe_replicate(i_l, i_s, cd, theta_start_deg, theta_end_deg, n_steps):
    """Replicate dyads across angular range to create a solid of revolution.

    Returns combined (x, y, z) arrays for all replicated points (both
    long and short sides).
    """
    angles = np.linspace(np.radians(theta_start_deg),
                         np.radians(theta_end_deg),
                         n_steps, endpoint=False)
    all_x, all_y, all_z = [], [], []
    for theta in angles:
        # Long side at θ
        lx, ly, lz = _cylindrical_to_cartesian(i_l, cd, theta)
        all_x.append(lx)
        all_y.append(ly)
        all_z.append(lz)
        # Short side mirrored at θ + 180°
        sx, sy, sz = _cylindrical_to_cartesian(i_s, cd, theta + np.pi)
        all_x.append(sx)
        all_y.append(sy)
        all_z.append(sz)
    return np.concatenate(all_x), np.concatenate(all_y), np.concatenate(all_z)


# =====================================================================
# 5a. PLOTLY — interactive HTML
# =====================================================================

def _add_skeleton_traces(fig, petal_data, colors, n_files, file_angles):
    """Add Stage 1 skeleton scatter dots + stems + labels to *fig*.

    *file_angles* maps filename → (theta_long_rad, theta_short_rad).
    """
    z_min_global = float("inf")
    z_max_global = float("-inf")

    for idx, (filename, df) in enumerate(petal_data):
        theta_long, theta_short = file_angles[filename]

        cd = df["Cycle Duration [cd] (ms)"].values
        i_s = df["Short Interval [i_s] (ms)"].values
        i_l = df["Long Interval [i_l] (ms)"].values

        z_min_global = min(z_min_global, cd.min())
        z_max_global = max(z_max_global, cd.max())

        short_name = os.path.splitext(filename)[0]

        # Long-interval side
        lx, ly, lz = _cylindrical_to_cartesian(i_l, cd, theta_long)
        fig.add_trace(go.Scatter3d(
            x=lx, y=ly, z=lz,
            mode="markers",
            marker=dict(size=RASTER_3D_DOT_SIZE, color=colors[idx],
                        opacity=RASTER_3D_PETAL_OPACITY, line=dict(width=0)),
            name=short_name,
            legendgroup=filename,
            showlegend=True,
            hovertemplate=(
                f"<b>{short_name}</b><br>"
                "i_l: %{customdata[0]:.1f} ms<br>"
                "cd: %{customdata[1]:.1f} ms<extra></extra>"
            ),
            customdata=np.column_stack([i_l, cd]),
        ))

        # Short-interval side (mirrored)
        sx, sy, sz = _cylindrical_to_cartesian(i_s, cd, theta_short)
        fig.add_trace(go.Scatter3d(
            x=sx, y=sy, z=sz,
            mode="markers",
            marker=dict(size=RASTER_3D_DOT_SIZE, color=colors[idx],
                        opacity=RASTER_3D_PETAL_OPACITY, line=dict(width=0)),
            name=f"{short_name} (short)",
            legendgroup=filename,
            showlegend=False,
            hovertemplate=(
                f"<b>{short_name}</b><br>"
                "i_s: %{customdata[0]:.1f} ms<br>"
                "cd: %{customdata[1]:.1f} ms<extra></extra>"
            ),
            customdata=np.column_stack([i_s, cd]),
        ))

        # Translucent mid-plane stems
        if RASTER_3D_SHOW_STEMS and len(cd) > 1:
            max_r = max(np.max(i_l), np.max(i_s))
            stem_r = np.array([0, max_r])
            stem_z = np.array([cd.min(), cd.max()])
            rr, zz = np.meshgrid(stem_r, stem_z)
            for th in (theta_long, theta_short):
                fig.add_trace(go.Surface(
                    x=rr * np.cos(th), y=rr * np.sin(th), z=zz,
                    colorscale=[[0, colors[idx]], [1, colors[idx]]],
                    opacity=0.08, showscale=False, showlegend=False,
                    hoverinfo="skip",
                ))

        # Petal label
        if RASTER_3D_SHOW_LABELS and len(cd) > 0:
            label_r = max(np.max(i_l), np.max(i_s)) * 1.10
            fig.add_trace(go.Scatter3d(
                x=[label_r * np.cos(theta_long)],
                y=[label_r * np.sin(theta_long)],
                z=[cd.max()],
                mode="text", text=[short_name],
                textfont=dict(size=9, color=colors[idx]),
                showlegend=False, hoverinfo="skip",
            ))

    return z_min_global, z_max_global


def _envelope_profile(cd, intervals, z_grid, pad=1.10):
    """Compute a smooth max-envelope radial profile that contains all points.

    1. Scatter every data point into the nearest z-grid bin (taking max).
    2. Running-maximum over a wide window so nearby sparse bins inherit
       the peak radius of their neighbours.
    3. Gaussian-like smoothing to eliminate staircase artefacts.
    4. Cosine taper that slopes the skin gently to r = 0 outside the
       file's data range (30 % of the data span on each end), so
       adjacent skins of different heights curve toward each other.
    """
    n_z = len(z_grid)
    profile = np.zeros(n_z)

    z_min, z_max = z_grid[0], z_grid[-1]
    z_span = z_max - z_min
    if z_span < 1e-9:
        return profile

    # --- 1.  Scatter data into bins (max per bin) --------------------
    indices = np.clip(
        ((cd - z_min) / z_span * (n_z - 1)).astype(int), 0, n_z - 1)
    for k in range(len(cd)):
        profile[indices[k]] = max(profile[indices[k]], abs(intervals[k]))

    # --- 2.  Running maximum (window ~ 15 % of n_z) -----------------
    hw = max(int(n_z * 0.075), 2)            # half-window
    run_max = profile.copy()
    for i in range(n_z):
        lo = max(0, i - hw)
        hi = min(n_z, i + hw + 1)
        run_max[i] = profile[lo:hi].max()

    # --- 3.  Smooth with a simple triangle kernel --------------------
    kern_hw = max(int(n_z * 0.06), 2)
    kernel = np.concatenate([np.arange(1, kern_hw + 1),
                             [kern_hw + 1],
                             np.arange(kern_hw, 0, -1)]).astype(float)
    kernel /= kernel.sum()
    smoothed = np.convolve(run_max, kernel, mode="same")

    smoothed *= pad  # headroom

    # --- 4.  Cosine taper outside the file's data range --------------
    data_zmin = cd.min()
    data_zmax = cd.max()
    data_span = data_zmax - data_zmin
    margin = max(data_span * 0.30, z_span * 0.05)   # at least 5 % of total

    for i in range(n_z):
        z = z_grid[i]
        if z < data_zmin - margin:
            smoothed[i] = 0.0
        elif z < data_zmin:
            # smooth cosine ramp  0 → 1
            t = (z - (data_zmin - margin)) / margin
            smoothed[i] *= 0.5 * (1.0 - np.cos(np.pi * t))
        elif z > data_zmax + margin:
            smoothed[i] = 0.0
        elif z > data_zmax:
            # smooth cosine ramp  1 → 0
            t = ((data_zmax + margin) - z) / margin
            smoothed[i] *= 0.5 * (1.0 - np.cos(np.pi * t))

    return smoothed


def _build_profile_ring(petal_data, colors, file_angles, z_grid,
                        grouped_layout=None):
    """Build an ordered ring of (angle, profile, colour) around 360°.

    Each file contributes **two** envelope profiles:
      • long-interval  at the file's base angle θ
      • short-interval at θ + 180°

    Profiles use max-envelope binning so all dots are fully contained,
    and taper to 0 outside each file's own z-range.

    Returns a list sorted by angle:
      ``[(angle_rad, profile_r, hex_colour, label), ...]``
    """
    profiles = []

    if grouped_layout:
        for gidx, (gname, fnames, s_deg, e_deg) in enumerate(grouped_layout):
            pls, pss = [], []
            for fn in fnames:
                df = next((d for f, d in petal_data if f == fn), None)
                if df is None:
                    continue
                cd = df["Cycle Duration [cd] (ms)"].values
                il = df["Long Interval [i_l] (ms)"].values
                is_ = df["Short Interval [i_s] (ms)"].values
                pls.append(_envelope_profile(cd, il, z_grid))
                pss.append(_envelope_profile(cd, is_, z_grid))
            if not pls:
                continue
            # For groups, take the element-wise max across files
            ml = np.max(pls, axis=0)
            ms = np.max(pss, axis=0)
            mid = np.radians((s_deg + e_deg) / 2.0)
            fidx = next(
                (i for i, (fn, _) in enumerate(petal_data) if fn in fnames),
                gidx)
            clr = colors[fidx]
            profiles.append((mid, ml, clr, f"{gname} (long)"))
            profiles.append((mid + np.pi, ms, clr, f"{gname} (short)"))
    else:
        for idx, (fname, df) in enumerate(petal_data):
            cd = df["Cycle Duration [cd] (ms)"].values
            il = df["Long Interval [i_l] (ms)"].values
            is_ = df["Short Interval [i_s] (ms)"].values
            prof_l = _envelope_profile(cd, il, z_grid)
            prof_s = _envelope_profile(cd, is_, z_grid)
            theta_long = file_angles[fname][0]
            short_name = os.path.splitext(fname)[0]
            profiles.append((theta_long, prof_l, colors[idx],
                              f"{short_name} (long)"))
            profiles.append((theta_long + np.pi, prof_s, colors[idx],
                              f"{short_name} (short)"))

    profiles.sort(key=lambda x: x[0])
    return profiles


def _build_splines(ring, n_z):
    """Build one periodic cubic spline per z-level through the ring.

    Interpolation is performed in **log-space**: each spline maps
    angle → log(radius).  This prevents the cubic polynomial from
    overshooting to negative radii when the dynamic range is large
    (e.g. File 2 i_l ≈ 7 000 ms vs the connectivity floor ≈ 100 ms).
    Callers must exponentiate: ``r = np.exp(spline(theta))``.

    Returns a list of *n_z* ``CubicSpline`` objects (or ``None`` if
    scipy is unavailable).
    """
    try:
        from scipy.interpolate import CubicSpline
    except ImportError:
        return None

    prof_angles = np.array([a for a, _, _, _ in ring])
    prof_radii = np.column_stack([p for _, p, _, _ in ring])  # (n_z, n_prof)

    # Extend by one period for the periodic BC
    angles_ext = np.append(prof_angles, prof_angles[0] + 2 * np.pi)
    splines = []
    for zi in range(n_z):
        radii = np.maximum(prof_radii[zi, :], 1e-6)  # guard log(0)
        log_ext = np.append(np.log(radii), np.log(radii[0]))
        splines.append(
            CubicSpline(angles_ext, log_ext, bc_type='periodic'))
    return splines


def _ensure_profile_floor(ring, floor_fraction=0.08,
                          global_floor_fraction=0.015):
    """Lift zero-profile values so every z-slice stays connected.

    Two passes:

    1. **Per-z floor** — at each z-level, every profile is raised to at
       least ``floor_fraction × max_radius_at_that_z``.
    2. **Global floor** — every profile everywhere is raised to at least
       ``global_floor_fraction × overall_max_radius``.  This turns
       z-levels with *no* data into a thin connecting tube rather than
       a hole, keeping the surface topologically closed from bottom to
       top.
    """
    n_z = len(ring[0][1])
    mat = np.column_stack([p for _, p, _, _ in ring])   # (n_z, n_prof)
    # --- per-z floor ---
    z_max = mat.max(axis=1, keepdims=True)               # (n_z, 1)
    floor = floor_fraction * z_max                        # (n_z, 1)
    mat = np.maximum(mat, floor)
    # --- global floor ---
    global_max = mat.max()
    if global_max > 0:
        mat = np.maximum(mat, global_floor_fraction * global_max)
    return [(a, mat[:, i], c, l)
            for i, (a, _, c, l) in enumerate(ring)]


def _add_surface_traces(fig, petal_data, colors, file_angles,
                        grouped_layout=None):
    """Add a single closed surface shell using periodic cubic splines.

    A connectivity floor prevents any radial profile from reaching zero
    so the resulting mesh is always one connected piece.  The surface is
    rendered as **one** ``go.Surface`` trace whose first and last angular
    columns coincide, producing a topologically closed cylinder with no
    inter-panel seams.  Colour is mapped continuously via the angular
    position of each vertex.
    """
    if not petal_data:
        return

    n_z = 120
    all_cd = np.concatenate(
        [df["Cycle Duration [cd] (ms)"].values for _, df in petal_data])
    z_grid = np.linspace(all_cd.min(), all_cd.max(), n_z)

    ring = _build_profile_ring(petal_data, colors, file_angles, z_grid,
                               grouped_layout)
    n_prof = len(ring)
    if n_prof < 2:
        return

    # Ensure connectivity — no profile collapses to zero
    ring = _ensure_profile_floor(ring)

    splines = _build_splines(ring, n_z)
    if not splines:
        return

    # --- single closed surface ---
    n_ang = max(n_prof * 16, 128)
    # Include endpoint (0 ≡ 2π) so the mesh closes into a cylinder
    angles = np.linspace(0, 2 * np.pi, n_ang + 1)

    xs = np.zeros((n_z, n_ang + 1))
    ys = np.zeros((n_z, n_ang + 1))
    zs = np.tile(z_grid.reshape(-1, 1), (1, n_ang + 1))

    for zi in range(n_z):
        r = np.exp(splines[zi](angles))   # log-space spline → always > 0
        xs[zi, :] = r * np.cos(angles)
        ys[zi, :] = r * np.sin(angles)

    # --- colour by angular sector ---
    cscale = []
    for a, _, c, _ in ring:
        cscale.append([a / (2 * np.pi), c])
    cscale.append([1.0, ring[0][2]])          # close the loop
    cscale.sort(key=lambda x: x[0])
    if cscale[0][0] > 1e-9:                   # ensure start at 0
        cscale.insert(0, [0.0, ring[-1][2]])

    surf_color = np.tile(angles / (2 * np.pi), (n_z, 1))

    fig.add_trace(go.Surface(
        x=xs, y=ys, z=zs,
        surfacecolor=surf_color,
        colorscale=cscale,
        opacity=RASTER_3D_MESH_OPACITY,
        showscale=False,
        name="Flower skin",
        showlegend=False,
        hoverinfo="skip",
    ))


# ------------------------------------------------------------------
# Angle-assignment helpers
# ------------------------------------------------------------------

def _compute_file_angles_flat(filenames):
    """Each file gets its own petal at θ = i × (180/N)."""
    n = len(filenames)
    angles = {}
    for i, fn in enumerate(filenames):
        th_long = np.radians(i * (180.0 / n))
        th_short = th_long + np.pi
        angles[fn] = (th_long, th_short)
    return angles


def _compute_file_angles_grouped(grouped_layout):
    """Files within each group share the group's sector mid-angle."""
    angles = {}
    for gname, fnames, sec_start, sec_end in grouped_layout:
        n = len(fnames)
        for j, fn in enumerate(fnames):
            if n == 1:
                mid = (sec_start + sec_end) / 2.0
            else:
                mid = sec_start + (j + 0.5) * (sec_end - sec_start) / n
            th_long = np.radians(mid)
            th_short = th_long + np.pi
            angles[fn] = (th_long, th_short)
    return angles


def _build_grouped_layout(petal_data, group_patterns):
    """Create (group_name, [filenames], sec_start, sec_end) list.

    360° is divided equally among groups.
    """
    filenames = [fn for fn, _ in petal_data]
    groups = _assign_groups(filenames, group_patterns)
    n_groups = len(groups)
    sector_size = 180.0 / n_groups
    layout = []
    for gi, (gname, fnames) in enumerate(groups):
        sec_start = gi * sector_size
        sec_end = sec_start + sector_size
        layout.append((gname, fnames, sec_start, sec_end))
    return layout


# ------------------------------------------------------------------
# HTML generation
# ------------------------------------------------------------------

def _create_3d_html(petal_data, dataset_name, save_path, grouped_layout=None):
    """Build an interactive 3D flower using Plotly and save as HTML."""
    n_files = len(petal_data)
    colors = _get_petal_colors(n_files)

    if grouped_layout:
        file_angles = _compute_file_angles_grouped(grouped_layout)
    else:
        file_angles = _compute_file_angles_flat([fn for fn, _ in petal_data])

    fig = go.Figure()

    # Stage 1 skeleton
    if RASTER_3D_SHOW_SKELETON or not RASTER_3D_MESH_ENABLED:
        z_min_global, z_max_global = _add_skeleton_traces(
            fig, petal_data, colors, n_files, file_angles)
    else:
        z_min_global = float("inf")
        z_max_global = float("-inf")
        for _, df in petal_data:
            cd = df["Cycle Duration [cd] (ms)"].values
            z_min_global = min(z_min_global, cd.min())
            z_max_global = max(z_max_global, cd.max())

    # Stage 2 volumetric surfaces
    if RASTER_3D_MESH_ENABLED:
        _add_surface_traces(fig, petal_data, colors,
                            file_angles, grouped_layout)

    # Central vertical axis
    if petal_data and z_max_global > z_min_global:
        z_pad = (z_max_global - z_min_global) * 0.05
        fig.add_trace(go.Scatter3d(
            x=[0, 0], y=[0, 0],
            z=[z_min_global - z_pad, z_max_global + z_pad],
            mode="lines",
            line=dict(color="black", width=5),
            name="Zero-interval axis",
            showlegend=False, hoverinfo="skip",
        ))

    # Mode label
    if len(petal_data) == 1:
        mode_label = "Signature"
    elif grouped_layout:
        n_grp = len(grouped_layout)
        mode_label = f"Grouped ({n_grp} groups)"
    else:
        mode_label = "Comparison"

    fig.update_layout(
        title=dict(
            text=f"3D Flower Raster ({mode_label}) — {dataset_name.title()}",
            font=dict(size=18),
        ),
        scene=dict(
            xaxis_title="X  (r · cos θ)  [ms]",
            yaxis_title="Y  (r · sin θ)  [ms]",
            zaxis_title="Cycle Duration  cd  [ms]",
            bgcolor=RASTER_3D_BG_COLOR,
            aspectmode="data",
        ),
        width=RASTER_3D_FIG_WIDTH,
        height=RASTER_3D_FIG_HEIGHT,
        legend=dict(font=dict(size=9), itemsizing="constant"),
        margin=dict(l=10, r=10, t=50, b=10),
    )

    fig.write_html(save_path, include_plotlyjs="cdn")
    print(f"  Saved interactive 3D flower → {save_path}")


# =====================================================================
# 5b. MATPLOTLIB — static PNG
# =====================================================================

def _create_3d_png(petal_data, dataset_name, save_path, grouped_layout=None):
    """Build a static 3D flower skeleton using matplotlib."""
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

    n_files = len(petal_data)
    colors = _get_petal_colors(n_files)

    if grouped_layout:
        file_angles = _compute_file_angles_grouped(grouped_layout)
    else:
        file_angles = _compute_file_angles_flat([fn for fn, _ in petal_data])

    dpi = 150
    fig = plt.figure(figsize=(RASTER_3D_FIG_WIDTH / dpi, RASTER_3D_FIG_HEIGHT / dpi), dpi=dpi)
    ax = fig.add_subplot(111, projection="3d")

    z_min_global = float("inf")
    z_max_global = float("-inf")

    petal_dict = {fn: df for fn, df in petal_data}
    is_single = (len(petal_data) == 1 and grouped_layout is None)

    for idx, (filename, df) in enumerate(petal_data):
        cd = df["Cycle Duration [cd] (ms)"].values
        i_s = df["Short Interval [i_s] (ms)"].values
        i_l = df["Long Interval [i_l] (ms)"].values

        z_min_global = min(z_min_global, cd.min())
        z_max_global = max(z_max_global, cd.max())

        short_name = os.path.splitext(filename)[0]
        theta_long, theta_short = file_angles[filename]

        if RASTER_3D_SHOW_SKELETON or not RASTER_3D_MESH_ENABLED:
            lx, ly, lz = _cylindrical_to_cartesian(i_l, cd, theta_long)
            ax.scatter(lx, ly, lz, s=RASTER_3D_DOT_SIZE, color=colors[idx],
                       alpha=RASTER_3D_PETAL_OPACITY, label=short_name, rasterized=True)

            sx, sy, sz = _cylindrical_to_cartesian(i_s, cd, theta_short)
            ax.scatter(sx, sy, sz, s=RASTER_3D_DOT_SIZE, color=colors[idx],
                       alpha=RASTER_3D_PETAL_OPACITY, rasterized=True)

            if RASTER_3D_SHOW_LABELS and len(cd) > 0:
                label_r = max(np.max(i_l), np.max(i_s)) * 1.10
                ax.text(label_r * np.cos(theta_long), label_r * np.sin(theta_long),
                        cd.max(), short_name, fontsize=6, color=colors[idx], ha="center")

    # Surface (spline-based, single closed mesh — same approach as Plotly)
    if RASTER_3D_MESH_ENABLED and petal_data:
        from matplotlib.colors import to_rgba

        n_z_surf = 120
        all_cd_surf = np.concatenate(
            [df["Cycle Duration [cd] (ms)"].values for _, df in petal_data])
        z_grid_surf = np.linspace(all_cd_surf.min(), all_cd_surf.max(),
                                  n_z_surf)

        ring = _build_profile_ring(petal_data, colors, file_angles,
                                   z_grid_surf, grouped_layout)
        n_prof = len(ring)

        if n_prof >= 2:
            ring = _ensure_profile_floor(ring)
            splines = _build_splines(ring, n_z_surf)

            if splines:
                na = max(n_prof * 8, 64)
                angs = np.linspace(0, 2 * np.pi, na + 1)

                xs = np.zeros((n_z_surf, na + 1))
                ys = np.zeros((n_z_surf, na + 1))
                zs = np.tile(z_grid_surf.reshape(-1, 1), (1, na + 1))

                for zi in range(n_z_surf):
                    r = np.exp(splines[zi](angs))
                    xs[zi, :] = r * np.cos(angs)
                    ys[zi, :] = r * np.sin(angs)

                avg_clr = to_rgba(colors[0], RASTER_3D_MESH_OPACITY)
                ax.plot_surface(xs, ys, zs, color=avg_clr,
                                shade=True, edgecolor="none",
                                rasterized=True)

    # Central axis
    if petal_data and z_max_global > z_min_global:
        z_pad = (z_max_global - z_min_global) * 0.05
        ax.plot([0, 0], [0, 0], [z_min_global - z_pad, z_max_global + z_pad],
                color="black", linewidth=2)

    ax.set_xlabel("X (r · cos θ) [ms]", fontsize=8, labelpad=5)
    ax.set_ylabel("Y (r · sin θ) [ms]", fontsize=8, labelpad=5)
    ax.set_zlabel("Cycle Duration cd [ms]", fontsize=8, labelpad=5)
    ax.set_title(f"3D Flower Raster — {dataset_name.title()}",
                 fontsize=13, fontweight="bold")
    ax.view_init(elev=RASTER_3D_ELEVATION, azim=RASTER_3D_AZIMUTH)

    if n_files <= 15:
        ax.legend(fontsize=6, loc="upper left", framealpha=0.7,
                  markerscale=3, handletextpad=0.3)

    fig.tight_layout()
    fig.savefig(save_path, dpi=dpi)
    plt.close(fig)
    print(f"  Saved static 3D flower → {save_path}")


# =====================================================================
# 6. MAIN
# =====================================================================

# Lazy import for plotly (used by helper functions above)
import importlib as _il
go = None

def _ensure_plotly():
    global go
    if go is None:
        go = _il.import_module("plotly.graph_objects")

if __name__ == "__main__":
    if not RASTER_3D_ENABLED:
        print("3D Flower Raster is disabled — skipping.")
        sys.exit(0)

    _ensure_plotly()

    print("\n=== 3D Flower Raster Plots ===")

    if not os.path.isfile(excel_path):
        print(f"ERROR: Workbook not found: {excel_path}")
        print("Run the Onset Finder (Step 2) first.")
        sys.exit(1)

    datasets = load_plot_datasets(excel_path, PLOT_DATASETS)

    # Merge any extra workbook sources
    if RASTER_3D_EXTRA_SOURCES:
        datasets = _merge_extra_sources(datasets, RASTER_3D_EXTRA_SOURCES,
                                        PLOT_DATASETS)

    if not datasets:
        print("No datasets available — nothing to plot.")
        sys.exit(0)

    want_html = RASTER_3D_FORMAT in ("html", "both")
    want_png  = RASTER_3D_FORMAT in ("png", "both")

    for ds_name, df in datasets:
        ds_folder = os.path.join(output_folder, ds_name)
        os.makedirs(ds_folder, exist_ok=True)

        files = df["File Name"].unique()

        petal_data = []
        for fname in files:
            fdf = df[df["File Name"] == fname]
            if fdf.empty:
                continue
            petal_data.append((fname, fdf))

        if not petal_data:
            continue

        # Build grouped layout if enabled
        grouped_layout = None
        if RASTER_3D_GROUP_MODE and RASTER_3D_GROUPS and len(petal_data) > 1:
            grouped_layout = _build_grouped_layout(petal_data, RASTER_3D_GROUPS)

        # Determine mode label
        if len(petal_data) == 1:
            mode = "Signature (single-file lathe)"
        elif grouped_layout:
            gnames = [g[0] for g in grouped_layout]
            mode = f"Grouped ({', '.join(gnames)})"
        else:
            mode = f"{len(petal_data)}-file comparison"

        print(f"  {ds_name}: {mode}...")

        if want_html:
            html_path = os.path.join(ds_folder, "3D_Flower_Raster.html")
            _create_3d_html(petal_data, ds_name, html_path, grouped_layout)

        if want_png:
            png_path = os.path.join(ds_folder, "3D_Flower_Raster.png")
            _create_3d_png(petal_data, ds_name, png_path, grouped_layout)

    print("3D Flower Raster complete.\n")
