# streamlit-and-langchain-poc
POC to explore the capabilities of the Streamlit and Langchain frameworks

### Requirements
* virtualenv
* pipenv
* An OpenAI account, with access to ChatGPT API

### Setup
1. Clone the repository and move on the new folder `streamlit-and-langchain-poc`
2. Create the virtual environment with `virtualenv` command
<br>``` virtualenv .venv ```
3. Install Pip dependencies with `pipenv` command.
<br>``` pipenv install```
4. Create a .env file with following content <br>
```
OPENAI_API_KEY="your-openai-api-key"
CHAT_GPT_MODEL="gpt-3.5-turbo" # default model, any other available model can be used
```
4. Open a pipenv shell and run the application with Streamlit <br>
```
pipenv shell
streamlit run app.py
```
5. Enjoy!
