import logging
import os

from github import Github

from libs.utils import *


log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='ACTION: %(message)s', level=log_level)


def main():
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    codebeamer_user = os.environ.get("INPUT_CODEBEAMER_USER")
    codebeamer_password = os.environ.get("INPUT_CODEBEAMER_PASSWORD")

    if not (codebeamer_user and codebeamer_password):
        raise Exception("codebeamer_user and codebeamer_password parameters must be set")

    g = Github(access_token)

    pr = getPullRequest(g)

    # Team Labels
    teams = getTeams(pr, (codebeamer_user, codebeamer_password))
    for team in teams:
        pr.add_to_labels(team)

    # Priority Label
    create_priority_labels(g.get_repo(os.environ.get("GITHUB_REPOSITORY")))
    priority = get_ticket_priority(pr, (codebeamer_user, codebeamer_password))
    replace_labels(pr, "priority", priority)

    # Branch Label
    if not (branch := os.environ.get("TARGET_BRANCH")):
        raise Exception("Can't find target branch")
    replace_labels(pr, "target", branch)


if __name__ == "__main__":
    main()
