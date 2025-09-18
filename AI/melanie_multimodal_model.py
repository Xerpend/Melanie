"""
Melanie Multimodal (GPT-5-mini) model wrapper implementing BaseAIModel interface.

This module provides:
- MelanieMultimodal class implementing BaseAIModel interface for image/PDF processing
- OpenAI API integration for multimodal tasks
- OCR and document extraction capabilities
- Image description and analysis features
- Comprehensive error handling and validation
"""

import asyncio
import base64
import json
import logging
import os
import time
from io import BytesIO
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from pathlib import Path

import httpx
from pydantic import ValidationError
from PIL import Image
import fitz  # PyMuPDF for PDF processing

# Import from API models - adjust path as needed
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'API'))

try:
    from models import (
        BaseAIModel, 
        ChatMessage, 
        ChatCompletionRequest, 
        ChatCompletionResponse,
        Tool,
        Choice,
        Usage,
        APIError,
        MessageRole
    )
except ImportError:
    # Fallback for testing - create minimal stubs
    from abc import ABC, abstractmethod
    from typing import List, Optional, Dict, Any
    from pydantic import BaseModel
    from enum import Enum
    
    class MessageRole(str, Enum):
        USER = "user"
        ASSISTANT = "assistant"
        SYSTEM = "system"
    
    class ChatMessage(BaseModel):
        role: MessageRole
        content: str
        name: Optional[str] = None
    
    class Usage(BaseModel):
        prompt_tokens: int
        completion_tokens: int
        total_tokens: int
    
    class Choice(BaseModel):
        index: int
        message: Dict[str, Any]
        finish_reason: Optional[str] = None
    
    class ChatCompletionResponse(BaseModel):
        id: str
        object: str = "chat.completion"
        created: int
        model: str
        choices: List[Choice]
        usage: Usage
        research_plan: Optional[Dict[str, Any]] = None
    
    class ToolFunction(BaseModel):
        name: str
        description: Optional[str] = None
        parameters: Optional[Dict[str, Any]] = None
    
    class Tool(BaseModel):
        function: ToolFunction
    
    class ChatCompletionRequest(BaseModel):
        model: str
        messages: List[ChatMessage]
        tools: Optional[List[Tool]] = None
    
    class BaseAIModel(ABC):
        def __init__(self, model_name: str, api_key: str, **kwargs):
            self.model_name = model_name
            self.api_key = api_key
            self.config = kwargs
        
        @abstractmethod
        async def generate(self, messages: List[ChatMessage], tools: Optional[List[Tool]] = None, **kwargs) -> ChatCompletionResponse:
            pass
        
        @abstractmethod
        async def validate_request(self, request: ChatCompletionRequest) -> bool:
            pass
        
        @abstractmethod
        def get_capabilities(self) -> List[str]:
            pass
        
        @abstractmethod
        def get_max_tokens(self) -> int:
            pass
        
        def get_model_info(self) -> Dict[str, Any]:
            return {
                "name": self.model_name,
                "capabilities": self.get_capabilities(),
                "max_tokens": self.get_max_tokens(),
                "config": self.config
            }
    
    class APIError(Exception):
        pass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ImageAnalysisResult:
    """Result from image analysis."""
    description: str
    objects_detected: List[str]
    text_extracted: str
    metadata: Dict[str, Any]
    confidence_score: float


@dataclass
class DocumentExtractionResult:
    """Result from document extraction."""
    text_content: str
    page_count: int
    images_extracted: List[str]
    metadata: Dict[str, Any]
    structure_analysis: Dict[str, Any]


class MelanieMultimodalError(Exception):
    """Custom exception for MelanieMultimodal model errors."""
    pass


class MelanieMultimodalTimeoutError(MelanieMultimodalError):
    """Timeout error for MelanieMultimodal model."""
    def __init__(self, timeout: float):
        self.timeout = timeout
        super().__init__(f"Request timed out after {timeout} seconds")


class MelanieMultimodalRateLimitError(MelanieMultimodalError):
    """Rate limit error for MelanieMultimodal model."""
    def __init__(self, retry_after: Optional[int] = None):
        self.retry_after = retry_after
        message = "Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after} seconds"
        super().__init__(message)


