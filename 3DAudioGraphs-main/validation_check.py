import backend.bioacoustics_workbook as bw
import pandas as pd
import os
import traceback

try:
    path = 'BioacousticsProject_ForReference/AudioData_OnsetFinder.xlsx'
    audio_file = '20230621_120000.wav'
    
    # 2) call bw.load_onsets_for_audio
    onsets, matched_file = bw.load_onsets_for_audio(path, audio_file)
    print(f"ONSET_COUNT: {len(onsets)}")
    print(f"MATCHED_FILE: {matched_file}")

    # 3) call bw.sync_workbook_onsets
    output_path = 'data/exports/backend_calls/_bio_helper_validation.xlsx'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    res = bw.sync_workbook_onsets(path, audio_file, [0.1, 0.5, 1.0], output_path=output_path)
    
    print(f"OUTPUT_PATH: {output_path}")
    if isinstance(res, dict):
        print(f"SYNC_ONSET_COUNT: {res.get('onsetCount')}")
        print(f"DYAD_COUNT: {res.get('dyadCount')}")
        print(f"STABLE_DYAD_COUNT: {res.get('stableDyadCount')}")
    else:
        print(f"SYNC_ONSET_COUNT: {getattr(res, '        print(f"SYNC_ONSET_COUNT:in        print(f"SYNC_ONSET_COUNT: {getat',         print(f"  pr     "STAB        priNT: {getattr        print(f"SYNC_ONSET_COUNT: {getattr(res, '        print(f"SYNC_Owi        print(f"SYNC_ONSET_COUNT: s
    xl = pd.ExcelFile(output_path)
    print(f"SHEET_NAMES: {xl.sheet_names}")

except Exception:
    traceback.print_exc()
