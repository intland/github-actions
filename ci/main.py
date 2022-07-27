import json
import logging
import os
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
    metadata_id = f"jenkins-{job_name}"

    if username and api_token:
        auth = (username, api_token)
    else:
        auth = None
        logging.info('Username or token not provided. Connecting without authentication.')

    g = Github(access_token)
    jenkins = Jenkins(url, auth=auth)

    pr = getPullRequest(g)
    if pr.draft and re.search('^merge_', pr.head.ref):
        return

    if 'NOTIFICATION_EMAIL' in parameters.keys():
        parameters['NOTIFICATION_EMAIL'] = ','.join(getPRAuthorEmails(pr))

    parameters = convertToJson(parameters)

    retry(connectToJenkins, 60, 10)(jenkins)

    logging.info('Start a build.')
    queue_item = retry(jenkins.build_job, 60, 10)(job_name, **parameters)
    build = retry(waitForBuild, start_timeout, interval)(queue_item)
    build_url = build.url
    logging.info(f"Build URL: {build_url}")

    if access_token:
        issue_comment(g, metadata_id, f'{display_job_name} - Build started [here]({build_url})', keepLogsMetadata(build))

    result = retry(wait_for_build, 60, 10)(build, timeout, interval)

    if not access_token:
        logging.info("No comment.")
        if result in ('FAILURE', 'ABORTED'):
            raise Exception(result)
        return

    retry(keep_logs, 60, 10)(build, auth)

    body = f'### [{display_job_name} - Build]({build_url}) status returned **{result}**.'

    try:
        duration = retry(waitForBuildExecution, job_query_timeout, job_query_interval)(build)
        body += '\n{display_job_name} - Build ran _{build_time}_'.format(display_job_name=display_job_name, build_time=convertMillisToHumanReadable(duration))
    except Exception as e:
        logging.info("Error fetching build details")
        body += "\nError fetching build details"
        issue_comment(g, metadata_id, body, keepLogsMetadata(build))
        raise Exception("Error fetching build details")

    issue_comment(g, metadata_id, f"{body}\n\n{buildResultMessage(build.get_test_report())}", keepLogsMetadata(build))

    if result in ('FAILURE', 'ABORTED'):
        raise Exception(result)


def convertToJson(parameters):
    if parameters:
        try:
            return json.loads(parameters)
        except json.JSONDecodeError as e:
            raise Exception('`parameters` is not valid JSON.') from e

    return {}


def buildResultMessage(test_reports):
    if test_reports is None:
        return "\n_No test were ran_"
    else:
        test_reports_json = test_reports.api_json()
        p = test_reports_json["passCount"]
        f = test_reports_json["failCount"]
        s = test_reports_json["skipCount"]
        return f"\n\n## Test Results:\n**Passed: {p}**\n**Failed: {f}**\n**Skipped: {s}**"


def keepLogsMetadata(build):
    fullName = build.get_job().full_name
    number = build.api_json()['number']
    return json.dumps([{"build": {"fullName": fullName, "number": number}, "enabled": True}])


def waitForBuildExecution(build):
    duration = build.api_json()["duration"]
    if not duration:
        raise Exception(f'Build has not finished yet. Waiting few seconds.')

    return duration


def waitForBuild(queue_item):
    build = queue_item.get_build()
    if not build:
        raise Exception(f'Build not started yet. Waiting few seconds.')

    logging.info(f'Build has been started.')
    return build


def connectToJenkins(jenkins):
    try:
        logging.info(f"Try to connect to jenkins")
        jenkins.version
        logging.info('Successfully connected to Jenkins.')
    except Exception as e:
        raise Exception('Could not connect to Jenkins.') from e


if __name__ == "__main__":
    main()
