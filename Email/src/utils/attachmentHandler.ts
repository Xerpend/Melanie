export interface AttachmentFile {
  id: string;
  name: string;
  size: number;
  type: string;
  url?: string;
  data?: ArrayBuffer;
  preview?: string;
}

export interface UploadProgress {
  fileId: string;
  progress: number;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  error?: string;
}

export class AttachmentHandler {
  private maxFileSize: number;
  private allowedTypes: string[];
  private maxTotalSize: number;

  constructor(options: {
    maxFileSize?: number;
    allowedTypes?: string[];
    maxTotalSize?: number;
  } = {}) {
    this.maxFileSize = options.maxFileSize || 25 * 1024 * 1024; // 25MB
    this.allowedTypes = options.allowedTypes || [
      // Images
      'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml',
      // Documents
      'application/pdf', 'application/msword', 
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-powerpoint',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      // Text files
      'text/plain', 'text/csv', 'text/html', 'text/css', 'text/javascript',
      'application/json', 'application/xml',
      // Archives
      'application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed',
      // Other
      'application/octet-stream'
    ];
    this.maxTotalSize = options.maxTotalSize || 100 * 1024 * 1024; // 100MB
  }

  /**
   * Validate files before processing
   */
  validateFiles(files: File[]): { valid: File[]; invalid: Array<{ file: File; reason: string }> } {
    const valid: File[] = [];
    const invalid: Array<{ file: File; reason: string }> = [];

    let totalSize = 0;

    for (const file of files) {
      // Check file size
      if (file.size > this.maxFileSize) {
        invalid.push({
          file,
          reason: `File size exceeds ${this.formatFileSize(this.maxFileSize)} limit`
        });
        continue;
      }

      // Check file type
      if (!this.allowedTypes.includes(file.type) && file.type !== '') {
        // Allow files without type if they have safe extensions
        const extension = this.getFileExtension(file.name).toLowerCase();
        const safeExtensions = ['.txt', '.md', '.json', '.csv', '.log'];
        
        if (!safeExtensions.includes(extension)) {
          invalid.push({
            file,
            reason: `File type '${file.type || 'unknown'}' is not allowed`
          });
          continue;
        }
      }

      totalSize += file.size;

      // Check total size
      if (totalSize > this.maxTotalSize) {
        invalid.push({
          file,
          reason: `Total attachment size exceeds ${this.formatFileSize(this.maxTotalSize)} limit`
        });
        continue;
      }

      valid.push(file);
    }

    return { valid, invalid };
  }

  /**
   * Process files into AttachmentFile objects
   */
  async processFiles(files: File[]): Promise<AttachmentFile[]> {
    const { valid } = this.validateFiles(files);
    const attachments: AttachmentFile[] = [];

    for (const file of valid) {
      const attachment: AttachmentFile = {
        id: this.generateId(),
        name: file.name,
        size: file.size,
        type: file.type || this.getMimeTypeFromExtension(file.name),
        data: await this.fileToArrayBuffer(file)
      };

      // Generate preview for images
      if (this.isImage(file.type)) {
        attachment.preview = await this.generateImagePreview(file);
      }

      attachments.push(attachment);
    }

    return attachments;
  }

  /**
   * Upload attachments to server
   */
  async uploadAttachments(
    attachments: AttachmentFile[],
    onProgress?: (progress: UploadProgress) => void
  ): Promise<AttachmentFile[]> {
    const uploadedAttachments: AttachmentFile[] = [];

    for (const attachment of attachments) {
      try {
        onProgress?.({
          fileId: attachment.id,
          progress: 0,
          status: 'uploading'
        });

        const formData = new FormData();
        const blob = new Blob([attachment.data!], { type: attachment.type });
        formData.append('file', blob, attachment.name);
        formData.append('type', 'email-attachment');

        const response = await fetch('/api/files', {
          method: 'POST',
          body: formData,
          headers: {
            'Authorization': `Bearer ${this.getApiKey()}`
          }
        });

        if (!response.ok) {
          throw new Error(`Upload failed: ${response.statusText}`);
        }

        const result = await response.json();
        
        const uploadedAttachment: AttachmentFile = {
          ...attachment,
          url: result.url,
          data: undefined // Remove data after upload to save memory
        };

        uploadedAttachments.push(uploadedAttachment);

        onProgress?.({
          fileId: attachment.id,
          progress: 100,
          status: 'completed'
        });

      } catch (error) {
        console.error(`Failed to upload ${attachment.name}:`, error);
        
        onProgress?.({
          fileId: attachment.id,
          progress: 0,
          status: 'error',
          error: error instanceof Error ? error.message : 'Upload failed'
        });
      }
    }

    return uploadedAttachments;
  }

