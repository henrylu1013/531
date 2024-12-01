from datetime import datetime
import json
import logging
import os
import re
import traceback

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from langchain_anthropic import ChatAnthropic
from langchain.schema import HumanMessage
from sqlalchemy import text

# initialize database object
db = SQLAlchemy()

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Check if ANTHROPIC_API_KEY is set
if not os.getenv("ANTHROPIC_API_KEY"):
    logger.warning("WARNING: ANTHROPIC_API_KEY is not set!")

app = Flask(__name__)

# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@db:5432/chatdb"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)

# Create tables within app context
with app.app_context():
    db.create_all()
    logger.info("Database tables created successfully")

try:
    # Initialize the ChatAnthropic instance
    chat = ChatAnthropic(temperature=0.7, model="claude-3-sonnet-20240229")
except Exception as e:
    logger.error(f"Error initializing ChatAnthropic: {str(e)}")
    traceback.print_exc()


# Database Models to store chat history
class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_user = db.Column(db.Boolean, default=True)
    query_info = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "content": self.content,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "is_user": self.is_user,
            "query_info": self.query_info,
        }

def load_schema():
    # Load Schema function used by chat endpoint to get the database schema to send to Claude
    with open('/app/data/static/schema.json', 'r') as f:
        return json.load(f)
    
@app.route("/chat", methods=["POST"])
def chat_endpoint():
    """
    This endpoint handles the chat functionality.
    The initial message is sent to Claude with the database schema.
    Claude generates an SQL query.
    SQL query will be ran on our Postgres database.
    We will again send the results of the DB query and the user query back to Claude to generate a natural language analysis of the results.

    If the user's message starts with "follow up:", it sends the user's message to Claude along with the last query info from the database.
    Claude then generates a response to the user's message.
    """
    try:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError("ANTHROPIC_API_KEY is not set")

        user_message = request.json.get("message", "")
        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        logger.info(f"Received message: {user_message}")  # Debug log

        # Check if this is a follow-up question
        is_followup = user_message.lower().startswith("follow up:")
        if is_followup:
            # Remove the "follow up:" prefix
            user_message = user_message[len("follow up:") :].strip()
            # Get the last AI message and user message from the database
            last_ai_message = (
                ChatMessage.query.filter_by(is_user=False)
                .order_by(ChatMessage.timestamp.desc())
                .first()
            )
            last_user_message = (
                ChatMessage.query.filter_by(is_user=True)
                .order_by(ChatMessage.timestamp.desc())
                .offset(1)
                .first()
            )

            if last_ai_message and last_ai_message.query_info and last_user_message:
                context = f"""Previous interaction:
Previous question: {last_user_message.content}
Previous response: {last_ai_message.content}
Previous query details: {last_ai_message.query_info}

User follow-up question: {user_message}

Answer the follow-up question based on the previous interaction. Answer in the perspective of a sales analyst but don't say that 'As a sales analyst'."""
            else:
                context = f"User follow-up question (no previous context available): {user_message}"

            # Save user message to database
            db_user_message = ChatMessage(content=user_message, is_user=True)
            db.session.add(db_user_message)
            db.session.commit()

            # Get response from Claude for follow-up
            messages = [HumanMessage(content=context)]
            response = chat.invoke(messages)
            ai_response = response.content

            # Save AI response to database with previous query info
            db_ai_message = ChatMessage(
                content=ai_response,
                is_user=False,
                query_info=last_ai_message.query_info if last_ai_message else None,
            )
            db.session.add(db_ai_message)
            db.session.commit()

            return jsonify(
                {
                    "response": ai_response,
                    "query_info": last_ai_message.query_info
                    if last_ai_message
                    else None,
                }
            )

        else:
            # Original SQL query handling code
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
                    sql_match = re.search(
                        r"(SELECT.*?;)", ai_response, re.IGNORECASE | re.DOTALL
                    )
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

                            logger.info(
                                f"Query executed successfully. Results: {query_result}"
                            )

                            followup_context = f"""Based on the user's question: "{user_message}"
                            
Here are the query results:
{json.dumps(query_result, indent=2)}

Please provide a natural language analysis of these results. Answer in the perspective of a sales analyst but don't say that 'As a sales analyst'."""

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
                                content=analysis, is_user=False, query_info=query_info
                            )
                            db.session.add(db_ai_message)
                            db.session.commit()

                            return jsonify(
                                {"response": analysis, "query_info": query_info}
                            )
            except Exception as e:
                error_msg = f"\n\nError executing query: {str(e)}"
                logger.error(f"""
Error Log:
{error_msg}
{'='*50}""")
                ai_response += error_msg
                return jsonify({"response": ai_response})
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route("/history", methods=["GET"])
def get_history():
    """
    This endpoint returns the chat history.
    """
    try:
        messages = ChatMessage.query.order_by(ChatMessage.timestamp).all()

        # Debug logging
        logger.info(f"Found {len(messages)} messages in database")

        history = []
        for message in messages:
            msg_dict = message.to_dict()
            logger.info(f"Processing message: {msg_dict}")  # Debug log
            history.append(msg_dict)

        # Ensure we're returning a list
        if not isinstance(history, list):
            logger.warning(f"Warning: history is not a list, it's {type(history)}")
            history = list(history)

        logger.info(f"Returning history with {len(history)} messages")
        return jsonify(history)
    except Exception as e:
        logger.error(f"Error fetching history: {str(e)}")
        traceback.print_exc()
        return jsonify([])  # Return empty array instead of error


@app.route("/reset", methods=["POST", "GET"])
def reset_history():
    """
    This endpoint clears the chat history.
    It is meant to be manually triggered.
    """
    try:
        # Delete all messages
        ChatMessage.query.delete()
        db.session.commit()
        logger.info("Chat history cleared successfully")
        return jsonify({"message": "Chat history cleared successfully"})
    except Exception as e:
        logger.error(f"Error clearing chat history: {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
