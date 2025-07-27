from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.utils.common import build_error_response
from app.database.mongo_client import (
    get_user_by_id, 
    update_user_profile, 
    update_user_theme,
    delete_user_account
)
from app.schemas.users import (
    UserResponse, 
    UserUpdateProfile, 
    UserUpdateTheme
)

# Create router with prefix and tag
router = APIRouter(prefix="/api/users", tags=["Users"])
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Extract and verify the current user from the authorization token.
    
    Args:
        credentials: The HTTP authorization credentials containing the Bearer token
        
    Returns:
        dict: The current user data
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    try:
        # Extract token (which is the user's _id) from credentials
        user_id = credentials.credentials
        print(f"Received user_id as token: {user_id}")  # Debug log
        
        if not user_id:
            raise HTTPException(status_code=401, detail="No user ID provided")
        
        # Get user from database using the _id
        user = get_user_by_id(user_id)
        print(f"Found user: {user is not None}")  # Debug log
        
        if not user:
            print(f"User not found for ID: {user_id}")  # Debug log
            raise HTTPException(status_code=404, detail="User not found")
            
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Auth error: {e}")  # Debug log
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


@router.get("/profile", response_model=UserResponse)
def get_user_profile(current_user: dict = Depends(get_current_user)):
    """
    Get the current user's profile information.
    
    Returns:
        UserResponse: The user's profile data
    """
    try:
        return UserResponse(
            id=str(current_user["_id"]),
            fullName=current_user["fullName"],
            email=current_user["email"],
            phone=current_user["phone"],
            nickname=current_user.get("nickname"),
            theme=current_user.get("theme", "light")
        )
    except Exception as e:
        return build_error_response(
            "PROFILE_FETCH_FAILED",
            f"Failed to fetch profile: {str(e)}",
            500
        )


@router.put("/profile", response_model=UserResponse)
def update_user_profile_endpoint(
    profile_data: UserUpdateProfile,
    current_user: dict = Depends(get_current_user)
):
    """
    Update the current user's profile information (fullName, nickname).
    
    Args:
        profile_data (UserUpdateProfile): The profile data to update
        current_user: The authenticated user
        
    Returns:
        UserResponse: The updated user profile data
    """
    try:
        if not profile_data.fullName and not profile_data.nickname:
            return build_error_response(
                "INVALID_INPUT",
                "At least one field (fullName or nickname) must be provided",
                400
            )
        
        # Prepare update data (only include non-None values)
        update_data = {}
        if profile_data.fullName is not None:
            if not profile_data.fullName.strip():
                return build_error_response(
                    "INVALID_INPUT",
                    "Full name cannot be empty",
                    400
                )
            update_data["fullName"] = profile_data.fullName.strip()
            
        if profile_data.nickname is not None:
            update_data["nickname"] = profile_data.nickname.strip()
        
        # Update user in database
        user_id = str(current_user["_id"])
        updated_user = update_user_profile(user_id, update_data)
        
        if not updated_user:
            return build_error_response(
                "UPDATE_FAILED",
                "Failed to update user profile",
                500
            )
        
        return UserResponse(
            id=str(updated_user["_id"]),
            fullName=updated_user["fullName"],
            email=updated_user["email"],
            phone=updated_user["phone"],
            nickname=updated_user.get("nickname"),
            theme=updated_user.get("theme", "light")
        )
        
    except Exception as e:
        print(f"Error updating user profile: {e}")
        return build_error_response(
            "UPDATE_FAILED",
            f"Profile update failed: {str(e)}",
            500
        )


@router.put("/theme", response_model=UserResponse)
def update_user_theme_endpoint(
    theme_data: UserUpdateTheme,
    current_user: dict = Depends(get_current_user)
):
    """
    Update the current user's theme preference.
    
    Args:
        theme_data (UserUpdateTheme): The theme preference to set
        current_user: The authenticated user
        
    Returns:
        UserResponse: The updated user data
    """
    try:
        # Validate theme value
        if theme_data.theme not in ["light", "dark"]:
            return build_error_response(
                "INVALID_THEME",
                "Theme must be either 'light' or 'dark'",
                400
            )
        
        # Update user theme in database
        user_id = str(current_user["_id"])
        updated_user = update_user_theme(user_id, theme_data.theme)
        
        if not updated_user:
            return build_error_response(
                "UPDATE_FAILED",
                "Failed to update user theme",
                500
            )
        
        return UserResponse(
            id=str(updated_user["_id"]),
            fullName=updated_user["fullName"],
            email=updated_user["email"],
            phone=updated_user["phone"],
            nickname=updated_user.get("nickname"),
            theme=updated_user.get("theme", "light")
        )
        
    except Exception as e:
        print(f"Error updating user theme: {e}")
        return build_error_response(
            "UPDATE_FAILED",
            f"Theme update failed: {str(e)}",
            500
        )


@router.delete("/account")
async def delete_user_account_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Permanently delete the current user's account and all associated data.
    
    Args:
        current_user: The authenticated user
        
    Returns:
        dict: Deletion confirmation message
    """
    try:
        user_id = str(current_user["_id"])
        
        # Delete user account from database
        deletion_result = delete_user_account(user_id)
        
        if not deletion_result:
            return build_error_response(
                "DELETION_FAILED",
                "Failed to delete user account",
                500
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "Account successfully deleted",
                "deleted_user_id": user_id
            }
        )
        
    except Exception as e:
        print(f"Error deleting user account: {e}")
        return build_error_response(
            "DELETION_FAILED",
            f"Account deletion failed: {str(e)}",
            500
        )