  /**
   * Download attachment from server
   */
  async downloadAttachment(attachment: AttachmentFile): Promise<void> {
    if (!attachment.url) {
      throw new Error('Attachment URL not available');
    }

    try {
      const response = await fetch(attachment.url, {
        headers: {
          'Authorization': `Bearer ${this.getApiKey()}`
        }
      });

      if (!response.ok) {
        throw new Error(`Download failed: ${response.statusText}`);
      }

      const blob = await response.blob();
      this.downloadBlob(blob, attachment.name);

    } catch (error) {
      console.error(`Failed to download ${attachment.name}:`, error);
      throw error;
    }
  }

  /**
   * Generate thumbnail for image attachments
   */
  async generateImagePreview(file: File, maxSize: number = 200): Promise<string> {
    return new Promise((resolve, reject) => {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      const img = new Image();

      img.onload = () => {
        // Calculate dimensions
        const { width, height } = this.calculateThumbnailSize(
          img.width,
          img.height,
          maxSize
        );

        canvas.width = width;
        canvas.height = height;

        // Draw and compress
        ctx?.drawImage(img, 0, 0, width, height);
        resolve(canvas.toDataURL('image/jpeg', 0.8));
      };

      img.onerror = () => reject(new Error('Failed to load image'));
      img.src = URL.createObjectURL(file);
    });
  }

  /**
   * Check if file is an image
   */
  isImage(mimeType: string): boolean {
    return mimeType.startsWith('image/');
  }

  /**
   * Check if file is a document
   */
  isDocument(mimeType: string): boolean {
    const documentTypes = [
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-powerpoint',
      'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    ];
    return documentTypes.includes(mimeType);
  }

  /**
   * Format file size for display
   */
  formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  /**
   * Get file extension
   */
  private getFileExtension(filename: string): string {
    return filename.substring(filename.lastIndexOf('.'));
  }

  /**
   * Get MIME type from file extension
   */
  private getMimeTypeFromExtension(filename: string): string {
    const extension = this.getFileExtension(filename).toLowerCase();
    const mimeTypes: Record<string, string> = {
      '.txt': 'text/plain',
      '.md': 'text/markdown',
      '.json': 'application/json',
      '.csv': 'text/csv',
      '.pdf': 'application/pdf',
      '.jpg': 'image/jpeg',
      '.jpeg': 'image/jpeg',
      '.png': 'image/png',
      '.gif': 'image/gif',
      '.webp': 'image/webp',
      '.svg': 'image/svg+xml',
      '.zip': 'application/zip',
      '.rar': 'application/x-rar-compressed',
      '.7z': 'application/x-7z-compressed'
    };
    return mimeTypes[extension] || 'application/octet-stream';
  }

  /**
   * Convert File to ArrayBuffer
   */
  private async fileToArrayBuffer(file: File): Promise<ArrayBuffer> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as ArrayBuffer);
      reader.onerror = () => reject(new Error('Failed to read file'));
      reader.readAsArrayBuffer(file);
    });
  }

  /**
   * Calculate thumbnail dimensions
   */
  private calculateThumbnailSize(
    originalWidth: number,
    originalHeight: number,
    maxSize: number
  ): { width: number; height: number } {
    if (originalWidth <= maxSize && originalHeight <= maxSize) {
      return { width: originalWidth, height: originalHeight };
    }

    const ratio = Math.min(maxSize / originalWidth, maxSize / originalHeight);
    return {
      width: Math.round(originalWidth * ratio),
      height: Math.round(originalHeight * ratio)
    };
  }

  /**
   * Download blob as file
   */
  private downloadBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  /**
   * Generate unique ID
   */
  private generateId(): string {
    return Math.random().toString(36).substring(2) + Date.now().toString(36);
  }

  /**
   * Get API key from environment or storage
   */
  private getApiKey(): string {
    // In a real implementation, this would get the API key from secure storage
    return localStorage.getItem('melanie_api_key') || '';
  }
}

export const attachmentHandler = new AttachmentHandler();