from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    fullName: str
    email: EmailStr
    password: str
    phone: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    fullName: str
    email: EmailStr
    phone: str
    nickname: Optional[str] = None
    theme: Optional[str] = "light"  # "light" or "dark"

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