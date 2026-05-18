import sys
import os

filepath = "/Users/mh295/Library/Application Support/Code/User/workspaceStorage/1ab697b59b0ecbfa9ded981a4ced5911/GitHub.copilot-chat/transcripts/938cc345-887e-49ee-b334-c155204febd5.jsonl"
patterns = [
    "_ONSET_EDITOR_DESC",
    "_PerSignalConfigDialog",
    "class _NegativeSubtractionDialog",
    "class _DetectOnsetsDialog",
    "class _AnalyzeSignalsDialog",
    "_DetectOnsetsWorker = _ExtractedDetectOnsetsWorker",
    "_AnalyzeSignalsDialog = _ExtractedAnalyzeSignalsDialog"
]

with open(filepath, 'r') as f:
    for i, line in enumerate(f, 1):
        for pattern in patterns:
            if pattern in line:
                # Find start and end indices to truncate the output around the match
                idx = line.find(pattern)
                start = max(0, idx - 100)
                end = min(len(line), idx + len(pattern) + 100)
                print(f"Line {i}: ...{line[start:end]}...")
