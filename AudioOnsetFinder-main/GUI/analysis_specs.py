from __future__ import annotations

import re


def _setting(
    key: str,
    label: str,
    help_text: str,
    *,
    type: str = "str",
    default=None,
    help_detailed: str | None = None,
    help_novice: str | None = None,
    **extra,
) -> dict:
    setting = {
        "key": key,
        "label": label,
        "type": type,
        "help": help_text,
    }
    if default is not None:
        setting["default"] = default
    if help_detailed:
        setting["help_detailed"] = help_detailed
    if help_novice:
        setting["help_novice"] = help_novice
    setting.update(extra)
    return setting


_COLUMN_VAR_IDS = {
    "Species": "species",
    "Latitude": "latitude",
    "Longitude": "longitude",
    "Modality": "modality",
    "Function": "function",
    "Tempo_BPM": "tempo_bpm",
    "BodyMass_kg": "body_mass_kg",
    "Total Onsets Used": "total_onsets_used",
    "Total Duration (s)": "total_duration_s",
    "Mean IOI (ms)": "mean_ioi_ms",
    "nPVI (Isochrony)": "npvi_isochrony",
    "CV of Intervals": "cv_intervals",
    "r_k Entropy (Categorical Measure)": "rk_entropy",
    "Rhythm Ratio [r_k]": "rhythm_ratio_rk",
    "Cycle Duration [cd] (ms)": "cycle_duration_ms",
    "Interval 1 (ms)": "interval_1_ms",
    "Interval 2 (ms)": "interval_2_ms",
}


_COLUMN_DESCRIPTIONS = {
    "Species": "Species label used for phylogenetic matching and species-level aggregation.",
    "Latitude": "Geographic latitude in decimal degrees.",
    "Longitude": "Geographic longitude in decimal degrees.",
    "Modality": "Categorical signal modality used as a fixed effect in model-based analyses.",
    "Function": "Categorical behavioral function label used as a fixed effect in model-based analyses.",
    "Tempo_BPM": "Tempo estimate in beats per minute.",
    "BodyMass_kg": "Body-mass covariate in kilograms.",
    "Total Onsets Used": "Per-file count of onset events retained for analysis.",
    "Total Duration (s)": "Duration of the analyzed recording in seconds.",
    "Mean IOI (ms)": "Mean inter-onset interval in milliseconds.",
    "nPVI (Isochrony)": "Normalized Pairwise Variability Index, a standard rhythm-variability measure.",
    "CV of Intervals": "Coefficient of variation across inter-onset intervals.",
    "r_k Entropy (Categorical Measure)": "Entropy of the rhythm-ratio distribution across categorical bins.",
    "Rhythm Ratio [r_k]": "Per-event rhythm ratio computed from adjacent interval pairs.",
    "Cycle Duration [cd] (ms)": "Combined duration of the two intervals used to compute each rhythm ratio.",
    "Interval 1 (ms)": "First interval in each overlapping dyadic pair.",
    "Interval 2 (ms)": "Second interval in each overlapping dyadic pair.",
}


def _column_var_id(column_name: str) -> str:
    if column_name in _COLUMN_VAR_IDS:
        return _COLUMN_VAR_IDS[column_name]
    slug = re.sub(r"[^a-z0-9]+", "_", column_name.lower()).strip("_")
    return slug or "column"


def _excel_columns(*column_names: str) -> list[dict]:
    columns = []
    seen = set()
    for column_name in column_names:
        if column_name in ("File Name", "Group"):
            continue
        if column_name in seen:
            continue
        seen.add(column_name)
        columns.append(
            {
                "var_id": _column_var_id(column_name),
                "column": column_name,
                "default": column_name,
                "description": _COLUMN_DESCRIPTIONS.get(column_name, "Excel column used by this analysis."),
            }
        )
    return columns


