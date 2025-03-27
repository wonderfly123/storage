from flask import Flask, request, jsonify
import os
import uuid
import base64
from datetime import datetime, timedelta
import threading
import time
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Important: Rename from app to application for Elastic Beanstalk
application = Flask(__name__)

# Simple in-memory storage with TTL
documents = {}
DOCUMENT_TTL_HOURS = 2  # Documents expire after 2 hours

# API key for basic security
API_KEY = os.environ.get("STORAGE_API_KEY", "your-secret-api-key")

def authenticate():
    """Check if the request has a valid API key"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return False
    token = auth_header.split(" ")[1]
    return token == API_KEY

def cleanup_expired_documents():
    """Background thread to remove expired documents"""
    while True:
        current_time = datetime.now()
        expired_docs = []
        
        for doc_id, doc_info in documents.items():
            if current_time > doc_info["expiration"]:
                expired_docs.append(doc_id)
        
        for doc_id in expired_docs:
            logger.info(f"Removing expired document: {doc_id}")
            try:
                del documents[doc_id]
            except KeyError:
                pass  # Document might have been deleted already
        
        time.sleep(3600)  # Check once per hour

# Start the cleanup thread
cleanup_thread = threading.Thread(target=cleanup_expired_documents, daemon=True)
cleanup_thread.start()

@application.route("/upload", methods=["POST"])
def upload_document():
    """Handle document upload requests"""
    if not authenticate():
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    if not data or "content" not in data or "file_name" not in data:
        return jsonify({"error": "Missing required fields"}), 400
    
    try:
        # Generate a unique document ID
        document_id = str(uuid.uuid4())
        
        # Store the document with expiration time
        documents[document_id] = {
            "content": data["content"],
            "file_name": data["file_name"],
            "session_id": data.get("session_id", "unknown"),
            "upload_time": datetime.now(),
            "expiration": datetime.now() + timedelta(hours=DOCUMENT_TTL_HOURS)
        }
        
        logger.info(f"Uploaded document: {data['file_name']} with ID: {document_id}")
        
        return jsonify({
            "document_id": document_id,
            "expiration": (datetime.now() + timedelta(hours=DOCUMENT_TTL_HOURS)).isoformat()
        })
    except Exception as e:
        logger.error(f"Error in upload: {str(e)}")
        return jsonify({"error": str(e)}), 500

@application.route("/document", methods=["GET"])
def get_document():
    """Retrieve a document by its ID (as query parameter)"""
    if not authenticate():
        return jsonify({"error": "Unauthorized"}), 401
    
    document_id = request.args.get("id")
    if not document_id or document_id not in documents:
        return jsonify({"error": "Document not found"}), 404
    
    # Extend the expiration time when accessed
    documents[document_id]["expiration"] = datetime.now() + timedelta(hours=DOCUMENT_TTL_HOURS)
    
    return jsonify({
        "document_id": document_id,
        "file_name": documents[document_id]["file_name"],
        "content": documents[document_id]["content"],
        "expiration": documents[document_id]["expiration"].isoformat()
    })

@application.route("/delete", methods=["DELETE"])
def delete_document():
    """Delete a document by its ID (as query parameter)"""
    if not authenticate():
        return jsonify({"error": "Unauthorized"}), 401
    
    document_id = request.args.get("id")
    if not document_id or document_id not in documents:
        return jsonify({"error": "Document not found"}), 404
    
    del documents[document_id]
    logger.info(f"Deleted document with ID: {document_id}")
    
    return jsonify({"status": "Document deleted successfully"})

@application.route("/health", methods=["GET"])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        "status": "healthy",
        "documents_count": len(documents),
        "uptime": "unknown"
    })

# Added root route for default health check
@application.route("/", methods=["GET"])
def root():
    return jsonify({
        "status": "ok",
        "message": "Document storage service is running"
    })

# Use application.run for local testing, but this is ignored by Elastic Beanstalk
if __name__ == "__main__":
    # Get port from environment variable, default to 8080 for EB
    port = int(os.environ.get("PORT", 8080))
    application.run(host="0.0.0.0", port=port)