import requests


class GithubGraphQl:
    def __init__(self, token):
        self.token = token

    def run_query(self, query):
        headers = {"Authorization": f"Bearer {self.token}"}

        request = requests.post('https://api.github.com/graphql', json={'query': query}, headers=headers)
        if request.status_code == 200:
            return request.json()
        else:
            raise Exception("Failed to run query. Return code: {}.\n{}".format(request.status_code, query))

    def get_pullRequest_id(self, owner, repository_name, pr_number):
        query = f"""
        {{
            repository(owner: "{owner}", name: "{repository_name}") {{
                pullRequest(number: {pr_number}) {{
                    id
                }}
            }}
        }}
        """
        return self.run_query(query)['data']['repository']['pullRequest']['id']

    def convert_to_draft(self, pull_request_id):
        query = f"""
        mutation {{
                convertPullRequestToDraft( input: {{pullRequestId: "{pull_request_id}" }} ) {{
                    pullRequest {{
                        number
                    }}
                }}
            }}
        """
        resp = self.run_query(query)
        if resp["data"]["convertPullRequestToDraft"]:
            return resp
        if (errors := resp.get("errors")):
            raise Exception(errors)
        raise Exception("Unknown Exception")
