import streamlit as st
import pandas as pd
import os #for accessing API keys
import shutil
import json
from langchain.memory import StreamlitChatMessageHistory
from langchain_core.messages.base import BaseMessage
from langchain_openai import ChatOpenAI
import openai
import jsonlines
from code_exec import SafeCodeExecutorWithInputs
from summarize_csv import summarize_csv
from streamlit_float import *

st.set_page_config(layout="wide")

float_init(theme=True, include_unstable_primary=False) #helps with placing the box for user input


### The LLM ###
apikey = os.environ["OPENAI_API_KEY"] #set this as an environment variable on your machine
gpt4 = ChatOpenAI(model_name="gpt-4o", temperature=0, api_key=apikey) 
#or caching for efficient deployment
#@st.cache_resource 
#def load_gpt4():
    #return ChatOpenAI(model_name="gpt-4o", temperature=0, api_key=apikey) 
#gpt4 = load_gpt4()    


### LLM call templates ###

template = """
You are an bot that writes python code to filter csv data, using pandas, and can answer questions about the dataset.

The dataset is provided in the following file: {filepath}

Here is a summary of the data:

<summary>
{data_summary}
</summary>

Write code that performs the filtering requested by the user and writes the result to a new file. 
CRITICAL: Always wrap code in <code language="python">...</code> HTML tags. Never leave code untagged. 


Preceeding conversation:
{conversation}

User query: {question}
Explanation and code:"""


retry_template = """The code you wrote did not run correctly. Try again.

User query: {question}

Generated answer: {answer}

Errors: {errors}

"""

insights_template = """

Summary of the full dataset: 
<summary>
{original_summary}
</summary>

User query: {question}

Generated answer: 
{answer}

Summary of resulting dataset: 
<summary>
{new_summary}
</summary>

Provide relevant insights about the filtered data
"""
### Management of session state variables for button behavior ###

if 'input_data' not in st.session_state:
    st.session_state.input_data = ''

if 'clicked1' not in st.session_state: #for dataset selection
    st.session_state.clicked1 = False

def hide_data_selection(dataset=''):
    st.session_state.clicked1 = True
    st.session_state.input_data = dataset

if 'clicked2' not in st.session_state: #for example selection
    st.session_state.clicked2 = False

if 'chosen_example' not in st.session_state:
    st.session_state.chosen_example = ''

if 'user_input' not in st.session_state:
    st.session_state.user_input = ''

if 'outfiles' not in st.session_state:
    st.session_state.outfiles = []

def hide_buttons(ex=''):
    st.session_state.clicked2 = True
    st.session_state.chosen_example = ex

### Other variables relevant for the whole session ###
msgs = StreamlitChatMessageHistory(key="langchain_messages")
working_file = ''
data_summary = ''
input_dir = 'original_data'
datadir = 'data' # working file and filtering results will be stored here
datasets = []
for fn in os.listdir(input_dir):
    datasets.append(os.path.join(input_dir, fn))


### Functions that support the main interaction, e.g. for callilng the LLM and making sure the generated code gets executed, and results get passed back ###

def display_code(response):
    response = response.replace('<code language="python">', '```python')
    response = response.replace('</code>', '```') #this format gets displayed as a pretty code block in streamlit
    return response

def execute_code(ai_answer): #this fuction uses the code execution functionality provided in 'code_exec.py' to extract and run the code from the ai_answer
    executor = SafeCodeExecutorWithInputs(timeout=100, max_memory_mb=500, input_directory=datadir)
    results = executor.execute_safe(ai_answer)
    outfiles = []
    print_output =[]
    errors = []
    if results:
        for r in results:
            print(r)
            if r:
                outfiles.extend(r.get('output_files'))
                print_output.append(r.get('stdout'))
                error = r.get('stderr')
                if error:
                    errors.append(error)
        for fn in os.listdir(executor.temp_dir): #copy output files from temporary directory to data for easier and contiued accessibility
                print(fn)
                if fn in outfiles:
                    st.session_state.outfiles.append(fn)
                    source_path = os.path.join(executor.temp_dir, fn)
                    dest_path = os.path.join(datadir, fn)
                    shutil.copy2(source_path, dest_path)
    executor.cleanup()
    return print_output, outfiles, errors


