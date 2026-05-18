"""Test Phase 3 additions: Preview fix, excel_column, ExcelDataUsedDialog."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'GUI'))

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from pipeline_gui import (nPVIGroupPanel, HistogramPanel, PlotPanel,
                          PreviewWindow, ExcelDataUsedDialog)
print('Imports OK')

# 1. nPVIGroupPanel get_values includes new key
npvi = nPVIGroupPanel()
vals = npvi.get_values()
assert 'NPVI_GROUP_EXCEL_COLUMN' in vals, 'Missing NPVI_GROUP_EXCEL_COLUMN'
assert vals['NPVI_GROUP_EXCEL_COLUMN'] == 'Group'
print('nPVIGroupPanel get_values: OK')

# 2. set_values roundtrip with excel_column
npvi.set_values({'NPVI_GROUP_SOURCE': 'excel_column', 'NPVI_GROUP_EXCEL_COLUMN': 'Species'})
vals2 = npvi.get_values()
assert vals2['NPVI_GROUP_SOURCE'] == 'excel_column'
assert vals2['NPVI_GROUP_EXCEL_COLUMN'] == 'Species'
print('nPVIGroupPanel set_values roundtrip: OK')

# 3. Preview rendering works
pw = PreviewWindow()
pw.render_npvi_group(vals)
print('Preview render: OK')

# 4. ExcelDataUsedDialog
defs = [{'var_id': 'test_col', 'column': 'Test Column',
         'default': 'Test Column', 'description': 'A test'}]
dlg = ExcelDataUsedDialog('Test Step', defs)
cols = dlg.get_columns()
assert cols == {'test_col': 'Test Column'}
print('ExcelDataUsedDialog: OK')

# 5. Excel Data Used buttons exist
hist = HistogramPanel()
assert hasattr(hist, '_excel_data_btn')
print('HistogramPanel button: OK')

plot = PlotPanel()
assert hasattr(plot, '_excel_data_btn')
print('PlotPanel button: OK')

assert hasattr(npvi, '_excel_data_btn')
print('nPVIGroupPanel button: OK')

# 6. excel_column in group_source combo
assert npvi.group_source.findText('excel_column') >= 0
print('excel_column option present: OK')

print('\nALL TESTS PASSED')
