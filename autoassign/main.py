import logging
import os

from github import Github
from github.GithubObject import NotSet

from libs.utils import *


log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='ACTION: %(message)s', level=log_level)


def main():
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    codebeamer_user = os.environ.get("INPUT_CODEBEAMER_USER")
    codebeamer_password = os.environ.get("INPUT_CODEBEAMER_PASSWORD")

    if not access_token:
        raise Exception("access_token parameters must be set")

    if not (codebeamer_user and codebeamer_password):
        raise Exception("codebeamer_user and codebeamer_password parameters must be set")

    g = Github(access_token)
    pr = getPullRequest(g)
    codebeamer_teams = getTeams(pr, (codebeamer_user, codebeamer_password))

    github_teams = getOrganization(g).get_teams()
    github_teams_cache = convert(github_teams)

    logging.info(f"github_teams_cache: {github_teams_cache}")

    reviewer_team_list = []
    for ct in codebeamer_teams:
        review_team_name = f"{ct} - Reviewers"
        if review_team_name in github_teams_cache:
            reviewer_team_list.append(github_teams_cache[review_team_name])

    # get_review_requests contains 2 list, first for user, second for teams
    for team_review_request in pr.get_review_requests()[1]:
        if team_review_request.slug in reviewer_team_list:
            reviewer_team_list.remove(team_review_request.slug)

    logging.info(f"Following teams are added to the PR asn reviewers: {reviewer_team_list}")

    if reviewer_team_list:
        logging.info("Create review request")
        pr.create_review_request(NotSet, reviewer_team_list)


def convert(a):
    it_name = iter(map(lambda e: e.name, a))
    it_slug = iter(map(lambda e: e.slug, a))
    return dict(zip(it_name, it_slug))


if __name__ == "__main__":
    main()
