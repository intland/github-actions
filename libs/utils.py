import imp
import json
import logging
import os
import re
import requests
from subprocess import run
from sys import stderr
from time import sleep, time


def wait_for_mergeable_pr(pr, timeout):
    return

#    t0 = time()
#    while time() - t0 < timeout:
#        is_mergeable = pr.mergeable
#        mergeable_state = pr.mergeable_state
#        if is_mergeable:
#            logging.info(f"Pull request is mergeable")
#            return
#
#        logging.info(f"Mergeable status: {pr.mergeable}, State: {mergeable_state}")
#        sleep(10)
#
#    raise Exception("Pull request is not mergeable")


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


def issue_comment(githubApi, metadata_id, content, metadata={}):
    comment = None
    pr = getPullRequest(githubApi)

    try:
        logging.info(f"Try to find comment by {metadata_id}...")
        comment = getCommentById(pr, metadata_id)
        logging.info(f"Comment is found by {metadata_id}")
    except Exception as e:
        logging.warning(f"Comments by Id cannot be found, {e}")

    content += "\n" + createMetadata(metadata_id, metadata)
    if comment:
        logging.info("Comment is deleted")
        comment.delete()

    logging.info("New comment is created")
    pr.create_issue_comment(content)


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
    github_event_file.close()

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


def getCommentById(pr, id):
    for comment in getAllComments(pr):
        for data in re.findall('<!--(.*)-->', comment.body):
            try:
                json_data = json.loads(data)
            except json.decoder.JSONDecodeError:
                pass
            else:
                if json_data['id'] == id:
                    return comment


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


def is_build_for_this_pr(build):
    for param in build.get_parameters():
        if param.name == 'CODEBEAMER':
            github_event = getGithubEvent()
            return param.value == '{0}#{1}'.format(github_event['pull_request']['head']['repo']['clone_url'], github_event['pull_request']['head']['ref'])
    return False


def getIds(text):
    if text:
        return list(map(lambda p: p[1:], filter(lambda p: bool(re.match(r'^#[\d]+$', p)), text.split())))
    else:
        return []


def retry(func, timeout, interval):
    def wrapper(*args, **kwargs):
        t0 = time()
        while time() - t0 < timeout:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                sleep(interval)
                logging.info(f"Something happened, re-try again... {e}")
        raise Exception('TIMEOUT')
    return wrapper


def convertMillisToHumanReadable(millis):
    millis = int(millis)
    seconds = int(int(millis / 1000) % 60)
    minutes = int(int(millis / (1000 * 60)) % 60)
    hours = int(int(millis / (1000 * 60 * 60)) % 24)

    if hours > 0:
        return f"{hours}h:{minutes}m:{seconds}s"
    elif minutes > 0:
        return f"{minutes}m:{seconds}s"
    else:
        return f"m:{seconds}s"


def find_old_logs(metadata_id, comments):
    old_logs = set()
    for comment in comments:
        for data in re.findall('<!--(.*)-->', comment.body):
            try:
                json_data = json.loads(data)
            except json.decoder.JSONDecodeError as e:
                logging.debug(f"{data}\nNot valid json:\n{e} ")
            else:
                if json_data["id"] == metadata_id:
                    for log_data in json_data['metadata']:
                        if log_data["enabled"]:
                            old_logs.add(json.dumps(log_data["build"]))
                        else:
                            old_logs.discard(json.dumps(log_data["build"]))
    return old_logs


def getPRAuthorEmails(pr):
    emails = set()
    if pr:
        if pr.user and (email := pr.user.email):
            emails.add(email)
        for c in pr.get_commits():
            if c:
                if c.author and (email := c.author.email):
                    emails.add(email)
                elif c.commit and c.commit.author and (email := c.commit.author.email):
                    emails.add(email)
    return emails


def runs(command, verbose=0):
    resp = run(command.split(), capture_output=True)
    if resp.returncode:
        raise Exception(resp.stderr.decode('utf8'))
    if verbose >= 2:
        print(f"START `{command}`")
    if verbose:
        if resp.stdout:
            print(resp.stdout.decode('utf8'))
        if resp.stderr:
            print(resp.stderr.decode('utf8'), file=stderr)
    if verbose >= 2:
        print(f"END `{command}`\n")
    return resp
