import json
import logging
import os
import re

from api4jenkins import Jenkins
from github import Github

from libs.utils import *


log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='JENKINS_ACTION: %(message)s', level=log_level)


def main():
    # Required
    url = os.environ["INPUT_URL"]

    # Optional
    username = os.environ.get("INPUT_USERNAME")
    api_token = os.environ.get("INPUT_API_TOKEN")
    cookies = os.environ.get("INPUT_COOKIES")
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    if not access_token:
        raise Exception("Access token is required to connect to github")
    github = Github(os.environ.get("INPUT_ACCESS_TOKEN"))

    # Predefined

    if username and api_token:
        auth = (username, api_token)
    else:
        auth = None
        logging.info('Username or token not provided. Connecting without authentication.')

    if cookies:
        try:
            cookies = json.loads(cookies)
        except json.JSONDecodeError as e:
            raise Exception('`cookies` is not valid JSON.') from e
    else:
        cookies = {}

    jenkins = Jenkins(url, auth=auth, cookies=cookies)

    try:
        jenkins.version
    except Exception as e:
        raise Exception('Could not connect to Jenkins.') from e
    logging.info('Successfully connected to Jenkins.')

    githubApi = Github(access_token)

    log_keep_metadata = {
        "id": "keepLogs",
        "metadata": []
    }

    for log in find_old_logs(getAllComments(getPullRequest(github))):
        log = json.loads(log)
        logging.debug(log)
        build = jenkins.get_job(log["fullName"]).get_build(log["number"])
        keep_logs(build, auth, False)
        log_keep_metadata["metadata"].append({"build": {"fullName": log["fullName"], "number": log["number"]}, "enabled": False})
    issue_comment(githubApi, "<!--{lkm}-->\n_Discarded old logs_".format(lkm=json.dumps(log_keep_metadata)))


def find_old_logs(comments):
    old_logs = set()
    for comment in comments:
        for data in re.findall('<!--(.*)-->', comment.body):
            try:
                json_data = json.loads(data)
            except json.decoder.JSONDecodeError as e:
                logging.debug(f"{data}\nNot valid json:\n{e} ")
            else:
                if json_data["id"] == "keepLogs":
                    for log_data in json_data['metadata']:
                        if log_data["enabled"]:
                            old_logs.add(json.dumps(log_data["build"]))
                        else:
                            old_logs.discard(json.dumps(log_data["build"]))
    return old_logs


if __name__ == "__main__":
    main()
