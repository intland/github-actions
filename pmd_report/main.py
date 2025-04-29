from api4jenkins import Jenkins
from requests.auth import HTTPBasicAuth
from github import Github
from libs.utils import *
import json
import logging
import requests
import os
import zipfile

output_file = os.environ.get('GITHUB_OUTPUT')
log_level = os.environ.get('INPUT_LOG_LEVEL', 'INFO')
logging.basicConfig(format='JENKINS_ACTION: %(message)s', level=log_level)

def main():
    extract_directory = "extracted_pmd"

    # Required
    url = os.environ["INPUT_URL"]
    job_name = os.environ["INPUT_JOB_NAME"]
    build_number = os.environ["INPUT_BUILD_NUMBER"]
    username = os.environ.get("INPUT_USERNAME")
    api_token = os.environ.get("INPUT_API_TOKEN")
    access_token = os.environ.get("INPUT_ACCESS_TOKEN")

    # Optional
    display_job_name = os.environ.get("INPUT_DISPLAY_JOB_NAME")
    job_type_identifier = os.environ.get('INPUT_JOB_TYPE_IDENTIFIER')

    # Preset
    job_query_timeout = 600
    job_query_interval = 10
    metadata_id = f"jenkins-{job_name}"
    metadata_id += f"-{job_type_identifier}" if job_type_identifier else ""
    
    if username and api_token:
        auth = (username, api_token)
    else:
        auth = None
        logging.info('Username or token not provided. Connecting without authentication.')

    jenkins = JenkinsWrapper(url, auth=auth)
    retry(jenkins.connect_to_jenkins, 60, 20)

    job = jenkins.get_job(job_name)
    build = job.get_build(build_number)

    artifact = find_artifact(build, "pmd.zip")
    artifact.save(artifact.name)
    
    os.makedirs(extract_directory, exist_ok=True)
    unzip_jenkins_artifact(artifact.name, extract_directory)
    all_violations = find_and_process_violations(extract_directory)
    if all_violations:
        logging.info(f"\nFound and processed {len(all_violations)} violations:")
        for violation in all_violations:
            logging.info(violation)

class Violation:
    def __init__(self, message, file, severity, category, lineNumber):
        self.message = message
        self.file = file
        self.severity = severity
        self.category = category
        self.lineNumber = lineNumber

    def __repr__(self):
        return (f"Violation(severity='{self.severity}', category='{self.category}', file='{self.file}', lineNumber={self.lineNumber}, message='{self.message[:50]}...')")

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

def find_artifact(build, name):
    artifacts = build.get_artifacts()
    for artifact in artifacts:
        if artifact.name == name:
            artifact.url = artifact.url.replace("jenkins/jenkins", "jenkins")
            return artifact

if __name__ == "__main__":
    main()
