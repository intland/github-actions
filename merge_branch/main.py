import logging
import os

from github import Github

from libs.utils import *

log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='ACTION: %(message)s', level=log_level)


def main():
    if (head_branch := os.environ.get("INPUT_HEAD_BRANCH")) is None:
        if (head_branch := os.environ.get("HEAD_BRANCH")) is None:
            raise Exception("head branch can't be determined from parameters or environment variables")
    print(head_branch)

    if (target_branch := os.environ.get("INPUT_TARGET_BRANCH")) is None:
        if (target_branch := os.environ.get("TARGET_BRANCH")) is None:
            raise Exception("target branch can't be determined from parameters or environment variables")
    print(target_branch)

    if (repository_name := os.environ.get("INPUT_REPOSITORY_NAME")) is None:
        if (repository_name := os.environ.get("GITHUB_REPOSITORY")) is None:
            raise Exception("repository name can't be determined from parameters or environment variables")
    print(repository_name)

    if (access_token := os.environ.get("INPUT_ACCESS_TOKEN")) is None:
        raise Exception("access_token parameters must be set")

    merge_branch, clean_merge = create_merge_branch(head_branch, target_branch)

    g = Github(access_token)
    repo = g.get_repo(repository_name)
    pr = repo.create_pull(owner=repo.owner.login, repo=repo.name, base=target_branch, head=merge_branch)
    if not clean_merge:
        pr.add_to_labels("merge-conflict")
    logging.info(pr.url)


def create_merge_branch(head, target):
    merge_branch = f"{head}_into_{target}"
    if merge_branch_exists(merge_branch):
        runs(f"git branch -D {merge_branch}")
    runs("git status")
    runs(f"git checkout {head}")
    runs("git pull")
    runs(f"git checkout {target}")
    runs("git pull")
    runs(f"git checkout -b {merge_branch}")
    try:
        runs(f"git merge {head} --no-edit")
        clean_merge = True
    except Exception:
        runs("git add .")
        runs(f"git commit -m {merge_branch}")
        clean_merge = False
    runs(f"git push --force --set-upstream origin {merge_branch}")
    return merge_branch, clean_merge


def merge_branch_exists(branch):
    try:
        runs(f"git rev-parse --verify {branch}")
    except Exception:
        return False
    return True


if __name__ == '__main__':
    main()
