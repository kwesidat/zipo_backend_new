from fastapi import APIRouter, HTTPException, status, UploadFile, File, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import supabase
from app.utils.auth_utils import AuthUtils
from typing import List
import uuid
import logging
import mimetypes

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)

def get_required_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user (required)"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    try:
        user_data = AuthUtils.verify_supabase_token(credentials.credentials)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        return user_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

@router.post("/upload/product-images", response_model=dict)
async def upload_product_images(
    files: List[UploadFile] = File(...),
    current_user = Depends(get_required_user)
):
    """
    Upload product images to Supabase Storage.
    Returns a list of public URLs for the uploaded images.
    """
    try:
        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No files provided"
            )

        # Validate file types
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
        uploaded_urls = []

        for file in files:
            # Check file type
            content_type = file.content_type
            if content_type not in allowed_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid file type: {content_type}. Allowed types: JPEG, PNG, WebP"
                )

            # Check file size (max 5MB)
            file_content = await file.read()
            file_size = len(file_content)
            max_size = 5 * 1024 * 1024  # 5MB in bytes

            if file_size > max_size:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File too large: {file.filename}. Max size: 5MB"
                )

            # Generate unique filename
            file_extension = mimetypes.guess_extension(content_type) or ".jpg"
            unique_filename = f"{current_user['user_id']}/{uuid.uuid4()}{file_extension}"

            try:
                # Upload to Supabase Storage
                response = supabase.storage.from_("product-images").upload(
                    path=unique_filename,
                    file=file_content,
                    file_options={"content-type": content_type}
                )

                # Get public URL
                public_url = supabase.storage.from_("product-images").get_public_url(unique_filename)
                uploaded_urls.append(public_url)

            except Exception as storage_error:
                logger.error(f"Storage upload error: {str(storage_error)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload {file.filename}"
                )

        return {
            "success": True,
            "urls": uploaded_urls,
            "count": len(uploaded_urls)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading images: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload images"
        )

@router.delete("/upload/product-images/{file_path:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_image(
    file_path: str,
    current_user = Depends(get_required_user)
):
    """
    Delete a product image from Supabase Storage.
    Only the user who uploaded the image can delete it.
    """
    try:
        # Ensure the file path starts with the user's ID for security
        if not file_path.startswith(current_user['user_id']):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own images"
            )

        # Delete from Supabase Storage
        try:
            supabase.storage.from_("product-images").remove([file_path])
        except Exception as storage_error:
            logger.error(f"Storage delete error: {str(storage_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete image"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete image"
        )
