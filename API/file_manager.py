"""
File Management System for Melanie AI API

This module implements:
- File storage and retrieval system
- Auto-processing for TXT/MD files via RAG integration
- PDF/image metadata storage for multimodal processing
- File validation and content checks
- Secure file operations with proper error handling
"""

import asyncio
import hashlib
import json
import logging
import mimetypes
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile
from pydantic import BaseModel

from models import FileInfo, FileType, FileUploadRequest, InputSanitizer

# Configure logging
logger = logging.getLogger(__name__)


class FileProcessingResult(BaseModel):
    """Result of file processing operations."""
    success: bool
    message: str
    rag_ingested: bool = False
    metadata_extracted: bool = False
    processing_time: float = 0.0
    error: Optional[str] = None


class FileStorageConfig:
    """Configuration for file storage system."""
    
    def __init__(self):
        self.base_storage_path = Path(os.getenv("FILE_STORAGE_PATH", "file_storage"))
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE", "52428800"))  # 50MB
        self.allowed_extensions = {
            '.txt', '.md', '.pdf', '.jpg', '.jpeg', '.png', '.webp', '.json'
        }
        self.auto_process_extensions = {'.txt', '.md'}
        self.multimodal_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.webp'}
        
        # Create storage directories
        self.base_storage_path.mkdir(exist_ok=True)
        (self.base_storage_path / "uploads").mkdir(exist_ok=True)
        (self.base_storage_path / "processed").mkdir(exist_ok=True)
        (self.base_storage_path / "metadata").mkdir(exist_ok=True)


