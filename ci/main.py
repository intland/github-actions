import json
import logging
import os
from api4jenkins import Jenkins
from github import Github
from libs.utils import *
import urllib.parse

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
    job_type_identifier = os.environ.get('INPUT_JOB_TYPE_IDENTIFIER')

    # Preset
    job_query_timeout = 600
    job_query_interval = 10
    metadata_id = f"jenkins-{job_name}"
    metadata_id += f"-{job_type_identifier}" if job_type_identifier else ""
    
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
    public_build_url =  jenkins.get_public_url(build.url)
    logging.info(f"Build URL: {public_build_url}")

    if access_token:
        issue_comment(g, metadata_id, f'{display_job_name} - Build started [here]({public_build_url})', jenkins.keep_logs_metadata(build))

    result = retry(wait_for_build, 28800, 120)(build, public_build_url, timeout, interval)

    if not access_token:
        logging.info("No comment.")
        if result in ('FAILURE', 'ABORTED'):
            raise Exception(result)
        return

    if keep_build_for_ever.lower() == 'true':
        try:
            pass # retry(keep_logs, 60, 10)(build, auth)
        except Exception as e:
            logging.warning(f"Cannot enable keep_this_build_forever parameter for this job: \n {e}")

    body = f'### [{display_job_name} - Build]({public_build_url}) status returned **{result}**.'

    try:
        duration = retry(waitForBuildExecution, job_query_timeout, job_query_interval)(build)
        body += '\n{display_job_name} - Build ran _{build_time}_'.format(display_job_name=display_job_name, build_time=convertMillisToHumanReadable(duration))
    except Exception as e:
        logging.info("Error fetching build details")
        body += "\nError fetching build details"
        issue_comment(g, metadata_id, body, jenkins.keep_logs_metadata(build))
        raise Exception("Error fetching build details")

    issue_comment(g, metadata_id, f"{body}\n\n{buildResultMessage(build.get_test_report(), public_build_url, result)}", jenkins.keep_logs_metadata(build))

    if result in ('FAILURE', 'ABORTED'):
        raise Exception(result)


def convertToJson(parameters):
    if parameters:
        try:
            return json.loads(parameters)
        except json.JSONDecodeError as e:
            raise Exception('`parameters` is not valid JSON.') from e

    return {}


def buildResultMessage(test_reports, build_url, result):
    if (result == "FAILURE" or result == "UNSTABLE") and test_reports is None:
        return "\n**Jenkins job FAILED, please check the run**"
    elif test_reports is None:
        return ""
    else:
        result = retry(get_failed_tests, 60, 10)(test_reports, build_url)
        failed_tests = result if result else ""

        test_reports_json = test_reports.api_json()
        p = test_reports_json["passCount"]
        f = test_reports_json["failCount"]
        s = test_reports_json["skipCount"]
        return f"\n\n## Test Results:\n**Passed: {p}**\n**Failed: {f}**\n{failed_tests}\n**Skipped: {s}**"


def waitForBuildExecution(build):
    duration = build.api_json()["duration"]
    if not duration:
        raise Exception(f'Build has not finished yet. Waiting few seconds.')

    return duration


def get_failed_tests(test_reports, build_url):
    failed_tests = ""
    try:
        for suite in test_reports.suites:
            for case in suite.cases:
                if(case.status == "FAILED" or case.status == "REGRESSION"):
                    splitted_class_name = case.class_name.split(".")
                    class_prefix = ".".join(splitted_class_name[0:-1])
                    class_name = splitted_class_name[-1]
                    path = urlencode(f"{class_prefix}/{class_name}/{case.name}")
                    link = f"{build_url}testReport/junit/{path}"
                    failed_tests += f"- [{case.class_name}.{case.name}]({link})\n"
        return failed_tests
    except Exception as e:
        logging.warning(f"Cannot get link for broken tests: \n {e}")   
        return failed_tests
    
def urlencode(url):
    # Specify the characters you want to remain unencoded (e.g., space, etc.)
      encoded_url = urllib.parse.quote(url, safe="[]()/:")
      # Replace [, ], (, and ) with _
      for char in "[]()":
          encoded_url = encoded_url.replace(char, "_")
      return encoded_url


if __name__ == "__main__":
    main()
