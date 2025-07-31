import secrets
from datetime import datetime, timedelta
from typing import Optional
from app.database.mongo_client import db  # Import your existing db instance

# Token expiration time (15 minutes)
TOKEN_EXPIRY_MINUTES = 15

async def generate_reset_token(email: str) -> str:
    """
    Generate a secure password reset token for the user.
    
    Args:
        email (str): User's email address
        
    Returns:
        str: Generated reset token
    """
    try:
        # Generate a secure random token
        token = secrets.token_urlsafe(32)
        
        # Create expiry time
        expiry_time = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRY_MINUTES)
        
        # Store token in database using your existing db instance
        reset_tokens_collection = db.reset_tokens
        
        # Remove any existing tokens for this email (ASYNC)
        await reset_tokens_collection.delete_many({"email": email})
        
        # Store new token (ASYNC)
        await reset_tokens_collection.insert_one({
            "email": email,
            "token": token,
            "expires_at": expiry_time,
            "used": False,
            "created_at": datetime.utcnow()
        })
        
        print(f"Reset token generated for {email}")
        return token
        
    except Exception as e:
        print(f"Error generating reset token: {str(e)}")
        raise


async def verify_reset_token(token: str) -> Optional[str]:
    """
    Verify a password reset token and return the associated email.
    """
    try:
        reset_tokens_collection = db.reset_tokens
        
        print("DEBUG: Searching for reset token in the database")  # Debug log
        
        # Find the token (ASYNC)
        token_doc = await reset_tokens_collection.find_one({
            "token": token,
            "used": False
        })
        
        print(f"DEBUG: Token found: {token_doc is not None}")  # Debug log
        
        if not token_doc:
            print("Token not found or already used")
            return None
            
        print(f"DEBUG: Token expires at: {token_doc['expires_at']}")  # Debug log
        print(f"DEBUG: Current time: {datetime.utcnow()}")  # Debug log
            
        # Check if token has expired
        if datetime.utcnow() > token_doc["expires_at"]:
            print("Token has expired")
            # Clean up expired token (ASYNC)
            await reset_tokens_collection.delete_one({"_id": token_doc["_id"]})
            return None
            
        print(f"Valid reset token found for {token_doc['email']}")
        return token_doc["email"]
        
    except Exception as e:
        print(f"Error verifying reset token: {str(e)}")
        return None


async def invalidate_reset_token(token: str) -> bool:
    """
    Mark a reset token as used/invalid.
    
    Args:
        token (str): The reset token to invalidate
        
    Returns:
        bool: True if token was invalidated, False otherwise
    """
    try:
        reset_tokens_collection = db.reset_tokens
        
        # Mark token as used (ASYNC)
        result = await reset_tokens_collection.update_one(
            {"token": token},
            {
                "$set": {
                    "used": True,
                    "used_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            print(f"Reset token invalidated successfully")
            return True
        else:
            print("Token not found for invalidation")
            return False
            
    except Exception as e:
        print(f"Error invalidating reset token: {str(e)}")
        return False


async def cleanup_expired_tokens():
    """
    Clean up expired reset tokens from the database.
    This should be called periodically (e.g., via a cron job).
    """
    try:
        reset_tokens_collection = db.reset_tokens
        
        # Delete expired tokens (ASYNC)
        result = await reset_tokens_collection.delete_many({
            "expires_at": {"$lt": datetime.utcnow()}
        })
        
        print(f"Cleaned up {result.deleted_count} expired tokens")
        return result.deleted_count
        
    except Exception as e:
        print(f"Error cleaning up expired tokens: {str(e)}")
        return 0