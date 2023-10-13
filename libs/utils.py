import json
import xml.dom.minidom
import logging
import os
import re
import requests
from urllib.parse import quote_plus
from subprocess import run
from sys import stderr
from time import sleep, time

from api4jenkins import Jenkins


class JenkinsWrapper:
    def __init__(self, url, auth):
        self.url = url
        self.queue_endpoint = "/queue/api/xml"
        self.auth = auth
        self.jenkins = Jenkins(url, auth=auth)

    def _wait_for_left_item(self, queue_item):
        if queue_item._class.endswith('$LeftItem'):
            logging.info('Build is not blocked anymore')
            return
        else:
            logging.info('Waiting for build not to be blocked')
            raise Exception('Build is currently blocked.')

    def _modify_url(self, object_to_modify):
        if (object_to_modify.url.split('/')[2] == 'jenkins.rd2.thingworx.io'):
            object_to_modify.url = object_to_modify.url.replace(
                'jenkins.rd2.thingworx.io', 'bitbucket-jenkins.rd2.thingworx.io'
            )
        return object_to_modify

    def _get_job(self, name):
        return self._modify_url(self.jenkins.get_job(name))

    def _is_running_or_pending(self, build):
        return self._modify_url(build).api_json()['result'] is None

    def get_public_url(self, private_url):
        public_url = ""
        if "bitbucket-jenkins.rd2.thingworx.io" in private_url:
            public_url = private_url.replace('bitbucket-jenkins.rd2.thingworx.io', 'jenkins.rd2.thingworx.io')
        else:
            public_url = private_url
        return public_url

    def connect_to_jenkins(self):
        try:
            logging.info(f"Try to connect to jenkins")
            self.jenkins.version
            logging.info('Successfully connected to Jenkins.')
        except Exception as e:
            raise Exception('Could not connect to Jenkins.') from e
        
    def stop_running_builds(self, job_url, job_name, pr_url):
        job              = self._get_job(job_name)
        tree_string      = f"tree=builds[result,number,actions[parameters[name,value]]]"
        xpath_string     = f"xpath=//build[not(result)][action[parameter[name[contains(text(),%27PR_LINK%27)]][value[contains(text(),%27{pr_url}%27)]]]]//number&wrapper=root"
        endpoint_to_call = f"{job_url}api/xml?{tree_string}&{xpath_string}"
        logging.info(f"Endpoint: {endpoint_to_call}")

        logging.info("Checking running builds")
        session = requests.Session()
        session.auth = self.auth
        response = session.get(endpoint_to_call)

        logging.info("Parsing running builds response")
        dom = xml.dom.minidom.parseString(response.text)
        if dom.getElementsByTagName('number'):
            for build_number in dom.getElementsByTagName('number'):
                parsed_build_number = build_number.firstChild.nodeValue
                logging.info(f"Stopping build: {parsed_build_number}")
                build_to_stop = job.get_build(parsed_build_number)
                build_to_stop = self._modify_url(build_to_stop)
                build_to_stop.stop()
                sleep(3)
            return True
        else:
            logging.info("No running builds for job")
            return False

    def remove_from_queue(self, job_original_url, pr_url):
        xpath_string     = f"xpath=//item[action[parameter[name[contains(text(),%27PR_LINK%27)]][value[contains(text(),%27{pr_url}%27)]]]][task[url[contains(text(),%27{job_original_url}%27)]]]//id&wrapper=root"
        endpoint_to_call = f"{self.url}{self.queue_endpoint}?{xpath_string}"
        logging.info(f"Endpoint: {endpoint_to_call}")

        logging.info("Checking queued items")
        session = requests.Session()
        session.auth = self.auth
        response = session.get(endpoint_to_call)

        logging.info("Parsing queue endpoint response")
        dom = xml.dom.minidom.parseString(response.text)
        if dom.getElementsByTagName('id'):
            for item_id in dom.getElementsByTagName('id'):
                parsed_item_id = item_id.firstChild.nodeValue
                logging.info(f"Removing item: {parsed_item_id} from queue ")
                q_obj = self.jenkins.queue.get(parsed_item_id)
                q_obj.cancel()
                sleep(5)

    def is_build_running(self, build):
        if build.api_json()['result'] not in ['UNSTABLE', 'ABORTED', 'SUCCESS', 'FAILURE']:
            return True
        return False

    def stop_and_remove(self, job_name):
        logging.info(f"Jenkins job name: {job_name}")
        original_job_url = self.jenkins.get_job(job_name).url
        modified_job_url = self._get_job(job_name).url
        job = self._get_job(job_name)
        if not job:
            logging.info(f"Job is not found by name: {job_name}")
            return False
        
        github_event = getGithubEvent()
        pull_request_url = github_event['pull_request']['_links']['html']['href']
        logging.info(f"PR url is {pull_request_url}")

        self.remove_from_queue(original_job_url, pull_request_url)

        has_build_stopped = False
        has_build_stopped = self.stop_running_builds(modified_job_url, job_name, pull_request_url)

        return has_build_stopped

    def build_job(self, job_name, parameters):
        job = self._get_job(job_name)
        return job.build(**parameters)

    def wait_for_build(self, queue_item):
        retry(self._wait_for_left_item, 600, 10)(queue_item)
        build = queue_item.get_build()
        build = self._modify_url(build)
        if not build:
            raise Exception(f'Build not started yet. Waiting few seconds.')
        logging.info(f'Build has been started.')
        return build
    
    def keep_logs_metadata(self, build):
        fullName = self._modify_url(build.get_job()).full_name
        number = build.api_json()['number']
        return json.dumps([{"build": {"fullName": fullName, "number": number}, "enabled": True}])


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


