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
    priority = get_ticket_priority(pr, (codebeamer_user, codebeamer_password))
    replace_labels(pr, "priority", priority)


if __name__ == "__main__":
    main()
