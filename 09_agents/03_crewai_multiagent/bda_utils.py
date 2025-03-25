import base64
import json
import tempfile
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import boto3
import botocore
import botocore.exceptions

BDA_CLIENT = boto3.client("bedrock-data-automation")
BDA_RUNTIME = boto3.client("bedrock-data-automation-runtime")
S3_CLIENT = boto3.client("s3")
REGION = boto3.session.Session().region_name
ACCOUNT_ID = boto3.client("sts").get_caller_identity().get("Account")


def get_bda_project_arn(project_name: str) -> Optional[str]:
    response = BDA_CLIENT.list_data_automation_projects(projectStageFilter="LIVE")
    projects = response["projects"]

    project_arn = None
    for project in projects:
        if project["projectName"] == project_name:
            project_arn = project["projectArn"]
            break

    return project_arn


# def create_bda_project(project_name: str, project_description: str):

#     try:
#         response = BDA_CLIENT.create_data_automation_project(
#             projectName=project_name,
#             projectDescription=project_description,
#             standardOutputConfiguration={
#                 "audio": {
#                     "extraction": {
#                         "category": {"state": "ENABLED", "types": ["TRANSCRIPT"]}
#                     },
#                     "generativeField": {"state": "DISABLED", "types": []},
#                 },
#                 "video": {
#                     "extraction": {
#                         "category": {"state": "ENABLED", "types": ["TEXT_DETECTION"]},
#                         "boundingBox": {"state": "ENABLED"},
#                     },
#                     "generativeField": {
#                         "state": "ENABLED",
#                         "types": ["VIDEO_SUMMARY", "SCENE_SUMMARY"],
#                     },
#                 },
#                 "image": {
#                     "extraction": {
#                         "category": {"state": "ENABLED", "types": ["TEXT_DETECTION"]},
#                         "boundingBox": {"state": "ENABLED"},
#                     },
#                     "generativeField": {"state": "ENABLED", "types": ["IMAGE_SUMMARY"]},
#                 },
#                 "document": {
#                     "extraction": {
#                         "granularity": {"types": ["PAGE", "ELEMENT"]},
#                         "boundingBox": {"state": "DISABLED"},
#                     },
#                     "generativeField": {"state": "DISABLED"},
#                     "outputFormat": {
#                         "textFormat": {"types": ["MARKDOWN", "HTML"]},
#                         "additionalFileFormat": {"state": "DISABLED"},
#                     },
#                 },
#             },
#             customOutputConfiguration={"blueprints": []},
#         )
#     except botocore.exceptions.ClientError as e:
#         if e.response["Error"]["Code"] == "ConflictException":
#             print("Using existing Data Automation project")
#             return get_bda_project_arn(project_name)
#         else:
#             raise e

#     project_arn = response["projectArn"]
#     creation_status = response["status"]

#     max_wait_time = 60
#     while creation_status == "IN_PROGRESS":
#         creation_status = BDA_CLIENT.get_data_automation_project(
#             projectArn=project_arn
#         )["project"]["status"]

#         print(f"Project creation status: {creation_status}")
#         time.sleep(5)
#         max_wait_time -= 5

#         if max_wait_time <= 0:
#             raise TimeoutError("Project creation took too long")

#     if creation_status == "COMPLETED":
#         return project_arn
#     else:
#         raise Exception(f"Project creation failed with status: {creation_status}")


def upload_file_to_s3(file_path: Union[str, Path], bucket: str, prefix: str):
    file_path = Path(file_path)

    s3_key = f"{prefix}/{file_path.name}"
    S3_CLIENT.upload_file(str(file_path), bucket, s3_key)

    return f"s3://{bucket}/{s3_key}"


def process_bda(
    local_file_path: Union[str, Path],
    s3_bucket: str,
    s3_input_prefix: str,
    s3_output_prefix: str,
    max_wait_time: int = 120,
):

    # data_automation_project_arn = create_bda_project(
    #     project_name="doc_processing_project",
    #     project_description="Project for processing documents",
    # )
    response = BDA_CLIENT.list_data_automation_projects(
    maxResults=3,
    projectStageFilter='LIVE')
    data_automation_project_arn = [project['projectArn'] for project in response['projects'] if project['projectName'] == 'doc_processing_project']

    input_file_s3_uri = upload_file_to_s3(local_file_path, s3_bucket, s3_input_prefix)
    output_s3_uri = f"s3://{s3_bucket}/{s3_output_prefix}"

    response = BDA_RUNTIME.invoke_data_automation_async(
        inputConfiguration={"s3Uri": input_file_s3_uri},
        outputConfiguration={"s3Uri": output_s3_uri},
        dataAutomationConfiguration={
            "dataAutomationProjectArn": data_automation_project_arn,
        },
        dataAutomationProfileArn=f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:data-automation-profile/us.data-automation-v1",
    )

    job_status = BDA_RUNTIME.get_data_automation_status(
        invocationArn=response["invocationArn"]
    )

    while job_status["status"] == "InProgress":
        job_status = BDA_RUNTIME.get_data_automation_status(
            invocationArn=response["invocationArn"]
        )
        print(f"Processing file {local_file_path}; Job status: {job_status['status']}")
        time.sleep(5)
        max_wait_time -= 5
        if max_wait_time <= 0:
            raise TimeoutError("Job took too long")

    if job_status["status"] == "Success":
        with tempfile.TemporaryDirectory() as tmpdirname:
            job_metadata_path = job_status["outputConfiguration"]["s3Uri"]
            bucket, key = job_metadata_path.split("s3://")[1].split("/", 1)
            S3_CLIENT.download_file(bucket, key, f"{tmpdirname}/job_metadata.json")

            with open(f"{tmpdirname}/job_metadata.json", "r") as f:
                job_metadata = json.load(f)
                job_result_path = job_metadata["output_metadata"][0][
                    "segment_metadata"
                ][0]["standard_output_path"]
                bucket, key = job_result_path.split("s3://")[1].split("/", 1)

                S3_CLIENT.download_file(bucket, key, f"{tmpdirname}/job_result.json")
                with open(f"{tmpdirname}/job_result.json", "r") as f:
                    job_result = json.load(f)
                    return job_result
    else:
        raise Exception(f"Job failed with status: {job_status['status']}")
