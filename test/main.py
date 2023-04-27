import logging
from datetime import datetime
import os
import re
import json
import glob

from api4jenkins import Jenkins
from github import Github

from libs.utils import *

log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='JENKINS_ACTION: %(message)s', level=log_level)
CONFIG_FILE = "/app/job_config.json"


def glob_to_re(pat: str) -> str:

    i, n = 0, len(pat)
    res = ''
    while i < n:
        c = pat[i]
        i = i + 1
        if c == '*':
            j = i
            if j < n and pat[j] == '*':
                res = res + '.*'
                i = j + 1
                j = i
                if j < n and pat[j] == '/':
                    i = j + 1
            else:
                res = res + '[^/]*'
            # -------- CHANGE END ----------
        elif c == '?':
            # -------- CHANGE START --------
            # prevent '?' matching directory boundaries
            res = res + '[^/]'
            # -------- CHANGE END ----------
        elif c == '[':
            j = i
            if j < n and pat[j] == '!':
                j = j + 1
            if j < n and pat[j] == ']':
                j = j + 1
            while j < n and pat[j] != ']':
                j = j + 1
            if j >= n:
                res = res + '\\['
            else:
                stuff = pat[i:j]
                if '--' not in stuff:
                    stuff = stuff.replace('\\', r'\\')
                else:
                    chunks = []
                    k = i + 2 if pat[i] == '!' else i + 1
                    while True:
                        k = pat.find('-', k, j)
                        if k < 0:
                            break
                        chunks.append(pat[i:k])
                        i = k + 1
                        k = k + 3
                    chunks.append(pat[i:j])
                    # Escape backslashes and hyphens for set difference (--).
                    # Hyphens that create ranges shouldn't be escaped.
                    stuff = '-'.join(s.replace('\\', r'\\').replace('-', r'\-')
                                     for s in chunks)
                # Escape set operations (&&, ~~ and ||).
                stuff = re.sub(r'([&~|])', r'\\\1', stuff)
                i = j + 1
                if stuff[0] == '!':
                    # -------- CHANGE START --------
                    # ensure sequence negations don't match directory boundaries
                    stuff = '^/' + stuff[1:]
                    # -------- CHANGE END ----------
                elif stuff[0] in ('^', '['):
                    stuff = '\\' + stuff
                res = '%s[%s]' % (res, stuff)
        else:
            res = res + re.escape(c)
    return r'(?s:%s)\Z' % res


def glob_filter(names, pattern):
    return (name for name in names if re.match(glob_to_re(pattern), name))


def main():
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    github = Github(access_token)
    pr = getPullRequest(github)
    logging.info(f"Files updated: {json.dumps([f.filename for f in pr.get_files()])}")
    extra_params = {}
    with open(CONFIG_FILE) as f:
        config = json.loads(f.read())
    for item in config['parameters_by_path']:
        for pattern in item['path_patterns']:
            if glob_filter([f.filename for f in pr.get_files()], pattern):
                extra_params.update(item["extra_parameters"])
                break

    logging.info(f"extra_parameters=\'{json.dumps(extra_params)}\'")
    # print(f'::set-output name=extra_parameters::{json.dumps(extra_params)}')
    with open(os.environ.get("GITHUB_OUTPUT"), "a") as f:
        f.write(f'"extra_parameters=\'{json.dumps(extra_params)}\'"')


if __name__ == "__main__":
    main()
