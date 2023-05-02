import logging
import os
import re
import json

from github import Github

from libs.utils import *

log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='JENKINS_ACTION: %(message)s', level=log_level)


def glob_to_re(pat: str) -> str:
    i, n = 0, len(pat)
    res = ''
    while i < n:
        c = pat[i]
        i = i + 1
        if c == '*':
            j = i
            # check for **
            if j < n and pat[j] == '*':
                res = res + '.*'
                i = j + 1
                j = i
                # let **/ match files in base directory
                if j < n and pat[j] == '/':
                    i = j + 1
            # prevent '/' crossing directory boundaries
            else:
                res = res + '[^/]*'
        elif c == '?':
            # prevent '?' matching directory boundaries
            res = res + '[^/]'
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
                    # ensure sequence negations don't match directory boundaries
                    stuff = '^/' + stuff[1:]
                elif stuff[0] in ('^', '['):
                    stuff = '\\' + stuff
                res = '%s[%s]' % (res, stuff)
        else:
            res = res + re.escape(c)
    return r'(?s:%s)\Z' % res


def glob_filter(names, pattern):
    return [name for name in names if re.match(glob_to_re(pattern), name)]


def get_extra_params(config, filenames):
    extra_params = {}
    for item in config['parameters_by_path']:
        for pattern in item['path_patterns']:
            if glob_filter(filenames, pattern):
                extra_params.update(item["extra_parameters"])
                break
    return extra_params


def main():
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    config_file = os.environ.get("INPUT_CONFIG_FILE_NAME")
    if not config_file:
        raise Exception("Please provide a configuration file.")
    config_file = f"/app/{config_file}"
    github = Github(access_token)
    pr = getPullRequest(github)
    logging.info(f"Files updated: {json.dumps([f.filename for f in pr.get_files()])}")
    with open(config_file) as f:
        config = json.loads(f.read())
    extra_params = get_extra_params(config, [f.filename for f in pr.get_files()])
    logging.info(f"extra_parameters=\'{json.dumps(extra_params)}\'")
    with open(os.environ.get("GITHUB_OUTPUT"), "a") as f:
        f.write(f'extra_parameters={json.dumps(extra_params)}')


if __name__ == "__main__":
    main()
