import streamlit as st
import sqlite3
import pandas as pd
import google.generativeai as genai
import re
import os

# --- Database Setup & Utilities ---

def get_database_schema(db_path):
    """Extracts the schema of the database to provide to the AI."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    schema = ""
    for table_name in tables:
        table_name = table_name[0]
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        column_details = [f"{col[1]} ({col[2]})" for col in columns]
        schema += f"Table: {table_name}\nColumns: {', '.join(column_details)}\n\n"
        
    conn.close()
    return schema

def execute_query(sql_query, db_path):
    """Executes the SQL query and returns a pandas DataFrame."""
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(sql_query, conn)
        conn.close()
        return df, None
    except Exception as e:
        return None, str(e)

def extract_sql(text):
    """Extracts SQL query from markdown code block if present."""
    match = re.search(r'```sql\n(.*?)\n```', text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()

# --- Streamlit App ---
st.set_page_config(page_title="AI Data Analyst (Text-to-SQL)", page_icon="🤖", layout="wide")

st.title("🤖 AI Data Analyst")
st.markdown("Upload a SQLite database, ask questions in plain English, and the AI will write and execute the SQL query for you.")

# Sidebar for configuration
st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("Enter Google Gemini API Key", type="password")

if not api_key:
    st.info("Please enter your Google Gemini API Key in the sidebar to continue. You can get one from Google AI Studio.")
    st.stop()

uploaded_db = st.sidebar.file_uploader("Upload SQLite Database", type=["db", "sqlite", "sqlite3"])

if not uploaded_db:
    st.info("Please upload a SQLite database file to continue.")
    st.stop()

# Save uploaded DB to a temporary file
db_path = "temp_uploaded_db.sqlite"
with open(db_path, "wb") as f:
    f.write(uploaded_db.getvalue())

# Configure Gemini
genai.configure(api_key=api_key)

try:
    model = genai.GenerativeModel('gemini-2.5-flash') # Or gemini-pro
except Exception as e:
    st.error(f"Error initializing model: {e}")
    st.stop()

schema = get_database_schema(db_path)

with st.expander("View Database Schema (Context for AI)", expanded=False):
    st.code(schema, language="sql")

st.markdown("### Ask a Question")
user_question = st.text_input("Example: 'Who are the top 3 highest paid employees?' or 'What is the total sales amount by John Doe?'")

if st.button("Generate & Run SQL"):
    if user_question:
        with st.spinner("Generating SQL query..."):
            prompt = f"""
            You are an expert SQL developer. Your task is to write a SQLite query to answer the user's question based on the following database schema.
            
            Schema:
            {schema}
            
            Question: {user_question}
            
            IMPORTANT:
            - Return ONLY the SQL query. Do not include any explanations, greetings, or markdown formatting around the query (like ```sql).
            - Ensure the query is valid SQLite syntax.
            - Use joins if the question requires data from multiple tables.
            """
            
            try:
                response = model.generate_content(prompt)
                raw_sql = response.text
                clean_sql = extract_sql(raw_sql) # In case it still adds markdown
                
                st.subheader("Generated SQL Query")
                st.code(clean_sql, language="sql")
                
                with st.spinner("Executing query..."):
                    df, error = execute_query(clean_sql, db_path)
                    
                    if error:
                        st.error(f"Error executing query: {error}")
                    elif df is not None and not df.empty:
                        st.subheader("Query Results")
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.warning("Query executed successfully but returned no results.")
                        
            except Exception as e:
                st.error(f"An error occurred during AI generation: {e}")
    else:
        st.warning("Please enter a question first.")
