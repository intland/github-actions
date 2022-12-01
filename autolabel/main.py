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
    teams = getTeams(pr, (codebeamer_user, codebeamer_password))

    for team in teams:
        pr.add_to_labels(team)

    try:
        priority = get_ticket_priority(pr, (codebeamer_user, codebeamer_password))
        pr.add_to_labels(priority)
    except Exception as e:
        logging.error("Couldn't put Ticket Priority Label:", e)


if __name__ == "__main__":
    main()
