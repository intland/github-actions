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
    username = os.environ.get("INPUT_USERNAME")
    api_token = os.environ.get("INPUT_API_TOKEN")
    job_name = os.environ["INPUT_JOB_NAME"]

    # Optional
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")

    # Preset
    queue_query_timeout = 600
    queue_query_interval = 10
    job_query_timeout = 600
    job_query_interval = 10

    if username and api_token:
        auth = (username, api_token)
    else:
        auth = None
        logging.info('Username or token not provided. Connecting without authentication.')

    jenkins = Jenkins(url, auth=auth)

    try:
        jenkins.version
    except Exception as e:
        raise Exception('Could not connect to Jenkins.') from e
    logging.info('Successfully connected to Jenkins.')

    t0 = time()
    while time() - t0 < queue_query_timeout:
        try:
            for queue_item in jenkins.queue.api_json()['items']:
                if queue_item.get('task').get('name') == 'tmp-test':
                    q_obj = jenkins.queue.get(queue_item['id'])
                    if is_build_for_this_pr(q_obj):
                        q_obj.cancel
            break
        finally:
            sleep(queue_query_interval)
    else:
        raise Exception("Queue query timeout")

    t0 = time()
    while time() - t0 < job_query_timeout:
        try:
            for build in jenkins.get_job(job_name).iter_all_builds():
                if is_build_for_this_pr(build):
                    build.delete()
            break
        finally:
            sleep(job_query_interval)
    else:
        raise Exception("Job query timeout")

    github = Github(access_token)
    issue_comment(github, f"_Builds running on this PR deleted for job: {job_name}_")


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
