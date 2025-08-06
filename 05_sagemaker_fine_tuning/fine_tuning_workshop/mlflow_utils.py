import argparse
import json
import time
from pathlib import Path

import boto3
import botocore
import sagemaker

SM_CLIENT = boto3.client("sagemaker")
SAGEMAKER_SESSION = sagemaker.Session()
ROLE = sagemaker.get_execution_role()


def create_mlflow_tracking_server(tracking_server_name, mlflow_artifact_path, role):

    response = SM_CLIENT.create_mlflow_tracking_server(
        TrackingServerName=tracking_server_name,
        ArtifactStoreUri=mlflow_artifact_path,
        TrackingServerSize="Small",
        RoleArn=role,
        AutomaticModelRegistration=True,
    )

    return response


def check_server_status(tracking_server_name):

    mlflow_server_status = SM_CLIENT.describe_mlflow_tracking_server(
        TrackingServerName=tracking_server_name
    )

    return mlflow_server_status


def wait_for_ready_state(tracking_server_name):

    mlflow_server_status = check_server_status(tracking_server_name)

    while mlflow_server_status["TrackingServerStatus"] == "Creating":
        print("Waiting for MLflow server to be created")
        time.sleep(20)
        mlflow_server_status = check_server_status(tracking_server_name)


def create_presigned_url(tracking_server_name):

    response = SM_CLIENT.create_presigned_mlflow_tracking_server_url(
        TrackingServerName=tracking_server_name,
        ExpiresInSeconds=300,
        SessionExpirationDurationInSeconds=3600 * 8,
    )

    url = response["AuthorizedUrl"]

    return url


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--tracking-server-name", type=str, default="workshop-mlflow")

    args = parser.parse_args()
    tracking_server_name = args.tracking_server_name

    bucket = SAGEMAKER_SESSION.default_bucket()
    mlflow_artifact_path = f"s3://{bucket}/mlflow/{tracking_server_name}"

    try:
        create_server_resp = create_mlflow_tracking_server(
            tracking_server_name, mlflow_artifact_path, ROLE
        )

        tracking_server_arn = create_server_resp["TrackingServerArn"]
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "ValidationException":
            tracking_server_status = check_server_status(tracking_server_name)
            tracking_server_arn = tracking_server_status["TrackingServerArn"]
            status = tracking_server_status["TrackingServerStatus"]

            print(f"Server {tracking_server_name} already exists with status {status}")

    Path("mlflow_config.json").write_text(
        json.dumps(
            {
                "tracking_server_name": tracking_server_name,
                "tracking_server_arn": tracking_server_arn,
            }
        )
    )
