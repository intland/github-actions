import logging
import os

from github import Github

from libs.utils import *

log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='ACTION: %(message)s', level=log_level)


def main():
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    title = os.environ.get("INPUT_TITLE")
    head = os.environ.get("INPUT_HEAD")
    base = os.environ.get("INPUT_BASE")

    if not access_token:
        raise Exception("access_token parameters must be set")

    if not title:
        raise Exception("title parameters must be set")

    if not head:
        raise Exception("head parameters must be set")

    if not base:
        raise Exception("base parameters must be set")
    
    repositoryName = getGithubEvent()["repository"]["full_name"]
    logging.info(f"Repository: {repositoryName}")
        
    g = Github(access_token)
    repo = g.get_repo(repositoryName)
    
    logging.info(f"Create Pull request. Base: {base}, Head: {head}, Title: {title}")
    pr = repo.create_pull(title = title, body = "", head = head, base = base)
    
    print(pr.mergeable)
    t0 = time()
    while time() - t0 < 60 or pr.mergeable:
        print(pr.mergeable)
        sleep(10)
        
if __name__ == "__main__":
    main()
