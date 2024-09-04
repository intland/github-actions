import logging
import os

from api4jenkins import Jenkins
from github import Github

from libs.utils import *

log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='JENKINS_ACTION: %(message)s', level=log_level)


def main():
    # Required
    url = "https://jenkins.rd2.thingworx.io/jenkins" # os.environ["INPUT_URL"]
    username = os.environ.get("INPUT_USERNAME")
    api_token = os.environ.get("INPUT_API_TOKEN")
    job_names = os.environ["INPUT_JOB_NAMES"]

    # Optional
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")

    # Preset
    queue_query_timeout = 60
    queue_query_interval = 10
    job_query_timeout = 60
    job_query_interval = 10

    if username and api_token:
        auth = (username, api_token)
    else:
        auth = None
        logging.info('Username or token not provided. Connecting without authentication.')

    jenkins = JenkinsWrapper(url, auth=auth)
    github = Github(access_token)

    retry(jenkins.connect_to_jenkins, 60, 10)

    for job_name in job_names.split(','):
        job_name = job_name.strip()
        if retry(jenkins.stop_and_remove, job_query_timeout, job_query_interval)(job_name):
            issue_comment(github, f"removed-{job_name}", f"_Builds running on this PR stopped and deleted for job: {job_name}_")


if __name__ == "__main__":
    main()
