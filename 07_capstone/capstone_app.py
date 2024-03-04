import streamlit as st #all streamlit commands will be available through the "st" alias
import rag_chatbot_lib_claude as glib #reference to local lib script
from pathlib import Path


st.set_page_config(page_title="Guidewire Demo") #HTML title
st.title("Anthropic Claude V2 100K model using Amazon Bedrock ") #page title


if 'memory' not in st.session_state: #see if the memory hasn't been created yet
    st.session_state.memory = glib.get_memory() #initialize the memory


if 'chat_history' not in st.session_state: #see if the chat history hasn't been created yet
    st.session_state.chat_history = [] #initialize the chat history


if 'vector_index' not in st.session_state: #see if the vector index hasn't been created yet

    #st.markdown("**Please fill the below form :**")
    with st.form(key="Form :", clear_on_submit = True):
        File = st.file_uploader(label = "Upload file", type=["pdf"])
        Submit = st.form_submit_button(label='Submit')
        
    if Submit :
        st.markdown("**The file is sucessfully Uploaded.**")
    
        # Save uploaded file to 'F:/tmp' folder.
        save_folder = Path.cwd()
        save_path = Path(save_folder, File.name)
        with open(save_path, mode='wb') as w:
            w.write(File.getvalue())
    
        if save_path.exists():
            st.success(f'File {File.name} is successfully saved!')
            with st.spinner("Indexing document..."): #show a spinner while the code in this with block runs
                st.session_state.vector_index = glib.get_index(File.name) #retrieve the index through the supporting library and store in the app's session cache


#Re-render the chat history (Streamlit re-runs this script, so need this to preserve previous chat messages)
for message in st.session_state.chat_history: #loop through the chat history
    with st.chat_message(message["role"]): #renders a chat line for the given role, containing everything in the with block
        st.markdown(message["text"]) #display the chat content


def add_user_message_to_session(prompt):
    if prompt:
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

input_text = st.chat_input("Chat with your bot here") #display a chat input box

if input_text: #run the code in this if block after the user submits a chat message
    
    with st.chat_message("user"): #display a user chat message
        st.markdown(input_text) #renders the user's latest message
    
    st.session_state.chat_history.append({"role":"user", "text":input_text}) #append the user's latest message to the chat history
    
    print(input_text)
    
    chat_response = glib.get_rag_chat_response(input_text=input_text, memory=st.session_state.memory, index=st.session_state.vector_index,) #call the model through the supporting library
    
    with st.chat_message("assistant"): #display a bot chat message
        st.markdown(chat_response) #display bot's latest response
    
    st.session_state.chat_history.append({"role":"assistant", "text":chat_response}) #append the bot's latest message to the chat history

