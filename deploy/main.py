from typing import List
import json
import logging
import os
from dataclasses import dataclass
from api4jenkins import Jenkins
from github import Github
from libs.utils import issue_comment


logging.basicConfig(format='JENKINS_ACTION: %(message)s', level='INFO')


ECSCB_APP_PREFIX = 'ecs/apps/'
ECSCB_CLIENT_PREFIX = 'ecs/single/applications/'
TERRAFORM_PREFIX = 'terraform/'


@dataclass
class Deployment:
    resource_name: str
    resource_kind: str
    operation: str


def main(git_hub, jenkins, changes):
    for deployment in collect_deployments(changes):
        start_build(
            git_hub,
            jenkins,
            deployment.resource_name,
            deployment.resource_kind,
            deployment.operation == 'DELETE'
        )


def collect_deployments(changes) -> List[Deployment]:
    result = dict()

    for change in changes['CreateOrUpdate']:
        resource_name = determine_resource_name(change)

        if resource_name and resource_name not in result:
            deployment = Deployment(
                resource_name,
                determine_resource_kind(change),
                determine_operation(change, False)
            )
            result[resource_name] = deployment

    for change in changes['Remove']:
        resource_name = determine_resource_name(change)
        operation = determine_operation(change, True)

        if resource_name and resource_name not in result or operation == 'DELETE':
            deployment = Deployment(
                resource_name,
                determine_resource_kind(change),
                operation
            )
            result[resource_name] = deployment

    return list(result.values())


def determine_resource_name(change) -> str:
    result = ''

    if change.startswith(ECSCB_APP_PREFIX):
        result = change.removeprefix(ECSCB_APP_PREFIX).split('/')[0]
    elif change.startswith(ECSCB_CLIENT_PREFIX):
        result = change.removeprefix(ECSCB_CLIENT_PREFIX).split('/')[0]
    elif change.startswith(TERRAFORM_PREFIX):
        result = change.removeprefix(TERRAFORM_PREFIX).split('/')[1]
    
    return result


def determine_resource_kind(change) -> str:
    # It's an APP resource kind if and only if its path starts with
    # ecs/apps/ or terraform/etc/
    # It's a CLIENT resource kind if and only if its path starts with
    # ecs/single/applications/ or terraform/clients/
    
    return 'APP' if change.startswith('ecs/apps/') or change.startswith('terraform/etc/') else 'CLIENT'


def determine_operation(change, deleted) -> str:
    # It's a delete operation if and only if 
    #  * it's a change in ecs/apps/** and the app.yaml was deleted
    #  * it's a change in ecs/single/applications/** and the client.yaml was deleted
    #  * it's a change in terraform/** and the main.tf was deleted

    return 'DELETE' if (
        (
            change.startswith(ECSCB_APP_PREFIX) and change.endswith('/app.yaml') and deleted
        ) or (
            change.startswith(ECSCB_CLIENT_PREFIX) and change.endswith('/client.yaml') and deleted
        ) or (
            change.startswith(TERRAFORM_PREFIX) and change.endswith('/main.tf') and deleted
        )
    ) else 'CREATE_OR_UPDATE'


def start_build(git_hub, jenkins, resource_name, resource_kind, delete):
    job = jenkins.get_job('auto-deployment')
    queue_item = job.build(**dict(
        RESOURCE_NAME=resource_name,
        RESOURCE_KIND=resource_kind,
        DELETE=delete,
        DRY_RUN=False
    ))
    build = queue_item.get_build()
    url = build.url
    issue_comment(git_hub, 'auto-deployment-start', f"Link to the deployment build: {url}")


if __name__ == '__main__':
    access_token = os.environ.get('INPUT_ACCESS_TOKEN')
    git_hub = Github(access_token)

    username = os.environ.get('INPUT_USERNAME')
    api_token = os.environ.get('INPUT_API_TOKEN')
    jenkins = Jenkins('https://ci.intland.de', auth=(username, api_token))

    changes = json.loads(os.environ.get('INPUT_CHANGES'))

    main(git_hub, jenkins, changes)
