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
    keep_build_for_ever = os.environ.get('INPUT_KEEP_BUILD', 'true')

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
    jenkins = JenkinsWrapper(url, auth=auth)

    pr = getPullRequest(g)
    if pr.draft and re.search('^merge_', pr.head.ref):
        return

    parameters = convertToJson(parameters)
    if 'NOTIFICATION_EMAIL' in parameters.keys():
        parameters['NOTIFICATION_EMAIL'] = ','.join(getPRAuthorEmails(pr.url, access_token))

    retry(jenkins.connect_to_jenkins, 60, 20)

    logging.info('Start a build.')
    queue_item = retry(jenkins.build_job, 60, 10)(job_name, parameters)
    build = retry(jenkins.wait_for_build, start_timeout, interval)(queue_item)
    build_url = build.url
    logging.info(f"Build URL: {build_url}")

    if access_token:
        issue_comment(g, metadata_id, f'{display_job_name} - Build started [here]({build_url})', jenkins.keep_logs_metadata(build))

    result = retry(wait_for_build, 60, 10)(build, timeout, interval)

    if not access_token:
        logging.info("No comment.")
        if result in ('FAILURE', 'ABORTED'):
            raise Exception(result)
        return

    if keep_build_for_ever.lower() == 'true':
        retry(keep_logs, 60, 10)(build, auth)

    body = f'### [{display_job_name} - Build]({build_url}) status returned **{result}**.'

    try:
        duration = retry(waitForBuildExecution, job_query_timeout, job_query_interval)(build)
        body += '\n{display_job_name} - Build ran _{build_time}_'.format(display_job_name=display_job_name, build_time=convertMillisToHumanReadable(duration))
    except Exception as e:
        logging.info("Error fetching build details")
        body += "\nError fetching build details"
        issue_comment(g, metadata_id, body, jenkins.keep_logs_metadata(build))
        raise Exception("Error fetching build details")

    issue_comment(g, metadata_id, f"{body}\n\n{buildResultMessage(build.get_test_report())}", jenkins.keep_logs_metadata(build))

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


def waitForBuildExecution(build):
    duration = build.api_json()["duration"]
    if not duration:
        raise Exception(f'Build has not finished yet. Waiting few seconds.')

    return duration


if __name__ == "__main__":
    main()
