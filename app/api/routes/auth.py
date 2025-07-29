from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.utils.common import build_error_response
from app.database.mongo_client import register_user, login_user, get_user_by_email, update_user_password
from app.schemas.users import UserCreate, UserLogin, UserResponse, ForgotPasswordRequest, ResetPasswordRequest
from app.utils.email_service import send_password_reset_email
from app.utils.token_service import generate_reset_token, verify_reset_token, invalidate_reset_token

# Create router with prefix and tag
router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Endpoint to register a new user
@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate):
    """
    Register a new user in the system.

    Args:
        user (UserCreate): The user registration data including email, password, and any other required fields.

    Returns:
        UserResponse: The registered user data including user ID and other non-sensitive information.
    """
    try:
        if not user:
            return build_error_response(
                "INVALID_INPUT",
                "User data is required",
                400
            )
        
        if not user.email:
            return build_error_response(
                "INVALID_INPUT",
                "Email is required",
                400
            )
        
        if not user.password:
            return build_error_response(
                "INVALID_INPUT",
                "Password is required",
                400
            )
        
        if not user.fullName:
            return build_error_response(
                "INVALID_INPUT",
                "Full name is required",
                400
            )
        
        # Validate email format (basic check)
        if "@" not in user.email or "." not in user.email:
            return build_error_response(
                "INVALID_EMAIL_FORMAT",
                "Invalid email format",
                400
            )
        
        # Validate password strength (basic check)
        if len(user.password) < 6:
            return build_error_response(
                "WEAK_PASSWORD",
                "Password must be at least 6 characters long",
                400
            )
        
        result = await register_user(user)
        print("Serialized user result:", result)
        
        # Check if result is an error response
        if isinstance(result, JSONResponse):
            return result
        
        if not result:
            return build_error_response(
                "REGISTRATION_FAILED",
                "User registration failed",
                500
            )
        
        return result
        
    except ValueError as ve:
        # Handle specific ValueError (like user already exists)
        if "already exists" in str(ve).lower():
            return build_error_response(
                "USER_ALREADY_EXISTS",
                "User with this email already exists",
                409
            )
        return build_error_response(
            "INVALID_INPUT",
            str(ve),
            400
        )
    except Exception as e:
        print("Unexpected error:", e)
        return build_error_response(
            "REGISTRATION_FAILED",
            f"Registration failed: {str(e)}",
            500
        )


# Endpoint to login a user
@router.post("/login", response_model=UserResponse)
async def login(user: UserLogin):
    """
    Authenticate an existing user and return user information.

    Args:
        user (UserLogin): The user login credentials, typically email and password.

    Returns:
        UserResponse: The authenticated user data including user ID and profile details.
    """
    try:
        if not user:
            return build_error_response(
                "INVALID_INPUT",
                "Login credentials are required",
                400
            )
        
        if not user.email:
            return build_error_response(
                "INVALID_INPUT",
                "Email is required",
                400
            )
        
        if not user.password:
            return build_error_response(
                "INVALID_INPUT",
                "Password is required",
                400
            )
        
        # Validate email format (basic check)
        if "@" not in user.email or "." not in user.email:
            return build_error_response(
                "INVALID_EMAIL_FORMAT",
                "Invalid email format",
                400
            )
        
        print("Login user")
        result = await login_user(user)
        
        print(result)
        
        # Check if result is an error response
        if isinstance(result, JSONResponse):
            return result
        
        if not result:
            return build_error_response(
                "INVALID_CREDENTIALS",
                "Invalid email or password",
                401
            )
        
        return result
        
    except Exception as e:
        print("Unexpected error during login:", e)
        return build_error_response(
            "LOGIN_FAILED",
            f"Login failed: {str(e)}",
            500
        )


# Endpoint for forgot password
@router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    """
    Send password reset link to user's email.

    Args:
        request (ForgotPasswordRequest): Contains the email address.

    Returns:
        JSONResponse: Success message or error response.
    """
    try:
        if not request.email:
            return build_error_response(
                "INVALID_INPUT",
                "Email is required",
                400
            )
        
        # Validate email format
        if "@" not in request.email or "." not in request.email:
            return build_error_response(
                "INVALID_EMAIL_FORMAT",
                "Invalid email format",
                400
            )
        
        # Check if user exists
        user = await get_user_by_email(request.email)
        if not user:
            # Don't reveal if email exists or not for security
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "If an account with this email exists, a password reset link has been sent."
                }
            )
        
        # Generate reset token
        reset_token = await generate_reset_token(request.email)
        
        # Send email with reset link
        reset_link = f"http://localhost:5173/reset-password?token={reset_token}"
        
        email_sent = await send_password_reset_email(
            email=request.email,
            reset_link=reset_link,
            user_name=user.get('fullName', 'User')
        )
        
        if not email_sent:
            return build_error_response(
                "EMAIL_SEND_FAILED",
                "Failed to send password reset email",
                500
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Password reset link has been sent to your email address."
            }
        )
        
    except Exception as e:
        print("Unexpected error during forgot password:", e)
        return build_error_response(
            "FORGOT_PASSWORD_FAILED",
            f"Failed to process forgot password request: {str(e)}",
            500
        )


# Endpoint to verify reset token
@router.get("/verify-reset-token")
async def verify_password_reset_token(token: str):
    """
    Verify if a password reset token is valid.

    Args:
        token (str): The reset token to verify.

    Returns:
        JSONResponse: Token validity status.
    """
    try:
        if not token:
            return JSONResponse(
                status_code=400,
                content={"valid": False, "message": "Token is required"}
            )
        
        is_valid = await verify_reset_token(token)
        
        return JSONResponse(
            status_code=200,
            content={"valid": is_valid}
        )
        
    except Exception as e:
        print("Error verifying reset token:", e)
        return JSONResponse(
            status_code=200,
            content={"valid": False}
        )


# Endpoint for reset password
@router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest):
    """
    Reset user's password using a valid reset token.

    Args:
        request (ResetPasswordRequest): Contains the reset token and new password.

    Returns:
        JSONResponse: Success message or error response.
    """
    try:
        if not request.token:
            return build_error_response(
                "INVALID_INPUT",
                "Reset token is required",
                400
            )
        
        if not request.password:
            return build_error_response(
                "INVALID_INPUT",
                "New password is required",
                400
            )
        
        # Validate password strength
        if len(request.password) < 6:
            return build_error_response(
                "WEAK_PASSWORD",
                "Password must be at least 6 characters long",
                400
            )
        
        # Verify reset token and get email
        email = await verify_reset_token(request.token)
        if not email:
            return build_error_response(
                "INVALID_TOKEN",
                "Invalid or expired reset token",
                400
            )
        
        # Get user by email
        user = await get_user_by_email(email)
        if not user:
            return build_error_response(
                "USER_NOT_FOUND",
                "User not found",
                404
            )
        
        # Update password
        password_updated = await update_user_password(email, request.password)
        if not password_updated:
            return build_error_response(
                "PASSWORD_UPDATE_FAILED",
                "Failed to update password",
                500
            )
        
        # Invalidate the reset token
        await invalidate_reset_token(request.token)
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Password has been reset successfully."
            }
        )
        
    except Exception as e:
        print("Unexpected error during password reset:", e)
        return build_error_response(
            "RESET_PASSWORD_FAILED",
            f"Failed to reset password: {str(e)}",
            500
        )