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
