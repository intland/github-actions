from api4jenkins import Jenkins
from requests.auth import HTTPBasicAuth
from github import Github
from libs.utils import *
import json
import logging
import requests
import os
import zipfile
import hashlib
import uuid
import shutil

output_file = os.environ.get('GITHUB_OUTPUT')
log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='JENKINS_ACTION: %(message)s', level=log_level)

timeout = 600
interval = 10

meta_data_id = 'pmd-violation'

def main():

    # Required
    url = os.environ["INPUT_URL"]
    job_name = os.environ["INPUT_JOB_NAME"]
    build_number = os.environ["INPUT_BUILD_NUMBER"]
    username = os.environ.get("INPUT_USERNAME")
    api_token = os.environ.get("INPUT_API_TOKEN")
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")
    commit_sha = os.environ.get("INPUT_COMMIT_SHA")

    # Optional
    display_job_name = os.environ.get("INPUT_DISPLAY_JOB_NAME")
    job_type_identifier = os.environ.get('INPUT_JOB_TYPE_IDENTIFIER')

    g = Github(access_token)

    # Preset
    metadata_id = f"jenkins-{job_name}"
    metadata_id += f"-{job_type_identifier}" if job_type_identifier else ""
    
    if username and api_token:
        auth = (username, api_token)
    else:
        auth = None
        logging.info('Username or token not provided. Connecting without authentication.')

    jenkins = JenkinsWrapper(url, auth=auth)
    retry(jenkins.connect_to_jenkins, 60, 20)

    artifact = jenkins.get_artifact(job_name, build_number, "pmd.zip")
    artifact.save(artifact.name)
    
    extract_directory = str(uuid.uuid4())
    deleteDir(extract_directory)

    try:
        os.makedirs(extract_directory, exist_ok=True)
        unzip_jenkins_artifact(artifact.name, extract_directory)

        violations = find_and_process_violations(extract_directory)
        logging.info(f'{violations}')

        review_comment_cache = get_review_comment_cache(g)
        violation_cache = get_violation_cache(violations)

        obsolite_review_comments = get_obsolite_review_comments(review_comment_cache, violation_cache)
        logging.info(f'{obsolite_review_comments}')

        new_violations = get_new_violations(review_comment_cache, violation_cache)
        logging.info(f'{new_violations}')

        ## any_comment_submitted = create_comments_from_issues(g, access_token, commit_sha, new_violations) # retry(create_comments_from_issues, timeout, interval)(g, access_token, commit_sha, new_violations)
        ## if any_comment_submitted:
        ##    issue_comment(g, "pmd-report", "### PMD Quality check\n\n FAILED", keepLogsMetadata(commit_sha))
        ##else:
        ##    issue_comment(g, "pmd-report", "### PMD Quality check\n\n PASSED", keepLogsMetadata(commit_sha))
    finally:
        deleteDir(extract_directory)

def get_new_violations(review_comment_cache, violation_cache):
    review_comment_keys = set(review_comment_cache.keys())
    violation_keys = set(violation_cache.keys())

    return [violation_cache[key] for key in violation_keys - review_comment_keys]

def get_obsolite_review_comments(review_comment_cache, violation_cache):
    review_comment_keys = set(review_comment_cache.keys())
    violation_keys = set(violation_cache.keys())

    return [review_comment_cache[key] for key in review_comment_keys - violation_keys]

def get_violation_cache(violations):
    violation_cache_map = {}
    for violation in violations:
        violation_cache_map[violation.md5Hash] = violation
    
    return violation_cache_map

def get_review_comment_cache(g):
    review_comments = retry(get_review_comments, timeout, interval)(g, 'github-actions[bot]', meta_data_id)

    review_comment_map = {}
    for review_comment in review_comments:
        logging.info(f'review_comment: {review_comment}')
        metadata = loadMetadata(meta_data_id, review_comment)
        logging.info(f'metadata: {metadata.md5Hash}')
        if metadata and metadata.md5Hash:
            review_comment_map[metadata.md5Hash] = review_comment
    
    logging.info(f'review_comment_map: {review_comment_map}')
    return review_comment_map