class ImageProcessor:
    """
    Handles image processing and analysis tasks.
    """
    
    def __init__(self):
        """Initialize image processor."""
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}
        self.max_image_size = 20 * 1024 * 1024  # 20MB
        self.max_dimension = 4096  # Max width/height
    
    def validate_image(self, image_path: Union[str, Path]) -> bool:
        """
        Validate image file.
        
        Args:
            image_path: Path to image file
            
        Returns:
            bool: True if image is valid
        """
        try:
            path = Path(image_path)
            
            # Check file exists
            if not path.exists():
                return False
            
            # Check file extension
            if path.suffix.lower() not in self.supported_formats:
                return False
            
            # Check file size
            if path.stat().st_size > self.max_image_size:
                return False
            
            # Try to open with PIL
            with Image.open(path) as img:
                # Check dimensions
                if img.width > self.max_dimension or img.height > self.max_dimension:
                    return False
                
                return True
                
        except Exception as e:
            logger.error(f"Image validation failed: {str(e)}")
            return False
    
    def encode_image_to_base64(self, image_path: Union[str, Path]) -> str:
        """
        Encode image to base64 for API transmission.
        
        Args:
            image_path: Path to image file
            
        Returns:
            str: Base64 encoded image
        """
        try:
            with open(image_path, 'rb') as image_file:
                encoded = base64.b64encode(image_file.read()).decode('utf-8')
                return encoded
        except Exception as e:
            raise MelanieMultimodalError(f"Failed to encode image: {str(e)}")
    
    def resize_image_if_needed(self, image_path: Union[str, Path]) -> Optional[str]:
        """
        Resize image if it exceeds dimension limits.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Optional[str]: Path to resized image or None if no resize needed
        """
        try:
            with Image.open(image_path) as img:
                if img.width <= self.max_dimension and img.height <= self.max_dimension:
                    return None
                
                # Calculate new dimensions maintaining aspect ratio
                ratio = min(self.max_dimension / img.width, self.max_dimension / img.height)
                new_width = int(img.width * ratio)
                new_height = int(img.height * ratio)
                
                # Resize image
                resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Save to temporary file
                temp_path = f"{image_path}_resized.jpg"
                resized.save(temp_path, "JPEG", quality=85)
                
                return temp_path
                
        except Exception as e:
            logger.error(f"Image resize failed: {str(e)}")
            return None
    
    def extract_image_metadata(self, image_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Extract metadata from image.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dict: Image metadata
        """
        try:
            with Image.open(image_path) as img:
                metadata = {
                    "format": img.format,
                    "mode": img.mode,
                    "size": img.size,
                    "width": img.width,
                    "height": img.height,
                    "has_transparency": img.mode in ('RGBA', 'LA') or 'transparency' in img.info
                }
                
                # Add EXIF data if available
                if hasattr(img, '_getexif') and img._getexif():
                    metadata["exif"] = dict(img._getexif())
                
                return metadata
                
        except Exception as e:
            logger.error(f"Metadata extraction failed: {str(e)}")
            return {}


class DocumentProcessor:
    """
    Handles PDF and document processing tasks.
    """
    
    def __init__(self):
        """Initialize document processor."""
        self.supported_formats = {'.pdf'}
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        self.max_pages = 100
    
    def validate_document(self, doc_path: Union[str, Path]) -> bool:
        """
        Validate document file.
        
        Args:
            doc_path: Path to document file
            
        Returns:
            bool: True if document is valid
        """
        try:
            path = Path(doc_path)
            
            # Check file exists
            if not path.exists():
                return False
            
            # Check file extension
            if path.suffix.lower() not in self.supported_formats:
                return False
            
            # Check file size
            if path.stat().st_size > self.max_file_size:
                return False
            
            # Try to open with PyMuPDF
            doc = fitz.open(path)
            
            # Check page count
            if len(doc) > self.max_pages:
                doc.close()
                return False
            
            doc.close()
            return True
            
        except Exception as e:
            logger.error(f"Document validation failed: {str(e)}")
            return False
    
    def extract_text_from_pdf(self, pdf_path: Union[str, Path]) -> str:
        """
        Extract text content from PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            str: Extracted text content
        """
        try:
            doc = fitz.open(pdf_path)
            text_content = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    text_content.append(f"--- Page {page_num + 1} ---\n{text}")
            
            doc.close()
            return "\n\n".join(text_content)
            
        except Exception as e:
            raise MelanieMultimodalError(f"PDF text extraction failed: {str(e)}")
    
    def extract_images_from_pdf(self, pdf_path: Union[str, Path]) -> List[str]:
        """
        Extract images from PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List[str]: List of paths to extracted images
        """
        try:
            doc = fitz.open(pdf_path)
            image_paths = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    
                    if pix.n - pix.alpha < 4:  # GRAY or RGB
                        img_path = f"{pdf_path}_page{page_num + 1}_img{img_index + 1}.png"
                        pix.save(img_path)
                        image_paths.append(img_path)
                    
                    pix = None
            
            doc.close()
            return image_paths
            
        except Exception as e:
            logger.error(f"PDF image extraction failed: {str(e)}")
            return []
    
    def analyze_document_structure(self, pdf_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Analyze document structure and metadata.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dict: Document structure analysis
        """
        try:
            doc = fitz.open(pdf_path)
            
            structure = {
                "page_count": len(doc),
                "metadata": doc.metadata,
                "has_toc": bool(doc.get_toc()),
                "pages_with_images": [],
                "pages_with_text": [],
                "total_characters": 0
            }
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Check for text
                text = page.get_text()
                if text.strip():
                    structure["pages_with_text"].append(page_num + 1)
                    structure["total_characters"] += len(text)
                
                # Check for images
                if page.get_images():
                    structure["pages_with_images"].append(page_num + 1)
            
            doc.close()
            return structure
            
        except Exception as e:
            logger.error(f"Document structure analysis failed: {str(e)}")
            return {}


class MelanieMultimodal(BaseAIModel):
    """
    Melanie Multimodal (GPT-5-mini) model wrapper implementing BaseAIModel interface.
    
    Provides multimodal capabilities including image analysis, PDF processing,
    OCR, and document extraction using OpenAI's GPT-5-mini model.
    """
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize MelanieMultimodal model.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            **kwargs: Additional configuration options
        """
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable or api_key parameter is required")
        
        super().__init__(
            model_name="gpt-4-vision-preview",  # Using available vision model
            api_key=api_key,
            **kwargs
        )
        
        # Configuration
        self.base_url = kwargs.get("base_url", "https://api.openai.com/v1")
        self.timeout = kwargs.get("timeout", 300)  # 5 minutes for multimodal processing
        self.max_retries = kwargs.get("max_retries", 3)
        self.retry_delay = kwargs.get("retry_delay", 1.0)
        
        # Multimodal settings
        self.enable_ocr = kwargs.get("enable_ocr", True)
        self.enable_image_analysis = kwargs.get("enable_image_analysis", True)
        self.enable_document_extraction = kwargs.get("enable_document_extraction", True)
        
        # Initialize processors
        self.image_processor = ImageProcessor()
        self.document_processor = DocumentProcessor()
        
        # HTTP client configuration
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
    
    def _create_multimodal_system_prompt(self) -> str:
        """
        Create system prompt optimized for multimodal tasks.
        
        Returns:
            System prompt string
        """
        return """You are Melanie, an expert AI assistant specializing in multimodal analysis including image understanding, document processing, and OCR tasks.

Your capabilities include:
1. Detailed image analysis and description
2. Object detection and recognition in images
3. Text extraction from images (OCR)
4. PDF document analysis and content extraction
5. Document structure analysis
6. Visual content understanding and interpretation

When analyzing images:
- Provide comprehensive descriptions of visual content
- Identify objects, people, text, and scenes
- Extract any readable text accurately
- Note colors, composition, and artistic elements
- Consider context and potential meanings

When processing documents:
- Extract and organize text content clearly
- Identify document structure (headings, sections, etc.)
- Summarize key information and themes
- Note any embedded images or graphics
- Preserve important formatting and layout information

Always be thorough, accurate, and helpful in your analysis."""
    
    def _format_messages_for_openai(self, messages: List[ChatMessage]) -> List[Dict[str, Any]]:
        """
        Format messages for OpenAI API with multimodal support.
        
        Args:
            messages: List of ChatMessage objects
            
        Returns:
            List of formatted message dictionaries
        """
        formatted_messages = []
        
        # Add multimodal-specific system prompt if not present
        has_system_prompt = any(msg.role == MessageRole.SYSTEM for msg in messages)
        if not has_system_prompt:
            formatted_messages.append({
                "role": "system",
                "content": self._create_multimodal_system_prompt()
            })
        
        for message in messages:
            formatted_message = {
                "role": message.role.value,
                "content": message.content
            }
            
            # Add name if provided
            if message.name:
                formatted_message["name"] = message.name
            
            formatted_messages.append(formatted_message)
        
        return formatted_messages
    
    def _create_openai_response(
        self, 
        openai_response: Dict[str, Any], 
        request_id: str,
        analysis_results: Optional[Dict[str, Any]] = None
    ) -> ChatCompletionResponse:
        """
        Convert OpenAI response to standard format with multimodal metadata.
        
        Args:
            openai_response: Raw response from OpenAI API
            request_id: Unique request identifier
            analysis_results: Optional multimodal analysis results
            
        Returns:
            ChatCompletionResponse object
        """
        # Extract choice data
        choices_data = []
        if "choices" in openai_response and openai_response["choices"]:
            for i, choice in enumerate(openai_response["choices"]):
                message = choice.get("message", {})
                
                # Add multimodal analysis metadata if available
                if analysis_results and message.get("role") == "assistant":
                    if "metadata" not in message:
                        message["metadata"] = {}
                    
                    message["metadata"]["multimodal_analysis"] = analysis_results
                
                choice_data = Choice(
                    index=i,
                    message=message,
                    finish_reason=choice.get("finish_reason")
                )
                choices_data.append(choice_data)
        else:
            # Fallback for simple response format
            choice_data = Choice(
                index=0,
                message={
                    "role": "assistant",
                    "content": str(openai_response)
                },
                finish_reason="stop"
            )
            choices_data.append(choice_data)
        
        # Extract usage data
        usage_data = openai_response.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0)
        )
        
        return ChatCompletionResponse(
            id=openai_response.get("id", request_id),
            object="chat.completion",
            created=openai_response.get("created", int(time.time())),
            model=self.model_name,
            choices=choices_data,
            usage=usage
        )
    
    async def _make_request_with_retry(
        self, 
        endpoint: str, 
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic.
        
        Args:
            endpoint: API endpoint path
            payload: Request payload
            
        Returns:
            Response data
            
        Raises:
            MelanieMultimodalError: On API or network errors
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.info(f"Making multimodal request to {endpoint} (attempt {attempt + 1})")
                
                response = await self.client.post(endpoint, json=payload)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    if attempt < self.max_retries:
                        logger.warning(f"Rate limited, waiting {retry_after} seconds")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        raise MelanieMultimodalRateLimitError(retry_after)
                
                # Handle other HTTP errors
                if response.status_code >= 400:
                    error_data = response.json() if response.content else {}
                    error_message = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                    raise MelanieMultimodalError(f"API error: {error_message}")
                
                # Success
                return response.json()
                
            except httpx.TimeoutException as e:
                last_exception = MelanieMultimodalTimeoutError(self.timeout)
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Request timed out, retrying in {delay} seconds")
                    await asyncio.sleep(delay)
                    continue
                    
            except httpx.RequestError as e:
                last_exception = MelanieMultimodalError(f"Network error: {str(e)}")
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Network error, retrying in {delay} seconds")
                    await asyncio.sleep(delay)
                    continue
                    
            except Exception as e:
                last_exception = MelanieMultimodalError(f"Unexpected error: {str(e)}")
                break
        
        # All retries exhausted
        raise last_exception or MelanieMultimodalError("Request failed after all retries")
    
    async def analyze_image(
        self, 
        image_path: Union[str, Path], 
        prompt: str = "Analyze this image in detail"
    ) -> ImageAnalysisResult:
        """
        Analyze an image using vision capabilities.
        
        Args:
            image_path: Path to image file
            prompt: Analysis prompt
            
        Returns:
            ImageAnalysisResult: Analysis results
        """
        try:
            # Validate image
            if not self.image_processor.validate_image(image_path):
                raise MelanieMultimodalError("Invalid image file")
            
            # Resize if needed
            resized_path = self.image_processor.resize_image_if_needed(image_path)
            analysis_path = resized_path or image_path
            
            # Encode image
            base64_image = self.image_processor.encode_image_to_base64(analysis_path)
            
            # Create vision request
            payload = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 1000
            }
            
            # Make request
            response = await self._make_request_with_retry("/chat/completions", payload)
            
            # Extract analysis
            description = response["choices"][0]["message"]["content"]
            
            # Extract metadata
            metadata = self.image_processor.extract_image_metadata(image_path)
            
            # Clean up resized image if created
            if resized_path and Path(resized_path).exists():
                Path(resized_path).unlink()
            
            return ImageAnalysisResult(
                description=description,
                objects_detected=[],  # Would need additional processing
                text_extracted="",    # Would need OCR processing
                metadata=metadata,
                confidence_score=0.9  # Placeholder
            )
            
        except Exception as e:
            logger.error(f"Image analysis failed: {str(e)}")
            if isinstance(e, MelanieMultimodalError):
                raise
            else:
                raise MelanieMultimodalError(f"Image analysis failed: {str(e)}")
    
    async def extract_document_content(
        self, 
        doc_path: Union[str, Path], 
        prompt: str = "Extract and summarize the content of this document"
    ) -> DocumentExtractionResult:
        """
        Extract content from a PDF document.
        
        Args:
            doc_path: Path to document file
            prompt: Extraction prompt
            
        Returns:
            DocumentExtractionResult: Extraction results
        """
        try:
            # Validate document
            if not self.document_processor.validate_document(doc_path):
                raise MelanieMultimodalError("Invalid document file")
            
            # Extract text content
            text_content = self.document_processor.extract_text_from_pdf(doc_path)
            
            # Extract images
            extracted_images = self.document_processor.extract_images_from_pdf(doc_path)
            
            # Analyze structure
            structure_analysis = self.document_processor.analyze_document_structure(doc_path)
            
            # If text is too long, truncate for API
            if len(text_content) > 50000:  # Limit for API
                text_content = text_content[:50000] + "\n... [Content truncated]"
            
            # Create analysis request
            messages = [
                ChatMessage(role=MessageRole.USER, content=f"{prompt}\n\nDocument content:\n{text_content}")
            ]
            
            # Generate analysis
            response = await self.generate(messages)
            analysis = response.choices[0].message["content"]
            
            return DocumentExtractionResult(
                text_content=text_content,
                page_count=structure_analysis.get("page_count", 0),
                images_extracted=extracted_images,
                metadata=structure_analysis.get("metadata", {}),
                structure_analysis=structure_analysis
            )
            
        except Exception as e:
            logger.error(f"Document extraction failed: {str(e)}")
            if isinstance(e, MelanieMultimodalError):
                raise
            else:
                raise MelanieMultimodalError(f"Document extraction failed: {str(e)}")
    
    async def generate(
        self, 
        messages: List[ChatMessage], 
        tools: Optional[List[Tool]] = None,
        **kwargs
    ) -> ChatCompletionResponse:
        """
        Generate chat completion using GPT-5-mini multimodal capabilities.
        
        Args:
            messages: List of chat messages
            tools: Optional list of available tools (not used for multimodal)
            **kwargs: Additional generation parameters
            
        Returns:
            ChatCompletionResponse: Generated response in OpenAI format
            
        Raises:
            MelanieMultimodalError: On generation errors
        """
        try:
            # Format request payload
            payload = {
                "model": self.model_name,
                "messages": self._format_messages_for_openai(messages),
                "max_tokens": kwargs.get("max_tokens", 2000),
                "temperature": kwargs.get("temperature", 0.7),
                "top_p": kwargs.get("top_p", 1.0)
            }
            
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            # Make request
            response_data = await self._make_request_with_retry(
                "/chat/completions", 
                payload
            )
            
            # Generate unique request ID
            request_id = f"chatcmpl-multimodal-{int(time.time())}-{hash(str(payload)) % 10000}"
            
            # Convert to standard format
            return self._create_openai_response(response_data, request_id)
            
        except Exception as e:
            logger.error(f"Generation failed: {str(e)}")
            if isinstance(e, MelanieMultimodalError):
                raise
            else:
                raise MelanieMultimodalError(f"Generation failed: {str(e)}")
    
    async def validate_request(self, request: ChatCompletionRequest) -> bool:
        """
        Validate if request is compatible with multimodal model.
        
        Args:
            request: Chat completion request
            
        Returns:
            bool: True if request is valid for this model
        """
        try:
            # Check model compatibility (accept any model for multimodal processing)
            
            # Check message count and content
            if not request.messages or len(request.messages) > 50:
                return False
            
            # Check token limits
            total_chars = sum(len(msg.content) for msg in request.messages)
            if total_chars > 200000:  # Larger limit for multimodal content
                return False
            
            # Tools are not typically used with multimodal model
            if request.tools and len(request.tools) > 5:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Request validation failed: {str(e)}")
            return False
    
    def get_capabilities(self) -> List[str]:
        """
        Get list of multimodal model capabilities.
        
        Returns:
            List[str]: List of capability names
        """
        return [
            "chat_completion",
            "image_analysis",
            "image_description",
            "ocr",
            "document_extraction",
            "pdf_processing",
            "visual_understanding",
            "multimodal_reasoning",
            "text_extraction",
            "object_detection",
            "scene_analysis",
            "document_structure_analysis"
        ]
    
    def get_max_tokens(self) -> int:
        """
        Get maximum token limit for multimodal model.
        
        Returns:
            int: Maximum token limit
        """
        return 128000  # 128k tokens for GPT-4 Vision
    
    def get_model_info(self) -> Dict[str, Any]:
        """
        Get comprehensive model information.
        
        Returns:
            Dict: Model information including capabilities and limits
        """
        info = super().get_model_info()
        info.update({
            "provider": "OpenAI",
            "version": "gpt-4-vision-preview",
            "context_window": self.get_max_tokens(),
            "supports_streaming": False,
            "supports_tools": False,
            "supports_vision": True,
            "supports_documents": True,
            "supported_image_formats": list(self.image_processor.supported_formats),
            "supported_document_formats": list(self.document_processor.supported_formats),
            "max_image_size": self.image_processor.max_image_size,
            "max_document_size": self.document_processor.max_file_size,
            "pricing_per_1k_tokens": {
                "input": 0.01,  # Example pricing
                "output": 0.03
            },
            "optimized_for": [
                "image_analysis",
                "document_processing",
                "ocr",
                "multimodal_understanding"
            ]
        })
        return info


# Convenience functions for backward compatibility
async def analyze_image_async(
    image_path: str, 
    prompt: str = "Analyze this image in detail",
    **kwargs
) -> str:
    """
    Async version of image analysis function for backward compatibility.
    
    Args:
        image_path: Path to image file
        prompt: Analysis prompt
        **kwargs: Additional parameters
        
    Returns:
        str: Image analysis result
    """
    async with MelanieMultimodal() as model:
        result = await model.analyze_image(image_path, prompt)
        return result.description


async def analyze_pdf_async(
    pdf_path: str, 
    prompt: str = "Extract and summarize the content of this document",
    **kwargs
) -> str:
    """
    Async version of PDF analysis function for backward compatibility.
    
    Args:
        pdf_path: Path to PDF file
        prompt: Analysis prompt
        **kwargs: Additional parameters
        
    Returns:
        str: PDF analysis result
    """
    async with MelanieMultimodal() as model:
        result = await model.extract_document_content(pdf_path, prompt)
        return result.text_content


# Example usage and testing
if __name__ == "__main__":
    async def test_multimodal_capabilities():
        """Test multimodal functionality."""
        try:
            async with MelanieMultimodal() as model:
                # Test basic generation
                messages = [
                    ChatMessage(role=MessageRole.USER, content="What are your multimodal capabilities?")
                ]
                
                response = await model.generate(messages)
                print(f"Response: {response.choices[0].message['content']}")
                print(f"Usage: {response.usage}")
                print(f"Capabilities: {model.get_capabilities()}")
                
        except Exception as e:
            print(f"Test failed: {str(e)}")
    
    # Run test
    asyncio.run(test_multimodal_capabilities())