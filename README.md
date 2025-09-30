# csv_filter_app

This is an initial prototype for an app that filters csv data upon natural language instructions. It uses the OpenAI API for the LLM (GPT-4o) and Streamlit for the GUI.

## How to run
If you have set OPENAI_API_KEY as an environment variable, and have all dependencies installed, you should be able to run the app with:

```
streamlit run csv_app.py
```
## What it does

### Choose a dataset

<img width="383" height="221" alt="image" src="https://github.com/user-attachments/assets/61cc8a8e-2f6c-44c1-ae36-0bdccd5a66ac" />

Right now there is only one dataset available. But more can be added. Must be a csv file in the folder 'original_data'.

### The data is displayed

A short of the data is given and the data is shown as a dataframe. Streamlit has pretty nice built-in functionality for displaying dataframes.

Colums that are not useful for filtering are removed from the dataset. Some do not contain any information. Others always have the same value. For example, 'is_gift_card' is always False in this dataset. The information about them is given below the dataframe. This way the information is conveyed efficiently, and viewing the dataframe is more convenient.

There is still a bit of redundancy in the provided dataset. For example, 'order_id' and 'order_name' appear to be the same.

Some 4-digit identifiers, such as 'product_id', are displayed as integers, with a comma after the first digit. This can probably best be fixed in the data itself.

Then some examples are given of what a user might want to ask for.

<img width="2716" height="1101" alt="image" src="https://github.com/user-attachments/assets/16773705-377c-4b70-9b89-9eae08fd342d" />

### Interact with the data

The user can type filtering instructions in the input box. The first time they can alternatively choose an example input.

The bot will generate code to perform the filtering. This code is executed and the result is displayed. Right now only filtering is supported, but creating plots could easily be added.

The main dataset and all interactions remain visible throughout the session.

<img width="2698" height="874" alt="image" src="https://github.com/user-attachments/assets/4e3137f4-c4ee-4c27-81a3-467d330ddbd4" />

The LLM is specifically instructed to use pandas to do the filtering. It is given the name of the input file and a summary of the data, so it knows the available columns and the type of values that they contain.

Thw LLM typically does a good job with writing the code, even for more complex queries. For large datasets it may be more efficient to create a database and write SQL queries.

Eventually the LLM gives some 'insights' on the result. This is not very useful yet, but is just to show the possibility of feeding the result back into the LLM and let it comment on it. It could for example also suggest the next thing to look into.

<img width="2677" height="735" alt="image" src="https://github.com/user-attachments/assets/f6548614-73f0-4636-829c-43bf7a8d2baf" />
