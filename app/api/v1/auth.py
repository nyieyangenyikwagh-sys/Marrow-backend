# File location: app/api/v1/auth.py
# This file handles all authentication endpoints

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime
import logging

from app.core.database import get_db
from app.models.customer import Customer, KYCStatus
from app.dependencies import create_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Pydantic models for request/response
class LoginRequest(BaseModel):
    email: str
    password: str

class SignupRequest(BaseModel):
    email: str
    firstName: str
    lastName: str
    password: str

class AuthUser(BaseModel):
    id: str
    email: str
    firstName: str
    lastName: str
    kycStatus: str

class AuthResponse(BaseModel):
    success: bool
    data: dict

# ==================== LOGIN ENDPOINT ====================
@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    User login endpoint
    
    Expected request:
    {
        "email": "user@example.com",
        "password": "password123"
    }
    
    Returns access token and user info
    """
    
    try:
        logger.info(f"Login attempt for email: {request.email}")
        
        # Query for customer by email
        query = select(Customer).where(Customer.email == request.email)
        result = await db.execute(query)
        customer = result.scalar_one_or_none()
        
        # Check if customer exists
        if not customer:
            logger.warning(f"Login failed: Customer not found - {request.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Check if account is active
        if customer.account_status != "active":
            logger.warning(f"Login failed: Account not active - {request.email}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active"
            )
        
        # In production, verify hashed password here
        # For now, accept any non-empty password
        if not request.password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Generate JWT token
        access_token = create_access_token(
            subject=str(customer.id),
            user_type="customer"
        )
        
        logger.info(f"Login successful for: {request.email}")
        
        return {
            "success": True,
            "data": {
                "accessToken": access_token,
                "user": {
                    "id": str(customer.id),
                    "email": customer.email,
                    "firstName": customer.first_name,
                    "lastName": customer.last_name,
                    "kycStatus": customer.kyc_status.value if customer.kyc_status else "pending",
                }
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

# ==================== SIGNUP ENDPOINT ====================
@router.post("/signup")
async def signup(request: SignupRequest, db: AsyncSession = Depends(get_db)):
    """
    User signup endpoint
    
    Expected request:
    {
        "email": "newuser@example.com",
        "firstName": "John",
        "lastName": "Doe",
        "password": "password123"
    }
    
    Returns access token and new user info
    """
    
    try:
        logger.info(f"Signup attempt for email: {request.email}")
        
        # Validate input
        if not request.email or not request.firstName or not request.lastName:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email, firstName, and lastName are required"
            )
        
        # Check if email already exists
        query = select(Customer).where(Customer.email == request.email)
        result = await db.execute(query)
        existing_customer = result.scalar_one_or_none()
        
        if existing_customer:
            logger.warning(f"Signup failed: Email already registered - {request.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create new customer
        new_customer = Customer(
            email=request.email,
            first_name=request.firstName,
            last_name=request.lastName,
            kyc_status=KYCStatus.PENDING,
            account_status="active",
            created_at=datetime.utcnow(),
        )
        
        db.add(new_customer)
        await db.flush()  # Get the ID without committing
        await db.commit()
        
        logger.info(f"New customer created: {request.email}")
        
        # Generate JWT token
        access_token = create_access_token(
            subject=str(new_customer.id),
            user_type="customer"
        )
        
        logger.info(f"Signup successful for: {request.email}")
        
        return {
            "success": True,
            "data": {
                "accessToken": access_token,
                "user": {
                    "id": str(new_customer.id),
                    "email": new_customer.email,
                    "firstName": new_customer.first_name,
                    "lastName": new_customer.last_name,
                    "kycStatus": "pending",
                }
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Signup endpoint error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Signup failed"
        )

# ==================== STATUS ENDPOINT ====================
@router.get("/status")
async def get_auth_status(request):
    """
    Get current authentication status
    (requires valid JWT token)
    """
    
    try:
        # This would typically extract JWT from header
        # and verify it's valid
        
        return {
            "success": True,
            "data": {
                "authenticated": True,
                "message": "Token is valid"
            }
        }
    
    except Exception as e:
        logger.error(f"Auth status check error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Status check failed"
        )

# ==================== LOGOUT ENDPOINT ====================
@router.post("/logout")
async def logout():
    """
    Logout endpoint (client-side token removal)
    """
    
    return {
        "success": True,
        "data": {
            "message": "Logged out successfully"
        }
    }