import logging
import os

from github import Github
from libs.utils import *

logging.basicConfig(format='ACTION: %(message)s', level='INFO')

def main():
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")

    metadata_id = "pr-status-check"

    g = Github(access_token)
    pr = getPullRequest(g)

    comment = getCommentById(pr, metadata_id)
    if comment:
        logging.info("Comment is deleted")
        comment.delete()

    missing_commits = get_missing_commits_from_upstream(
        github=g,
        repo_name=pr.head.repo.full_name,
        dest_user=pr.base.user.login,
        dest_branch=pr.base.ref,
        source_branch=pr.head.ref
    )
    pr_is_mergeable = 'true' if missing_commits == 0 else 'false'
    logging.info(f'PR is mergable: {pr_is_mergeable} hence number of missing commits: {missing_commits}')

    if pr_is_mergeable == 'false':
        issue_comment(
            g,
            metadata_id,
            f'This PR can not be merged cause it is {missing_commits} commits behind upstream'
        )

    with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
        print(f'PR_IS_MERGEABLE={pr_is_mergeable}', file=fh)

if __name__ == "__main__":
    main()