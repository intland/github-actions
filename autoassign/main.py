import os
from github import Github
from github.GithubObject import NotSet
import logging
import re
import json
import requests

log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='ACTION: %(message)s', level=log_level)

def main():
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    codebeamer_user = os.environ.get("INPUT_CODEBEAMER_USER")
    codebeamer_password = os.environ.get("INPUT_CODEBEAMER_PASSWORD")
   
    if not access_token:
        raise Exception("access_token parameters must be set")
        
    if not (codebeamer_user and codebeamer_password):
        raise Exception("codebeamer_user and codebeamer_password parameters must be set")
    
    g = Github(access_token)
    pr = getPullRequest(g)
    codebeamer_teams = getTeams(pr, (codebeamer_user, codebeamer_password))
 
    github_teams = getOrganization(g).get_teams()
    github_teams_cache = convert(github_teams)
    
    reviewer_team_list = []
    for ct in codebeamer_teams:
        review_team_name = f"{ct} - Reviewers"
        if review_team_name in github_teams_cache:
            reviewer_team_list.append(github_teams_cache[review_team_name])
            
    # get_review_requests contains 2 list, first for user, second for teams
    for team_review_request in pr.get_review_requests()[1]:
        if team_review_request.slug in reviewer_team_list:
            reviewer_team_list.remove(team_review_request.slug)
    
    logging.info(f"Following teams are added to the PR asn reviewers: {reviewer_team_list}")
    
    if reviewer_team_list:
        logging.info("Create review request")
        pr.create_review_request(NotSet, reviewer_team_list)

def getOrganization(githubApi):
    return githubApi.get_organization("intland")

def getPullRequest(githubApi):
    github_event_file = open(os.environ.get("GITHUB_EVENT_PATH"), "r")
    github_event = json.loads(github_event_file.read())
    github_event_file.close

    pr_repo_name = github_event["pull_request"]["base"]["repo"]["full_name"]
    pr_number = github_event["number"]

    return githubApi.get_repo(pr_repo_name).get_pull(pr_number)

def getTeams(pr, cbAuth):    
    ids = []
    ids.extend(getIds(pr.title))
    ids.extend(getIds(pr.body))
    
    for c in pr.get_commits():
        ids.extend(getIds(c.commit.message))
    
    teams = []
    for i in set(ids):
        itemGetUrl = f"https://codebeamer.com/cb/api/v3/items/{i}"
        
        try:
            logging.info(f"Fetching information from: {itemGetUrl}")
            response = requests.get(url=itemGetUrl, auth=cbAuth)
            if response.status_code == 200:
                logging.info(f"Ticket is found")
                for t in response.json()["teams"]:
                    team = t["name"]
                    logging.info(f"'{team}' is added to teams")
                    teams.append(t["name"])
                    
        except Exception as e:
             logging.warning(f"Team information cannot be fetched from: {itemGetUrl}", e)
                
    return set(teams)

def convert(a):
    it_name = iter(map(lambda e: e.name, a))
    it_slug = iter(map(lambda e: e.slug, a))
    return dict(zip(it_name, it_slug))

def getIds(text):
    if text:
        return re.findall(r'#([\d]+)', text)
    else:
        return []

if __name__ == "__main__":
    main()
