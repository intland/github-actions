import logging
from datetime import datetime
import os
import json

from api4jenkins import Jenkins
from github import Github

from libs.utils import *

log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='JENKINS_ACTION: %(message)s', level=log_level)


def main():
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    github = Github(access_token)
    pr = getPullRequest(github)
    files = set()
    commits = {}
    resp = {
        "files": files,
        "commits": commits,
        "timestamp": datetime.now()
    }
    content = json.dumps(resp, indent=4, default=str)
    pr.create_issue_comment(content)


if __name__ == "__main__":
    main()
