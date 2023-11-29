import logging
import os

from github import Github

from libs.utils import *
from libs.github_graphql import GithubGraphQl


log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='ACTION: %(message)s', level=log_level)


def main():
    logging.info("Starting execution")
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    abort_pr = os.environ.get("INPUT_ABORT_PR")

    g = Github(access_token)
    gql = GithubGraphQl(access_token)
    pr = getPullRequest(g)
    if not pr.draft and not re.search('#[0-9]+', pr.title) and not re.search('^merge.*into.*', pr.title.lower()):
        logging.info("Converting to draft")
        pr.create_issue_comment('>_Please define a tracker ID in your PR\'s title_')
        logging.info(gql.convert_to_draft(gql.get_pullRequest_id(*pr.base.repo.full_name.split("/"), pr.number)))
        if abort_pr.lower() == 'true':
            raise Exception("Task ID is needed, marking the check failed")


if __name__ == '__main__':
    main()
