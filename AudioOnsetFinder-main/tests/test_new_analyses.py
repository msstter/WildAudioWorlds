"""Smoke tests for the new "Multi-Species Rhythmic Landscape" analyses.

Generates a small synthetic Cross_Species_Rhythm_Data.xlsx in a temp
directory, writes a pipeline_config.json alongside it pointing each new
step at that workbook, then runs each of the 10 new scripts as a
subprocess and asserts the expected outputs exist.

Covers:
- rhythmRatios.py           (A1)
- ksTest.py                 (A2)
- wilcoxonIsochrony.py      (A3)
- lagOneAutocorrelation.py  (A4)
- tempoRatioHeatmap.py      (B1)
- raincloudMetrics.py       (B2)
- pDFA.py                   (C1)
- mantelTest.py             (C2)
- glmmRhythm.py             (C3)
- pgls.py                   (D1)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.join(_REPO_ROOT, "scripts")


def _build_synth_excel(path: str, seed: int = 0):
    rng = np.random.default_rng(seed)
    groups = ["EastAfrica", "WestAfrica", "Australia"]
    species = {"EastAfrica": "Pan_troglodytes_schweinfurthii",
               "WestAfrica": "Pan_troglodytes_verus",
               "Australia": "Malurus_cyaneus"}
    coords = {"EastAfrica": (0.5, 30.0),
              "WestAfrica": (7.0, -5.0),
              "Australia": (-33.0, 150.0)}
    modality = {"EastAfrica": "hand_on_wood",
                "WestAfrica": "hand_on_wood",
                "Australia": "stick_on_skin"}
    function = {"EastAfrica": "long_distance",
                "WestAfrica": "long_distance",
                "Australia": "close_range"}
    body_mass = {"EastAfrica": 45.0, "WestAfrica": 47.0, "Australia": 0.01}

    # File summaries: 12 files, 4 per group
    file_rows = []
    event_rows_raw = []
    event_rows_stable = []
    for gi, g in enumerate(groups):
        for f in range(4):
            fname = f"{g}_file{f}.wav"
            # Group-specific r distribution
            if g == "EastAfrica":
                rs = rng.beta(2, 2, 30)            # broader
            elif g == "WestAfrica":
                rs = rng.normal(0.5, 0.05, 30).clip(0.02, 0.98)  # peaky
            else:
                rs = rng.uniform(0, 1, 30)         # flat

            intervals = rng.uniform(150, 450, 31)
            cycles = intervals[:-1] + intervals[1:]
            npvi = 100 * np.mean(np.abs(2 * (intervals[1:] - intervals[:-1]) /
                                        (intervals[1:] + intervals[:-1] + 1e-9)))
            cv = float(np.std(intervals) / np.mean(intervals))
            hist, _ = np.histogram(rs, bins=10, range=(0, 1))
            p = hist / hist.sum()
            p = p[p > 0]
            entropy = float(-(p * np.log(p)).sum())
            mean_ioi = float(np.mean(intervals))
            bpm = 60000.0 / mean_ioi

            file_rows.append({
                "File Name": fname,
                "Group": g,
                "Species": species[g],
                "Region": "East Africa" if g == "EastAfrica" else
                          "West Africa" if g == "WestAfrica" else "Oceania",
                "Modality": modality[g],
                "Function": function[g],
                "Individual_ID": f"{g}_ind{f // 2}",
                "Latitude": coords[g][0],
                "Longitude": coords[g][1],
                "BodyMass_kg": body_mass[g],
                "Tempo_BPM": bpm,
                "Number of Onsets": int(len(intervals) + 1),
                "Bout Duration (s)": float(intervals.sum() / 1000),
                "Total Onsets Used": int(len(intervals) + 1),
                "nPVI (Isochrony)": float(npvi),
                "CV of Intervals": cv,
                "r_k Entropy (Categorical Measure)": entropy,
                "Mean IOI (ms)": mean_ioi,
                "Stable Rhythm nPVI": float(npvi * 0.8),
                "Stable Rhythm Entropy": float(entropy * 0.9),
                "Stable Rhythm CV": cv * 0.9,
                "Stable Rhythm Mean IOI (ms)": mean_ioi,
                "Stable Rhythm Onsets Used": int(len(intervals)),
            })
            for k, (r, c, i1) in enumerate(zip(rs, cycles, intervals[:-1])):
                event_rows_raw.append({
                    "File Name": fname, "r_k": float(r),
                    "Cycle Duration (ms)": float(c),
                    "IOI (ms)": float(i1),
                })
                if k % 2 == 0:
                    event_rows_stable.append({
                        "File Name": fname, "r_k": float(r),
                        "Cycle Duration (ms)": float(c),
                        "IOI (ms)": float(i1),
                    })

    df_files = pd.DataFrame(file_rows)
    df_raw = pd.DataFrame(event_rows_raw)
    df_stable = pd.DataFrame(event_rows_stable)

    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        df_files.to_excel(xw, sheet_name="File Summaries", index=False)
        df_raw.to_excel(xw, sheet_name="Dyadic Events (For Plots)", index=False)
        df_stable.to_excel(xw, sheet_name="Dyadic Events (Stable Rhythms)",
                           index=False)


class NewAnalysesSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="bioacoustics_new_steps_")
        cls.excel = os.path.join(cls.tmp, "Cross_Species_Rhythm_Data.xlsx")
        _build_synth_excel(cls.excel, seed=7)

    def _run(self, script: str, cfg_key: str, extra_cfg: dict, out_name: str):
        out_dir = os.path.join(self.tmp, out_name)
        cfg = {
            cfg_key: {
                "excel_path": self.excel,
                "output_folder": out_dir,
                **extra_cfg,
            }
        }
        cfg_path = os.path.join(self.tmp, "pipeline_config.json")
        with open(cfg_path, "w") as fh:
            json.dump(cfg, fh)
        # Run from a working dir where pipeline_config.json lives next to scripts/
        env = os.environ.copy()
        # The script reads <project_root>/pipeline_config.json where project_root
        # is derived from the script location (scripts/..). So we must write the
        # config to THAT path, not the temp dir. Temporarily rename & restore.
        real_cfg = os.path.join(_REPO_ROOT, "pipeline_config.json")
        backup = None
        if os.path.exists(real_cfg):
            backup = real_cfg + ".smoketest_backup"
            os.replace(real_cfg, backup)
        try:
            with open(real_cfg, "w") as fh:
                json.dump(cfg, fh)
            subprocess.run(
                [sys.executable, os.path.join(_SCRIPTS, script)],
                check=True, env=env, cwd=_REPO_ROOT,
            )
        finally:
            try:
                os.remove(real_cfg)
            except FileNotFoundError:
                pass
            if backup is not None:
                os.replace(backup, real_cfg)
        self.assertTrue(os.path.isdir(out_dir),
                        f"{script}: output folder not created")
        return out_dir

    # -- Category A -------------------------------------------------

    def test_A1_rhythmRatios(self):
        out = self._run("rhythmRatios.py", "rhythm_ratios",
                        {"RR_OVERLAY_GROUPS": True,
                         "RR_FACET_PER_GROUP": False},
                        "A1_rhythm_ratios")
        self.assertTrue(os.path.isfile(
            os.path.join(out, "rhythm_ratios_per_group.csv")))

    def test_A2_ksTest(self):
        out = self._run("ksTest.py", "ks_test",
                        {"KS_N_NULL_SAMPLES": 500}, "A2_ks_test")
        self.assertTrue(os.path.isfile(os.path.join(out, "ks_results.csv")))

    def test_A3_wilcoxonIsochrony(self):
        out = self._run("wilcoxonIsochrony.py", "wilcoxon_isochrony",
                        {"WIL_MIN_EVENTS_PER_UNIT": 3},
                        "A3_wilcoxon")
        self.assertTrue(os.path.isfile(
            os.path.join(out, "wilcoxon_isochrony_results.csv")))

    def test_A4_lagOneAutocorrelation(self):
        out = self._run("lagOneAutocorrelation.py", "lag_one_autocorrelation",
                        {"AC_MIN_INTERVALS_PER_BOUT": 3,
                         "AC_N_BOOTSTRAP": 50},
                        "A4_lag1")
        self.assertTrue(os.path.isfile(os.path.join(out, "autocorr_lag1.csv")))

    # -- Category B -------------------------------------------------

    def test_B1_tempoRatioHeatmap(self):
        out = self._run("tempoRatioHeatmap.py", "tempo_ratio_heatmap",
                        {"TRH_X_BINS": 20, "TRH_Y_BINS": 20,
                         "TRH_FACET_BY_GROUP": True},
                        "B1_tempo_ratio")
        self.assertTrue(os.path.isfile(
            os.path.join(out, "tempo_ratio_density.csv")))

    def test_B2_raincloudMetrics(self):
        out = self._run("raincloudMetrics.py", "raincloud_metrics",
                        {"RC_METRICS": ["nPVI (Isochrony)",
                                        "CV of Intervals"],
                         "RC_PAIRWISE_STATS": "mannwhitney"},
                        "B2_raincloud")
        # Should produce at least the nPVI figure
        files = os.listdir(out)
        self.assertTrue(any(f.startswith("raincloud_") for f in files),
                        f"no raincloud files in {files}")

    # -- Category C -------------------------------------------------

    def test_C1_pDFA(self):
        out = self._run("pDFA.py", "pdfa",
                        {"PDFA_CLASS_COLUMN": "Group",
                         "PDFA_N_PERMUTATIONS": 99,
                         "PDFA_CROSSVALIDATION": "leave_one_out",
                         "PDFA_MIN_OBS_PER_CLASS": 2},
                        "C1_pdfa")
        self.assertTrue(os.path.isfile(os.path.join(out, "pdfa_results.csv")))
        self.assertTrue(os.path.isfile(os.path.join(out, "pdfa_loadings.csv")))

    def test_C2_mantelTest(self):
        out = self._run("mantelTest.py", "mantel_test",
                        {"MANTEL_UNIT_COLUMN": "Individual_ID",
                         "MANTEL_N_PERMUTATIONS": 99,
                         "MANTEL_PHYLO_SOURCE": "skip"},
                        "C2_mantel")
        self.assertTrue(os.path.isfile(
            os.path.join(out, "mantel_results.csv")))

    def test_C3_glmmRhythm(self):
        out = self._run("glmmRhythm.py", "glmm_rhythm",
                        {"GLMM_RESPONSE": "nPVI (Isochrony)",
                         "GLMM_FIXED_EFFECTS": ["Tempo_BPM", "Modality"],
                         "GLMM_RANDOM_EFFECTS": ["Group"],
                         "GLMM_COMPARE_NULL": False},
                        "C3_glmm")
        self.assertTrue(os.path.isfile(
            os.path.join(out, "glmm_coefficients.csv")))

    # -- Category D -------------------------------------------------

    def test_D1_pgls(self):
        # Build a small VCV CSV over the synthetic species names
        species = ["Pan_troglodytes_schweinfurthii",
                   "Pan_troglodytes_verus",
                   "Malurus_cyaneus"]
        vcv = pd.DataFrame(
            [[1.0, 0.9, 0.1],
             [0.9, 1.0, 0.1],
             [0.1, 0.1, 1.0]],
            index=species, columns=species)
        vcv_path = os.path.join(self.tmp, "vcv.csv")
        vcv.to_csv(vcv_path)
        out = self._run("pgls.py", "pgls",
                        {"PGLS_RESPONSE": "nPVI (Isochrony)",
                         "PGLS_PREDICTORS": ["BodyMass_kg", "Tempo_BPM"],
                         "PGLS_UNIT_COLUMN": "Species",
                         "PGLS_TREE_SOURCE": "vcv_matrix_csv",
                         "PGLS_TREE_PATH": vcv_path,
                         "PGLS_ESTIMATE_LAMBDA": False,
                         "PGLS_FIXED_LAMBDA": 0.5},
                        "D1_pgls")
        self.assertTrue(os.path.isfile(
            os.path.join(out, "pgls_coefficients.csv")))
        self.assertTrue(os.path.isfile(os.path.join(out, "pgls_lambda.csv")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
