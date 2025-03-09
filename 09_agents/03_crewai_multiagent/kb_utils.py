import time

import boto3
import sagemaker

# get the current region and execution role
SAGEMAKER_SESSION = sagemaker.Session()
BOTO3_SESSION = boto3.Session()
REGION = SAGEMAKER_SESSION.boto_region_name
ROLE = sagemaker.get_execution_role()
ACCOUNT = ROLE.split(":")[4]
BUCKET = SAGEMAKER_SESSION.default_bucket()
DOCUMENT_PREFIX = "loan_underwriting_docs"

BEDROCK_AGENT_CLIENT = boto3.client("bedrock-agent")
KB_NAME = "loan-underwriting-kb"
INDEX_NAME = "loan-underwriting-index"
EMD_FIELD_NAME = "embedding"
TEXT_FIELD_NAME = "text"
METADATA_FIELD_NAME = "metadata"
KB_DESCRIPTION = "Loan underwriting knowledge base"

from opensearchpy import AWSV4SignerAuth, OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth


def upload_document(doc_path):
    s3_path = SAGEMAKER_SESSION.upload_data(
        path=doc_path, bucket=BUCKET, key_prefix=DOCUMENT_PREFIX
    )
    return s3_path


def get_collection_data():
    aoss_client = boto3.client("opensearchserverless")
    collections = aoss_client.list_collections(
        collectionFilters={"name": "bedrock-workshop-rag", "status": "ACTIVE"}
    )

    collection_details = collections["collectionSummaries"][0]
    collection_endpoint = f'{collection_details["id"]}.{REGION}.aoss.amazonaws.com'
    collection_arn = collection_details["arn"]

    return collection_endpoint, collection_arn


def get_opensearch_client(collection_endpoint):

    credentials = BOTO3_SESSION.get_credentials()
    awsauth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        BOTO3_SESSION.region_name,
        "aoss",
        session_token=credentials.token,
    )

    oss_client = OpenSearch(
        hosts=[{"host": collection_endpoint, "port": 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
    )

    return oss_client


def create_index(
    oss_client, index_name, embedding_field_name, text_field_name, metadata_field_name
):

    index_settings = {
        "settings": {"index": {"knn": True, "knn.algo_param.ef_search": 512}},
        "mappings": {
            "properties": {
                embedding_field_name: {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "name": "hnsw",
                        "engine": "faiss",
                        "space_type": "l2",
                        "parameters": {"m": 16, "ef_construction": 512},
                    },
                },
                text_field_name: {"type": "text"},
                metadata_field_name: {"type": "text"},
            }
        },
    }

    oss_client.indices.create(index=index_name, body=index_settings)


def create_kb(
    collection_arn,
    collection_endpoint,
):

    oss_client = get_opensearch_client(collection_endpoint)

    if not oss_client.indices.exists(INDEX_NAME):
        create_index(
            oss_client,
            INDEX_NAME,
            EMD_FIELD_NAME,
            TEXT_FIELD_NAME,
            METADATA_FIELD_NAME,
        )
        time.sleep(5)

    existing_kb = BEDROCK_AGENT_CLIENT.list_knowledge_bases()["knowledgeBaseSummaries"]

    for kb in existing_kb:
        if kb["name"] == KB_NAME:
            print("Knowledge base already exists.")
            return kb["knowledgeBaseId"]

    response = BEDROCK_AGENT_CLIENT.create_knowledge_base(
        description=KB_DESCRIPTION,
        knowledgeBaseConfiguration={
            "type": "VECTOR",
            "vectorKnowledgeBaseConfiguration": {
                "embeddingModelArn": f"arn:aws:bedrock:{REGION}::foundation-model/amazon.titan-embed-text-v2:0",
                "embeddingModelConfiguration": {
                    "bedrockEmbeddingModelConfiguration": {"dimensions": 1024}
                },
            },
        },
        name=KB_NAME,
        roleArn=ROLE,
        storageConfiguration={
            "opensearchServerlessConfiguration": {
                "collectionArn": collection_arn,
                "fieldMapping": {
                    "metadataField": METADATA_FIELD_NAME,
                    "textField": TEXT_FIELD_NAME,
                    "vectorField": EMD_FIELD_NAME,
                },
                "vectorIndexName": INDEX_NAME,
            },
            "type": "OPENSEARCH_SERVERLESS",
        },
    )

    kb_id = response["knowledgeBase"]["knowledgeBaseId"]

    kb_status = BEDROCK_AGENT_CLIENT.get_knowledge_base(knowledgeBaseId=kb_id)[
        "knowledgeBase"
    ]["status"]

    print("Knowledge base is being created. Waiting for completion.")

    while kb_status == "CREATING":
        time.sleep(2)
        kb_status = BEDROCK_AGENT_CLIENT.get_knowledge_base(knowledgeBaseId=kb_id)[
            "knowledgeBase"
        ]["status"]
    print("Knowledge base created successfully.")

    return kb_id


def create_data_source(kb_id):

    existing_data_sources = BEDROCK_AGENT_CLIENT.list_data_sources(
        knowledgeBaseId=kb_id
    )["dataSourceSummaries"]

    data_source_id = None
    for ds in existing_data_sources:
        if ds["name"] == "underwriting_docs":
            print("Data source already exists.")
            data_source_id = ds["dataSourceId"]

    if data_source_id is None:
        print("Creating data source.")
        data_source_response = BEDROCK_AGENT_CLIENT.create_data_source(
            dataSourceConfiguration={
                "s3Configuration": {
                    "bucketArn": f"arn:aws:s3:::{BUCKET}",
                    "bucketOwnerAccountId": ACCOUNT,
                    "inclusionPrefixes": [
                        DOCUMENT_PREFIX,
                    ],
                },
                "type": "S3",
            },
            description="underwriting docs",
            knowledgeBaseId=kb_id,
            name="underwriting_docs",
            vectorIngestionConfiguration={
                "chunkingConfiguration": {
                    "chunkingStrategy": "FIXED_SIZE",
                    "fixedSizeChunkingConfiguration": {
                        "maxTokens": 300,
                        "overlapPercentage": 20,
                    },
                },
            },
        )

        data_source_id = data_source_response["dataSource"]["dataSourceId"]

    print("Ingesting data into the knowledge base.")
    ingestion_job_response = BEDROCK_AGENT_CLIENT.start_ingestion_job(
        dataSourceId=data_source_id,
        knowledgeBaseId=kb_id,
    )

    ingestion_job_id = ingestion_job_response["ingestionJob"]["ingestionJobId"]

    ingestion_status = BEDROCK_AGENT_CLIENT.get_ingestion_job(
        ingestionJobId=ingestion_job_id,
        knowledgeBaseId=kb_id,
        dataSourceId=data_source_id,
    )["ingestionJob"]["status"]

    max_wait = 60
    while ingestion_status != "COMPLETE":
        time.sleep(10)
        ingestion_status = BEDROCK_AGENT_CLIENT.get_ingestion_job(
            ingestionJobId=ingestion_job_id,
            knowledgeBaseId=kb_id,
            dataSourceId=data_source_id,
        )["ingestionJob"]["status"]
        max_wait -= 10
        if max_wait <= 0:
            raise Exception("Ingestion job did not complete in time.")

    print("Data has been ingested successfully.")

    return data_source_id
