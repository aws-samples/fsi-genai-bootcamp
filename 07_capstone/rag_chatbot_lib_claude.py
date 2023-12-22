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



def get_llm():
        
    model_kwargs =  { 
        "max_tokens_to_sample": 8000, 
        "temperature": 0, 
    }
    
    '''
    llm = Bedrock(
        credentials_profile_name="default", #sets the profile name to use for AWS credentials (if not the default)
        region_name="us-east-1", #sets the region name (if not the default)
        #endpoint_url=os.environ.get("BWB_ENDPOINT_URL"), #sets the endpoint URL (if necessary)
        model_id="anthropic.claude-v2", #set the foundation model
        model_kwargs=model_kwargs) #configure the properties for Claude
    '''
    llm = Bedrock(
        credentials_profile_name=os.environ.get("BWB_PROFILE_NAME"), #sets the profile name to use for AWS credentials (if not the default)
        region_name=os.environ.get("BWB_REGION_NAME"), #sets the region name (if not the default)
        endpoint_url=os.environ.get("BWB_ENDPOINT_URL"), #sets the endpoint URL (if necessary)
        model_id="anthropic.claude-v2", #set the foundation model
        model_kwargs=model_kwargs) #configure the properties for Claude
    
    return llm



def get_index(file_name): #creates and returns an in-memory vector store to be used in the application
    
    embeddings = BedrockEmbeddings(
        credentials_profile_name=os.environ.get("BWB_PROFILE_NAME"), #sets the profile name to use for AWS credentials (if not the default)
        region_name=os.environ.get("BWB_REGION_NAME"), #sets the region name (if not the default)
        endpoint_url=os.environ.get("BWB_ENDPOINT_URL"), #sets the endpoint URL (if necessary)
    ) #create a Titan Embeddings client
    
    #pdf_path = '/Users/evikram/Documents/github/amazon-bedrock-workshop/fmr-anthropic-demo/index_docs' #assumes local PDF file with this name

    loader = PyPDFLoader(file_path=file_name) #load the pdf file

    #loader = [UnstructuredPDFLoader(os.path.join(pdf_path, fn)) for fn in os.listdir(pdf_path)]
    
    text_splitter = RecursiveCharacterTextSplitter( #create a text splitter
        separators=["\n\n", "\n", " ",""], #split chunks at (1) paragraph, (2) line, (3) sentence, or (4) word, in that order
        chunk_size=300, #divide into 1000-character chunks using the separators above
        chunk_overlap=10 #number of characters that can overlap with previous chunk
    )
    

    '''text_splitter = RecursiveCharacterTextSplitter(
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
    )'''
    
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



