import bcrypt
from typing import Dict
from bson import ObjectId
from datetime import datetime
from pymongo import MongoClient
from fastapi import HTTPException
from app.schemas.conversations import Message
from app.schemas.users import UserCreate, UserLogin
from app.database.redis_client import get_redis_config
from app.utils.common import serialize_mongo_document, serialize_user
from app.database.qdrant_client import add_message_vector, delete_conversation_vectors

api_keys = get_redis_config("api_keys")
client = MongoClient(api_keys["MONGO_DB_URL"])
db = client["AHA"]
conversation_collection = db["conversations"]
user_collection = db["users"]

# Test connection
try:
    # Ping the database
    client.admin.command('ping')
    print("Successfully connected to MongoDB Atlas!")
except Exception as e:
    print(f"Connection failed: {e}")

# Create a new conversation document in the database
def create_conversation(user_id: str, title: str):
    """
    Create a new conversation document for a given user.

    Args:
        user_id (str): The ID of the user who owns the conversation.
        title (str): The title of the conversation.

    Returns:
        dict: The newly created conversation document with an `id` field.
    """
    convo = {
        "title": title,
        "user_id": user_id,
        "created_at": datetime.utcnow(),
        "messages": []
    }
    result = conversation_collection.insert_one(convo)

    # Add the inserted ObjectId as a string id for frontend compatibility
    convo["id"] = str(result.inserted_id)
    
    return convo

# Retrieve all conversation documents and serialize ObjectId to id
def get_all_conversations(user_id: str):
    """
    Retrieve all conversations belonging to a specific user.

    Args:
        user_id (str): User ID to filter conversations.

    Returns:
        list: A list of serialized conversation documents.
    """
    # Only get conversations belonging to this user
    conversations = list(conversation_collection.find({"user_id": user_id}))
    
    for convo in conversations:
        if "_id" in convo:
            convo["id"] = str(convo["_id"])
            del convo["_id"]
    
    return conversations

# Retrieve a single conversation by its string id
def get_conversation_by_id(convo_id: str):
    """
    Retrieve a single conversation by its ID.

    Args:
        convo_id (str): String ID of the conversation (MongoDB ObjectId).

    Returns:
        dict | None: The serialized conversation if found, else None.

    Notes:
        Catches and logs errors if the ObjectId is invalid or a DB error occurs.
    """
    try:
        convo = conversation_collection.find_one({"_id": ObjectId(convo_id)})
        if convo:
            return serialize_mongo_document(convo)
        return None
    except Exception as e:
        # If ObjectId is invalid (e.g. wrong format), catch and log
        print(f"Error finding conversation: {e}")
        return None

# Save a user or bot message to an existing conversation
async def save_message(convo_id: str, message: Message, response: str) -> None:
    """
    Save a user message and corresponding assistant response to a conversation.

    Args:
        convo_id (str): ID of the conversation.
        message (Message): Message object from the user.
        response (str): Assistant-generated response.

    Side Effects:
        - Updates the MongoDB conversation.
        - Saves corresponding vectors to Qdrant for semantic search and history tracking.

    Returns:
        None
    """
    message.content = message.content or "" 
    msg = {
        "sender": "user",
        "content": message.content,
        "timestamp": message.timestamp
    }

    bot_reply = {
        "sender": "assistant",
        "content": response,
        "timestamp": datetime.utcnow()
    }
    
    # Push both user message and bot reply into the conversation
    conversation_collection.update_one(
        {"_id": ObjectId(convo_id)},
        {"$push": {"messages": {"$each": [msg, bot_reply]}}}
    )
    
    # Add message to Qdrant for history tracking
    # Lookup conversation
    convo = conversation_collection.find_one({"_id": ObjectId(convo_id)})
    if not convo:
        return None
    # Extract user_id from the conversation document
    user_id = convo["user_id"]

    # Store the message and bot response vector in Qdrant for retrieval/history
    await add_message_vector(
        collection_name=user_id,
        conversation_id=convo_id,
        user_message=message.content,
        bot_response=response,
        timestamp=msg["timestamp"].isoformat(),
    )

"""Update the title of a conversation"""
def update_conversation_title(convo_id: str, new_title: str):
    """
    Update the title of a specific conversation.

    Args:
        convo_id (str): ID of the conversation to update.
        new_title (str): New title to assign.

    Returns:
        dict | None: The updated conversation document, or None if update failed.
    """
    try:
        result = conversation_collection.update_one(
            {"_id": ObjectId(convo_id)},
            {"$set": {"title": new_title}}
        )
        
        if result.modified_count == 0:
            return None
            
        # Return the updated conversation
        updated_convo = conversation_collection.find_one({"_id": ObjectId(convo_id)})
        return serialize_mongo_document(updated_convo)
        
    except Exception as e:
        print(f"Error updating conversation title: {e}")
        return None

async def delete_conversation_by_id(conversation_id: str, user_id: str) -> Dict:
    """
    Delete a conversation and its associated vectors in both MongoDB and Qdrant.

    Args:
        conversation_id (str): The ID of the conversation to delete.
        user_id (str): The ID of the user to ensure ownership.

    Returns:
        dict: A message indicating the result and the conversation ID.

    Raises:
        HTTPException:
            - 400: If conversation ID is invalid.
            - 404: If conversation is not found in MongoDB.
            - 500: If deletion from Qdrant fails after MongoDB deletion.
    """
    if not ObjectId.is_valid(conversation_id):
        raise HTTPException(status_code=400, detail="Invalid conversation ID")

    # Step 1: Delete from MongoDB
    result = conversation_collection.delete_one({
        "_id": ObjectId(conversation_id),
        "user_id": user_id
    })

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found or already deleted")

    # Step 2: Delete from Qdrant
    try:
        await delete_conversation_vectors(collection_name=user_id, conversation_id=conversation_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deleted in MongoDB but failed in Qdrant: {str(e)}")

    return {"message": "Conversation deleted from MongoDB and Qdrant", "conversation_id": conversation_id}


def register_user(user_data: UserCreate):
    """
    Register a new user after validating uniqueness and hashing the password.

    Args:
        user_data (UserCreate): The user registration payload.

    Returns:
        dict: Serialized user object for API response.

    Raises:
        ValueError: If a user with the same email already exists.
    """
    print("Registering use function:", user_data)
    existing_user = user_collection.find_one({"email": user_data.email})
    if existing_user:
        raise ValueError("User already exists")

    hashed_pw = bcrypt.hashpw(user_data.password.encode("utf-8"), bcrypt.gensalt())

    new_user = {
        "fullName": user_data.fullName,
        "email": user_data.email,
        "password": hashed_pw.decode("utf-8"),  # Store as string
        "phone": user_data.phone
    }
    print("Create new user", new_user)
    

    result = user_collection.insert_one(new_user)
    print("Inserted user with ID:", result.inserted_id)
    new_user["_id"] = result.inserted_id
    return serialize_user(new_user)


def login_user(credentials: UserLogin):
    """
    Authenticate a user using email and password.

    Args:
        credentials (UserLogin): Login request containing email and password.

    Returns:
        dict | None: Serialized user if authentication is successful, else None.
    """
    user = user_collection.find_one({"email": credentials.email})
    if user and bcrypt.checkpw(credentials.password.encode("utf-8"), user["password"].encode("utf-8")):
        return serialize_user(user)
    return None
