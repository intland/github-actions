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
    job_names = os.environ["INPUT_JOB_NAMES"]

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
    github = Github(access_token)

    retry(connectToJenkins, 60, 10)(jenkins)
    
    for job_name in job_names.split(','):
        job_name = job_name.strip()
        retry(removeFromQueue, queue_query_timeout, queue_query_interval)(jenkins, job_name)
        retry(stopAndRemove, job_query_timeout, job_query_interval)(jenkins, job_name)
        issue_comment(github, f"_Builds running on this PR deleted for job: {job_name}_")

def connectToJenkins(jenkins):
    try:
        jenkins.version
        logging.info('Successfully connected to Jenkins.')
    except Exception as e:
        raise Exception('Could not connect to Jenkins.') from e

def stopAndRemove(jenkins, job_name):
    for build in jenkins.get_job(job_name).iter_all_builds():
        if is_build_for_this_pr(build):
            logging.info(f"Build of '{build.get_job().name}' job will be stopped and removed")
            build.stop()
            build.delete()

def removeFromQueue(jenkins, job_name):
    for queue_item in jenkins.queue.api_json()['items']:
        name = queue_item.get('task').get('name')
        logging.info(f"Queue item name is {name}")
        if name == job_name:
            q_obj = jenkins.queue.get(queue_item['id'])
            if is_build_for_this_pr(q_obj):
                logging.info(f"'{name}' will be canceled")
                q_obj.cancel


if __name__ == "__main__":
    main()
