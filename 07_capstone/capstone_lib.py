import os
from langchain.memory import ConversationBufferWindowMemory
from langchain.llms.bedrock import Bedrock
from langchain.chains import ConversationalRetrievalChain

from langchain.embeddings import BedrockEmbeddings
from langchain.indexes import VectorstoreIndexCreator
from langchain.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.document_loaders import PyPDFLoader
from langchain.document_loaders import UnstructuredPDFLoader
from langchain.text_splitter import CharacterTextSplitter

from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from langchain.vectorstores import OpenSearchVectorSearch

# from IPython.display import Markdown, display

import json
import os
import sys

import boto3
import botocore
sys.path.append("/home/sagemaker-user/fsi-genai-bootcamp/")

from utils import bedrock, print_ww

def get_client():


    #Since the Lab accounts provisioned for this workshop doesn't have access to Bedrock Models, the role "aws:iam::067564772063:role/Crossaccountbedrock" is added to inherit  Bedrock Model Access from the Parent Account which has access to Bedrock. If you running in your own account and you can follow through the bedrock "model management section" and can request access for the specific models.
    #os.environ["BEDROCK_ASSUME_ROLE"] = "arn:aws:iam::067564772063:role/Crossaccountbedrock"  # E.g. "arn:aws:..."


    boto3_bedrock = bedrock.get_bedrock_client(
        assumed_role=os.environ.get("BEDROCK_ASSUME_ROLE", None),
        region=os.environ.get("AWS_DEFAULT_REGION", None)
    )
    return boto3_bedrock


def get_llm():
        
    model_kwargs =  { 
        "max_tokens_to_sample": 8000, 
        "temperature": 0, 
    }
    llm = Bedrock(
    client=get_client(),
    model_id="anthropic.claude-instant-v1",
    model_kwargs={"max_tokens_to_sample": 500, "temperature": 0.9}
    )

    return llm

def process_documents():
    # Load all the PDFs from the data folder
    loader = PyPDFDirectoryLoader("fsi-genai-bootcamp/07_capstone/data")
    # Include loader from 2B
    documents = loader.load()
    # Include the Text splitter from 2C
    text_splitter = RecursiveCharacterTextSplitter(
    # Set a really small chunk size, just to show.
    chunk_size=2000,
    chunk_overlap=200,
    )
    
    split_docs = text_splitter.split_documents(documents)
    # Function returns text_splitter
    
    return documents, split_docs

# use this variable in the Vector Store creation
documents, split_docs = process_documents()

def create_oss_vector_index():
    
    documents, split_docs = process_documents()
    
    #change this if you need to use HuggingFaceEmebedding
    embeddings = BedrockEmbeddings(client=get_client(), model_id="amazon.titan-embed-text-v1")
    
    service = 'aoss'
    credentials = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(credentials, os.environ.get("AWS_DEFAULT_REGION", None), service)
    
    vector_store_1 = OpenSearchVectorSearch.from_documents(
    documents=docs, 
    embedding=embeddings, # Use 'embeddings' if using Jina AI or mpnet embeddings
    opensearch_url=host,
    http_auth=auth,
    timeout = 100,
    use_ssl = True,
    verify_certs = True,
    connection_class = RequestsHttpConnection,
    index_name=index_name,
    engine="nmslib", # Options are: “nmslib”, “faiss”, “lucene”; default: “nmslib”
    space_type="cosinesimil", # Options are: “l2”, “l1”, “cosinesimil”, “linf”, “innerproduct”; default: “l2”
    m=16,
    ef_construction=128,
    ef_search=128
    )

def get_index(file_name): #creates and returns an in-memory vector store to be used in the application
    
    
    embeddings = BedrockEmbeddings(client=get_client(), model_id="amazon.titan-embed-text-v1")
    
    loader = PyPDFLoader(file_path=file_name) #load the pdf file
    
    text_splitter = RecursiveCharacterTextSplitter( #create a text splitter
        separators=["\n\n", "\n", " ",""], #split chunks at (1) paragraph, (2) line, (3) sentence, or (4) word, in that order
        chunk_size=300, #divide into 1000-character chunks using the separators above
        chunk_overlap=10 #number of characters that can overlap with previous chunk
    )
    

    '''
    Experiment with different chunking strategies below
    text_splitter = RecursiveCharacterTextSplitter(
    # Set a really small chunk size, just to show.
    chunk_size = 500,
    chunk_overlap  = 20,
    length_function = len,
    is_separator_regex = False,
    )

    text_splitter = CharacterTextSplitter(        
    separator = "\n\n",
    chunk_size = 500,
    chunk_overlap  = 200,
    length_function = len,
    is_separator_regex = True,
    )
    '''
    
    index_creator = VectorstoreIndexCreator( #create a vector store factory
        vectorstore_cls=FAISS, #use an in-memory vector store for demo purposes
        embedding=embeddings, #use Titan embeddings
        text_splitter=text_splitter, #use the recursive text splitter
    )
    
    index_from_loader = index_creator.from_loaders([loader]) #create an vector store index from the loaded PDF
    
    return index_from_loader #return the index to be cached by the client app


def get_memory(): #create memory for this chat session
    
    memory = ConversationBufferWindowMemory(memory_key="chat_history", return_messages=True) #Maintains a history of previous messages
    
    return memory


def get_rag_chat_response(input_text, memory, index): #chat client function
    
    llm = get_llm()
    
    conversation_with_retrieval = ConversationalRetrievalChain.from_llm(llm, index.vectorstore.as_retriever(), memory=memory)
    
    input_text_updated = f"""Human: {input_text}
    Assistant:
    """
    chat_response = conversation_with_retrieval({"question": input_text_updated}) #pass the user message, history, and knowledge to the model
    
    return chat_response['answer']
