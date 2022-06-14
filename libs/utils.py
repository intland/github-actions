import json
import logging
import os
import re
import requests
from time import sleep, time


def wait_for_build(build, timeout, interval):
    build_url = build.url
    t0 = time()
    sleep(interval)
    while time() - t0 < timeout:
        try:
            result = build.result
            if result == 'SUCCESS':
                logging.info(f'Build successful')
                return result
            if result == 'UNSTABLE':
                logging.info(f'Build unstable')
                return result
            if result in ('FAILURE', 'ABORTED'):
                logging.info(f'Build status returned "{result}".Build has failed ☹️.')
                return result
            logging.info(f'Build not finished yet. Waiting {interval} seconds. {build_url}')
        finally:
            sleep(interval)
    logging.info(f"Build has not finished and timed out. Waited for {timeout} seconds.")
    return "TIMEOUT"


def issue_comment(githubApi, body):

    github_event_file = open(os.environ.get("GITHUB_EVENT_PATH"), "r")
    github_event = json.loads(github_event_file.read())
    github_event_file.close

    pr_repo_name = github_event["pull_request"]["base"]["repo"]["full_name"]
    pr_number = github_event["number"]

    githubApi.get_repo(pr_repo_name).get_pull(pr_number).create_issue_comment(body)


def keep_logs(build, auth, enabled=True):
    if build.api_json()['keepLog'] == enabled:
        return
    response = requests.post(url=build.url + "toggleLogKeep", auth=auth)
    if not response.ok:
        raise Exception(f"Post request returned {response.status_code}")

def getPullRequest(githubApi):
    github_event = getGithubEvent()
    pr_repo_name = github_event["pull_request"]["base"]["repo"]["full_name"]
    pr_number = github_event["number"]

    return githubApi.get_repo(pr_repo_name).get_pull(pr_number)

def getGithubEvent():
    github_event_file = open(os.environ.get("GITHUB_EVENT_PATH"), "r")
    github_event = json.loads(github_event_file.read())
    github_event_file.close
    
    return github_event

def loadMetadata(id, comment):
    for data in re.findall('<!--(.*)-->', comment.body):
        try:
            json_data = json.loads(data)
        except json.decoder.JSONDecodeError:
            pass
        else:
            if json_data['id'] == id:
                return json_data['metadata']


def createMetadata(id, metadata):
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    data = {
        "id": id,
        "metadata": metadata
    }
    return f"<!--{json.dumps(data)}-->"


def getAllComments(pullRequest):
    commentsList = []
    for comment in pullRequest.as_issue().get_comments():
        commentsList.append(comment)
    return commentsList


def getOrganization(githubApi):
    return githubApi.get_organization("intland")


def getTeams(pr, cbAuth):
    ids = []
    ids.extend(getIds(pr.title))
    ids.extend(getIds(pr.body))

    for c in pr.get_commits():
        ids.extend(getIds(c.commit.message))

    teams = []
    for i in set(ids):
        itemGetUrl = f"https://codebeamer.com/cb/api/v3/items/{i}"

        try:
            logging.info(f"Fetching information from: {itemGetUrl}")
            response = requests.get(url=itemGetUrl, auth=cbAuth)
            if response.status_code == 200:
                logging.info(f"Ticket is found")
                for t in response.json()["teams"]:
                    team = t["name"]
                    logging.info(f"'{team}' is added to teams")
                    teams.append(t["name"])

        except Exception as e:
            logging.warning(f"Team information cannot be fetched from: {itemGetUrl}", e)

    return set(teams)


def getIds(text):
    if text:
        return list(map(lambda p: p[1:], filter(lambda p: bool(re.match(r'^#[\d]+$', p)), text.split())))
    else:
        return []
