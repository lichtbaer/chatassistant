"""
SAML service for handling SAML authentication flows.

This module provides SAML client setup, metadata parsing,
and assertion processing for enterprise SSO integration.
"""

import base64
import tempfile
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request, status
from loguru import logger
from saml2 import BINDING_HTTP_POST, BINDING_HTTP_REDIRECT
from saml2.client import Saml2Client
from saml2.config import Config as Saml2Config

# from saml2.entity import EntityDescriptor  # Not available in pysaml2
from saml2.metadata import create_metadata_string
from saml2.saml import NAMEID_FORMAT_EMAILADDRESS
from saml2.sigver import get_xmlsec_binary

from backend.app.core.config import get_settings
from backend.app.core.security import create_access_token, create_refresh_token
from backend.app.models.user import AuthProvider, User
from backend.app.schemas.user import SSOUserCreate
from backend.app.services.user_service import UserService


class SAMLService:
    """Service for handling SAML authentication flows."""

    def __init__(self):
        self.settings = get_settings()
        self.saml_client = None
        self._setup_saml_client()

    def _setup_saml_client(self):
        """Setup SAML client with configuration."""
        if not self.settings.sso_saml_enabled:
            return

        try:
            # Create temporary certificate and key files if not provided
            cert_file, key_file = self._get_certificate_files()

            # SAML configuration
            saml_config = {
                "entityid": self.settings.sso_saml_entity_id,
                "service": {
                    "sp": {
                        "name_id_format": NAMEID_FORMAT_EMAILADDRESS,
                        "endpoints": {
                            "assertion_consumer_service": [
                                (self.settings.sso_saml_acs_url, BINDING_HTTP_POST),
                                (self.settings.sso_saml_acs_url, BINDING_HTTP_REDIRECT),
                            ],
                        },
                        "allow_unsolicited": True,
                        "authn_requests_signed": False,
                        "want_assertions_signed": True,
                        "want_response_signed": False,
                    },
                },
                "metadata": {
                    "remote": [
                        {
                            "url": self.settings.sso_saml_metadata_url,
                        },
                    ],
                },
                "cert_file": cert_file,
                "key_file": key_file,
                "xmlsec_binary": get_xmlsec_binary(),
                "encryption_keypairs": [
                    {
                        "key_file": key_file,
                        "cert_file": cert_file,
                    },
                ],
                "valid_for": 24,  # hours
            }

            config = Saml2Config()
            config.load(saml_config)
            self.saml_client = Saml2Client(config)

            logger.info("SAML client initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize SAML client: {e}")
            self.saml_client = None

    def _get_certificate_files(self) -> tuple[str, str]:
        """Get certificate and key file paths, creating temporary ones if needed."""
        cert_file = self.settings.sso_saml_cert_file
        key_file = self.settings.sso_saml_key_file

        # If no certificate files provided, create temporary ones
        if not cert_file or not key_file:
            cert_file, key_file = self._create_temp_certificates()

        return cert_file, key_file

    def _create_temp_certificates(self) -> tuple[str, str]:
        """Create temporary self-signed certificate for testing."""
        try:
            from datetime import datetime, timedelta

            from cryptography import x509
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.x509.oid import NameOID

            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )

            # Create certificate
            subject = issuer = x509.Name(
                [
                    x509.NameAttribute(NameOID.COUNTRY_NAME, "DE"),
                    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Bavaria"),
                    x509.NameAttribute(NameOID.LOCALITY_NAME, "Munich"),
                    x509.NameAttribute(
                        NameOID.ORGANIZATION_NAME,
                        "AI Assistant Platform",
                    ),
                    x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
                ],
            )

            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(private_key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.utcnow())
                .not_valid_after(datetime.utcnow() + timedelta(days=365))
                .add_extension(
                    x509.SubjectAlternativeName(
                        [
                            x509.DNSName("localhost"),
                        ],
                    ),
                    critical=False,
                )
                .sign(private_key, hashes.SHA256())
            )

            # Create temporary files
            cert_file = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".crt",
                delete=False,
            )
            key_file = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".key",
                delete=False,
            )

            # Write certificate
            cert_file.write(cert.public_bytes(serialization.Encoding.PEM).decode())
            cert_file.close()

            # Write private key
            key_file.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                ).decode(),
            )
            key_file.close()

            logger.info(
                f"Created temporary certificates: {cert_file.name}, {key_file.name}",
            )
            return cert_file.name, key_file.name

        except Exception as e:
            logger.error(f"Failed to create temporary certificates: {e}")
            # Return dummy files in temp directory
            import tempfile

            temp_dir = tempfile.gettempdir()
            return (
                f"{temp_dir}/dummy.crt",
                f"{temp_dir}/dummy.key",
            )  # nosec B108 - using tempfile.gettempdir()

    def is_enabled(self) -> bool:
        """Check if SAML is enabled and configured."""
        return (
            self.settings.sso_saml_enabled
            and self.settings.sso_saml_metadata_url
            and self.saml_client is not None
        )

    async def get_login_url(self, request: Request) -> str:
        """
        Get SAML login URL.

        Args:
            request: FastAPI request object

        Returns:
            str: SAML login URL

        Raises:
            HTTPException: If SAML is not configured
        """
        if not self.is_enabled():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SAML SSO is not configured",
            )

        try:
            # Get the IdP entity ID from metadata
            idp_entity_id = self._get_idp_entity_id()

            # Create authentication request
            authn_req = self.saml_client.create_authn_request(
                idp_entity_id,
                binding=BINDING_HTTP_REDIRECT,
                sign=False,
            )

            # Get the redirect URL
            redirect_url = self.saml_client.apply_binding(
                BINDING_HTTP_REDIRECT,
                authn_req,
                idp_entity_id,
                relay_state="",
            )

            return redirect_url[1]  # URL is the second element

        except Exception as e:
            logger.error(f"Failed to create SAML login URL: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create SAML login URL: {str(e)}",
            )

    def _get_idp_entity_id(self) -> str:
        """Get the IdP entity ID from metadata."""
        try:
            # This is a simplified version - in production, you'd parse the metadata
            # For now, we'll use a placeholder
            return "http://idp.example.com"
        except Exception as e:
            logger.error(f"Failed to get IdP entity ID: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get IdP entity ID",
            )

    async def handle_saml_response(self, request: Request) -> dict[str, Any]:
        """
        Handle SAML response and extract user information.

        Args:
            request: FastAPI request object

        Returns:
            Dict containing user information

        Raises:
            HTTPException: If SAML response is invalid
        """
        if not self.is_enabled():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SAML SSO is not configured",
            )

        try:
            # Get SAML response from request
            saml_response = await self._extract_saml_response(request)

            # Parse and validate SAML response
            authn_response = self.saml_client.parse_authn_request_response(
                saml_response,
                BINDING_HTTP_POST,
            )

            # Extract user information
            user_info = self._extract_user_info(authn_response)

            return {
                "user_info": user_info,
                "saml_response": authn_response,
                "provider": "saml",
            }

        except Exception as e:
            logger.error(f"SAML response handling failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"SAML authentication failed: {str(e)}",
            )

    async def _extract_saml_response(self, request: Request) -> str:
        """Extract SAML response from request."""
        try:
            # Handle POST request with SAMLResponse
            form_data = await request.form()
            saml_response = form_data.get("SAMLResponse")

            if not saml_response:
                raise ValueError("SAMLResponse not found in request")

            # Decode base64 response
            return base64.b64decode(saml_response).decode("utf-8")

        except Exception as e:
            logger.error(f"Failed to extract SAML response: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid SAML response",
            )

    def _extract_user_info(self, authn_response) -> dict[str, Any]:
        """Extract user information from SAML assertion."""
        try:
            # Get the first assertion
            assertion = authn_response.assertions[0]

            # Extract basic user information
            user_info = {
                "email": None,
                "external_id": None,
                "first_name": None,
                "last_name": None,
                "display_name": None,
                "avatar_url": None,
                "sso_attributes": {},
            }

            # Extract attributes from assertion
            if assertion.attribute_statement:
                for attribute in assertion.attribute_statement.attribute:
                    attr_name = attribute.name
                    attr_values = [
                        attr_value.text for attr_value in attribute.attribute_value
                    ]

                    if attr_values:
                        user_info["sso_attributes"][attr_name] = (
                            attr_values[0] if len(attr_values) == 1 else attr_values
                        )

                        # Map common SAML attributes
                        if attr_name in ["email", "mail", "emailAddress"]:
                            user_info["email"] = attr_values[0]
                        elif attr_name in ["uid", "userid", "employeeID"]:
                            user_info["external_id"] = attr_values[0]
                        elif attr_name in ["givenName", "firstName"]:
                            user_info["first_name"] = attr_values[0]
                        elif attr_name in ["sn", "lastName", "surname"]:
                            user_info["last_name"] = attr_values[0]
                        elif attr_name in ["displayName", "cn", "commonName"]:
                            user_info["display_name"] = attr_values[0]

            # Extract name ID as fallback for email/external_id
            if assertion.subject.name_id:
                name_id = assertion.subject.name_id.text
                if not user_info["email"] and "@" in name_id:
                    user_info["email"] = name_id
                if not user_info["external_id"]:
                    user_info["external_id"] = name_id

            # Ensure we have at least an email or external_id
            if not user_info["email"] and not user_info["external_id"]:
                raise ValueError("No email or external ID found in SAML assertion")

            return user_info

        except Exception as e:
            logger.error(f"Failed to extract user info from SAML assertion: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to extract user information from SAML response",
            )

    def get_metadata(self) -> str:
        """
        Get SAML metadata for this service provider.

        Returns:
            str: SAML metadata XML
        """
        if not self.saml_client:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SAML client not initialized",
            )

        try:
            return create_metadata_string(
                None,
                config=self.saml_client.config,
                valid=None,
                cert=None,
                keyfile=None,
                mid=None,
                name=None,
            )

        except Exception as e:
            logger.error(f"Failed to generate SAML metadata: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate SAML metadata",
            )

    async def process_saml_user(self, user_info: dict[str, Any], db) -> User:
        """
        Process SAML user and create/update user account.

        Args:
            user_info: User information from SAML assertion
            db: Database session

        Returns:
            User: Created or existing user
        """
        user_service = UserService(db)
        auth_provider = AuthProvider.SAML

        # Check if user already exists by external ID
        existing_user = user_service.get_user_by_external_id(
            user_info["external_id"],
            auth_provider,
        )

        if existing_user:
            # Update existing user with latest SAML info
            logger.info(f"Updating existing SAML user: {existing_user.email}")
            existing_user.sso_attributes = user_info.get("sso_attributes", {})
            db.commit()
            return existing_user

        # Create new SAML user
        logger.info(f"Creating new SAML user: {user_info['email']}")
        sso_user_data = SSOUserCreate(
            email=user_info["email"],
            username=user_info.get("username") or user_info["email"].split("@")[0],
            first_name=user_info.get("first_name"),
            last_name=user_info.get("last_name"),
            display_name=user_info.get("display_name"),
            auth_provider=auth_provider,
            external_id=user_info["external_id"],
            sso_attributes=user_info.get("sso_attributes", {}),
        )

        return user_service.create_sso_user(sso_user_data)

    async def create_saml_tokens(self, user: User) -> dict[str, Any]:
        """
        Create JWT tokens for SAML user.

        Args:
            user: User object

        Returns:
            Dict containing access and refresh tokens
        """
        # Create access token
        access_token = create_access_token(
            data={"sub": str(user.id)},
            expires_delta=datetime.timedelta(
                minutes=self.settings.jwt_access_token_expire_minutes,
            ),
        )

        # Create refresh token
        refresh_token = create_refresh_token(data={"sub": str(user.id)})

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.settings.jwt_access_token_expire_minutes * 60,
        }


# Global SAML service instance
saml_service = SAMLService()


class MockSamlSettings:
    """Mock SAML settings for testing."""

    def __init__(self):
        self.sso_saml_enabled = False
        self.sso_saml_metadata_url = None
        self.sso_saml_entity_id = None
        self.sso_saml_acs_url = None
        self.sso_saml_cert_file = None
        self.sso_saml_key_file = None
        self.jwt_access_token_expire_minutes = 30
