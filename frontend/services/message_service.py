"""
Message service for chat functionality.

This module provides message management, AI integration, and real-time
chat capabilities using WebSocket connections.
"""

import asyncio
import base64
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, field
from enum import Enum

from .api_client import api_client
from .error_handler import handle_api_error, handle_network_error
from utils.helpers import generate_id, format_timestamp
from utils.validators import validate_message_data, sanitize_input
from .websocket_service import websocket_service


class MessageType(Enum):
    """Message types enumeration."""
    TEXT = "text"
    FILE = "file"
    TOOL = "tool"
    SYSTEM = "system"
    ERROR = "error"
    TYPING = "typing"


class MessageStatus(Enum):
    """Message status enumeration."""
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    PROCESSING = "processing"


class MessageRole(Enum):
    """Message roles."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class FileAttachment:
    """File attachment data model."""
    id: str
    filename: str
    file_type: str
    file_size: int
    url: Optional[str] = None
    content: Optional[bytes] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ToolResult:
    """Tool execution result data model."""
    tool_name: str
    tool_id: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    execution_time: float
    status: str  # success, error, timeout
    error_message: Optional[str] = None


@dataclass
class Message:
    """Message data model."""
    id: str
    content: str
    role: str  # "user" or "assistant"
    message_type: str = "text"
    timestamp: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Conversation:
    """Conversation model."""
    id: Optional[int] = None
    title: str = ""
    assistant_id: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    messages: List[Message] = field(default_factory=list)


@dataclass
class AdvancedMessage:
    """Advanced message data model with support for different types."""
    id: str
    conversation_id: str
    content: str
    role: str  # user, assistant, system
    message_type: MessageType
    status: MessageStatus
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    file_attachments: Optional[List[FileAttachment]] = None
    tool_results: Optional[List[ToolResult]] = None
    reply_to: Optional[str] = None
    is_edited: bool = False
    edit_history: Optional[List[Dict[str, Any]]] = None


class MessageService:
    """Service for managing chat messages and AI interactions."""
    
    def __init__(self):
        """Initialize the message service."""
        self.current_conversation_id: Optional[str] = None
        self.messages: List[Message] = []
        self.is_connected = False
        self.is_typing = False
        
        # Setup WebSocket handlers
        self._setup_websocket_handlers()
    
    def _setup_websocket_handlers(self):
        """Setup WebSocket message handlers."""
        @websocket_service.on_message("message")
        async def handle_message(data: Dict[str, Any]):
            """Handle incoming message."""
            message = Message(
                id=data.get("id", ""),
                content=data.get("content", ""),
                role=data.get("role", "user"),
                message_type=data.get("message_type", "text"),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
                metadata=data.get("metadata")
            )
            
            # Add message to local list
            self.messages.append(message)
            
            # Notify listeners
            await self._notify_message_received(message)
        
        @websocket_service.on_message("typing")
        async def handle_typing(data: Dict[str, Any]):
            """Handle typing indicator."""
            user_id = data.get("user_id")
            is_typing = data.get("is_typing", False)
            
            if user_id and user_id != "assistant":  # Don't show typing for assistant
                await self._notify_typing_changed(str(user_id), is_typing)
        
        @websocket_service.on_message("ai_response")
        async def handle_ai_response(data: Dict[str, Any]):
            """Handle AI response."""
            message = Message(
                id=data.get("id", ""),
                content=data.get("content", ""),
                role="assistant",
                message_type=data.get("message_type", "text"),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
                metadata=data.get("metadata")
            )
            
            # Add message to local list
            self.messages.append(message)
            
            # Notify listeners
            await self._notify_message_received(message)
        
        websocket_service.on_connect(self._on_websocket_connect)
        websocket_service.on_disconnect(self._on_websocket_disconnect)
    
    async def _on_websocket_connect(self):
        """Handle WebSocket connection."""
        self.is_connected = True
        await self._notify_connection_changed(True)
    
    async def _on_websocket_disconnect(self):
        """Handle WebSocket disconnection."""
        self.is_connected = False
        await self._notify_connection_changed(False)
    
    async def connect_to_conversation(self, conversation_id: str) -> bool:
        """
        Connect to a conversation for real-time chat.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.current_conversation_id = conversation_id
            
            # Connect to WebSocket
            await websocket_service.connect(f"/api/v1/chat/ws/{conversation_id}")
            
            # Load existing messages
            await self.load_messages(conversation_id)
            
            return True
            
        except Exception as e:
            print(f"Failed to connect to conversation: {e}")
            return False
    
    async def disconnect_from_conversation(self):
        """Disconnect from current conversation."""
        if self.current_conversation_id:
            try:
                await websocket_service.leave_conversation(int(self.current_conversation_id))
                await websocket_service.disconnect()
            except Exception as e:
                print(f"Error disconnecting: {e}")
            finally:
                self.current_conversation_id = None
                self.messages.clear()
    
    async def send_message(self, content: str, message_type: str = "text") -> Optional[Message]:
        """
        Send a message to the current conversation.
        
        Args:
            content: Message content
            message_type: Type of message
            
        Returns:
            Message: Sent message or None if failed
        """
        if not self.current_conversation_id:
            raise ValueError("No active conversation")
        
        if not content.strip():
            return None
        
        try:
            # Create message object
            message = Message(
                id=f"temp_{datetime.now().timestamp()}",
                content=content,
                role="user",
                message_type=message_type,
                timestamp=datetime.now()
            )
            
            # Add to local list immediately for UI responsiveness
            self.messages.append(message)
            
            # Send via WebSocket if connected
            if self.is_connected:
                await websocket_service.send_chat_message(
                    conversation_id=int(self.current_conversation_id),
                    content=content,
                    role="user"
                )
            else:
                # Fallback to REST API
                response = await api_client.send_message(
                    conversation_id=int(self.current_conversation_id),
                    content=content,
                    role="user"
                )
                
                if response.get("success"):
                    # Update message with server response
                    message.id = response.get("data", {}).get("id", message.id)
                    message.timestamp = datetime.fromisoformat(
                        response.get("data", {}).get("timestamp", datetime.now().isoformat())
                    )
            
            # Notify listeners
            await self._notify_message_sent(message)
            
            return message
            
        except Exception as e:
            print(f"Failed to send message: {e}")
            # Remove message from local list if failed
            if message in self.messages:
                self.messages.remove(message)
            return None
    
    async def load_messages(self, conversation_id: str, limit: int = 50) -> List[Message]:
        """
        Load messages for a conversation.
        
        Args:
            conversation_id: Conversation ID
            limit: Maximum number of messages to load
            
        Returns:
            List[Message]: List of messages
        """
        try:
            response = await api_client.get_messages(int(conversation_id), limit=limit)
            
            if response.get("success"):
                messages_data = response.get("data", [])
                self.messages = []
                
                for msg_data in messages_data:
                    message = Message(
                        id=msg_data.get("id", ""),
                        content=msg_data.get("content", ""),
                        role=msg_data.get("role", "user"),
                        message_type=msg_data.get("message_type", "text"),
                        timestamp=datetime.fromisoformat(msg_data.get("timestamp", datetime.now().isoformat())),
                        metadata=msg_data.get("metadata")
                    )
                    self.messages.append(message)
                
                return self.messages
            else:
                print(f"Failed to load messages: {response.get('error')}")
                return []
                
        except Exception as e:
            print(f"Error loading messages: {e}")
            return []
    
    async def start_typing(self):
        """Send typing indicator."""
        if self.current_conversation_id and self.is_connected:
            try:
                await websocket_service.send_typing_indicator(
                    conversation_id=int(self.current_conversation_id),
                    is_typing=True
                )
                self.is_typing = True
            except Exception as e:
                print(f"Failed to send typing indicator: {e}")
    
    async def stop_typing(self):
        """Stop typing indicator."""
        if self.current_conversation_id and self.is_connected:
            try:
                await websocket_service.send_typing_indicator(
                    conversation_id=int(self.current_conversation_id),
                    is_typing=False
                )
                self.is_typing = False
            except Exception as e:
                print(f"Failed to stop typing indicator: {e}")
    
    def get_messages(self) -> List[Message]:
        """Get all messages in current conversation."""
        return self.messages.copy()
    
    def get_message_by_id(self, message_id: str) -> Optional[Message]:
        """Get message by ID."""
        for message in self.messages:
            if message.id == message_id:
                return message
        return None
    
    def clear_messages(self):
        """Clear all messages."""
        self.messages.clear()
    
    # Event notification methods (to be implemented by UI components)
    async def _notify_message_received(self, message: Message):
        """Notify that a message was received."""
        # TODO: Implement event system for UI updates
        pass
    
    async def _notify_message_sent(self, message: Message):
        """Notify that a message was sent."""
        # TODO: Implement event system for UI updates
        pass
    
    async def _notify_typing_changed(self, user_id: str, is_typing: bool):
        """Notify typing status change."""
        # TODO: Implement event system for UI updates
        pass
    
    async def _notify_connection_changed(self, connected: bool):
        """Notify connection status change."""
        # TODO: Implement event system for UI updates
        pass


# Global message service instance
message_service = MessageService() 