import streamlit as st
import requests
import base64
import uuid
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API configurations - you'll need to set these in your .env file or environment variables
STORAGE_API_URL = os.getenv("STORAGE_API_URL", "http://your-flask-app-url.com")
STORAGE_API_KEY = os.getenv("STORAGE_API_KEY", "your-storage-api-key")
SNAPLOGIC_API_URL = os.getenv("SNAPLOGIC_API_URL", "http://your-snaplogic-api-url.com")
SNAPLOGIC_API_KEY = os.getenv("SNAPLOGIC_API_KEY", "your-snaplogic-api-key")

# Page setup
st.set_page_config(page_title="Document Chatbot", layout="wide")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    
if "document_id" not in st.session_state:
    st.session_state.document_id = None
    st.session_state.document_name = None

# Function to upload document to storage
def upload_to_storage(file_data, file_name):
    """
    Uploads a document to the temporary storage service
    Returns the document ID if successful, None otherwise
    """
    try:
        # Encode file data as base64
        encoded_content = base64.b64encode(file_data).decode('utf-8')
        
        # Send to storage service
        response = requests.post(
            f"{STORAGE_API_URL}/upload",
            headers={
                "Authorization": f"Bearer {STORAGE_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "file_name": file_name,
                "content": encoded_content,
                "session_id": st.session_state.session_id
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get("document_id")
        else:
            st.error(f"Failed to upload document: {response.status_code}")
            if hasattr(response, 'text'):
                st.error(response.text)
            return None
    except Exception as e:
        st.error(f"Error uploading document: {str(e)}")
        return None

# Function to query the chatbot
def query_chatbot(query, document_id):
    """
    Sends a query to the SnapLogic pipeline with the document ID
    Returns the response if successful, error message otherwise
    """
    try:
        response = requests.post(
            f"{SNAPLOGIC_API_URL}/query",
            headers={
                "Authorization": f"Bearer {SNAPLOGIC_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "query": query,
                "document_id": document_id,
                "session_id": st.session_state.session_id
            }
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Error: {response.status_code}", "response": response.text if hasattr(response, 'text') else "Unknown error"}
    except Exception as e:
        return {"error": str(e)}

# Sidebar for document upload
with st.sidebar:
    st.title("Document Upload")
    
    # Display current document info
    if st.session_state.document_id is not None:
        st.success(f"Current Document: {st.session_state.document_name}")
        if st.button("Remove Document"):
            st.session_state.document_id = None
            st.session_state.document_name = None
            st.session_state.messages = []
            st.experimental_rerun()
    else:
        st.info("No document loaded")
    
    # Upload new document
    st.subheader("Upload New Document")
    uploaded_file = st.file_uploader(
        "Upload a document",
        type=["pdf", "docx", "doc", "txt", "csv", "xlsx"]
    )
    
    if uploaded_file is not None:
        file_name = uploaded_file.name
        doc_name = st.text_input("Document Name (optional)", value=file_name)
        
        if st.button("Use This Document"):
            with st.spinner("Processing document..."):
                # Upload to storage service
                document_id = upload_to_storage(uploaded_file.getvalue(), file_name)
                
                if document_id:
                    # Store in session state
                    st.session_state.document_id = document_id
                    st.session_state.document_name = doc_name or file_name
                    
                    # Clear chat history
                    st.session_state.messages = []
                    
                    st.success("Document processed successfully!")
                    st.experimental_rerun()
                else:
                    st.error("Failed to process document.")

# Main chat interface
st.title("Document Chatbot")

if st.session_state.document_id is not None:
    st.caption(f"Currently using: {st.session_state.document_name}")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
    
    # User input
    if prompt := st.chat_input("Ask a question about your document..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.write(prompt)
        
        # Get and display assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # Query using the document ID
                result = query_chatbot(
                    prompt,
                    st.session_state.document_id
                )
                
                if "error" in result:
                    response = f"I encountered an error: {result['error']}"
                else:
                    response = result.get("response", "No response received.")
                
                st.write(response)
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})
else:
    # No document selected
    st.info("👈 Please upload a document in the sidebar to start chatting.")
    st.write("This chatbot will answer questions based on your document content.")

# Footer with info
st.divider()
st.caption("This Document Chatbot uses SnapLogic to provide contextual answers based on your document. Documents are temporarily stored for 2 hours.")