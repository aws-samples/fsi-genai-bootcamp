import boto3
import time
import datetime
import json
import os
from pathlib import Path
from opensearchpy import RequestsHttpConnection, AWSV4SignerAuth


from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from typing import Any, Iterable, List
from langchain_core.retrievers import BaseRetriever

USER_IDENTITY = boto3.client("sts").get_caller_identity()["Arn"]
USER_ACCOUNT = boto3.client("sts").get_caller_identity()["Account"]

SAGEMAKER_NOTEBOOK_ROLE = (
    "arn:aws:iam::"
    + USER_ACCOUNT
    + ":role/aws-service-role/sagemaker.amazonaws.com/AWSServiceRoleForAmazonSageMakerNotebooks"
)

REGION = os.environ.get("AWS_DEFAULT_REGION", boto3.session.Session().region_name)

AOSS_CLIENT = boto3.client(
    "opensearchserverless"
)  # Create the Amazon OpenSearch Serverless client


def generate_resource_names() -> dict:

    time_stamp = datetime.datetime.now().strftime("%H-%M-%S")

    vector_store_name = f"bedrock-workshop-rag-{time_stamp}"
    index_name = f"bedrock-workshop-rag-index-{time_stamp}"
    encryption_policy_name = f"bedrock-workshop-rag-sp-{time_stamp}"
    network_policy_name = f"bedrock-workshop-rag-np-{time_stamp}"
    access_policy_name = f"bedrock-workshop-rag-ap-{time_stamp}"

    resource_names = dict(
        vector_store_name=vector_store_name,
        index_name=index_name,
        encryption_policy_name=encryption_policy_name,
        network_policy_name=network_policy_name,
        access_policy_name=access_policy_name,
    )

    return resource_names


def create_security_policy(encryption_policy_name: str, vector_store_name: str):

    print("Creating a security policy for AOSS collection..")
    security_policy = AOSS_CLIENT.create_security_policy(
        name=encryption_policy_name,
        policy=json.dumps(
            {
                "Rules": [
                    {
                        "Resource": ["collection/" + vector_store_name],
                        "ResourceType": "collection",
                    }
                ],
                "AWSOwnedKey": True,
            }
        ),
        type="encryption",
    )

    return security_policy


def create_network_policy(network_policy_name: str, vector_store_name: str):

    print("Creating a network policy for AOSS collection..")
    network_policy = AOSS_CLIENT.create_security_policy(
        name=network_policy_name,
        policy=json.dumps(
            [
                {
                    "Rules": [
                        {
                            "Resource": ["collection/" + vector_store_name],
                            "ResourceType": "collection",
                        }
                    ],
                    "AllowFromPublic": True,
                }
            ]
        ),
        type="network",
    )

    return network_policy


def create_collection(vector_store_name: str):

    print("Creating an AOSS collection..")
    collection = AOSS_CLIENT.create_collection(
        name=vector_store_name, type="VECTORSEARCH"
    )

    print("Waiting for an AOSS collection to be created..")
    while True:
        status = AOSS_CLIENT.list_collections(
            collectionFilters={"name": vector_store_name}
        )["collectionSummaries"][0]["status"]
        if status in ("ACTIVE", "FAILED"):
            break
        print(".")
        time.sleep(10)

    return collection


def create_access_policy(access_policy_name: str, vector_store_name: str):

    print("Creating an access policy for the AOSS collection..")
    access_policy = AOSS_CLIENT.create_access_policy(
        name=access_policy_name,
        policy=json.dumps(
            [
                {
                    "Rules": [
                        {
                            "Resource": ["collection/" + vector_store_name],
                            "Permission": [
                                "aoss:CreateCollectionItems",
                                "aoss:DeleteCollectionItems",
                                "aoss:UpdateCollectionItems",
                                "aoss:DescribeCollectionItems",
                            ],
                            "ResourceType": "collection",
                        },
                        {
                            "Resource": ["index/" + vector_store_name + "/*"],
                            "Permission": [
                                "aoss:CreateIndex",
                                "aoss:DeleteIndex",
                                "aoss:UpdateIndex",
                                "aoss:DescribeIndex",
                                "aoss:ReadDocument",
                                "aoss:WriteDocument",
                            ],
                            "ResourceType": "index",
                        },
                    ],
                    "Principal": [USER_IDENTITY, SAGEMAKER_NOTEBOOK_ROLE],
                    "Description": "Easy data policy",
                }
            ]
        ),
        type="data",
    )

    return access_policy


