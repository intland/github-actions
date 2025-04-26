import logging
import os
import re
import itertools
import json

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

def get_hunk_start(line):
    return int(re.search(r"@@ -(\d+),(\d+) \+(\d+),(\d+) @@.*", line).group(3))

def get_hunk_length(line):
    return int(re.search(r"@@ -(\d+),(\d+) \+(\d+),(\d+) @@.*", line).group(4))

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
        while True:
            next_hunk_line = get_next_line_number(lines, start_hunk_line + 1)
            hunk_range = compute_hunk_range(lines, start_hunk_line, next_hunk_line)
            if len(hunk_range) > 0:
                line_ranges.append(compute_hunk_range(lines, start_hunk_line, next_hunk_line))
            start_hunk_line = next_hunk_line
            if start_hunk_line == len(lines):
                break

    return line_ranges

def collectChanges(pr_files):
    output_data = []

    for file in pr_files:
        filename = file.filename
        patch = file.patch
        
        logging.info(f"File '{filename}' is processed")

        lines = list(itertools.chain.from_iterable(extract_line_ranges_from_patch(patch)))

        if len(lines) > 0:
            output_data.append({ "path": filename, "lineNumbers": lines })

    return output_data

def main():
    logging.info("Starting execution")
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")

    g = Github(access_token)
    pr = getPullRequest(g)
    files = pr.get_files()

    json_data = json.dumps(collectChanges(files))

    with open(output_file, "a") as f:
        f.write(f"changed_files={json_data}\n")

if __name__ == '__main__':
    main()
