import logging
import os
import json

from github import Github

from libs.utils import *

log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='JENKINS_ACTION: %(message)s', level=log_level)


def main():
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    github = Github(access_token)
    pr = getPullRequest(github)

    content = json.loads(os.environ.get("INPUT_PARAMETERS", '{}'))
    pr.create_issue_comment(json.dumps(content, indent=4, default=str))


if __name__ == "__main__":
    main()