class FileManager:
    """
    File management system with RAG integration and multimodal support.
    
    Handles file uploads, storage, processing, and retrieval with proper
    validation and security measures.
    """
    
    def __init__(self, config: Optional[FileStorageConfig] = None):
        """
        Initialize file manager.
        
        Args:
            config: File storage configuration
        """
        self.config = config or FileStorageConfig()
        self.files_db: Dict[str, FileInfo] = {}
        self.rag_client = None
        
        # Load existing files database
        self._load_files_database()
    
    def _load_files_database(self):
        """Load files database from disk."""
        db_path = self.config.base_storage_path / "files_db.json"
        
        if db_path.exists():
            try:
                with open(db_path, 'r') as f:
                    data = json.load(f)
                
                # Convert to FileInfo objects
                for file_id, file_data in data.items():
                    file_data['uploaded_at'] = datetime.fromisoformat(file_data['uploaded_at'])
                    self.files_db[file_id] = FileInfo(**file_data)
                
                logger.info(f"Loaded {len(self.files_db)} files from database")
                
            except Exception as e:
                logger.error(f"Failed to load files database: {e}")
                self.files_db = {}
    
    def _save_files_database(self):
        """Save files database to disk."""
        db_path = self.config.base_storage_path / "files_db.json"
        
        try:
            # Convert FileInfo objects to dict
            data = {}
            for file_id, file_info in self.files_db.items():
                file_dict = file_info.model_dump()
                file_dict['uploaded_at'] = file_info.uploaded_at.isoformat()
                data[file_id] = file_dict
            
            with open(db_path, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save files database: {e}")
    
    def _generate_file_id(self) -> str:
        """Generate unique file ID."""
        return str(uuid.uuid4())
    
    def _get_file_hash(self, content: bytes) -> str:
        """Generate SHA-256 hash of file content."""
        return hashlib.sha256(content).hexdigest()
    
    def _validate_file_upload(self, file: UploadFile) -> FileUploadRequest:
        """
        Validate file upload request.
        
        Args:
            file: Uploaded file
            
        Returns:
            FileUploadRequest: Validated upload request
            
        Raises:
            HTTPException: If validation fails
        """
        try:
            # Basic validation
            if not file.filename:
                raise ValueError("Filename is required")
            
            if not file.content_type:
                raise ValueError("Content type is required")
            
            # Get file size (this is an approximation)
            file_size = 0
            if hasattr(file, 'size') and file.size:
                file_size = file.size
            
            # Validate using Pydantic model
            upload_request = FileUploadRequest(
                filename=file.filename,
                content_type=file.content_type,
                size=file_size
            )
            
            # Additional security checks
            file_extension = Path(upload_request.filename).suffix.lower()
            if file_extension not in self.config.allowed_extensions:
                raise ValueError(f"File extension {file_extension} not allowed")
            
            return upload_request
            
        except Exception as e:
            logger.error(f"File validation failed: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"File validation failed: {str(e)}"
            )
    
    async def _read_file_content(self, file: UploadFile) -> bytes:
        """
        Read file content with size validation.
        
        Args:
            file: Uploaded file
            
        Returns:
            bytes: File content
            
        Raises:
            HTTPException: If file is too large or read fails
        """
        try:
            content = await file.read()
            
            if len(content) > self.config.max_file_size:
                raise ValueError(f"File size {len(content)} exceeds maximum {self.config.max_file_size}")
            
            if len(content) == 0:
                raise ValueError("File is empty")
            
            return content
            
        except Exception as e:
            logger.error(f"Failed to read file content: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to read file: {str(e)}"
            )
    
    def _store_file_content(self, file_id: str, content: bytes, filename: str) -> Path:
        """
        Store file content to disk.
        
        Args:
            file_id: Unique file identifier
            content: File content
            filename: Original filename
            
        Returns:
            Path: Path to stored file
        """
        # Create safe filename
        safe_filename = InputSanitizer.sanitize_text(filename, max_length=255)
        file_extension = Path(safe_filename).suffix
        stored_filename = f"{file_id}{file_extension}"
        
        # Store in uploads directory
        file_path = self.config.base_storage_path / "uploads" / stored_filename
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        logger.info(f"Stored file {file_id} at {file_path}")
        return file_path
    
    async def _process_text_file(self, file_id: str, content: str) -> FileProcessingResult:
        """
        Process text/markdown file through RAG system.
        
        Args:
            file_id: File identifier
            content: Text content
            
        Returns:
            FileProcessingResult: Processing result
        """
        start_time = datetime.now()
        
        try:
            # Import RAG client here to avoid circular imports
            if self.rag_client is None:
                try:
                    import sys
                    ai_path = os.path.join(os.path.dirname(__file__), '..', 'AI')
                    if ai_path not in sys.path:
                        sys.path.insert(0, ai_path)
                    from rag_integration_client import RagIntegrationPipeline
                    self.rag_client = RagIntegrationPipeline()
                except ImportError as e:
                    logger.warning(f"RAG client not available: {e}")
                    return FileProcessingResult(
                        success=False,
                        message="RAG system not available",
                        error=str(e)
                    )
            
            # Prepare document for RAG ingestion
            document = {
                "content": content,
                "metadata": {
                    "file_id": file_id,
                    "source": "file_upload",
                    "processed_at": datetime.utcnow().isoformat()
                }
            }
            
            # Ingest into RAG system
            documents = [document]
            async with self.rag_client as rag:
                await rag.process_documents_for_rag(documents)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"Successfully processed text file {file_id} through RAG in {processing_time:.2f}s")
            
            return FileProcessingResult(
                success=True,
                message="File processed through RAG system",
                rag_ingested=True,
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"RAG processing failed for file {file_id}: {e}")
            
            return FileProcessingResult(
                success=False,
                message="RAG processing failed",
                processing_time=processing_time,
                error=str(e)
            )
    
    def _extract_multimodal_metadata(self, file_id: str, content: bytes, content_type: str) -> FileProcessingResult:
        """
        Extract metadata from PDF/image files for multimodal processing.
        
        Args:
            file_id: File identifier
            content: File content
            content_type: MIME type
            
        Returns:
            FileProcessingResult: Processing result
        """
        start_time = datetime.now()
        
        try:
            metadata = {
                "file_id": file_id,
                "content_type": content_type,
                "size": len(content),
                "extracted_at": datetime.utcnow().isoformat()
            }
            
            # Basic metadata extraction based on file type
            if content_type.startswith('image/'):
                # For images, we can extract basic info
                metadata.update({
                    "type": "image",
                    "format": content_type.split('/')[-1],
                    "ready_for_multimodal": True
                })
                
            elif content_type == 'application/pdf':
                # For PDFs, mark as ready for multimodal processing
                metadata.update({
                    "type": "pdf",
                    "ready_for_multimodal": True,
                    "pages": "unknown"  # Would need PDF library to extract
                })
            
            # Store metadata
            metadata_path = self.config.base_storage_path / "metadata" / f"{file_id}.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(f"Extracted metadata for multimodal file {file_id} in {processing_time:.2f}s")
            
            return FileProcessingResult(
                success=True,
                message="Metadata extracted for multimodal processing",
                metadata_extracted=True,
                processing_time=processing_time
            )
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Metadata extraction failed for file {file_id}: {e}")
            
            return FileProcessingResult(
                success=False,
                message="Metadata extraction failed",
                processing_time=processing_time,
                error=str(e)
            )
    
    async def upload_file(self, file: UploadFile) -> Tuple[str, FileInfo]:
        """
        Upload and process a file.
        
        Args:
            file: Uploaded file
            
        Returns:
            Tuple of (file_id, FileInfo)
            
        Raises:
            HTTPException: If upload or processing fails
        """
        try:
            # Validate file
            upload_request = self._validate_file_upload(file)
            
            # Read file content
            content = await self._read_file_content(file)
            
            # Generate file ID and hash
            file_id = self._generate_file_id()
            content_hash = self._get_file_hash(content)
            
            # Check for duplicate files
            for existing_id, existing_info in self.files_db.items():
                if hasattr(existing_info, 'content_hash') and existing_info.content_hash == content_hash:
                    logger.info(f"Duplicate file detected, returning existing file {existing_id}")
                    return existing_id, existing_info
            
            # Store file content
            file_path = self._store_file_content(file_id, content, upload_request.filename)
            
            # Create file info
            file_info = FileInfo(
                id=file_id,
                filename=upload_request.filename,
                content_type=upload_request.content_type,
                size=len(content),
                uploaded_at=datetime.utcnow(),
                processed=False,
                rag_ingested=False
            )
            
            # Add content hash for duplicate detection
            file_info.content_hash = content_hash
            
            # Store in database
            self.files_db[file_id] = file_info
            self._save_files_database()
            
            # Process file based on type
            file_extension = Path(upload_request.filename).suffix.lower()
            
            if file_extension in self.config.auto_process_extensions:
                # Auto-process TXT/MD files through RAG
                try:
                    text_content = content.decode('utf-8')
                    processing_result = await self._process_text_file(file_id, text_content)
                    
                    if processing_result.success:
                        file_info.rag_ingested = True
                        file_info.processed = True
                        logger.info(f"Auto-processed text file {file_id} through RAG")
                    else:
                        logger.warning(f"Auto-processing failed for {file_id}: {processing_result.error}")
                        
                except UnicodeDecodeError:
                    logger.warning(f"Could not decode text file {file_id} as UTF-8")
                    
            elif file_extension in self.config.multimodal_extensions:
                # Extract metadata for multimodal files
                processing_result = self._extract_multimodal_metadata(
                    file_id, content, upload_request.content_type
                )
                
                if processing_result.success:
                    file_info.processed = True
                    logger.info(f"Extracted metadata for multimodal file {file_id}")
                else:
                    logger.warning(f"Metadata extraction failed for {file_id}: {processing_result.error}")
            
            # Update database with processing results
            self.files_db[file_id] = file_info
            self._save_files_database()
            
            logger.info(f"Successfully uploaded file {file_id}: {upload_request.filename}")
            return file_id, file_info
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"File upload failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"File upload failed: {str(e)}"
            )
    
    def get_file_info(self, file_id: str) -> Optional[FileInfo]:
        """
        Get file information.
        
        Args:
            file_id: File identifier
            
        Returns:
            FileInfo or None if not found
        """
        return self.files_db.get(file_id)
    
    def get_file_content(self, file_id: str) -> Optional[bytes]:
        """
        Get file content.
        
        Args:
            file_id: File identifier
            
        Returns:
            File content as bytes or None if not found
        """
        file_info = self.get_file_info(file_id)
        if not file_info:
            return None
        
        try:
            # Construct file path
            file_extension = Path(file_info.filename).suffix
            stored_filename = f"{file_id}{file_extension}"
            file_path = self.config.base_storage_path / "uploads" / stored_filename
            
            if not file_path.exists():
                logger.error(f"File content not found on disk: {file_path}")
                return None
            
            with open(file_path, 'rb') as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"Failed to read file content for {file_id}: {e}")
            return None
    
    def delete_file(self, file_id: str) -> bool:
        """
        Delete a file and its associated data.
        
        Args:
            file_id: File identifier
            
        Returns:
            True if deleted successfully, False otherwise
        """
        file_info = self.get_file_info(file_id)
        if not file_info:
            return False
        
        try:
            # Delete file content
            file_extension = Path(file_info.filename).suffix
            stored_filename = f"{file_id}{file_extension}"
            file_path = self.config.base_storage_path / "uploads" / stored_filename
            
            if file_path.exists():
                file_path.unlink()
            
            # Delete metadata if exists
            metadata_path = self.config.base_storage_path / "metadata" / f"{file_id}.json"
            if metadata_path.exists():
                metadata_path.unlink()
            
            # Remove from database
            del self.files_db[file_id]
            self._save_files_database()
            
            logger.info(f"Successfully deleted file {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            return False
    
    def list_files(self, limit: int = 100, offset: int = 0) -> List[FileInfo]:
        """
        List uploaded files with pagination.
        
        Args:
            limit: Maximum number of files to return
            offset: Number of files to skip
            
        Returns:
            List of FileInfo objects
        """
        files = list(self.files_db.values())
        
        # Sort by upload date (newest first)
        files.sort(key=lambda x: x.uploaded_at, reverse=True)
        
        # Apply pagination
        return files[offset:offset + limit]
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.
        
        Returns:
            Dictionary with storage statistics
        """
        total_files = len(self.files_db)
        total_size = sum(file_info.size for file_info in self.files_db.values())
        processed_files = sum(1 for file_info in self.files_db.values() if file_info.processed)
        rag_ingested_files = sum(1 for file_info in self.files_db.values() if file_info.rag_ingested)
        
        # Count by file type
        type_counts = {}
        for file_info in self.files_db.values():
            content_type = file_info.content_type
            type_counts[content_type] = type_counts.get(content_type, 0) + 1
        
        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "processed_files": processed_files,
            "rag_ingested_files": rag_ingested_files,
            "file_types": type_counts,
            "storage_path": str(self.config.base_storage_path)
        }


# Global file manager instance
file_manager = FileManager()