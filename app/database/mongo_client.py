import bcrypt
from typing import Dict
from bson import ObjectId
from datetime import datetime
from fastapi import HTTPException
from app.schemas.conversations import Message
from motor.motor_asyncio import AsyncIOMotorClient
from app.schemas.users import UserCreate, UserLogin
from app.database.redis_client import get_redis_config
from app.services.search_service import write_client, INDEX_NAME
from app.utils.common import serialize_mongo_document, serialize_user
from app.database.gcs_client import upload_file_to_gcs, delete_files_from_gcs
from app.database.qdrant_client import add_message_vector, delete_conversation_vectors

api_keys = get_redis_config("api_keys")
client = AsyncIOMotorClient(api_keys["MONGO_DB_URL"])
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
async def create_conversation(user_id: str, title: str):
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
    result = await conversation_collection.insert_one(convo)

    # Add the inserted ObjectId as a string id for frontend compatibility
    convo["id"] = str(result.inserted_id)
    
    return convo

# Retrieve all conversation documents and serialize ObjectId to id
async def get_all_conversations(user_id: str):
    """
    Retrieve all conversations belonging to a specific user.

    Args:
        user_id (str): User ID to filter conversations.

    Returns:
        list: A list of serialized conversation documents.
    """
    # Only get conversations belonging to this user
    cursor = conversation_collection.find({"user_id": user_id})
    conversations = await cursor.to_list(length=None)  # or set a limit
    
    for convo in conversations:
        if "_id" in convo:
            convo["id"] = str(convo["_id"])
            del convo["_id"]
    
    return conversations

