"""Shared session-state services and models."""

from .analysis_types import (
	BACKEND_ANALYSIS_TYPE_CONFIGS,
	DEFAULT_BACKEND_ANALYSIS_TYPE,
	get_backend_analysis_type_config,
	is_bioacoustics_analysis_type,
	is_bioacoustics_import_analysis_type,
	is_bioacoustics_sync_analysis_type,
	normalize_backend_analysis_type,
)
from .command_contracts import (
	DEFAULT_BACKEND_SAVE_MODE,
	normalize_backend_analysis_request,
	normalize_backend_save_mode,
	parse_backend_analysis_request_json,
)
from .error_metadata import (
	build_backend_failure,
	enrich_backend_failure,
	get_backend_error_metadata,
	normalize_backend_error_code,
)
from .result_metadata import (
	enrich_backend_save_result,
	get_backend_save_mode_metadata,
	normalize_backend_save_mode_key,
)
from .selection_contracts import (
	normalize_backend_selection_contract,
	normalize_selection_amplitude_pct_range,
	normalize_selection_frequency_window,
	normalize_selection_time_window,
)

__all__ = [
	"BACKEND_ANALYSIS_TYPE_CONFIGS",
	"DEFAULT_BACKEND_ANALYSIS_TYPE",
	"DEFAULT_BACKEND_SAVE_MODE",
	"get_backend_analysis_type_config",
	"is_bioacoustics_analysis_type",
	"is_bioacoustics_import_analysis_type",
	"is_bioacoustics_sync_analysis_type",
	"normalize_backend_analysis_request",
	"normalize_backend_analysis_type",
	"normalize_backend_selection_contract",
	"normalize_backend_save_mode",
	"normalize_backend_save_mode_key",
	"normalize_selection_amplitude_pct_range",
	"normalize_selection_frequency_window",
	"normalize_selection_time_window",
	"parse_backend_analysis_request_json",
	"get_backend_save_mode_metadata",
	"build_backend_failure",
	"enrich_backend_failure",
	"get_backend_error_metadata",
	"enrich_backend_save_result",
	"normalize_backend_error_code",
]