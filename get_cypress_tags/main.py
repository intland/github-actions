#!/usr/bin/env python3

import requests
import logging
import os
from github import Github
from libs.utils import *

def main():
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    codebeamer_user = os.environ.get("INPUT_CODEBEAMER_USER")
    codebeamer_password = os.environ.get("INPUT_CODEBEAMER_PASSWORD")

    if not access_token:
        raise Exception("access_token parameters must be set")

    if codebeamer_user and codebeamer_password:
        auth = (codebeamer_user, codebeamer_password)
    else:
        raise Exception("codebeamer_user and codebeamer_password parameters must be set")
    
    g = Github(access_token)
    pr = getPullRequest(g)

    # Tags found in reference field
    tagList = getCypressTags(pr, auth)
    
    # Always required tags
    tags_all = "@cpViewsQG, @cpWorkItemsQG, @cpRegProjectReportingQG, @cpReviewHubQG, @cpTestManagementQG"
    
    # Add tags found in reference field
    for tag in tagList:
        if tag not in tags_all:
            tags_all += f', {tag}'
    
    print(tags_all)
    
    with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
        print(f'cypressTagList={tags_all}', file=fh)

def getCypressTags(pr, cbAuth):
    ids = collectIds(pr)
    tagList = []
    modules = getCustomFieldItems(ids[-1], cbAuth, "Test Automation Module")
    for module in modules:
        module_id = module["id"]
        tags = getCustomFieldItems(module_id, cbAuth, "Cypress tags")
        for tag in tags:
            tagList.append(tag["name"])
    return tagList

def getCustomFieldItems(id, cbAuth, fieldName):
    try:
        items = []
        getUrl = f"https://codebeamer.com/cb/api/v3/items/{id}"
        response = requests.get(url=getUrl, auth=cbAuth)
        print(response)
        if response.status_code == 200:
            for customField in response.json()["customFields"]:
                if customField["name"] == fieldName:
                    for item in customField["values"]:
                       items.append(item)
        return items

    except Exception as e:
        logging.warning(f"Custom field item information cannot be fetched from: {getUrl}", e)

if __name__ == "__main__":
    main()