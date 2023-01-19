import json
import logging
import os
from github import Github
from libs.utils import *
import requests

log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='SONAR_ACTION: %(message)s', level=log_level)
headers = {'User-Agent':'groovy-2.4.4', 'Accept':'application/json'}

def main():
    # Required
    url = os.environ["INPUT_URL"]
    api_token = os.environ.get("INPUT_API_TOKEN")
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    commit_sha = os.environ.get("INPUT_COMMIT_SHA")
    timeout = int(os.environ.get("INPUT_TIMEOUT"))
    interval = int(os.environ.get("INPUT_INTERVAL"))

    # Preset
    g = Github(access_token)
    pr = getPullRequest(g)
    if re.search('^merge_', pr.head.ref):
        return

    issue_comment(g, "sonar-report", getSonarStatusMessage(url, api_token, commit_sha, timeout, interval), keepLogsMetadata(commit_sha))

def getSonarStatusMessage(url, api_token, commit_sha, timeout, interval):
    message = ''
    for projectKey in getSonarProjects(url, api_token, timeout, interval):
        status = getProjectStatus(url, api_token, projectKey, commit_sha)
        if status == 'ERROR':
            dashboardUrl = f'{url}/dashboard?branch={commit_sha}&id={projectKey}'
            message += f'*{projectKey}*\n'
            message += f'QUALITY GATE STATUS: FAILED - View details on {dashboardUrl}\n'

def getProjectStatus(url, api_token, projectKey, branch):
    response = requests.get(f'{url}/api/qualitygates/project_status', params={'projectKey' : projectKey, 'branch' : branch}, auth=(api_token,''), headers=headers)
    if response.status_code == 200:
        return response['projectStatus']['status']
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
    requests.get(f'{url}/api/projects/search', params={'p' : page}, auth=(api_token,''), headers=headers)

def keepLogsMetadata(commit_sha):
    return json.dumps([{"build": {"commit_sha": commit_sha}, "enabled": True}])

if __name__ == "__main__":
    main()
