from dotenv.main import load_dotenv
from functools import partial
from pathlib import Path
from langchain.agents import AgentType
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain.memory import ConversationBufferWindowMemory
from langchain_community.callbacks.streamlit import StreamlitCallbackHandler
from langchain_community.chat_models import ChatOpenAI
import streamlit as st
import pandas as pd
import xxhash
import os
import uuid
import base64
import io


def get_button_label(chat_df, chat_id):
    first_message = chat_df[(chat_df["chat_id"] == chat_id) & (chat_df["role"] == "user")]

    if first_message.empty:
        return None
    
    msg_words = base64.b64decode(first_message.iloc[0]['content']).decode("ascii").split()
    if len(msg_words) < 5:
        return f"{' '.join(msg_words)} ..."
    else:
        return f"{' '.join(msg_words[:5])}..."


@st.dialog("Upload a new file")
def upload_new_file(previous_files:pd.DataFrame):
    st.write("Upload the document to explore")
    uploaded_file = st.file_uploader(label="Choose a file", type="xlsx")
    if uploaded_file is not None:

        try:
            pd.read_excel(io.BytesIO(uploaded_file.getvalue()))
        except Exception as e:
            print(e)
            st.write("The file can't be processed.")   
            if st.button("Close"):
                st.rerun()
        
        x = xxhash.xxh3_128()
        for chunk in iter(partial(uploaded_file.read, 32), b''):
            x.update(chunk)
        print(x.hexdigest())

        if (previous_files['file_hash'] == x.hexdigest()).any():
            st.write("The file has been uploaded before")   
            if st.button("Close"):
                st.rerun()
        else:
            if st.button("Submit"):
                st.session_state.current_file = x.hexdigest()
                st.session_state.current_file_name = uploaded_file.name

                previous_files = pd.concat(
                    [
                        previous_files,
                        pd.DataFrame(
                            {
                                "file_hash": [x.hexdigest()],
                                "file_name": [uploaded_file.name],
                            }
                        )
                    ], ignore_index=True 
                )
                previous_files.to_csv(UPLOADED_FILES_LOG)

                save_path = Path(SAVE_FOLDER, uploaded_file.name)

                with open(save_path, mode='wb') as w:
                    w.write(uploaded_file.getvalue())
            
                st.rerun()
    else:
        if st.button("Close"):
            st.rerun()


# ----- Initialization ---------
load_dotenv()

SAVE_FOLDER = './artifacts/'

UPLOADED_FILES_LOG='uploaded_files.csv'
try:
    uploaded_files_df = pd.read_csv(UPLOADED_FILES_LOG)
except FileNotFoundError:
    uploaded_files_df = pd.DataFrame(columns=["file_hash", "file_name"])

CSV_FILE = "chat_history.csv"
try:
    chat_history_df = pd.read_csv(CSV_FILE)
except FileNotFoundError:
    chat_history_df = pd.DataFrame(columns=["chat_id", "file_hash", "role", "content"])


with st.sidebar:
    st.title("Spreadsheet personal helper")
    st.write("Build using Open AI Models")
    st.divider()

    if st.button("Upload file"):
        uploaded_file = upload_new_file(uploaded_files_df)

    st.divider()

    if uploaded_files_df.empty:
        st.write("No files were uploaded yet.")
    else:
        st.write("Available files.")
        for idx, file_info in uploaded_files_df.iterrows():
            if st.sidebar.button(file_info['file_name']):
                st.session_state.current_file = file_info['file_hash']
                st.session_state.current_file_name = file_info['file_name']

    st.divider()

    # The workflow is guided by the selection of a file to process
    if "current_file" in st.session_state:
        st.write(f"Working with file {st.session_state.current_file_name}")

        if st.sidebar.button("New chat!"):
            st.session_state.current_chat_id = uuid.uuid4()
            st.session_state.messages = []
            st.rerun()

        # We need to list previous chats over the selected file
        for chat_id in chat_history_df[(chat_history_df["file_hash"] == st.session_state.current_file)]["chat_id"].unique():
            button_label = get_button_label(chat_history_df, chat_id)
            if button_label and st.sidebar.button(button_label):
                # Get the selected chat
                st.session_state.current_chat_id = chat_id

                loaded_chat = chat_history_df[
                    (chat_history_df["chat_id"] == chat_id) & 
                    (chat_history_df["file_hash"] == st.session_state.current_file)
                    ] 
                st.session_state.messages = []
                for _, row in loaded_chat.iterrows():
                    st.session_state.messages.append({"role": row['role'], "content": base64.b64decode(row['content']).decode("ascii")})
    else:
        st.write("No file was selected to work.")



    st.divider()

# I want to work on the chat if that is available only
if 'current_chat_id' not in st.session_state:
    st.title("Work with Excel data is easy")
    st.markdown(
        '''
            1. Upload a new spreadsheet or choose an existing one
            2. Create a new chat or choose an existing one
            3. Done!
        '''
    )
    st.stop()


# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages from history on app rerun

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
if prompt := st.chat_input("What is up?"):
    # Display user message in chat message container
    st.chat_message("user").markdown(prompt)
    # Add user message to chat history and save it
    st.session_state.messages.append({"role": "user", "content": prompt})
    chat_history_df = pd.concat(
        [
            chat_history_df,
            pd.DataFrame(
                {
                    "chat_id": [st.session_state.current_chat_id],
                    "file_hash": [st.session_state.current_file],
                    "role":["user"],
                    "content": [base64.b64encode(prompt.encode('ascii')).decode("ascii")]
                }
            )
        ], ignore_index=True 
    )

    llm = ChatOpenAI(
        temperature=0, model=os.environ.get("CHAT_GPT_MODEL"), streaming=True
    )

    df = pd.read_excel(Path(SAVE_FOLDER, st.session_state.current_file_name))

    pandas_df_agent = create_pandas_dataframe_agent(
        llm,
        df,
        verbose=True,        
        agent_type=AgentType.OPENAI_FUNCTIONS,
        handle_parsing_errors=True,
        allow_dangerous_code=True,
        return_intermediate_steps=False,
        early_stopping_method='force',
        prefix=f'''
            You will work with a Pandas dataframe using Python tools to return information to the user. The name of the dataframe is `df`.
            Only queries related to the document are allowed.
            No files should be created as output of any query. If the user requests an output file, deny that action. 
            
            The result of the query have to be always a string.

            If you don't understand a query, or it isn't related to the document ask for more information to the user, explaining what is the problem.
            Sugest that maybe that query isn't related to the document.

            You should use the tools below to answer the question posed of you:

            python_repl_ast: A Python shell. Use this to execute python commands. Input should be a valid python command. When using this tool, 
            sometimes output is abbreviated - make sure it does not look abbreviated before using it in your answer.

            Below is the query.
            Query: 
        '''
    )

    st_cb = StreamlitCallbackHandler(st.container(), expand_new_thoughts=False)
    response = pandas_df_agent.invoke(input={'input':st.session_state.messages[-1]})
    st.session_state.messages.append({"role": "AI", "content": response['output']})
    with st.chat_message("AI"):
        st.markdown(response['output'])


    chat_history_df = pd.concat(
        [
            chat_history_df,
            pd.DataFrame(
                {
                    "chat_id": [st.session_state.current_chat_id],
                    "file_hash": [st.session_state.current_file],
                    "role":["AI"],
                    "content": [base64.b64encode(response['output'].encode('ascii')).decode("ascii")]
                }
            )
        ], ignore_index=True 
    )

    chat_history_df.to_csv(CSV_FILE, index=False)



