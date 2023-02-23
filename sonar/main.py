import json
import logging
import os
from github import Github
from libs.utils import *
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='SONAR_ACTION: %(message)s', level=log_level)
headers = {'User-Agent':'groovy-2.4.4', 'Accept':'application/json'}

# Some DevOps issue, using internal IP
DNS = {
  "https://sq.intland.de": "https://172.30.0.14"
}

def main():
    # Required
    original_url = os.environ["INPUT_URL"]
    url = DNS[original_url]
    api_token = os.environ.get("INPUT_API_TOKEN")
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    commit_sha = os.environ.get("INPUT_COMMIT_SHA")
    timeout = int(os.environ.get("INPUT_TIMEOUT"))
    interval = int(os.environ.get("INPUT_INTERVAL"))

    # Preset
    g = Github(access_token)
    message = getSonarStatusMessage(url, original_url, api_token, commit_sha, timeout, interval)
    if message:
        issue_comment(g, "sonar-report", "### Sonar Quality check result\n\n" + message, keepLogsMetadata(commit_sha))
    else:
        issue_comment(g, "sonar-report", "### Sonar Quality check result\n\nQUALITY GATE STATUS: PASSED", keepLogsMetadata(commit_sha))

    # Review comments based on Solar result
    logging.info(f'Creating comments on commit: {commit_sha}')
    retry(delete_review_comments, timeout, interval)(g, 'github-actions[bot]')

    mapping = get_component_path_mappings(get_pull_request_files(g))

    bugs        = retry(search_in_sonar_issues, timeout, interval)(url, api_token, mapping, commit_sha, 'BUG', 'MAJOR,CRITICAL,BLOCKER', 'true')
    code_smells = retry(search_in_sonar_issues, timeout, interval)(url, api_token, mapping, commit_sha, 'CODE_SMELL', 'CRITICAL,BLOCKER', 'true')
    issues      = bugs + code_smells

    retry(create_comments_from_issues, timeout, interval)(g, access_token, commit_sha, issues)

def getSonarStatusMessage(url, original_url, api_token, commit_sha, timeout, interval):
    message = ''
    for projectKey in getSonarProjects(url, api_token, timeout, interval):
        status = getProjectStatus(url, api_token, projectKey, commit_sha)
        if status == 'ERROR':
            dashboardUrl = f'{original_url}/dashboard?branch={commit_sha}&id={projectKey}'
            message += f'**{projectKey}**\n'
            message += f'QUALITY GATE STATUS: FAILED - View details on [dashboard]({dashboardUrl})\n\n'

    logging.info(f'Message: {message}')
    return message

def getProjectStatus(url, api_token, projectKey, branch):
    response = requests.get(f'{url}/api/qualitygates/project_status', params={'projectKey' : projectKey, 'branch' : branch}, auth=(api_token,''), headers=headers, verify=False)
    if response.status_code == 200:
        return response.json()['projectStatus']['status']
    elif response.status_code == 404:
        return 'N/A'
    else:
        raise Exception(f'Status cannot be checked for {projectKey}')

def getSonarProjects(url, api_token, timeout, interval):
    projects = []
    page = 1
    while(True):
        response = retry(search, timeout, interval)(url, page, api_token)
        if response.status_code == 200:
            components = response.json()["components"]
            if not components: 
                break

            for c in components:
                projects.append(c["key"])
        else:
            break

        page += 1 
    
    return projects

def search(url, page, api_token):
    return requests.get(f'{url}/api/projects/search', params={'p' : page}, auth=(api_token,''), headers=headers, verify=False)

def keepLogsMetadata(commit_sha):
    return json.dumps([{"build": {"commit_sha": commit_sha}, "enabled": True}])

def search_in_sonar_issues(url, api_token, mapping, branch, types, severities, is_new):
    logging.info(f"Getting issues with type: {types} and severities: {severities}")
    issues = []
    for component, path_prefix in mapping.items():
        project_issues = requests.get(
            f'{url}/api/issues/search',
            params={
                'componentKeys': component,
                'branch' : branch,
                'inNewCodePeriod': is_new,
                'types': types,
                'severities': severities
            },
            auth=(api_token,''),
            headers=headers,
            verify=False
        ).json()['issues']
        issues = issues + format_issues(project_issues, path_prefix)
    return issues

def get_component_path_mappings(files):
    mapping = {}
    for file in files:
        if '/src/' in file.filename:
            path_prefix = file.filename[:file.filename.index("src")]
            component   = path_prefix.split('/')[-2]
            if component not in mapping:
                mapping[component] = path_prefix
    return mapping

def create_comments_from_issues(github_api, access_token, commit_sha, issues):
    for issue in issues:
        content = format_content(list(DNS.keys())[0], issue)
        create_review_comment(
            github_api=github_api,
            auth=access_token,
            commit_sha=commit_sha,
            content=content,
            path=issue['file'],
            line=issue['endLine'],
            start_line=issue['startLine'] if issue['startLine'] != issue['endLine'] else None
        )

def format_issues(issues, path_prefix):
    formatted_issues = []
    for issue in issues:
        new_issue = {}
        new_issue['rule']         = issue['rule']
        new_issue['main_message'] = issue['message']
        new_issue['file']         = f"{path_prefix}{issue['component'].split(':')[-1]}"
        new_issue['startLine']    = issue['textRange']['startLine']
        new_issue['endLine']      = issue['textRange']['endLine']

        if issue['flows']:
            for flow in issue['flows']:
                for location in flow['locations']:
                    shallow_copy = new_issue.copy()
                    shallow_copy['startLine'] = location['textRange']['startLine']
                    shallow_copy['endLine'] = location['textRange']['endLine']
                    shallow_copy['sub_message'] = location['msg']
                    shallow_copy['file'] = f"{path_prefix}{location['component'].split(':')[-1]}"
                    formatted_issues.append(shallow_copy)
        else:
            formatted_issues.append(new_issue)
    return formatted_issues

def format_content(url, issue):
    content = f"<h3>{issue['main_message']}</h3><a href='{url}/coding_rules?open={issue['rule']}&rule_key={issue['rule']}'>Rule: {issue['rule']}</a>"
    if 'sub_message' in issue:
        content = content + f"<br/>{issue['sub_message']}"
    return content


if __name__ == "__main__":
    main()