def retry_generation(user_input, ai_answer, errors):
    with st.spinner('Trying again...'):
        try:
            retry_prompt = retry_template.format(question=user_input, answer=ai_answer, errors=errors)
            result = gpt4.invoke(retry_prompt)
            ai_answer = result.content
        except ValueError:
            ai_answer = ''
    if not ai_answer:
        st.write('Oops, something went wrong. Please try again.')
        return '', [], [], []  
    print_output, outfiles, new_errors = execute_code(ai_answer)
    return ai_answer, print_output, outfiles, new_errors


def act_on_input(user_input): # This function takes care of the main LLM call
    st.chat_message("human").write(user_input) # the user input is displayed 
    prev_conv = '\n'.join([msg.type+': '+msg.content for msg in msgs.messages[-4:]]) # the previous two interactions are retrieved from the message history and provided as context
    user_msg = BaseMessage(type="human", content=user_input) # the user input is added to the message history
    msgs.add_message(user_msg)
    with st.spinner('Generating...'): # a spinner is shown while the LLM is working
        try:
            # the name of the input file, data summary and previous interactions are provided to the LLM, together with user input and the instructions provided in the template. #
            full_prompt = template.format(question=user_input, filepath=working_file, data_summary=data_summary, conversation=prev_conv)
            print(full_prompt)
            result = gpt4.invoke(full_prompt)
            ai_answer = result.content
        except ValueError:
            ai_answer = ''
    if not ai_answer: # in a previous project it has happened that the answer triggered some filter and was not returned
        st.write('Oops, something went wrong. Please try again.')
    else:
        print_output, outfiles, errors = execute_code(ai_answer) # code (if any) is extracted and executed
        # One retry if the generated code throws an error. Not yet tested. If there are still errors after that, we return the answer with errors. The user can then maybe reformulate their request to help the LLM. #
        if errors:
            ai_answer, print_output, outfiles, errors = retry_generation(user_input, ai_answer, errors) 
        # add any print output from running the code to the answer, so it gets displayed (and goes into the message history) as part of the answer  #
        if ai_answer and not errors:
            if print_output:
                ai_answer = ai_answer+'  \n\n'+'\n'.join(print_output)  
        return ai_answer, print_output, outfiles, errors


### Some placeholder functionality for providing user-friendly text descriptions of datasets ###
# Users may alreay know this or need something different as an introduction to the loaded dataset. This is just an example.
stored_descriptions = {}
with open("stored_descriptions.json", 'r') as f:
    data = json.load(f)
    stored_descriptions = data
    
def get_description(dataset):
    # Description is LLM generated, with minimal editing, based on csv summary. For efficiency reasons we don't want to generate a new description every time we load the dataset.
    if dataset in stored_descriptions.keys():
        description = stored_descriptions[dataset].get("description")
    else:
        description = "Description needs to be generated"
        # Not yet added: Description generation and storage for new datasets. Prompt needs to be optimized for user needs. 
    return description


### The actual interaction ###

# Title and initial message #
st.title('CSV Filtering App')
st.markdown("In this app you can filter csv data.")
if st.session_state.clicked1 == False:
    st.markdown("Choose a dataset to load:") #for now it's just the one dataset (with a not very descriptive name), but it will offer any dataset that is added to the original_data folder
    datafiles = [f for f in datasets if f.endswith('csv')]
    for dataset in datafiles:
        st.button(os.path.basename(dataset), on_click=hide_data_selection, args=[dataset]) #displays buttons with the names of the available data files
    if not datafiles:
        st.markdown('There are no available datasets. Please put a csv file in the original_data folder')

