import os

db_user = os.environ["db_user"]
db_password = os.environ["db_password"]
db_host = os.environ["db_host"]
db_name = os.environ["db_name"]

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
print(OPENAI_API_KEY)


from langchain_community.utilities.sql_database import SQLDatabase
from langchain.chains import create_sql_query_chain
from langchain_openai import ChatOpenAI
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from langchain.memory import ChatMessageHistory

from operator import itemgetter

from langchain_core.output_parsers import StrOutputParser

from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

from table_details import table_chain as select_table
from prompts import final_prompt, answer_prompt
import streamlit as st


@st.cache_resource
def get_chain():
    print("Creating chain")
    db = SQLDatabase.from_uri(
    f"postgresql://{db_user}:{db_password}@{db_host}/{db_name}")    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    generate_query = create_sql_query_chain(llm, db, final_prompt)
    execute_query = QuerySQLDataBaseTool(db=db)
    rephrase_answer = answer_prompt | llm | StrOutputParser()
    # chain = generate_query | execute_query
    chain = (
            RunnablePassthrough.assign(table_names_to_use=select_table) |
            RunnablePassthrough.assign(query=generate_query).assign(
                result=itemgetter("query") | execute_query
            )
            | rephrase_answer
    )

    return chain


def create_history(messages):
    history = ChatMessageHistory()
    for message in messages:
        if message["role"] == "user":
            history.add_user_message(message["content"])
        else:
            history.add_ai_message(message["content"])
    return history


def invoke_chain(question, messages):
    chain = get_chain()
    history = create_history(messages)
    response = chain.invoke({"question": question, "top_k": 3, "messages": history.messages})
    
    error_keywords = [
        "error in the SQL query",
        "type mismatch",
        "cast",
        "column is likely of type",
    ]
    
    if any(keyword in response.lower() for keyword in error_keywords):
        response = "I'm sorry, I couldn't understand the question or find the relevant information."

    history.add_user_message(question)
    history.add_ai_message(response)
    return response