def _group_assignment_settings(prefix: str) -> list[dict]:
    return [
        _setting(
            f"{prefix}DATASET",
            "Dataset",
            "Choose whether the analysis should read the raw dyadic-event dataset or the stable-rhythm subset.",
            type="choice",
            choices=["raw", "stable"],
            default="raw",
        ),
        _setting(
            f"{prefix}GROUP_SOURCE",
            "Group source",
            "How group labels should be assigned to each file or event.",
            type="choice",
            choices=["filename_pattern", "mapping_csv", "manual", "excel_column"],
            default="filename_pattern",
        ),
        _setting(
            f"{prefix}GROUP_PATTERN",
            "Filename pattern",
            "Regular expression used when group labels are extracted from filenames.",
            default=r"(?P<group>[A-Za-z]+)_",
        ),
        _setting(
            f"{prefix}GROUP_EXCEL_COLUMN",
            "Group Excel column",
            "Excel column to use when the group source is set to excel_column.",
            default="Group",
        ),
    ]


NEW_ANALYSIS_SPECS = [
    {
        "title": "Rhythm Ratio Distributions",
        "subtitle": (
            "Computes the per-file proportion of IOI ratios that fall in an "
            "isochronous band and plots group-wise rhythm-ratio distributions."
        ),
        "config_key": "rhythm_ratios",
        "prefix": "RR_",
        "output_folder": "Rhythm_Ratios",
        "excel_columns": _excel_columns("Rhythm Ratio [r_k]"),
        "settings": [
            *_group_assignment_settings("RR_"),
            _setting(
                "BIN_COUNT",
                "Histogram bins",
                "Number of bins used for the rhythm-ratio histograms.",
                type="int",
                min=5,
                max=200,
                default=40,
            ),
            _setting(
                "ISOCHRONOUS_BAND_LOW",
                "Isochronous band low",
                "Lower boundary of the isochronous band used to count near-1:1 ratios.",
                type="float",
                min=0.0,
                max=1.0,
                decimals=3,
                step=0.01,
                default=0.45,
            ),
            _setting(
                "ISOCHRONOUS_BAND_HIGH",
                "Isochronous band high",
                "Upper boundary of the isochronous band used to count near-1:1 ratios.",
                type="float",
                min=0.0,
                max=1.0,
                decimals=3,
                step=0.01,
                default=0.55,
            ),
            _setting(
                "NORMALIZE",
                "Normalize histogram density",
                "When enabled, the histograms are plotted as densities rather than raw counts.",
                type="bool",
                default=True,
            ),
        ],
    },
    {
        "title": "KS Test vs. Uniform",
        "subtitle": (
            "Runs a one-sample Kolmogorov-Smirnov test comparing each group's "
            "rhythm-ratio distribution to a null distribution."
        ),
        "config_key": "ks_test",
        "prefix": "KS_",
        "output_folder": "KS_Test",
        "excel_columns": _excel_columns("Rhythm Ratio [r_k]"),
        "settings": [
            *_group_assignment_settings("KS_"),
            _setting(
                "NULL_DISTRIBUTION",
                "Null distribution",
                "Reference distribution used by the KS test.",
                type="choice",
                choices=["uniform", "bootstrap_shuffle", "custom_csv"],
                default="uniform",
            ),
            _setting(
                "N_NULL_SAMPLES",
                "Null samples",
                "Number of synthetic samples to draw when constructing the null distribution.",
                type="int",
                min=100,
                max=1000000,
                default=10000,
            ),
            _setting(
                "ALTERNATIVE",
                "Alternative hypothesis",
                "Tail direction for the KS hypothesis test.",
                type="choice",
                choices=["two-sided", "less", "greater"],
                default="two-sided",
            ),
            _setting(
                "MULTIPLE_COMPARISONS",
                "Multiple-comparison correction",
                "Correction method applied across groups when more than one test is run.",
                type="choice",
                choices=["none", "bonferroni", "fdr_bh"],
                default="none",
            ),
        ],
    },
    {
        "title": "Wilcoxon Isochrony",
        "subtitle": (
            "Tests whether the proportion of near-isochronous rhythm ratios exceeds "
            "chance using a one-sample Wilcoxon signed-rank formulation."
        ),
        "config_key": "wilcoxon_isochrony",
        "prefix": "WIL_",
        "output_folder": "Wilcoxon_Isochrony",
        "excel_columns": _excel_columns("Rhythm Ratio [r_k]"),
        "settings": [
            *_group_assignment_settings("WIL_"),
            _setting(
                "UNIT",
                "Statistical unit",
                "Whether the Wilcoxon test is computed per file or per bout.",
                type="choice",
                choices=["per_file", "per_bout"],
                default="per_file",
            ),
            _setting(
                "ISOCHRONOUS_BAND_LOW",
                "Isochronous band low",
                "Lower edge of the band treated as isochronous.",
                type="float",
                min=0.0,
                max=1.0,
                decimals=3,
                step=0.01,
                default=0.45,
            ),
            _setting(
                "ISOCHRONOUS_BAND_HIGH",
                "Isochronous band high",
                "Upper edge of the band treated as isochronous.",
                type="float",
                min=0.0,
                max=1.0,
                decimals=3,
                step=0.01,
                default=0.55,
            ),
            _setting(
                "ALTERNATIVE",
                "Alternative hypothesis",
                "Tail direction for the Wilcoxon test.",
                type="choice",
                choices=["greater", "two-sided", "less"],
                default="greater",
            ),
            _setting(
                "MIN_EVENTS_PER_UNIT",
                "Minimum events per unit",
                "Minimum number of rhythm-ratio events required before a unit is included.",
                type="int",
                min=1,
                max=1000,
                default=5,
            ),
        ],
    },
    {
        "title": "Lag-1 Autocorrelation",
        "subtitle": (
            "Computes lag-1 autocorrelation of consecutive intervals to quantify "
            "tempo persistence versus short-long alternation."
        ),
        "config_key": "lag_one_autocorrelation",
        "prefix": "AC_",
        "output_folder": "Lag1_Autocorrelation",
        "excel_columns": _excel_columns("Interval 1 (ms)", "Interval 2 (ms)"),
        "settings": [
            *_group_assignment_settings("AC_"),
            _setting(
                "INTERVAL_SOURCE",
                "Interval source",
                "Column or auto-mode used to reconstruct the interval sequence.",
                default="auto",
            ),
            _setting(
                "DETREND",
                "Detrend method",
                "Preprocessing applied to the interval sequence before autocorrelation is computed.",
                type="choice",
                choices=["none", "mean", "linear"],
                default="mean",
            ),
            _setting(
                "CONFIDENCE_METHOD",
                "Confidence-interval method",
                "Method used to estimate the confidence interval around the lag-1 correlation.",
                type="choice",
                choices=["fisher_z", "bootstrap"],
                default="fisher_z",
            ),
            _setting(
                "N_BOOTSTRAP",
                "Bootstrap samples",
                "Number of bootstrap resamples used when confidence intervals are bootstrapped.",
                type="int",
                min=100,
                max=100000,
                default=1000,
            ),
            _setting(
                "GROUP_AGGREGATION",
                "Group aggregation",
                "Whether autocorrelation is kept per file or pooled by group before visualization.",
                type="choice",
                choices=["per_file", "pooled_by_group"],
                default="per_file",
            ),
        ],
    },
    {
        "title": "Tempo × Ratio Heatmap",
        "subtitle": (
            "Builds a 2D density map of tempo against rhythm ratio so the joint "
            "rhythmic landscape can be compared across groups."
        ),
        "config_key": "tempo_ratio_heatmap",
        "prefix": "TRH_",
        "output_folder": "Tempo_Ratio_Heatmap",
        "excel_columns": _excel_columns("Rhythm Ratio [r_k]", "Cycle Duration [cd] (ms)"),
        "settings": [
            *_group_assignment_settings("TRH_"),
            _setting(
                "X_AXIS",
                "X-axis variable",
                "Whether the x-axis should represent BPM or cycle duration.",
                type="choice",
                choices=["BPM", "cycle_duration_ms"],
                default="BPM",
            ),
            _setting(
                "TEMPO_FROM",
                "Tempo derivation",
                "Whether BPM is computed from mean IOI or directly from cycle duration.",
                type="choice",
                choices=["ioi", "cycle"],
                default="ioi",
            ),
            _setting(
                "KDE_MODE",
                "Density mode",
                "Choose between a binned 2D histogram and Gaussian KDE smoothing.",
                type="choice",
                choices=["2d_histogram", "gaussian_kde"],
                default="2d_histogram",
            ),
            _setting(
                "X_BINS",
                "X bins",
                "Number of bins along the x-axis when the heatmap uses histogram mode.",
                type="int",
                min=5,
                max=200,
                default=40,
            ),
            _setting(
                "Y_BINS",
                "Y bins",
                "Number of bins along the rhythm-ratio axis when the heatmap uses histogram mode.",
                type="int",
                min=5,
                max=200,
                default=40,
            ),
            _setting(
                "NORMALIZE",
                "Normalization",
                "How densities are normalized when comparing groups or facets.",
                type="choice",
                choices=["per_group", "joint", "none"],
                default="per_group",
            ),
        ],
    },
    {
        "title": "Raincloud Metrics",
        "subtitle": (
            "Generates raincloud plots for continuous rhythm metrics across groups, "
            "with optional pairwise statistical comparisons."
        ),
        "config_key": "raincloud_metrics",
        "prefix": "RC_",
        "output_folder": "Raincloud_Metrics",
        "excel_columns": _excel_columns(
            "nPVI (Isochrony)",
            "CV of Intervals",
            "Mean IOI (ms)",
            "r_k Entropy (Categorical Measure)",
        ),
        "settings": [
            *_group_assignment_settings("RC_"),
            _setting(
                "METRICS",
                "Metrics",
                "Comma-separated list of File Summaries columns to visualize as rainclouds.",
                type="list",
                default=[
                    "nPVI (Isochrony)",
                    "r_k Entropy (Categorical Measure)",
                    "CV of Intervals",
                    "Mean IOI (ms)",
                ],
            ),
            _setting(
                "ORIENTATION",
                "Orientation",
                "Layout of the raincloud plots.",
                type="choice",
                choices=["vertical", "horizontal"],
                default="vertical",
            ),
            _setting(
                "ONE_FIG_PER_METRIC",
                "One figure per metric",
                "When enabled, each metric is written as its own figure instead of a combined grid.",
                type="bool",
                default=True,
            ),
            _setting(
                "PAIRWISE_STATS",
                "Pairwise statistical test",
                "Optional across-group statistical test to compute for each metric.",
                type="choice",
                choices=["none", "mannwhitney", "wilcoxon", "ks"],
                default="none",
            ),
            _setting(
                "STATS_CORRECTION",
                "P-value correction",
                "Multiple-comparison correction applied to the optional pairwise tests.",
                type="choice",
                choices=["none", "bonferroni", "fdr_bh"],
                default="none",
            ),
        ],
    },
    {
        "title": "pDFA",
        "subtitle": (
            "Runs permuted discriminant function analysis to test whether class labels "
            "are predicted by rhythmic features better than chance."
        ),
        "config_key": "pdfa",
        "prefix": "PDFA_",
        "output_folder": "pDFA",
        "excel_columns": _excel_columns(
            "Total Onsets Used",
            "Total Duration (s)",
            "nPVI (Isochrony)",
            "CV of Intervals",
            "Mean IOI (ms)",
            "r_k Entropy (Categorical Measure)",
        ),
        "settings": [
            _setting(
                "PREDICTORS",
                "Predictor columns",
                "Continuous File Summaries columns used as predictors by the discriminant model.",
                type="list",
                default=[
                    "Total Onsets Used",
                    "Total Duration (s)",
                    "nPVI (Isochrony)",
                    "CV of Intervals",
                    "r_k Entropy (Categorical Measure)",
                    "Mean IOI (ms)",
                ],
            ),
            _setting(
                "CLASS_COLUMN",
                "Class column",
                "Categorical File Summaries column that the pDFA attempts to classify.",
                default="Group",
            ),
            _setting(
                "REPEATED_MEASURES_COLUMN",
                "Repeated-measures column",
                "Optional blocking column used when labels should only be permuted within repeated-measures groups.",
                default="",
            ),
            _setting(
                "N_PERMUTATIONS",
                "Permutations",
                "Number of label permutations used to estimate the p-value.",
                type="int",
                min=10,
                max=100000,
                default=999,
            ),
            _setting(
                "CROSSVALIDATION",
                "Cross-validation",
                "Cross-validation strategy used to estimate classification performance.",
                type="choice",
                choices=["none", "leave_one_out", "kfold", "leave_one_group_out"],
                default="leave_one_out",
            ),
            _setting(
                "PRIOR",
                "Class prior",
                "How class priors are assigned inside the discriminant model.",
                type="choice",
                choices=["equal", "empirical"],
                default="equal",
            ),
        ],
    },
    {
        "title": "Mantel Test",
        "subtitle": (
            "Correlates a rhythm-distance matrix with geographic and optional phylogenetic "
            "distance matrices using Mantel or partial-Mantel tests."
        ),
        "config_key": "mantel_test",
        "prefix": "MANTEL_",
        "output_folder": "Mantel_Test",
        "excel_columns": _excel_columns(
            "Latitude",
            "Longitude",
            "nPVI (Isochrony)",
            "CV of Intervals",
            "Mean IOI (ms)",
            "r_k Entropy (Categorical Measure)",
        ),
        "settings": [
            _setting(
                "UNIT_COLUMN",
                "Unit column",
                "Column used to aggregate recordings before distance matrices are computed.",
                default="Group",
            ),
            _setting(
                "RHYTHM_METRIC",
                "Rhythm metric",
                "Rhythmic distance metric used to construct the rhythm matrix.",
                type="choice",
                choices=["nPVI", "entropy", "CV", "mean_IOI", "euclidean_multivar"],
                default="nPVI",
            ),
            _setting(
                "RHYTHM_MULTIVAR_COLS",
                "Multivariate rhythm columns",
                "Columns used when the rhythm metric is set to euclidean_multivar.",
                type="list",
                default=[
                    "nPVI (Isochrony)",
                    "CV of Intervals",
                    "r_k Entropy (Categorical Measure)",
                    "Mean IOI (ms)",
                ],
            ),
            _setting(
                "GEO_LAT_COLUMN",
                "Latitude column",
                "Latitude column used when geographic distance is derived from coordinates.",
                default="Latitude",
            ),
            _setting(
                "GEO_LON_COLUMN",
                "Longitude column",
                "Longitude column used when geographic distance is derived from coordinates.",
                default="Longitude",
            ),
            _setting(
                "GEO_DISTANCE",
                "Geographic distance",
                "Distance function applied to the latitude and longitude columns.",
                type="choice",
                choices=["haversine_km", "euclidean"],
                default="haversine_km",
            ),
            _setting(
                "TEST_MODE",
                "Test mode",
                "Whether to run a two-matrix Mantel test or a partial Mantel test.",
                type="choice",
                choices=["two_matrix", "partial"],
                default="two_matrix",
            ),
            _setting(
                "CORRELATION",
                "Correlation statistic",
                "Correlation coefficient used when comparing flattened distance matrices.",
                type="choice",
                choices=["pearson", "spearman"],
                default="pearson",
            ),
        ],
    },
    {
        "title": "GLMM for Rhythm",
        "subtitle": (
            "Fits a generalized linear mixed-effects model predicting a rhythmic response "
            "from fixed effects with one or more random-effect grouping terms."
        ),
        "config_key": "glmm_rhythm",
        "prefix": "GLMM_",
        "output_folder": "GLMM",
        "excel_columns": _excel_columns(
            "nPVI (Isochrony)",
            "Mean IOI (ms)",
            "CV of Intervals",
            "Total Duration (s)",
            "Modality",
            "Function",
            "Tempo_BPM",
            "BodyMass_kg",
        ),
        "settings": [
            _setting(
                "DATASET",
                "Dataset",
                "Dataset label retained in the config for this model-oriented analysis.",
                type="choice",
                choices=["raw", "stable"],
                default="raw",
            ),
            _setting(
                "RESPONSE",
                "Response column",
                "Numeric File Summaries column modeled as the dependent variable.",
                default="nPVI (Isochrony)",
            ),
            _setting(
                "RESPONSE_FAMILY",
                "Response family",
                "Distribution family used by the GLMM engine.",
                type="choice",
                choices=["gaussian", "beta", "binomial", "poisson"],
                default="gaussian",
            ),
            _setting(
                "LINK",
                "Link function",
                "Link function associated with the chosen response family.",
                type="choice",
                choices=["identity", "logit", "log"],
                default="identity",
            ),
            _setting(
                "FIXED_EFFECTS",
                "Fixed effects",
                "File Summaries columns included as fixed effects in the model formula.",
                type="list",
                default=["Mean IOI (ms)", "CV of Intervals", "Total Duration (s)"],
            ),
            _setting(
                "RANDOM_EFFECTS",
                "Random effects",
                "Columns used as random-effect grouping terms.",
                type="list",
                default=["Group"],
            ),
            _setting(
                "ENGINE",
                "Model engine",
                "Backend used to fit the mixed-effects model.",
                type="choice",
                choices=["statsmodels", "pymer4"],
                default="statsmodels",
            ),
            _setting(
                "COMPARE_NULL",
                "Compare against null model",
                "When enabled, the fit is compared against an intercept-only null model.",
                type="bool",
                default=True,
            ),
        ],
    },
    {
        "title": "PGLS",
        "subtitle": (
            "Fits a phylogenetically informed generalized least-squares regression so "
            "species non-independence is accounted for in trait modeling."
        ),
        "config_key": "pgls",
        "prefix": "PGLS_",
        "output_folder": "PGLS",
        "excel_columns": _excel_columns("Species", "nPVI (Isochrony)", "Tempo_BPM", "BodyMass_kg"),
        "settings": [
            _setting(
                "RESPONSE",
                "Response column",
                "Species-level trait modeled as the PGLS response variable.",
                default="nPVI (Isochrony)",
            ),
            _setting(
                "PREDICTORS",
                "Predictor columns",
                "Species-level columns used as predictors in the regression.",
                type="list",
                default=["BodyMass_kg", "Tempo_BPM"],
            ),
            _setting(
                "UNIT_COLUMN",
                "Unit column",
                "Column used to aggregate measurements before fitting the phylogenetic model.",
                default="Species",
            ),
            _setting(
                "TREE_SOURCE",
                "Tree source",
                "Whether the phylogenetic covariance is loaded from a VCV matrix CSV or a Newick tree file.",
                type="choice",
                choices=["vcv_matrix_csv", "newick_file"],
                default="vcv_matrix_csv",
            ),
            _setting(
                "TREE_PATH",
                "Tree path",
                "Filesystem path to the VCV matrix or Newick tree used to build the covariance structure.",
                default="",
            ),
            _setting(
                "CORRELATION_MODEL",
                "Correlation model",
                "Phylogenetic correlation model applied to the covariance matrix.",
                type="choice",
                choices=["brownian", "pagel_lambda", "ornstein_uhlenbeck"],
                default="pagel_lambda",
            ),
            _setting(
                "ESTIMATE_LAMBDA",
                "Estimate lambda",
                "When enabled, Pagel's lambda is estimated instead of fixed.",
                type="bool",
                default=True,
            ),
            _setting(
                "ENGINE",
                "Solver backend",
                "Backend used to solve the generalized least-squares system.",
                type="choice",
                choices=["numpy_gls", "rpy2_caper"],
                default="numpy_gls",
            ),
        ],
    },
]