def deleteDir(directory_to_delete):
    try:
        shutil.rmtree(directory_to_delete)
        print(f"Directory '{directory_to_delete}' and its contents deleted.")
    except FileNotFoundError:
        print(f"Error: Directory '{directory_to_delete}' not found.")
    except OSError as e:
        print(f"Error deleting '{directory_to_delete}': {e}")

def keepLogsMetadata(commit_sha):
    return json.dumps([{"build": {"commit_sha": commit_sha}}])

def create_comments_from_issues(github_api, access_token, commit_sha, violations):
    logging.info(f'Number of violations: {len(violations)}')

    pr = getPullRequest(github_api)

    number_of_comments = 0
    for violation in violations:
        content = violation.format_content()
        #retry(create_review_comment, timeout, interval)
        is_successful = create_review_comment(
            pr_url=pr.url,
            auth=access_token,
            commit_sha=commit_sha,
            content=content,
            path=violation.file,
            line=violation.lineNumber,
            start_line=None
        )
        if is_successful:
            number_of_comments += 1
        else:
            logging.info(f'Violation: {content}')

    return number_of_comments > 0

class Violation:
    def __init__(self, message, file, severity, category, lineNumber):
        self.message = message
        self.file = file
        self.severity = severity
        self.category = category
        self.lineNumber = lineNumber
        self.md5Hash = self._compute_md5_hash()

    def _compute_md5_hash(self):
        combined_string = f"{self.message}{self.file}{self.severity}{self.category}{self.lineNumber}"
        encoded_string = combined_string.encode('utf-8')
        return hashlib.md5(encoded_string).hexdigest()

    def __eq__(self, other):
        if isinstance(other, Violation):
            return self.md5Hash == other.md5Hash and self.md5Hash == other.md5Hash
        return NotImplemented

    def __repr__(self):
        return (f"Violation(severity='{self.severity}', category='{self.category}', file='{self.file}', lineNumber={self.lineNumber}, message='{self.message[:50]}...')")

    def format_content(self):
        metadata = createMetadata(meta_data_id, json.dumps({"md5Hash": self.md5Hash}))
        return f"""**{self.severity} - {self.category}**

**Details:**
{self.message}
""" + "\n" + metadata

def process_violation_file(file_path):
    violations = []
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    if all(key in item for key in ["message", "file", "severity", "category", "lineNumber"]):
                        violation = Violation(
                            item["message"],
                            item["file"],
                            item["severity"],
                            item["category"],
                            item["lineNumber"]
                        )
                        violations.append(violation)
                    else:
                        print(f"Warning: Incomplete violation data found in '{file_path}': {item}")
            else:
                print(f"Warning: Expected a list in '{file_path}', found: {type(data)}")
    except FileNotFoundError:
        print(f"Error: File not found at '{file_path}'")
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON in '{file_path}'")
    except Exception as e:
        print(f"An unexpected error occurred while processing '{file_path}': {e}")
    return violations

def unzip_jenkins_artifact(zip_file_path, extract_path="."):
    try:
    
        print(f"Successfully downloaded artifact to: {zip_file_path}")

        try:
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            print(f"Successfully extracted '{zip_file_path}' to '{extract_path}'")
            os.remove(zip_file_path)
        except zipfile.BadZipFile:
            print(f"Error: '{zip_file_path}' is not a valid ZIP file.")
            os.remove(zip_file_path) if os.path.exists(zip_file_path) else None
            return False
        except Exception as e:
            print(f"An error occurred during unzipping: {e}")
            os.remove(zip_file_path) if os.path.exists(zip_file_path) else None
            return False

    except requests.exceptions.RequestException as e:
        print(f"Error downloading artifact: {e}")
        return False

def find_and_process_violations(root_dir):
    all_violations = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename == "violations.json":
                file_path = os.path.join(dirpath, filename)
                violations = process_violation_file(file_path)
                all_violations.extend(violations)
    return all_violations

if __name__ == "__main__":
    main()