def create_oss_resources(config_file: str, replace: bool = False):
    config_path = Path(config_file)
    if config_path.exists() and not replace:
        print(f"Config file {config_file} already exists. Skipping..")

        config = json.loads(config_path.read_text())

        collection_id = config["collection"]["createCollectionDetail"]["id"]

        print(f"Reusing the existing AOSS resources with collection_id {collection_id}")
        print(
            "If you want to delete and recreate the resources, rerun the function with repalce=True"
        )

        host_name = collection_id + "." + REGION + ".aoss.amazonaws.com:443"

        return host_name, config

    elif config_path.exists() and replace:

        print("Deleting the existing AOSS resources and creating new ones")
        delete_oss_resources(config_file)
        return create_oss_resources(config_file)

    else:
        resource_names = generate_resource_names()
        vector_store_name = resource_names["vector_store_name"]
        index_name = resource_names["index_name"]
        encryption_policy_name = resource_names["encryption_policy_name"]
        network_policy_name = resource_names["network_policy_name"]
        access_policy_name = resource_names["access_policy_name"]

        security_policy = create_security_policy(
            encryption_policy_name, vector_store_name
        )
        network_policy = create_network_policy(network_policy_name, vector_store_name)
        collection = create_collection(vector_store_name)
        access_policy = create_access_policy(access_policy_name, vector_store_name)

        config = dict(
            collection=collection,
            encryption_policy_name=encryption_policy_name,
            network_policy_name=network_policy_name,
            access_policy_name=access_policy_name,
            index_name=index_name,
        )

        config_path.write_text(json.dumps(config, indent=4))

        host_name = (
            collection["createCollectionDetail"]["id"]
            + "."
            + REGION
            + ".aoss.amazonaws.com:443"
        )
        return host_name, config


def delete_oss_resources(config_file: str):
    config_path = Path(config_file)

    if not config_path.exists():
        raise FileNotFoundError(f"Config file {config_file} does not exist.")
    else:
        config = json.loads(config_path.read_text())
        collection = config["collection"]
        encryption_policy_name = config["encryption_policy_name"]
        network_policy_name = config["network_policy_name"]
        access_policy_name = config["access_policy_name"]

        print("Deleting the AOSS resources..")
        AOSS_CLIENT.delete_collection(id=collection["createCollectionDetail"]["id"])
        AOSS_CLIENT.delete_access_policy(name=access_policy_name, type="data")
        AOSS_CLIENT.delete_security_policy(
            name=encryption_policy_name, type="encryption"
        )
        AOSS_CLIENT.delete_security_policy(name=network_policy_name, type="network")

        config_path.unlink()

        print("Deleted the AOSS resources successfully.")


def get_aws_auth():
    service = "aoss"
    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, REGION, service)

    return auth


def get_host(collection_name: str):
    sess = boto3.session.Session()
    region = sess.region_name
    aoss_client = sess.client("opensearchserverless")
    collections = aoss_client.list_collections(
        collectionFilters={"name": collection_name, "status": "ACTIVE"}
    )

    collection_details = collections["collectionSummaries"][0]
    collection_endpoint = f'{collection_details["id"]}.{region}.aoss.amazonaws.com'

    return collection_endpoint


class OpenSearchBM25Retriever(BaseRetriever):
    client: Any
    index_name: str
    k: int = 10

    def _get_relevant_documents(
        self,
        query_text: str,
        k: int = None,
        pre_filters: List[dict] = [],
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> List[Document]:
        """
        Get relevant documents from the OpenSearch index using BM25.
        """
        if not k:
            k = self.k

        # Pre-filtering
        if pre_filters:
            query = {
                "query": {
                    "bool": {
                        "must": [{"match": {"text": query_text}}],
                        "filter": pre_filters,
                    }
                }
            }

        else:
            query = {"query": {"match": {"text": query_text}}}

        response = self.client.search(index=self.index_name, body=query, size=k)

        hits = response["hits"]["hits"]
        docs = []
        for hit in hits:
            doc = Document(
                page_content=hit["_source"]["text"], metadata=hit["_source"]["metadata"]
            )
            docs.append(doc)

        return docs
