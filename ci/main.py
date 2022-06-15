import json
import logging
import os
from time import time, sleep
from api4jenkins import Jenkins
from github import Github
from libs.utils import *

log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='JENKINS_ACTION: %(message)s', level=log_level)


def main():
    # Required
    url = os.environ["INPUT_URL"]
    job_name = os.environ["INPUT_JOB_NAME"]

    # Optional
    username = os.environ.get("INPUT_USERNAME")
    api_token = os.environ.get("INPUT_API_TOKEN")
    parameters = os.environ.get("INPUT_PARAMETERS")
    timeout = int(os.environ.get("INPUT_TIMEOUT"))
    start_timeout = int(os.environ.get("INPUT_START_TIMEOUT"))
    interval = int(os.environ.get("INPUT_INTERVAL"))
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    display_job_name = os.environ.get("INPUT_DISPLAY_JOB_NAME")

    # Preset
    job_query_timeout = 600
    job_query_interval = 10

    if username and api_token:
        auth = (username, api_token)
    else:
        auth = None
        logging.info('Username or token not provided. Connecting without authentication.')

    if parameters:
        try:
            parameters = json.loads(parameters)
        except json.JSONDecodeError as e:
            raise Exception('`parameters` is not valid JSON.') from e
    else:
        parameters = {}

    g = Github(access_token)
    jenkins = Jenkins(url, auth=auth)

    try:
        jenkins.version
    except Exception as e:
        raise Exception('Could not connect to Jenkins.') from e

    try:
        if access_token:
            wait_for_mergeable_pr(getPullRequest(g), 60)
    except Exception as e:
        issue_comment(g, 'Pull request is not mergeable, please resolve your conflict(s)')
        raise e

    logging.info('Successfully connected to Jenkins.')

    queue_item = jenkins.build_job(job_name, **parameters)

    logging.info('Requested to build job.')

    t0 = time()
    sleep(interval)
    while time() - t0 < start_timeout:
        build = queue_item.get_build()
        if build:
            break
        logging.info(f'Build not started yet. Waiting {interval} seconds.')
        sleep(interval)
    else:
        raise Exception(f"Could not obtain build and timed out. Waited for {start_timeout} seconds.")

    build_url = build.url
    if access_token:
        issue_comment(g, f'{display_job_name} - Build started [here]({build_url})')

    logging.info(f"Build URL: {build_url}")
    print(f"::set-output name=build_url::{build_url}")
    print(f"::notice title=build_url::{build_url}")

    result = wait_for_build(build, timeout, interval)

    if not access_token:
        logging.info("No comment.")
        if result in ('FAILURE', 'ABORTED'):
            raise Exception(result)
        return

    keep_logs(build, auth)
    body = keepLogsMeta(build)
    body += f'\n### [{display_job_name} - Build]({build_url}) status returned **{result}**.'
    t0 = time()
    while time() - t0 < job_query_timeout:
        try:
            duration = build.api_json()["duration"]
            if duration != 0:
                body += '\n{display_job_name} - Build ran _{build_time} ms_'.format(display_job_name=display_job_name, build_time=duration)
                break
        except e:
            logging.info(f"Build duration unknown:\n{e}")
        sleep(job_query_interval)
    else:
        logging.info("Error fetching build details")
        body += "\nError fetching build details"
        issue_comment(g, body)
        raise Exception("Error fetching build details")

    test_reports = build.get_test_report()
    if build.get_test_report() is None:
        body += "\n_No test were ran_"
    else:
        test_reports_json = test_reports.api_json()
        body += "\n\n## Test Results:\n**Passed: {p}**\n**Failed: {f}**\n**Skipped: {s}**".format(
            p=test_reports_json["passCount"],
            f=test_reports_json["failCount"],
            s=test_reports_json["skipCount"]
        )

#    try:
#        joke = requests.get('https://api.chucknorris.io/jokes/random', timeout=1).json()["value"]
#        body += f"\n\n>{joke}"
#    except e:
#        logging.info(f"API cannot be called:\n{e}")

    issue_comment(g, body)

    if result in ('FAILURE', 'ABORTED'):
        raise Exception(result)


def keepLogsMeta(build):
    return "<!--{data}-->".format(
        data=json.dumps({
            "id": "keepLogs",
            "metadata": [
                {
                    "build": {
                        "fullName": build.get_job().full_name,
                        "number": build.api_json()['number']
                    },
                    "enabled": True
                }
            ]
        })
    )


if __name__ == "__main__":
    main()
