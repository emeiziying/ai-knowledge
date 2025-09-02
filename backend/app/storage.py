"""
MinIO object storage integration for file management.
"""
import logging
import io
from typing import Optional, BinaryIO
from minio import Minio
from minio.error import S3Error
from .config import settings

logger = logging.getLogger(__name__)


class ObjectStorage:
    """MinIO object storage client wrapper."""
    
    def __init__(self):
        self.client = None
        self.bucket_name = settings.minio_bucket
        
    async def connect(self):
        """Initialize connection to MinIO."""
        try:
            self.client = Minio(
                settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=False  # Set to True for HTTPS
            )
            
            # Test connection by checking if bucket exists
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Created bucket: {self.bucket_name}")
            else:
                logger.info(f"Bucket {self.bucket_name} already exists")
                
            logger.info("Connected to MinIO successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to MinIO: {e}")
            raise
    
    async def upload_file(
        self, 
        file_data: BinaryIO, 
        object_name: str, 
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None
    ) -> bool:
        """
        Upload a file to MinIO.
        
        Args:
            file_data: File data as binary stream
            object_name: Name of the object in storage
            content_type: MIME type of the file
            metadata: Optional metadata dictionary
            
        Returns:
            True if upload successful, False otherwise
        """
        try:
            # Get file size
            file_data.seek(0, 2)  # Seek to end
            file_size = file_data.tell()
            file_data.seek(0)  # Reset to beginning
            
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file_data,
                length=file_size,
                content_type=content_type,
                metadata=metadata or {}
            )
            
            logger.info(f"Uploaded file: {object_name} ({file_size} bytes)")
            return True
            
        except S3Error as e:
            logger.error(f"S3 error uploading file {object_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to upload file {object_name}: {e}")
            return False
    
    async def download_file(self, object_name: str) -> Optional[bytes]:
        """
        Download a file from MinIO.
        
        Args:
            object_name: Name of the object to download
            
        Returns:
            File data as bytes, or None if failed
        """
        try:
            response = self.client.get_object(self.bucket_name, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            
            logger.info(f"Downloaded file: {object_name} ({len(data)} bytes)")
            return data
            
        except S3Error as e:
            logger.error(f"S3 error downloading file {object_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to download file {object_name}: {e}")
            return None
    
    async def delete_file(self, object_name: str) -> bool:
        """
        Delete a file from MinIO.
        
        Args:
            object_name: Name of the object to delete
            
        Returns:
            True if deletion successful, False otherwise
        """
        try:
            self.client.remove_object(self.bucket_name, object_name)
            logger.info(f"Deleted file: {object_name}")
            return True
            
        except S3Error as e:
            logger.error(f"S3 error deleting file {object_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete file {object_name}: {e}")
            return False
    
    async def file_exists(self, object_name: str) -> bool:
        """
        Check if a file exists in MinIO.
        
        Args:
            object_name: Name of the object to check
            
        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.stat_object(self.bucket_name, object_name)
            return True
        except S3Error:
            return False
        except Exception as e:
            logger.error(f"Error checking file existence {object_name}: {e}")
            return False
    
    async def get_file_info(self, object_name: str) -> Optional[dict]:
        """
        Get file information from MinIO.
        
        Args:
            object_name: Name of the object
            
        Returns:
            Dictionary with file info, or None if failed
        """
        try:
            stat = self.client.stat_object(self.bucket_name, object_name)
            return {
                "size": stat.size,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
                "metadata": stat.metadata
            }
        except S3Error as e:
            logger.error(f"S3 error getting file info {object_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to get file info {object_name}: {e}")
            return None
    
    async def list_files(self, prefix: str = "") -> list:
        """
        List files in the bucket.
        
        Args:
            prefix: Optional prefix to filter files
            
        Returns:
            List of file names
        """
        try:
            objects = self.client.list_objects(
                self.bucket_name, 
                prefix=prefix, 
                recursive=True
            )
            
            file_list = []
            for obj in objects:
                file_list.append({
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                    "etag": obj.etag
                })
            
            logger.info(f"Listed {len(file_list)} files with prefix: {prefix}")
            return file_list
            
        except S3Error as e:
            logger.error(f"S3 error listing files: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return []
    
    async def get_presigned_url(self, object_name: str, expires_in_seconds: int = 3600) -> Optional[str]:
        """
        Generate a presigned URL for file access.
        
        Args:
            object_name: Name of the object
            expires_in_seconds: URL expiration time in seconds
            
        Returns:
            Presigned URL string, or None if failed
        """
        try:
            from datetime import timedelta
            url = self.client.presigned_get_object(
                self.bucket_name, 
                object_name, 
                expires=timedelta(seconds=expires_in_seconds)
            )
            logger.info(f"Generated presigned URL for: {object_name}")
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for {object_name}: {e}")
            return None


# Global storage instance
storage = ObjectStorage()