import logging
import os

from github import Github

from libs.utils import *


log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='ACTION: %(message)s', level=log_level)


def main():
    status = os.environ.get("INPUT_STATUS")
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    codebeamer_user = os.environ.get("INPUT_CODEBEAMER_USER")
    codebeamer_password = os.environ.get("INPUT_CODEBEAMER_PASSWORD")

    if not (codebeamer_user and codebeamer_password):
        raise Exception("codebeamer_user and codebeamer_password parameters must be set")

    g = Github(access_token)
    pr = getPullRequest(g)
    if pr.draft:
        logging.debug("PR is in draft state, exiting.")
        return
    auth = (codebeamer_user, codebeamer_password)

    trackerItemIds = collectIds(pr)
    for trackerItemId in trackerItemIds:
        resolvedStatus = retry(getStatus, 30, 10)(trackerItemId, status, auth)
        if resolvedStatus:
            retry(updateStatus, 30, 10)(trackerItemId, resolvedStatus, auth)
        else:
            logging.warning(f"Status cannot be resolved for #{trackerItemId} item by '{status}'")


def updateStatus(tracker_item_id, status, auth):
    id = status["id"]
    name = status["name"]

    data = {
        "fieldValues": [{
            "fieldId": 7,
            "name": "Status",
            "type": "ChoiceFieldValue",
            "values": [{"id": id, "name": name, "type": "ChoiceOptionReference"}]
        }]}
    updateStatus = f"https://codebeamer.com/cb/api/v3/items/{tracker_item_id}/fields?quietMode=false"

    try:
        logging.info(f"Fetching information from: {updateStatus}")
        response = requests.put(url=updateStatus, auth=auth, headers={'accept': 'application/json', 'Content-Type': 'application/json'}, json=data)
        logging.info(f"Response: {response.text}")
        if response.status_code == 200:
            logging.warning(f"Ticket({id}) status has been changed to: {name}")

    except Exception as e:
        logging.warning(
            f"Ticket({id}) status cannot be changed to: {name}. Exception: {e}"
        )


def getStatus(id, status, auth):
    itemStatuses = f"https://codebeamer.com/cb/api/v3/items/{id}/fields/7/options?page=1&pageSize=100"
    logging.info(f"Fetching information from: {itemStatuses}")
    response = requests.get(url=itemStatuses, auth=auth, headers={'accept': 'application/json', 'Content-Type': 'application/json'})
    if response.status_code == 200:
        for reference in response.json()['references']:
            if (reference["name"] == status):
                return {"name": reference["name"], "id": reference["id"]}

    return None


if __name__ == "__main__":
    main()
