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

    g = Github(access_token)
    gql = GithubGraphQl(access_token)
    pr = getPullRequest(g)
    if not pr.draft and not re.search('#[0-9]+', pr.title) and not re.search('Merge merge_.*into.* into .*', pr.title):
        logging.info("Converting to draft")
        pr.create_issue_comment('>_Please define a tracker ID in your PR\'s title_')
        logging.info(gql.convert_to_draft(gql.get_pullRequest_id(*pr.base.repo.full_name.split("/"), pr.number)))


if __name__ == '__main__':
    main()
