"""
Authentication Service
Handles user authentication, session management, and token refresh
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.brokers.base import BrokerAdapter, AuthResult
from app.brokers.factory import get_broker
from app.models.database import UserSession, BrokerCredentials
from app.api.exceptions import AuthenticationError, TokenExpiredError
from app.config import settings
from app.utils.logger import logger
from app.utils.encryption import encrypt, decrypt


class AuthService:
    """Service for authentication and session management"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def login(
        self,
        broker_name: str,
        client_id: str,
        password: str,
        totp: str,
        broker_api_key: Optional[str] = None,
        totp_secret: Optional[str] = None,
        save_credentials: bool = False
    ) -> Dict[str, str]:
        """
        Login to broker and create session.
        
        Args:
            broker_name: Broker name (angelone, etc.)
            client_id: Client/User ID
            password: Password or PIN
            totp: TOTP code
            broker_api_key: Broker API key (optional, uses config if not provided)
            totp_secret: TOTP secret for auto-generation (optional)
            save_credentials: Whether to save credentials to DB
        
        Returns:
            Dict with generated API key for frontend
        """
        # Get broker adapter
        broker = get_broker(broker_name, broker_api_key)
        
        # Authenticate with broker
        credentials = {
            "client_id": client_id,
            "password": password,
            "totp": totp
        }
        
        result = await broker.authenticate(credentials)
        
        if not result.success:
            logger.warning(f"Login failed for {client_id}: {result.error_code}")
            raise AuthenticationError(
                message=result.error_message,
                details={"error_code": result.error_code}
            )
        
        # Save credentials if requested
        if save_credentials and broker_api_key:
            await self.save_credentials(
                broker=broker_name,
                client_id=client_id,
                api_key=broker_api_key,
                password=password if password else None,
                totp_secret=totp_secret
            )
        
        # Generate API key for frontend
        api_key = self._generate_api_key()
        
        # Calculate expiry (default 24 hours)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        # Check if session exists for this client
        existing = await self.db.execute(
            select(UserSession).where(
                UserSession.client_id == client_id,
                UserSession.broker == broker_name
            )
        )
        session = existing.scalar_one_or_none()
        
        if session:
            # Update existing session
            session.api_key = api_key
            session.broker_api_key = broker_api_key  # Store broker API key
            session.jwt_token = result.jwt_token
            session.refresh_token = result.refresh_token
            session.feed_token = result.feed_token
            session.is_active = True
            session.updated_at = datetime.utcnow()
            session.expires_at = expires_at
        else:
            # Create new session
            session = UserSession(
                api_key=api_key,
                broker=broker_name,
                broker_api_key=broker_api_key,  # Store broker API key
                client_id=client_id,
                jwt_token=result.jwt_token,
                refresh_token=result.refresh_token,
                feed_token=result.feed_token,
                is_active=True,
                expires_at=expires_at
            )
            self.db.add(session)
        
        await self.db.commit()
        
        logger.info(f"Login successful for {client_id} on {broker_name}")
        
        return {
            "apikey": api_key,
            "broker": broker_name,
            "client_id": client_id
        }
    
    async def logout(self, api_key: str) -> bool:
        """
        Logout and invalidate session.
        
        Args:
            api_key: Frontend API key
        
        Returns:
            True if logout successful
        """
        session = await self.get_session(api_key)
        
        if not session:
            return False
        
        # Logout from broker
        try:
            broker = await self.get_broker_for_session(session)
            await broker.logout(session.client_id)
        except Exception as e:
            logger.warning(f"Broker logout failed: {e}")
        
        # Invalidate session
        session.is_active = False
        session.jwt_token = None
        session.refresh_token = None
        session.feed_token = None
        await self.db.commit()
        
        logger.info(f"Logout successful for {session.client_id}")
        
        return True
    
    async def get_session(self, api_key: str) -> Optional[UserSession]:
        """Get session by API key"""
        result = await self.db.execute(
            select(UserSession).where(
                UserSession.api_key == api_key,
                UserSession.is_active == True
            )
        )
        return result.scalar_one_or_none()
    
    async def validate_session(self, api_key: str) -> UserSession:
        """
        Validate session and refresh token if needed.
        
        Args:
            api_key: Frontend API key
        
        Returns:
            Valid UserSession
        
        Raises:
            AuthenticationError: If session invalid
            TokenExpiredError: If session expired and refresh failed
        """
        session = await self.get_session(api_key)
        
        if not session:
            raise AuthenticationError(message="Invalid API key")
        
        # Check if session expired
        if session.expires_at and session.expires_at < datetime.utcnow():
            # Try to refresh token
            refreshed = await self.refresh_session(session)
            if not refreshed:
                raise TokenExpiredError()
        
        return session
    
    async def refresh_session(self, session: UserSession) -> bool:
        """
        Refresh broker tokens for a session.
        
        Args:
            session: UserSession to refresh
        
        Returns:
            True if refresh successful
        """
        if not session.refresh_token:
            return False
        
        try:
            broker = await self.get_broker_for_session(session)
            result = await broker.refresh_token(session.refresh_token)
            
            if result.success:
                session.jwt_token = result.jwt_token
                session.refresh_token = result.refresh_token
                session.feed_token = result.feed_token
                session.expires_at = datetime.utcnow() + timedelta(hours=24)
                session.updated_at = datetime.utcnow()
                await self.db.commit()
                
                logger.info(f"Token refreshed for {session.client_id}")
                return True
            
            logger.warning(f"Token refresh failed: {result.error_message}")
            return False
            
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return False
    
    async def get_broker_for_session(self, session: UserSession) -> BrokerAdapter:
        """
        Get configured broker adapter for a session.
        
        Args:
            session: UserSession with broker info
        
        Returns:
            BrokerAdapter with tokens set
        """
        # Get broker with API key from session
        broker = get_broker(session.broker, session.broker_api_key)
        
        # Set tokens on broker
        broker.set_tokens(
            jwt_token=session.jwt_token,
            refresh_token=session.refresh_token,
            feed_token=session.feed_token,
            client_id=session.client_id
        )
        
        return broker
    
    async def check_token_expiry(self, session: UserSession) -> bool:
        """
        Check if token is near expiry and refresh if needed.
        
        Args:
            session: UserSession to check
        
        Returns:
            True if token is valid (refreshed if needed)
        """
        if not session.expires_at:
            return True
        
        # Refresh if expiring within 5 minutes
        threshold = datetime.utcnow() + timedelta(minutes=5)
        
        if session.expires_at < threshold:
            return await self.refresh_session(session)
        
        return True
    
    def _generate_api_key(self) -> str:
        """Generate secure API key"""
        return secrets.token_urlsafe(32)
    
    async def get_all_active_sessions(self) -> list:
        """Get all active sessions"""
        result = await self.db.execute(
            select(UserSession).where(UserSession.is_active == True)
        )
        return result.scalars().all()
    
    async def save_credentials(
        self,
        broker: str,
        client_id: str,
        api_key: str,
        password: Optional[str] = None,
        totp_secret: Optional[str] = None
    ) -> None:
        """
        Save broker credentials to database (encrypted).
        
        Args:
            broker: Broker name
            client_id: Client ID
            api_key: Broker API key
            password: Password/PIN (optional)
            totp_secret: TOTP secret (optional)
        """
        # Check if credentials exist
        existing = await self.db.execute(
            select(BrokerCredentials).where(
                BrokerCredentials.broker == broker,
                BrokerCredentials.client_id == client_id
            )
        )
        creds = existing.scalar_one_or_none()
        
        if creds:
            # Update existing
            creds.api_key = encrypt(api_key)
            creds.password = encrypt(password) if password else None
            creds.totp_secret = encrypt(totp_secret) if totp_secret else None
            creds.updated_at = datetime.utcnow()
        else:
            # Create new
            creds = BrokerCredentials(
                broker=broker,
                client_id=client_id,
                api_key=encrypt(api_key),
                password=encrypt(password) if password else None,
                totp_secret=encrypt(totp_secret) if totp_secret else None
            )
            self.db.add(creds)
        
        await self.db.commit()
        logger.info(f"Saved credentials for {client_id} on {broker}")
    
    async def get_saved_credentials(self, broker: str, client_id: str) -> Optional[Dict]:
        """
        Get saved credentials from database.
        
        Args:
            broker: Broker name
            client_id: Client ID
        
        Returns:
            Dict with decrypted credentials or None
        """
        result = await self.db.execute(
            select(BrokerCredentials).where(
                BrokerCredentials.broker == broker,
                BrokerCredentials.client_id == client_id,
                BrokerCredentials.is_active == True
            )
        )
        creds = result.scalar_one_or_none()
        
        if not creds:
            return None
        
        return {
            "broker": creds.broker,
            "client_id": creds.client_id,
            "api_key": decrypt(creds.api_key),
            "password": decrypt(creds.password) if creds.password else None,
            "totp_secret": decrypt(creds.totp_secret) if creds.totp_secret else None
        }
    
    async def list_saved_credentials(self) -> List[Dict[str, str]]:
        """
        List all saved credentials (without sensitive data).
        
        Returns:
            List of {broker, client_id}
        """
        result = await self.db.execute(
            select(BrokerCredentials).where(BrokerCredentials.is_active == True)
        )
        creds_list = result.scalars().all()
        
        return [
            {"broker": c.broker, "client_id": c.client_id}
            for c in creds_list
        ]
    
    async def delete_credentials(self, broker: str, client_id: str) -> bool:
        """
        Delete saved credentials.
        
        Args:
            broker: Broker name
            client_id: Client ID
        
        Returns:
            True if deleted
        """
        result = await self.db.execute(
            select(BrokerCredentials).where(
                BrokerCredentials.broker == broker,
                BrokerCredentials.client_id == client_id
            )
        )
        creds = result.scalar_one_or_none()
        
        if creds:
            creds.is_active = False
            await self.db.commit()
            logger.info(f"Deleted credentials for {client_id} on {broker}")
            return True
        
        return False