# Selected dataset is introduced and displayed #
if st.session_state.input_data: #This session state variable gets its value, when a dataset selection button is clicked. The buttons then disappear.
    input_file = st.session_state.input_data
    st.markdown("You have chosen to load:")
    st.markdown("**"+os.path.basename(input_file)+"**") # display the file name of the selected dataset
    # summarize_csv (imported from separate file) creates the csv file were are going to display and work with (removing less informative columns for better readability) and the information needed for a data summary that we will feed to the LLM #
    info, column_info, extra_info, output_file = summarize_csv(input_file, datadir) 
    working_file = output_file # this is going to be the input file for the generated scripts throughout the session
    # display a text description of the selected dataset #
    description = get_description(os.path.basename(input_file)) 
    st.markdown(description)
    # display the data in streamlit and prepare the data summary for the LLM #
    df = pd.read_csv(working_file)
    st.dataframe(df, use_container_width=True)
    data_summary = '  \n'.join(['  \n'.join(info), '  \n'.join(column_info)])
    if extra_info:
        st.markdown("The following colums have been removed:")
        st.markdown('  \n'.join(extra_info))
        data_summary = data_summary + "The following colums have been removed:  \n\n" + '  \n'.join(extra_info)

    # Display of previous interactions #
    for msg in msgs.messages:
        st.chat_message(msg.type).write(msg.content)
        if msg.type == "ai" and hasattr(msg, "data_frames"):
            for df in msg.data_frames:
                 st.dataframe(df, use_container_width=True)

    # The user can provide input by chosing an example, or by typing in the input field #
    if len(msgs.messages) == 0 and not st.session_state.clicked2: #examples are displayed intitially to get the user started
        st.markdown("You can ask to filter this data using natural language, for example:")
        examples = ["Show me data for Aarhus", "Give me the returning customers", "Show the jackets sold on weekend days"]
        for ex in examples:
            st.button(ex, on_click=hide_buttons, args=[ex])
    container = st.container()
    if st.session_state.clicked2:
        container.float(css=float_css_helper(width="2.2rem", bottom="3rem", transition=0))
    with container:
        st.chat_input(key='content', on_submit=hide_buttons)
    if st.session_state.chosen_example:
        st.session_state.user_input = st.session_state.chosen_example
        st.session_state.chosen_example = ''
    if content:=st.session_state.content:
        st.session_state.user_input = st.session_state.content
    # Once user input has been entered, the LLM will be called to generate a response #
    if st.session_state.user_input:
        user_input = st.session_state.user_input
        st.session_state.user_input = ''
        ai_answer, print_output, outfiles, errors = act_on_input(user_input) # this is wehre the main LLM call happens
        display_answer = display_code(ai_answer) # modifying the answer to ensure that the code is displayed nicely in the UI
        st.chat_message("ai").write(display_answer) # the answer is displayed
        print(ai_answer)
        ai_msg = BaseMessage(type="ai", content=display_answer) # a message is created for storing in the message history
        interaction = {} # some basic storage of interaction data for future analysis
        interaction['user_input'] = user_input
        interaction['ai_answer'] = ai_answer
        # Display data frames from output files and store them in history #
        if outfiles: # These are csv files. For other file types, e.g. plots, additional fuctionality is needed
            interaction['output_files'] = outfiles
            new_dfs = []
            for fn in outfiles:
                dest_path = os.path.join(datadir, fn)
                df = pd.read_csv(dest_path)
                st.dataframe(df, use_container_width=True) # display any csv files that result from running the generated code
                new_dfs.append(df)
            setattr(ai_msg, 'data_frames', new_dfs) # add the resulting dataframes to the answer as a separate attribute, so they can continue to be displayed
            msgs.add_message(ai_msg) 
        print('current outfiles: ', outfiles)
        # Display any errors resulting from running the code #
        if errors:
            st.markdown('  \n'.join(errors))
            print('  \n'.join(errors))
            interaction['errors'] = errors
        # Small experiment to let the LLM comment on the output. Not very useful yet. Adding business objectives to the instructions might be good here. #
        if outfiles:
            info, column_info, extra_info, output_file = summarize_csv(os.path.join(datadir, outfiles[0]), datadir)
            new_summary = '  \n'.join(['  \n'.join(info), '  \n'.join(column_info)])
            with st.spinner('Generating insights...'):
                try:
                    prompt = insights_template.format(question=user_input, answer=ai_answer, original_summary=data_summary,  new_summary=new_summary)
                    print(prompt)
                    result = gpt4.invoke(prompt)
                    ai_insights = result.content
                except ValueError:
                    ai_insights = ''
                if ai_insights:
                    print(ai_insights)
                    st.chat_message("ai").write(ai_insights)
                    interaction['ai_insights'] = ai_insights
        # collect data in a file for future reference #
        with jsonlines.open('interaction_data.jsonl', mode='a') as writer: 
            writer.write(interaction)
        
        