SIDEBAR_ANALYSIS_OFFSET = 8
ANALYSIS_RUN_KEYS = {
    spec["config_key"]: f"RUN_{spec['config_key'].upper()}" for spec in NEW_ANALYSIS_SPECS
}


STEP_SETTINGS_PREFIX = {
    "Audio Editor": "AudioEditor",
    "Onset Finder": "OnsetFinder",
    "Beat & Tempo": "BeatTempo",
    "Flower Raster Plots": "FlowerRasterPlots",
    "Histogram Generator": "HistogramGenerator",
    "nPVI Group Plot": "nPVIGroupPlot",
    "Rhythm Ratio Distributions": "RhythmRatioDistributions",
    "KS Test vs. Uniform": "KSTestVsUniform",
    "Wilcoxon Isochrony": "WilcoxonIsochrony",
    "Lag-1 Autocorrelation": "Lag1Autocorrelation",
    "Tempo × Ratio Heatmap": "TempoRatioHeatmap",
    "Raincloud Metrics": "RaincloudMetrics",
    "pDFA": "pDFA",
    "Mantel Test": "MantelTest",
    "GLMM for Rhythm": "GLMMForRhythm",
    "PGLS": "PGLS",
    "Association Rule Learning": "AssociationRuleLearning",
}


__all__ = [
    "ANALYSIS_RUN_KEYS",
    "NEW_ANALYSIS_SPECS",
    "SIDEBAR_ANALYSIS_OFFSET",
    "STEP_SETTINGS_PREFIX",
]