def wait_for_build(build, build_url, timeout, interval):
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


def delete_review_comments(github_api, user_name):
    pr = getPullRequest(github_api)
    comments = pr.get_review_comments()
    logging.info(f"Deleting review comments for user:  {user_name}")
    for comment in comments:
        if comment.user.login == user_name:
            comment.delete()


def create_review_comment(
    pr_url,
    auth,
    commit_sha,
    content,
    path,
    line,
    start_line=None,
    api_version='2022-11-28'
):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {auth}",
        "X-GitHub-Api-Version": api_version
    }
    payload = {
        'body': content,
        'commit_id': commit_sha,
        'path': path,
        'line': line,
        'side': 'RIGHT'
    }
    if start_line:
        payload['start_line'] = start_line
        payload['start_side'] = 'RIGHT'

    try:
        r = requests.post(
            url=f"{pr_url}/comments",
            headers=headers,
            data=json.dumps(payload)
        )
        r.raise_for_status()
        return True
    except Exception as e:
        if e.response.status_code == 422:
            logging.info(f'Error code: {e.response.status_code} is expected as of now.')
        else:
            raise Exception(f"Post request returned {e.response.status_code}. Message: {e.response.text}")
        return False


def keep_logs(build, auth, enabled=True):
    return

def getPullRequest(githubApi):
    github_event = getGithubEvent()
    pr_repo_name = github_event["pull_request"]["base"]["repo"]["full_name"]
    pr_number = github_event["number"] if "number" in github_event else github_event["pull_request"]['number']

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


def get_pull_request_files(github_api):
    pr = getPullRequest(github_api)
    return pr.get_files()


def getOrganization(githubApi):
    return githubApi.get_organization("intland")


def getTeams(pr, cbAuth):
    ids = collectIds(pr)
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


def get_ticket_priority(pr, cbAuth):
    ids = collectIds(pr)
    priority = None
    for id in ids:
        itemGetUrl = f"https://codebeamer.com/cb/api/v3/items/{id}"
        try:
            logging.info(f"Fetching information from: {itemGetUrl}")
            response = requests.get(url=itemGetUrl, auth=cbAuth)
            if response.status_code == 200:
                logging.info(f"Ticket #{id} is found")
                if not priority or priority.get("id") > response.json()['priority']['id']:
                    priority = response.json()['priority']
        except Exception as e:
            logging.warning(f"Ticket priority information cannot be fetched from: {itemGetUrl}", e)
    if priority:
        return priority.get("name")
    return None

def find_params(build, param_name):
    for param in build.get_parameters():
        if param.name == param_name:
            return param
    return None

def get_missing_commits_from_upstream(github, repo_name, dest_user, dest_branch, source_branch):
    repository = github.get_repo(repo_name)
    return repository.compare(quote_plus(f'{dest_user}:{dest_branch}'), quote_plus(source_branch)).behind_by


def collectIds(pr):
    ids = []
    ids.extend(getIds(pr.title))
    ids.extend(getIds(pr.body))
    for c in pr.get_commits():
        ids.extend(getIds(c.commit.message))

    return ids


def getIds(text):
    if text:
        return re.findall(r'#([\d]+)', text)
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


def getPRAuthorEmails(url, auth):
    resp = requests.get(f"{url}/commits", headers={"Authorization": f"token {auth}"})
    if resp.ok:
        emails = set()
        for commit in json.loads(resp.content):
            if commit.get('author') and (email := commit['author'].get('email')):
                emails.add(email)
            if commit.get('commit') and commit['commit'].get('author') and (email := commit['commit']['author'].get('email')):
                emails.add(email)
        if emails:
            return emails
    return set(["github.runner@intland.com"])


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


def replace_labels(pr, prefix, value):
    for label in pr.get_labels():
        if re.match(f"{prefix}:.*", label.name):
            if label.name == f"{prefix}:{value}":
                return
            pr.remove_from_labels(label)
    if not value:
        return
    pr.add_to_labels(f"{prefix}:{value}")


def create_priority_labels(repo):
    defaults = {
        "priority:Lowest": "858585",
        "priority:Low": "0092BA",
        "priority:Normal": "00A95A",
        "priority:High": "FFAC38",
        "priority:Highest": "B50F0B"
    }
    for label in repo.get_labels():
        if label.name in defaults.keys():
            if label.color != (color := defaults.pop(label.name)):
                label.edit(label.name, color)
    for label in defaults:
        repo.create_label(label, defaults[label])
