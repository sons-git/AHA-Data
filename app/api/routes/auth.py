from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.utils.common import build_error_response
from app.database.mongo_client import register_user, login_user
from app.schemas.users import UserCreate, UserLogin, UserResponse

# Create router with prefix and tag
router = APIRouter(prefix="/api/auth", tags=["Users"])

# Endpoint to register a new user
@router.post("/register", response_model=UserResponse)
def register(user: UserCreate):
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
        
        result = register_user(user)
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
def login(user: UserLogin):
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
        
        result = login_user(user)
        
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