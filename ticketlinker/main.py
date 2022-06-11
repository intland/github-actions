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
    codebeamer_tickets = getTickets(pr, (codebeamer_user, codebeamer_password))
    
    if codebeamer_tickets: 
        pr.create_issue_comment(buildComment(codebeamer_tickets))

def buildComment(codebeamer_tickets):
    if len(codebeamer_tickets) == 1:
        return f"**Ticket:** {buildLine(codebeamer_tickets[0])}"

    body = "**Tickets**\n"
    for t in codebeamer_tickets:
        body += f"- {buildLine(t)}\n"

    return body

def buildLine(t):
    body = f"[#{t.id}](https://codebeamer.com/cb/item/{t.id})"

    if t.title:
        body += f" - {t.title}"
    else:
        body += " - N/A"    
    
    if t.teams:
        body += f" - {', '.join(t.teams)}"

    return body


def getPullRequest(githubApi):
    github_event_file = open(os.environ.get("GITHUB_EVENT_PATH"), "r")
    github_event = json.loads(github_event_file.read())
    github_event_file.close

    pr_repo_name = github_event["pull_request"]["base"]["repo"]["full_name"]
    pr_number = github_event["number"]

    return githubApi.get_repo(pr_repo_name).get_pull(pr_number)

def getTickets(pr, cbAuth):
    ids = []
    ids.extend(getIds(pr.title))
    ids.extend(getIds(pr.body))
    
    for c in pr.get_commits():
        ids.extend(getIds(c.commit.message))
    
    tickets = []
    for i in set(ids):
        itemGetUrl = f"https://codebeamer.com/cb/api/v3/items/{i}"
        
        try:
            logging.info(f"Fetching information from: {itemGetUrl}")
            response = requests.get(url=itemGetUrl, auth=cbAuth)
            if response.status_code == 200:
                logging.info(f"Ticket is found")
                name = response.json()["name"]
                teams = list(map(lambda t: t["name"], response.json()["teams"]))
                tickets.append(CodebeamerTicket(i, name, teams))
            else:
                tickets.append(CodebeamerTicket(i, "", []))    

        except Exception as e:
             logging.warning(f"Ticket information cannot be fetched from: {itemGetUrl}", e)
             tickets.append(CodebeamerTicket(i, "", []))
    
    return sorted(list(set(tickets)))

def getIds(text):
    if text:
        return re.findall(r'#([\d]+)', text)
    else:
        return []

class CodebeamerTicket:
    def __init__(self, id, title, teams):
        self.id = id
        self.title = title
        self.teams = teams

    def __repr__(self):
        return f'CodebeamerTicket(id={self.id}, title={self.title}, teams={self.teams})'

    def __lt__(self, other):
        return self.id < other.id

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other): 
        if not isinstance(other, CodebeamerTicket):
            return NotImplemented

        return self.id == other.id

if __name__ == "__main__":
    main()
