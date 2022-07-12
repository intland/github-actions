import logging
import os

from github import Github

from libs.utils import *

# log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
log_level = "DEBUG"
logging.basicConfig(format='ACTION: %(message)s', level=log_level)


def main():
    if head_branch := os.environ.get("INPUT_HEAD_BRANCH") is None:
        if head_branch := os.environ.get("HEAD_BRANCH") is None:
            raise Exception("head branch can't be determined from parameters or environment variables")
    logging.debug(head_branch)

    if target_branch := os.environ.get("INPUT_TARGET_BRANCH") is None:
        if target_branch := os.environ.get("TARGET_BRANCH") is None:
            raise Exception("target branch can't be determined from parameters or environment variables")
    logging.debug(target_branch)

    if repository_name := os.environ.get("INPUT_REPOSITORY_NAME") is None:
        if repository_name := os.environ.get("GITHUB_REPOSITORY") is None:
            raise Exception("repository name can't be determined from parameters or environment variables")
    logging.debug(repository_name)

    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    if not access_token:
        raise Exception("access_token parameters must be set")

    g = Github(access_token)
    repo = g.get_repo(repository_name)
    pr = repo.create_pull(owner=repo.owner.login, repo=repo.name, base=target_branch, head=head_branch)
    logging.info(pr.url)


if __name__ == '__main__':
    main()
