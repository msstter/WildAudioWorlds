"""Test selection playback buttons in OnsetEditorPanel."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'GUI'))

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from onset_editor import OnsetEditorPanel
panel = OnsetEditorPanel()
panel._audio_path = '/tmp/example.wav'

# Check new buttons exist
assert hasattr(panel, '_play_sel_btn'), 'Missing _play_sel_btn'
assert hasattr(panel, '_loop_sel_btn'), 'Missing _loop_sel_btn'
assert not panel._play_sel_btn.isEnabled(), 'play_sel should start disabled'
assert not panel._loop_sel_btn.isEnabled(), 'loop_sel should start disabled'
assert panel._loop_sel_btn.isCheckable(), 'loop_sel should be checkable'
print('Buttons created OK')

# Check methods exist
assert hasattr(panel, '_play_selection'), 'Missing _play_selection'
assert hasattr(panel, '_toggle_loop_selection'), 'Missing _toggle_loop_selection'
assert hasattr(panel, '_clear_selection_state'), 'Missing _clear_selection_state'
print('Methods exist OK')

# Simulate region selection
panel._on_viewer_region_selected(1.0, 3.0)
assert panel._play_sel_btn.isEnabled(), 'play_sel should be enabled after region select'
assert panel._loop_sel_btn.isEnabled(), 'loop_sel should be enabled after region select'
assert panel._detect_region_btn.isEnabled(), 'detect should be enabled after region select'
assert panel._edit_audio_btn.isEnabled(), 'audio editor should be enabled after region select when audio is loaded'
assert panel._selected_region == (1.0, 3.0)
print('Region selection OK')

# Clear selection
panel._clear_selection_state()
assert not panel._play_sel_btn.isEnabled(), 'play_sel should be disabled after clear'
assert not panel._loop_sel_btn.isEnabled(), 'loop_sel should be disabled after clear'
assert panel._selected_region is None
print('Clear selection OK')

print('\nALL ONSET EDITOR TESTS PASSED')
