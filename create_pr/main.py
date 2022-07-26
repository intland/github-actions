import logging
import os

from github import Github

from libs.utils import *

log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='ACTION: %(message)s', level=log_level)


def main():

    if not (head_branch := os.environ.get("INPUT_HEAD_BRANCH")):
        if not (head_branch := os.environ.get("HEAD_BRANCH")):
            raise Exception("head branch can't be determined from parameters or environment variables")
    logging.info(f"head_branch: {head_branch}")

    if not (target_branch := os.environ.get("INPUT_TARGET_BRANCH")):
        if not (target_branch := os.environ.get("TARGET_BRANCH")):
            raise Exception("target branch can't be determined from parameters or environment variables")
    logging.info(f"target_branch: {target_branch}")

    if not (repository_name := os.environ.get("INPUT_REPOSITORY_NAME")):
        if not (repository_name := os.environ.get("GITHUB_REPOSITORY")):
            raise Exception("repository name can't be determined from parameters or environment variables")
    logging.info(f"repository_name: {repository_name}")

    if not (access_token := os.environ.get("INPUT_ACCESS_TOKEN")):
        raise Exception("access_token parameters must be set")

    if (draft := os.environ.get("INPUT_DRAFT")).lower() in ["true", "yes"]:
        draft = True
    else:
        draft = False

    g = Github(access_token)

    repo = g.get_repo(repository_name)
    prs = repo.get_pulls(state='open')
    for pr in prs:
        if pr.head.ref == head_branch and pr.base.ref == target_branch:
            logging.info(f"PR already exists for Merge {head_branch} into {target_branch} at {pr.url}")
            return
    pr = repo.create_pull(title=f"Merge {head_branch} into {target_branch}", body="", base=target_branch, head=head_branch, draft=draft)
    logging.info(pr.url)


if __name__ == '__main__':
    main()
