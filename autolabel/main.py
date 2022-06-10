import os
from api4jenkins import Jenkins
from github import Github
import logging
import re
import json
import requests
from time import time, sleep

log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='JENKINS_ACTION: %(message)s', level=log_level)

def main():
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    codebeamer_user = os.environ.get("INPUT_CODEBEAMER_USER")
    codebeamer_password = os.environ.get("INPUT_CODEBEAMER_PASSWORD")
    
    if not (codebeamer_user and codebeamer_password):
        raise Exception("codebeamer_user and codebeamer_password parameters must be set")
        
    g = Github(access_token)
    
    pr = getPullRequest(g)
    teams = getTeams(g, (codebeamer_user, codebeamer_password))

    for l in teams:
        pr.add_to_labels(l)


def getPullRequest(githubApi):
    github_event_file = open(os.environ.get("GITHUB_EVENT_PATH"), "r")
    github_event = json.loads(github_event_file.read())
    github_event_file.close

    pr_repo_name = github_event["pull_request"]["base"]["repo"]["full_name"]
    pr_number = github_event["number"]

    return githubApi.get_repo(pr_repo_name).get_pull(pr_number)

def getTeams(pr, cbAuth):
    commits = pr.get_commits()
    
    ids = []
    ids.extend(getIds(pr.title))
    
    for c in pr.get_commits():
        ids.extend(getIds(c.commit.message))
    
    teams = []
    for i in set(ids):
        itemGetUrl = f"https://codebeamer.com/cb/api/v3/items/{i}"
        response = requests.get(url=itemGetUrl, auth=cbAuth)
        if response.status_code == 200:
            for t in response.json()["teams"]:
                teams.append(t["name"])
                
    return set(teams)
        
def getIds(text):
    return re.findall(r'#([\d]+)', text)

if __name__ == "__main__":
    main()