# Retrieve a single conversation by its string id
async def get_conversation_by_id(convo_id: str):
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
        convo = await conversation_collection.find_one({"_id": ObjectId(convo_id)})
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
    # Ensure content is None instead of empty string
    message.content = message.content or None

    files = []
    for file_data in (message.files or []):
        try:
            gcs_url = await upload_file_to_gcs(convo_id, file_data)
            files.append({
                "name": file_data.name,
                "type": file_data.type,
                "file": gcs_url
            })
        except Exception as e:
            # fallback: mark upload failed but keep metadata
            files.append({
                "name": file_data.name,
                "type": file_data.type,
                "file": file_data.file if isinstance(file_data.file, str) else None
            })

    msg = {
        "sender": "user",
        "content": message.content,
        "files": files,
        "timestamp": message.timestamp
    }

    bot_reply = {
        "_id": str(ObjectId()), 
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
    convo = await conversation_collection.find_one({"_id": ObjectId(convo_id)})
    if not convo:
        return None
    # Extract user_id from the conversation document
    user_id = convo["user_id"]

    # Store the message and bot response vector in Qdrant for retrieval/history
    task = asyncio.create_task(
        add_message_vector(
            collection_name=user_id,
            conversation_id=convo_id,
            user_message=message.content,
            bot_response=response,
            timestamp=msg["timestamp"].isoformat(),
        )
    )

    # Sync message to Algolia
    response = await write_client.save_object(
        index_name=INDEX_NAME,
        body={
            "objectID": bot_reply["_id"],
            "title": convo.get("title", ""),
            "content": response,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": convo["user_id"],
            "conversation_id": convo_id
        }
    )
    if not response or (hasattr(response, "errors") and response.errors):
        raise Exception("Failed to save message to Algolia index")

"""Update the title of a conversation"""
async def update_conversation_title(convo_id: str, new_title: str):
    """
    Update the title of a specific conversation.

    Args:
        convo_id (str): ID of the conversation to update.
        new_title (str): New title to assign.

    Returns:
        dict | None: The updated conversation document, or None if update failed.
    """
    try:
        result = await conversation_collection.update_one(
            {"_id": ObjectId(convo_id)},
            {"$set": {"title": new_title}}
        )
        
        if result.modified_count == 0:
            return None
            
        # Return the updated conversation
        updated_convo = await conversation_collection.find_one({"_id": ObjectId(convo_id)})
        
        # Update Algolia index with new title
        objects_to_update = []
        for msg in updated_convo.get("messages", []):
            if msg.get("sender") == "assistant":
                objects_to_update.append({
                    "objectID": msg.get("_id", f"{convo_id}_{msg.get('timestamp', '').isoformat()}"),
                    "title": new_title
                })

        response = await write_client.partial_update_objects(
            objects=objects_to_update,
            index_name=INDEX_NAME
        )
        if not response or (hasattr(response, "errors") and response.errors):
            raise Exception("Failed to update Algolia index with new conversation title")

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
    result = await conversation_collection.delete_one({
        "_id": ObjectId(conversation_id),
        "user_id": user_id
    })

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Conversation not found or already deleted")
    
    # Step 2: Delete from GCS
    try:
        await delete_files_from_gcs(conversation_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deleted in DBs but failed to delete GCS files: {str(e)}")
    
    # Step 3: Delete from Qdrant
    try:
        await delete_conversation_vectors(collection_name=user_id, conversation_id=conversation_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deleted in MongoDB but failed in Qdrant: {str(e)}")
    
    # Step 4: Delete from Algolia
    response = await write_client.delete_by(
        index_name=INDEX_NAME,
        delete_by_params={
            "filters": f"conversation_id:{conversation_id}",
        }
    )
    if not response or (hasattr(response, "errors") and response.errors):
        raise HTTPException(status_code=500, detail="Failed to delete conversation from Algolia index")
    
    return {"message": "Conversation deleted from MongoDB and GCS", "conversation_id": conversation_id}


async def register_user(user_data: UserCreate):
    """
    Register a new user after validating uniqueness and hashing the password.

    Args:
        user_data (UserCreate): The user registration payload.

    Returns:
        dict: Serialized user object for API response.

    Raises:
        ValueError: If a user with the same email already exists.
    """
    existing_user = await user_collection.find_one({"email": user_data.email})
    if existing_user:
        raise ValueError("User already exists")

    hashed_pw = bcrypt.hashpw(user_data.password.encode("utf-8"), bcrypt.gensalt())

    new_user = {
        "fullName": user_data.fullName,
        "email": user_data.email,
        "password": hashed_pw.decode("utf-8"),  
        "phone": user_data.phone
    }
    
    result = await user_collection.insert_one(new_user)
    new_user["_id"] = result.inserted_id
    return serialize_user(new_user)


async def login_user(credentials: UserLogin):
    """
    Authenticate a user using email and password.

    Args:
        credentials (UserLogin): Login request containing email and password.

    Returns:
        dict | None: Serialized user if authentication is successful, else None.
    """
    user = await user_collection.find_one({"email": credentials.email})
    if user and bcrypt.checkpw(credentials.password.encode("utf-8"), user["password"].encode("utf-8")):
        return serialize_user(user)
    return None


async def get_user_by_id(user_id: str):
    """
    Retrieve a user by their ID.
    
    Args:
        user_id (str): The user's unique identifier
        
    Returns:
        dict: The user document or None if not found
    """
    try:
        
        # Convert string ID to ObjectId
        object_id = ObjectId(user_id)
        
        # Find user in database - use user_collection (not users_collection)
        user = await user_collection.find_one({"_id": object_id})
        
        if user:
            print(f"Found user: {user.get('email', 'no email')}")  # Debug log
        else:
            print("User not found in database")  # Debug log
        
        return user
        
    except Exception as e:
        print(f"Error fetching user by ID: {e}")
        return None


async def update_user_profile(user_id: str, update_data: dict):
    """
    Update a user's profile information (fullName, nickname).
    
    Args:
        user_id (str): The user's unique identifier
        update_data (dict): Dictionary containing fields to update
        
    Returns:
        dict: The updated user document or None if update failed
    """
    try:
        # Convert string ID to ObjectId
        object_id = ObjectId(user_id)
        
        # Add timestamp for when profile was last updated
        update_data["updatedAt"] = datetime.utcnow()
        
        # Update user in database - use user_collection
        result = await user_collection.update_one(
            {"_id": object_id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            print("No user was updated")
            return None
        
        # Return the updated user document
        updated_user = await user_collection.find_one({"_id": object_id})
        return updated_user
        
    except Exception as e:
        print(f"Error updating user profile: {e}")
        return None


async def update_user_theme(user_id: str, theme: str):
    """
    Update a user's theme preference.
    
    Args:
        user_id (str): The user's unique identifier
        theme (str): The theme preference ("light" or "dark")
        
    Returns:
        dict: The updated user document or None if update failed
    """
    try:
        # Convert string ID to ObjectId
        object_id = ObjectId(user_id)
        
        # Update user theme in database - use user_collection
        result = await user_collection.update_one(
            {"_id": object_id},
            {
                "$set": {
                    "theme": theme,
                    "updatedAt": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count == 0:
            print("No user theme was updated")
            return None
        
        # Return the updated user document
        updated_user = await user_collection.find_one({"_id": object_id})
        return updated_user
        
    except Exception as e:
        print(f"Error updating user theme: {e}")
        return None


from bson import ObjectId
import asyncio

async def delete_user_account(user_id: str):
    """
    Permanently delete a user's account and all associated data.
    
    Args:
        user_id (str): The user's unique identifier
        
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        object_id = ObjectId(user_id)
        print(f"Starting account deletion for user: {user_id}")
        
        # Step 1: Get all conversations for this user (for cleanup purposes)
        cursor = conversation_collection.find({"user_id": user_id})
        user_conversations = await cursor.to_list(length=None)
        conversation_ids = [str(convo["_id"]) for convo in user_conversations]
        
        print(f"Found {len(conversation_ids)} conversations to delete")
        
        # Step 2: Delete files from GCS for all conversations
        for convo_id in conversation_ids:
            try:
                delete_files_from_gcs(convo_id)
                print(f"Deleted GCS files for conversation: {convo_id}")
            except Exception as e:
                print(f"Failed to delete GCS files for conversation {convo_id}: {e}")
        
        # Step 3: Delete vectors from Qdrant (async, fire-and-forget)
        for convo_id in conversation_ids:
            try:
                print(f"Initiated vector deletion for conversation: {convo_id}")
            except Exception as e:
                print(f"Failed to delete vectors for conversation {convo_id}: {e}")
        
        # Step 4: Delete all conversations from MongoDB
        conversation_delete_result = await conversation_collection.delete_many({"user_id": user_id})
        print(f"Deleted {conversation_delete_result.deleted_count} conversations from MongoDB")
        
        # Step 5: Delete the user account
        user_delete_result = await user_collection.delete_one({"_id": object_id})
        
        if user_delete_result.deleted_count == 0:
            print("No user was deleted")
            return False
        
        print(f"Successfully deleted user and all associated data for ID: {user_id}")
        return True
        
    except Exception as e:
        print(f"Error deleting user account: {e}")
        return False


async def get_user_by_email(email: str):
    """
    Get user by email address.
    
    Args:
        email (str): User's email address
        
    Returns:
        dict | None: User document if found, None otherwise
    """
    try:
        user = await user_collection.find_one({"email": email})
        return user  # Return the full user document including password for verification
        
    except Exception as e:
        print(f"Error getting user by email: {str(e)}")
        return None


async def update_user_password(email: str, new_password: str) -> bool:
    """
    Update user's password.
    
    Args:
        email (str): User's email address
        new_password (str): New password (plain text)
        
    Returns:
        bool: True if password updated successfully, False otherwise
    """
    try:
        # Hash the new password using the same method as registration
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        # Update password in database
        result = await user_collection.update_one(
            {"email": email},
            {
                "$set": {
                    "password": hashed_password.decode("utf-8"),  # Store as string like in register
                    "updatedAt": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            print(f"Password updated successfully for {email}")
            return True
        else:
            print(f"No user found with email {email}")
            return False
            
    except Exception as e:
        print(f"Error updating password: {str(e)}")
        return False


def get_database():
    """
    Get database instance.
    """
    return db  # Use your existing db variable