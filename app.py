from flask import Flask, render_template, request, jsonify
from langchain_anthropic import ChatAnthropic
from langchain.schema import HumanMessage
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import text
import os
import traceback
import json
from database_setup import db, load_schema, CustomerData
import re
import logging

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Check if ANTHROPIC_API_KEY is set
if not os.getenv('ANTHROPIC_API_KEY'):
    print("WARNING: ANTHROPIC_API_KEY is not set!")

app = Flask(__name__)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@db:5432/chatdb')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)

# Create tables within app context
with app.app_context():
    db.create_all()
    print("Database tables created successfully")

try:
    # Initialize the ChatAnthropic instance
    chat = ChatAnthropic(
        temperature=0.7,
        model="claude-3-opus-20240229"  # or use another Claude model
    )
except Exception as e:
    print(f"Error initializing ChatAnthropic: {str(e)}")
    traceback.print_exc()

# Database Models
class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_user = db.Column(db.Boolean, default=True)
    query_info = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'is_user': self.is_user,
            'query_info': self.query_info
        }

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    try:
        if not os.getenv('ANTHROPIC_API_KEY'):
            raise ValueError("ANTHROPIC_API_KEY is not set")

        user_message = request.json.get('message', '')
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        
        print(f"Received message: {user_message}")  # Debug log
        
        # Load schema and create context for Claude
        schema = load_schema()
        context = f"""I have a customer database with the following schema:
{json.dumps(schema, indent=2)}

When generating SQL queries:
- Use the table name 'customer_data'
- Follow the exact column names from the schema
- For customer name searches, use case-insensitive pattern matching with: LOWER(customer_name) LIKE LOWER('%search_term%')
- Return only the SQL query without additional explanation unless specifically asked

For example, if searching for a customer named "westmount", the WHERE clause should be:
WHERE LOWER(customer_name) LIKE LOWER('%westmount%')

User question: {user_message}"""
        
        # Save user message to database
        db_user_message = ChatMessage(content=user_message, is_user=True)
        db.session.add(db_user_message)
        db.session.commit()
        
        # Get the response from Claude
        messages = [HumanMessage(content=context)]
        response = chat.invoke(messages)
        logger.info(f"""
API Call Log:
User Message: {user_message}
Context Sent: {context}
API Response: {response.content}
{'='*50}""")
        
        ai_response = response.content
        try:
            # Extract SQL query using regex - looks for content between SELECT and semicolon
            if "SELECT" in ai_response.upper():
                sql_match = re.search(r'(SELECT.*?;)', ai_response, re.IGNORECASE | re.DOTALL)
                if sql_match:
                    sql_query = sql_match.group(1)
                    with db.engine.connect() as connection:
                        result = connection.execute(text(sql_query))
                        # Get column names from result
                        columns = result.keys()
                        # Convert results to list of dicts
                        query_result = [
                            {col: value for col, value in zip(columns, row)}
                            for row in result.fetchall()
                        ]
                        
                        logger.info(f"Query executed successfully. Results: {query_result}")
                        
                        followup_context = f"""Based on the user's question: "{user_message}"
                        
Here are the query results:
{json.dumps(query_result, indent=2)}

Please provide a natural language analysis of these results."""

                        # Send follow-up request to Claude
                        followup_messages = [HumanMessage(content=followup_context)]
                        followup_response = chat.invoke(followup_messages)
                        
                        # Log the follow-up interaction
                        logger.info(f"""
Follow-up API Call Log:
Context: {followup_context}
API Response: {followup_response.content}
{'='*50}""")
                        
                        # Prepare the final response
                        analysis = followup_response.content
                        query_info = f"""Query Results:
{json.dumps(query_result, indent=2)}

SQL Query Used:
{sql_query}"""
                        
                        # Save AI response to database
                        db_ai_message = ChatMessage(
                            content=analysis,
                            is_user=False,
                            query_info=query_info
                        )
                        db.session.add(db_ai_message)
                        db.session.commit()
                        
                        return jsonify({'response': analysis, 'query_info': query_info})
        except Exception as e:
            error_msg = f"\n\nError executing query: {str(e)}"
            logger.error(f"""
Error Log:
{error_msg}
{'='*50}""")
            ai_response += error_msg
            return jsonify({'response': ai_response})
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/history', methods=['GET'])
def get_history():
    try:
        messages = ChatMessage.query.order_by(ChatMessage.timestamp).all()
        
        # Debug logging
        print(f"Found {len(messages)} messages in database")
        
        history = []
        for message in messages:
            msg_dict = message.to_dict()
            print(f"Processing message: {msg_dict}")  # Debug log
            history.append(msg_dict)
        
        # Ensure we're returning a list
        if not isinstance(history, list):
            print(f"Warning: history is not a list, it's {type(history)}")
            history = list(history)
        
        print(f"Returning history with {len(history)} messages")
        return jsonify(history)
    except Exception as e:
        print(f"Error fetching history: {str(e)}")
        traceback.print_exc()
        return jsonify([])  # Return empty array instead of error

@app.route('/reset', methods=['POST', 'GET'])
def reset_history():
    try:
        # Delete all messages
        ChatMessage.query.delete()
        db.session.commit()
        print("Chat history cleared successfully")
        return jsonify({"message": "Chat history cleared successfully"})
    except Exception as e:
        print(f"Error clearing chat history: {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)