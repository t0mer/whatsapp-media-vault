import os
import yaml
import requests
import shutil
from pathlib import Path
from loguru import logger
from typing import Dict, Optional, Any

class Utils:
    """
    Utility class for handling various operations including:
    - Message data processing
    - Configuration management
    - Image downloading
    - AWS Rekognition operations
    """
   
    def __init__(self):
        """Initialize Utils class with default values"""
        self.config: Dict[str, Any] = {}
        self.webhook_type: Optional[str] = None
        self.message_type: Optional[str] = None
        self.message_id: Optional[str] = None
        self.sender: Dict[str, Any] = {}
        self.chat_id: Optional[str] = None
        self.chat_name: Optional[str] = None
        self.sender_id: Optional[str] = None
        self.is_image: bool = False
        self.file_data: Dict[str, Any] = {}
        self.fileName: Optional[str] = None
        self.downloadUrl: Optional[str] = None
        self.mimeType: Optional[str] = None
        self.download_path: Optional[str] = None

    def create_application_folders(self):
        try:
            vault_base_path = Path.cwd() / "vault/"
            vault_base_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"Unable to create application folders: {str(e)}")

    def get_message_data(self, message: Dict[str, Any]) -> None:
        """
        Extract and store relevant data from incoming message.
        
        Args:
            message (Dict[str, Any]): The incoming message data
        """
        self.webhook_type = message.get('typeWebhook')
        self.message_type = self.get_media_type(message.get('messageData', {}).get('typeMessage'))
        self.message_id = message.get("idMessage")
        self.sender = message.get('senderData', {})
        self.chat_id = self.sender.get('chatId')
        self.chat_name = self.sender.get('chatName')
        self.sender_id = self.sender.get('sender')
        
        # Check if message contains an image
        if self.message_type is not None:
            self.is_image = True
            self.file_data = message.get('messageData', {}).get('fileMessageData', {})
            self.fileName = self.file_data.get('fileName')
            self.downloadUrl = self.file_data.get('downloadUrl')
            self.mimeType = self.file_data.get('mimeType')
            
    def load_config(self) -> None:
        """
        Load configuration from YAML file.
        If config.yaml doesn't exist in config directory, copy it from app directory.
        """
        config_dir = Path("config")
        config_file = config_dir / "config.yaml"
        app_config_file = Path("config.yaml")
        
        # Create config directory if it doesn't exist
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy config file if needed
        if not config_file.exists() and app_config_file.exists():
            try:
                shutil.copy2(app_config_file, config_file)
            except Exception as e:
                logger.error(f"Error copying config file: {e}")
                raise
        
        # Load configuration
        try:
            with open(config_file, 'r') as file:
                self.config = yaml.safe_load(file)
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            raise


    def get_media_type(self, msg_type: str) -> Optional[str]:
        """
        If msg_type is one of: imageMessage, videoMessage, documentMessage, audioMessage,
        return the base type without 'Message' (e.g. 'image', 'video', etc.).
        Otherwise return None.
        """
        suffix = "Message"
        if msg_type.endswith(suffix):
            base = msg_type[:-len(suffix)]
            if base in {"image", "video", "document", "audio"}:
                logger.debug(base)
                return base
        return None

    def get_vault_path(self) -> Optional[str]:
        """
        Get the collection ID for the current chat ID.
        
        Returns:
            Optional[str]: The collection ID if found, None otherwise
        """
        for kid, details in self.config.get("chats", {}).items():
            if self.chat_id in details.get("chat_ids", []):
                return details.get("media_path")
        return None        
            
    def download_image(self, vault_path: str) -> bool:
        """
        Download an image from a URL and save it to the specified path.
        
        Args:
            collection_id (str): The ID of the collection for organizing downloaded images
            
        Returns:
            bool: True if download was successful, raises Exception otherwise
            
        Raises:
            Exception: If there's an error during download
        """
        try:
            # Create download directory
            vault_base_path = Path.cwd() / "vault" / vault_path / self.message_type
            vault_base_path.mkdir(parents=True, exist_ok=True)
            # Download media
            response = requests.get(self.downloadUrl, stream=True)
            response.raise_for_status()
            
            # Save image
            self.download_path = str(vault_base_path / self.fileName)
            with open(self.download_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            return True
            
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            raise Exception(e)

