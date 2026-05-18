import os
import re

def find_pattern(directory):
    pattern = re.compile(r'(\w+)\s*=\s*QHBoxLayout\((.+)\)')
    add_layout_pattern = re.compile(r'addLayout\(\s*{}\s*\)')
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                with open(path, 'r') as f:
                    lines = f.readlines()
                
                # Dictionary to store variable names and their line numbers
                found_vars = {}
                for i, line in enumerate(lines):
                    match = pattern.search(line)
                    if match:
                        var_name = match.group(1)
                        arg = match.group(2).strip()
                        if arg and arg != '': # Not empty
                            if var_name not in found_vars:
                                found_vars[var_name] = []
                            found_var                        1, line.strip()))
                
                # Now check for addLayout
                for var_name, instances in found_vars.items():
                    target_pattern = re.compile(r'addLayout\(\s*' + re.escape(var_name) + r'\s*\)')
                    for i, line in enumerate(lines):
                        if target_pattern.search(line):
                            # It's a match if addLayout is called on the variable found above
                            # We should ideally check if it's after the assignment
                            for line_num, original_line in instances:
                                if i + 1 > line_num:
                                    print(f"{path}:{line_num}: variable '{var_name}' assigned with parent: {original_line}")
                                    print(f"{path}:{i + 1}: variable '{var_name}' added to layout: {line.strip()}")
                                    print("-" * 20)

find_pattern('GUI')
