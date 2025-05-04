import logging
import os
import re
import itertools
import json
import base64

from github import Github

from libs.utils import *

output_file = os.environ.get('GITHUB_OUTPUT')
log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='ACTION: %(message)s', level=log_level)

def get_next_line_number(lines, start_from):
    for index, line in enumerate(lines[start_from:]):
        original_index = start_from + index
        if line.startswith('@@'):
            return original_index
    return len(lines)

def is_new_file(line):
    return re.match(r"^@@ -0,0 \+\d+,\d+ @@.*", line) is not None

def get_hunk_start(line):
    return int(re.search(r"@@.*\+(\d+),(\d+) @@.*", line).group(1))

def get_hunk_length(line):
    return int(re.search(r"@@.*\+(\d+),(\d+) @@.*", line).group(2))

def compute_hunk_range(lines, start, end):
    line_numbers = []
    hunk_start = get_hunk_start(lines[start])
    for index, line in enumerate(lines[start + 1 : end]):
        if line.startswith('+'):
            line_numbers.append(hunk_start + index)

    return line_numbers

def extract_line_ranges_from_patch(patch):
    line_ranges = []
    if patch:
        lines = [line for line in patch.splitlines() if not line.startswith('-')]

        start_hunk_line = 0
        is_new = False
        while True:
            is_new = False # is_new or is_new_file(lines)
            next_hunk_line = get_next_line_number(lines, start_hunk_line + 1)
            hunk_range = compute_hunk_range(lines, start_hunk_line, next_hunk_line)
            if len(hunk_range) > 0:
                line_ranges.append(compute_hunk_range(lines, start_hunk_line, next_hunk_line))
            start_hunk_line = next_hunk_line
            if start_hunk_line == len(lines):
                break

    return (is_new, line_ranges)

def collectChanges(pr_files):
    output_data = []

    for file in pr_files:
        filename = file.filename
        patch = file.patch
        
        logging.info(f"File '{filename}' is processed")

        is_new_file, lines = list(itertools.chain.from_iterable(extract_line_ranges_from_patch(patch)))

        if len(lines) > 0:
            output_data.append({ "path": filename, "lineNumbers": lines, "isNewFile": is_new_file})

    return output_data

def main():
    logging.info("Starting execution")
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")

    g = Github(access_token)
    pr = getPullRequest(g)
    files = pr.get_files()

    json_data = json.dumps(collectChanges(files))
    json_bytes = json_data.encode('utf-8')
    base64_bytes = base64.b64encode(json_bytes)
    base64_str = base64_bytes.decode('utf-8')

    with open(output_file, "a") as f:
        f.write(f"changed_files={base64_str}\n")

if __name__ == '__main__':
    main()
