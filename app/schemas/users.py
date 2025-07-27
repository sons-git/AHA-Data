from typing import Optional
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    fullName: str
    email: EmailStr
    password: str
    phone: str

# Used when logging in
class UserLogin(BaseModel):
    email: EmailStr
    password: str
    
class UserResponse(BaseModel):
    id: str
    fullName: str
    email: EmailStr
    phone: str

class UserUpdateProfile(BaseModel):
    fullName: Optional[str] = None
    nickname: Optional[str] = None

class UserUpdateTheme(BaseModel):
    theme: str  # "light" or "dark"

class UserChangePassword(BaseModel):
    currentPassword: str
    newPassword: str
    
class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    password: str