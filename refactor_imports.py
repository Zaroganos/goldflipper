import os
import re


def compute_relative_prefix(file_path):
    """Computes the relative import prefix based on file location relative to the 'goldflipper' package root."""
    # Get relative path from the 'goldflipper' folder
    rel_path = os.path.relpath(file_path, start='goldflipper')
    # Count the number of directories in the relative path
    parts = rel_path.split(os.sep)
    depth = len(parts) - 1  # file at root has depth 0, one subdirectory: depth 1, etc.
    # For a file in the package root, we need '.'; for one level deeper, '..', etc.
    return '.' * (depth + 1)


def update_import_line(line, relative_prefix):
    """Update a single import line if it uses an absolute import from 'goldflipper'."""
    # Handle 'from goldflipper... import ...'
    from_pattern = r'^(\s*)from\s+goldflipper(.*)$'
    m = re.match(from_pattern, line)
    if m:
        indent = m.group(1)
        rest = m.group(2)
        # Replace with relative import using the computed prefix
        return f"{indent}from {relative_prefix}{rest}\n"

    # Handle 'import goldflipper.something [as name]'
    import_pattern = r'^(\s*)import\s+goldflipper(\S.*)$'
    m = re.match(import_pattern, line)
    if m:
        indent = m.group(1)
        rest = m.group(2).strip()
        # Convert: "import goldflipper.tools.module" to "from <prefix> import tools.module"
        return f"{indent}from {relative_prefix} import {rest}\n"

    return line


def update_sys_path(lines):
    """Removes lines that modify sys.path and returns the updated lines list."""
    updated_lines = []
    for line in lines:
        # Skip common sys.path modification lines that insert parent directory
        if 'sys.path.insert' in line or 'sys.path.append' in line:
            continue
        updated_lines.append(line)
    return updated_lines


def insert_package_assignment(lines, file_basename):
    """Insert a __package__ assignment in entry scripts if not already present.
       We check for goldflipper_tui.py and run.py in the package root."""
    if file_basename in ["goldflipper_tui.py", "run.py"]:
        content = ''.join(lines)
        if '__package__' not in content:
            assignment = "if __name__ == '__main__' and __package__ is None:\n    __package__ = 'goldflipper'\n\n"
            return assignment + ''.join(lines)
    return ''.join(lines)


def update_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f'Failed to read {file_path}: {e}')
        return

    # Remove sys.path modifications if present
    lines = update_sys_path(lines)
    relative_prefix = compute_relative_prefix(file_path)
    new_lines = []
    for line in lines:
        new_line = update_import_line(line, relative_prefix)
        new_lines.append(new_line)

    # Insert __package__ assignment if applicable
    new_content = insert_package_assignment(new_lines, os.path.basename(file_path))

    # Write the updated content back to the file
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated {file_path}')
    except Exception as e:
        print(f'Failed to write {file_path}: {e}')


def main():
    # Walk through the 'goldflipper' directory recursively
    for root, dirs, files in os.walk('goldflipper'):
        for f in files:
            if f.endswith('.py'):
                file_path = os.path.join(root, f)
                update_file(file_path)

if __name__ == '__main__':
    main() 