"""
SSO Manager for handling multiple authentication providers.

This module provides comprehensive Single Sign-On (SSO) management including
LDAP, SAML, OAuth, and OpenID Connect with advanced features like role mapping,
group synchronization, and session management.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import requests
from app.models.domain_groups import DomainGroup
from app.models.user import AuthProvider, User, UserRole, UserStatus
from app.utils.exceptions import (
    AuthenticationError,
    GroupSyncError,
    SSOConfigurationError,
    UserNotFoundError,
)
from ldap3 import SUBTREE, Connection, Server
from saml2 import BINDING_HTTP_POST, BINDING_HTTP_REDIRECT
from saml2.client import Saml2Client
from saml2.config import Config as SamlConfig
from saml2.response import AuthnResponse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class SSOProvider:
    """Base class for SSO providers."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.name = config.get("name", "unknown")
        self.enabled = config.get("enabled", False)
        self.priority = config.get("priority", 0)

    async def authenticate(
        self,
        credentials: dict[str, Any],
        db: Session,
    ) -> tuple[User, dict[str, Any]]:
        """Authenticate user and return user object with additional data."""
        raise NotImplementedError

    async def get_user_info(self, user_id: str, db: Session) -> dict[str, Any]:
        """Get user information from SSO provider."""
        raise NotImplementedError

    async def sync_user_groups(self, user: User, db: Session) -> list[str]:
        """Synchronize user groups from SSO provider."""
        raise NotImplementedError

    async def validate_token(self, token: str) -> dict[str, Any]:
        """Validate SSO token."""
        raise NotImplementedError


class LDAPProvider(SSOProvider):
    """LDAP/Active Directory SSO provider."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.server_url = config.get("server_url")
        self.base_dn = config.get("base_dn")
        self.bind_dn = config.get("bind_dn")
        self.bind_password = config.get("bind_password")
        self.user_search_base = config.get("user_search_base", self.base_dn)
        self.group_search_base = config.get("group_search_base", self.base_dn)
        self.user_search_filter = config.get(
            "user_search_filter",
            "(sAMAccountName={username})",
        )
        self.group_search_filter = config.get(
            "group_search_filter",
            "(member={user_dn})",
        )
        self.attributes = config.get(
            "attributes",
            ["cn", "mail", "displayName", "memberOf"],
        )

        # Role mapping configuration
        self.role_mapping = config.get("role_mapping", {})
        self.default_role = config.get("default_role", UserRole.USER)

        # Group mapping configuration
        self.group_mapping = config.get("group_mapping", {})
        self.auto_create_groups = config.get("auto_create_groups", False)

        # Connection settings
        self.use_ssl = config.get("use_ssl", True)
        self.timeout = config.get("timeout", 10)

        if not all([self.server_url, self.base_dn, self.bind_dn, self.bind_password]):
            raise SSOConfigurationError("LDAP configuration incomplete")

    async def authenticate(
        self,
        credentials: dict[str, Any],
        db: Session,
    ) -> tuple[User, dict[str, Any]]:
        """Authenticate user against LDAP."""
        username = credentials.get("username")
        password = credentials.get("password")

        if not username or not password:
            raise AuthenticationError("Username and password required")

        try:
            # Connect to LDAP server
            server = Server(
                self.server_url,
                use_ssl=self.use_ssl,
                connect_timeout=self.timeout,
            )
            conn = Connection(
                server,
                user=self.bind_dn,
                password=self.bind_password,
                auto_bind=True,
            )

            # Search for user
            user_filter = self.user_search_filter.format(username=username)
            conn.search(
                self.user_search_base,
                user_filter,
                SUBTREE,
                attributes=self.attributes,
            )

            if not conn.entries:
                raise AuthenticationError("User not found in LDAP")

            user_entry = conn.entries[0]
            user_dn = user_entry.entry_dn

            # Verify password
            user_conn = Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=True,
            )
            if not user_conn.bound:
                raise AuthenticationError("Invalid credentials")

            # Get user attributes
            user_attrs = user_entry.entry_attributes
            email = user_attrs.get("mail", [""])[0] if user_attrs.get("mail") else ""
            display_name = (
                user_attrs.get("displayName", [""])[0]
                if user_attrs.get("displayName")
                else ""
            )

            # Get or create user in database
            user = await self._get_or_create_user(username, email, display_name, db)

            # Sync groups
            groups = await self.sync_user_groups(user, db)

            # Additional data
            additional_data = {
                "ldap_dn": user_dn,
                "ldap_groups": groups,
                "provider": "ldap",
                "last_sync": datetime.now(UTC).isoformat(),
            }

            return user, additional_data

        except Exception as e:
            logger.exception(f"LDAP authentication failed: {str(e)}")
            raise AuthenticationError(f"LDAP authentication failed: {str(e)}")

    async def get_user_info(self, user_id: str, db: Session) -> dict[str, Any]:
        """Get user information from LDAP."""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise UserNotFoundError("User not found")

            server = Server(
                self.server_url,
                use_ssl=self.use_ssl,
                connect_timeout=self.timeout,
            )
            conn = Connection(
                server,
                user=self.bind_dn,
                password=self.bind_password,
                auto_bind=True,
            )

            user_filter = self.user_search_filter.format(username=user.username)
            conn.search(
                self.user_search_base,
                user_filter,
                SUBTREE,
                attributes=self.attributes,
            )

            if not conn.entries:
                return {"error": "User not found in LDAP"}

            user_entry = conn.entries[0]
            user_attrs = user_entry.entry_attributes

            return {
                "dn": user_entry.entry_dn,
                "email": (
                    user_attrs.get("mail", [""])[0] if user_attrs.get("mail") else ""
                ),
                "display_name": (
                    user_attrs.get("displayName", [""])[0]
                    if user_attrs.get("displayName")
                    else ""
                ),
                "groups": await self.sync_user_groups(user, db),
                "last_sync": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            logger.exception(f"Failed to get LDAP user info: {str(e)}")
            return {"error": str(e)}

    async def sync_user_groups(self, user: User, db: Session) -> list[str]:
        """Synchronize user groups from LDAP."""
        try:
            server = Server(
                self.server_url,
                use_ssl=self.use_ssl,
                connect_timeout=self.timeout,
            )
            conn = Connection(
                server,
                user=self.bind_dn,
                password=self.bind_password,
                auto_bind=True,
            )

            # Get user DN
            user_filter = self.user_search_filter.format(username=user.username)
            conn.search(
                self.user_search_base,
                user_filter,
                SUBTREE,
                attributes=["distinguishedName"],
            )

            if not conn.entries:
                return []

            user_dn = conn.entries[0].entry_dn

            # Search for groups
            group_filter = self.group_search_filter.format(user_dn=user_dn)
            conn.search(
                self.group_search_base,
                group_filter,
                SUBTREE,
                attributes=["cn", "distinguishedName"],
            )

            ldap_groups = []
            for entry in conn.entries:
                group_cn = entry.entry_attributes.get("cn", [""])[0]
                if group_cn:
                    ldap_groups.append(group_cn)

            # Map LDAP groups to application groups
            app_groups = []
            for ldap_group in ldap_groups:
                if ldap_group in self.group_mapping:
                    app_groups.append(self.group_mapping[ldap_group])
                elif self.auto_create_groups:
                    # Auto-create domain groups for LDAP groups
                    domain_group = await self._create_domain_group_from_ldap(
                        ldap_group,
                        db,
                    )
                    if domain_group:
                        app_groups.append(str(domain_group.id))

            return app_groups

        except Exception as e:
            logger.exception(f"Failed to sync LDAP groups: {str(e)}")
            raise GroupSyncError(f"LDAP group sync failed: {str(e)}")

    async def _get_or_create_user(
        self,
        username: str,
        email: str,
        display_name: str,
        db: Session,
    ) -> User:
        """Get existing user or create new one from LDAP."""
        user = db.query(User).filter(User.username == username).first()

        if not user:
            # Create new user
            user = User(
                username=username,
                email=email,
                full_name=display_name,
                auth_provider=AuthProvider.LDAP,
                role=self.default_role,
                status=UserStatus.ACTIVE,
                email_verified=True,  # LDAP users are considered verified
                last_login=datetime.now(UTC),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            # Update existing user
            user.email = email
            user.full_name = display_name
            user.last_login = datetime.now(UTC)
            db.commit()

        return user

    async def _create_domain_group_from_ldap(
        self,
        ldap_group: str,
        db: Session,
    ) -> DomainGroup | None:
        """Create domain group from LDAP group."""
        try:
            # Check if domain group already exists
            existing_group = (
                db.query(DomainGroup)
                .filter(DomainGroup.external_id == f"ldap:{ldap_group}")
                .first()
            )

            if existing_group:
                return existing_group

            # Create new domain group
            domain_group = DomainGroup(
                name=ldap_group,
                display_name=f"LDAP Group: {ldap_group}",
                domain_type="TEAM",
                external_id=f"ldap:{ldap_group}",
                tags=["ldap", "auto-created"],
                is_system=True,
                settings={"ldap_source": True},
            )

            db.add(domain_group)
            db.commit()
            db.refresh(domain_group)

            return domain_group

        except Exception as e:
            logger.exception(f"Failed to create domain group from LDAP: {str(e)}")
            return None


class SAMLProvider(SSOProvider):
    """SAML 2.0 SSO provider."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.idp_metadata_url = config.get("idp_metadata_url")
        self.idp_entity_id = config.get("idp_entity_id")
        self.sp_entity_id = config.get("sp_entity_id")
        self.acs_url = config.get("acs_url")
        self.slo_url = config.get("slo_url")
        self.cert_file = config.get("cert_file")
        self.key_file = config.get("key_file")

        # Attribute mapping
        self.attribute_mapping = config.get(
            "attribute_mapping",
            {
                "username": "urn:oid:0.9.2342.19200300.100.1.1",  # uid
                "email": "urn:oid:0.9.2342.19200300.100.1.3",  # mail
                "first_name": "urn:oid:2.5.4.42",  # givenName
                "last_name": "urn:oid:2.5.4.4",  # sn
                "groups": "urn:oid:1.3.6.1.4.1.5923.1.5.1.1",  # eduPersonAffiliation
            },
        )

        # Role mapping
        self.role_mapping = config.get("role_mapping", {})
        self.default_role = config.get("default_role", UserRole.USER)

        # Initialize SAML client
        self._init_saml_client()

    def _init_saml_client(self):
        """Initialize SAML client configuration."""
        try:
            saml_config = {
                "entityid": self.sp_entity_id,
                "service": {
                    "sp": {
                        "endpoints": {
                            "assertion_consumer_service": [
                                (self.acs_url, BINDING_HTTP_POST),
                            ],
                            "single_logout_service": [
                                (self.slo_url, BINDING_HTTP_REDIRECT),
                            ],
                        },
                        "allow_unsolicited": True,
                        "authn_requests_signed": False,
                        "want_assertions_signed": True,
                        "want_response_signed": False,
                    },
                },
                "metadata": {"remote": [{"url": self.idp_metadata_url}]},
                "key_file": self.key_file,
                "cert_file": self.cert_file,
                "encryption_keypairs": [
                    {"key_file": self.key_file, "cert_file": self.cert_file},
                ],
            }

            self.saml_config = SamlConfig()
            self.saml_config.load(saml_config)
            self.saml_client = Saml2Client(self.saml_config)

        except Exception as e:
            logger.exception(f"Failed to initialize SAML client: {str(e)}")
            raise SSOConfigurationError(f"SAML configuration error: {str(e)}")

    async def authenticate(
        self,
        credentials: dict[str, Any],
        db: Session,
    ) -> tuple[User, dict[str, Any]]:
        """Authenticate user via SAML."""
        saml_response = credentials.get("saml_response")
        credentials.get("relay_state")

        if not saml_response:
            raise AuthenticationError("SAML response required")

        try:
            # Parse and validate SAML response
            authn_response = AuthnResponse(self.saml_config)
            authn_response.loads(saml_response, BINDING_HTTP_POST)

            if not authn_response.is_valid():
                raise AuthenticationError("Invalid SAML response")

            # Extract user attributes
            attributes = authn_response.ava
            username = attributes.get(self.attribute_mapping["username"], [""])[0]
            email = attributes.get(self.attribute_mapping["email"], [""])[0]
            first_name = attributes.get(self.attribute_mapping["first_name"], [""])[0]
            last_name = attributes.get(self.attribute_mapping["last_name"], [""])[0]
            groups = attributes.get(self.attribute_mapping["groups"], [])

            if not username:
                raise AuthenticationError("Username not found in SAML response")

            # Get or create user
            user = await self._get_or_create_user(
                username,
                email,
                first_name,
                last_name,
                db,
            )

            # Sync groups
            await self.sync_user_groups(user, groups, db)

            additional_data = {
                "saml_session_index": authn_response.session_index,
                "saml_name_id": authn_response.name_id,
                "saml_groups": groups,
                "provider": "saml",
                "last_sync": datetime.now(UTC).isoformat(),
            }

            return user, additional_data

        except Exception as e:
            logger.exception(f"SAML authentication failed: {str(e)}")
            raise AuthenticationError(f"SAML authentication failed: {str(e)}")

    async def get_user_info(self, user_id: str, db: Session) -> dict[str, Any]:
        """Get user information from SAML provider."""
        # SAML doesn't support direct user info queries
        # Return cached information from database
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise UserNotFoundError("User not found")

        return {
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "provider": "saml",
            "last_sync": user.last_login.isoformat() if user.last_login else None,
        }

    async def sync_user_groups(
        self,
        user: User,
        groups: list[str],
        db: Session,
    ) -> list[str]:
        """Synchronize user groups from SAML."""
        try:
            app_groups = []
            for group in groups:
                if group in self.role_mapping:
                    # Map SAML groups to roles
                    mapped_role = self.role_mapping[group]
                    if user.role != mapped_role:
                        user.role = mapped_role
                        db.commit()

                # Create domain groups for SAML groups
                domain_group = await self._create_domain_group_from_saml(group, db)
                if domain_group:
                    app_groups.append(str(domain_group.id))

            return app_groups

        except Exception as e:
            logger.exception(f"Failed to sync SAML groups: {str(e)}")
            raise GroupSyncError(f"SAML group sync failed: {str(e)}")

    async def _get_or_create_user(
        self,
        username: str,
        email: str,
        first_name: str,
        last_name: str,
        db: Session,
    ) -> User:
        """Get existing user or create new one from SAML."""
        user = db.query(User).filter(User.username == username).first()

        if not user:
            # Create new user
            user = User(
                username=username,
                email=email,
                full_name=f"{first_name} {last_name}".strip(),
                auth_provider=AuthProvider.SAML,
                role=self.default_role,
                status=UserStatus.ACTIVE,
                email_verified=True,
                last_login=datetime.now(UTC),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            # Update existing user
            user.email = email
            user.full_name = f"{first_name} {last_name}".strip()
            user.last_login = datetime.now(UTC)
            db.commit()

        return user

    async def _create_domain_group_from_saml(
        self,
        saml_group: str,
        db: Session,
    ) -> DomainGroup | None:
        """Create domain group from SAML group."""
        try:
            # Check if domain group already exists
            existing_group = (
                db.query(DomainGroup)
                .filter(DomainGroup.external_id == f"saml:{saml_group}")
                .first()
            )

            if existing_group:
                return existing_group

            # Create new domain group
            domain_group = DomainGroup(
                name=saml_group,
                display_name=f"SAML Group: {saml_group}",
                domain_type="TEAM",
                external_id=f"saml:{saml_group}",
                tags=["saml", "auto-created"],
                is_system=True,
                settings={"saml_source": True},
            )

            db.add(domain_group)
            db.commit()
            db.refresh(domain_group)

            return domain_group

        except Exception as e:
            logger.exception(f"Failed to create domain group from SAML: {str(e)}")
            return None


class OAuthProvider(SSOProvider):
    """OAuth 2.0 / OpenID Connect SSO provider."""

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.authorization_url = config.get("authorization_url")
        self.token_url = config.get("token_url")
        self.userinfo_url = config.get("userinfo_url")
        self.scope = config.get("scope", "openid email profile")

        # Attribute mapping
        self.attribute_mapping = config.get(
            "attribute_mapping",
            {
                "username": "sub",
                "email": "email",
                "first_name": "given_name",
                "last_name": "family_name",
                "groups": "groups",
            },
        )

        # Role mapping
        self.role_mapping = config.get("role_mapping", {})
        self.default_role = config.get("default_role", UserRole.USER)

        # Token validation
        self.jwks_url = config.get("jwks_url")
        self.issuer = config.get("issuer")

        if not all(
            [
                self.client_id,
                self.client_secret,
                self.authorization_url,
                self.token_url,
            ],
        ):
            raise SSOConfigurationError("OAuth configuration incomplete")

    async def authenticate(
        self,
        credentials: dict[str, Any],
        db: Session,
    ) -> tuple[User, dict[str, Any]]:
        """Authenticate user via OAuth."""
        authorization_code = credentials.get("code")
        redirect_uri = credentials.get("redirect_uri")

        if not authorization_code or not redirect_uri:
            raise AuthenticationError("Authorization code and redirect URI required")

        try:
            # Exchange authorization code for access token
            token_data = await self._exchange_code_for_token(
                authorization_code,
                redirect_uri,
            )
            access_token = token_data.get("access_token")

            if not access_token:
                raise AuthenticationError("Failed to obtain access token")

            # Get user information
            user_info = await self._get_user_info(access_token)

            # Extract user attributes
            username = user_info.get(self.attribute_mapping["username"])
            email = user_info.get(self.attribute_mapping["email"])
            first_name = user_info.get(self.attribute_mapping["first_name"], "")
            last_name = user_info.get(self.attribute_mapping["last_name"], "")
            groups = user_info.get(self.attribute_mapping["groups"], [])

            if not username:
                raise AuthenticationError("Username not found in OAuth response")

            # Get or create user
            user = await self._get_or_create_user(
                username,
                email,
                first_name,
                last_name,
                db,
            )

            # Sync groups
            await self.sync_user_groups(user, groups, db)

            additional_data = {
                "oauth_access_token": access_token,
                "oauth_refresh_token": token_data.get("refresh_token"),
                "oauth_groups": groups,
                "provider": "oauth",
                "last_sync": datetime.now(UTC).isoformat(),
            }

            return user, additional_data

        except Exception as e:
            logger.exception(f"OAuth authentication failed: {str(e)}")
            raise AuthenticationError(f"OAuth authentication failed: {str(e)}")

    async def get_user_info(self, user_id: str, db: Session) -> dict[str, Any]:
        """Get user information from OAuth provider."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise UserNotFoundError("User not found")

        # Try to refresh user info from OAuth provider
        try:
            # This would require storing refresh tokens securely
            # For now, return cached information
            return {
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "provider": "oauth",
                "last_sync": user.last_login.isoformat() if user.last_login else None,
            }
        except Exception as e:
            logger.exception(f"Failed to get OAuth user info: {str(e)}")
            return {"error": str(e)}

    async def sync_user_groups(
        self,
        user: User,
        groups: list[str],
        db: Session,
    ) -> list[str]:
        """Synchronize user groups from OAuth provider."""
        try:
            app_groups = []
            for group in groups:
                if group in self.role_mapping:
                    # Map OAuth groups to roles
                    mapped_role = self.role_mapping[group]
                    if user.role != mapped_role:
                        user.role = mapped_role
                        db.commit()

                # Create domain groups for OAuth groups
                domain_group = await self._create_domain_group_from_oauth(group, db)
                if domain_group:
                    app_groups.append(str(domain_group.id))

            return app_groups

        except Exception as e:
            logger.exception(f"Failed to sync OAuth groups: {str(e)}")
            raise GroupSyncError(f"OAuth group sync failed: {str(e)}")

    async def _exchange_code_for_token(
        self,
        authorization_code: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        """Exchange authorization code for access token."""
        token_data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        response = requests.post(
            self.token_url, data=token_data, timeout=30
        )  # nosec B113 - timeout added
        response.raise_for_status()

        return response.json()

    async def _get_user_info(self, access_token: str) -> dict[str, Any]:
        """Get user information from OAuth provider."""
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(
            self.userinfo_url, headers=headers, timeout=30
        )  # nosec B113 - timeout added
        response.raise_for_status()

        return response.json()

    async def _get_or_create_user(
        self,
        username: str,
        email: str,
        first_name: str,
        last_name: str,
        db: Session,
    ) -> User:
        """Get existing user or create new one from OAuth."""
        user = db.query(User).filter(User.username == username).first()

        if not user:
            # Create new user
            user = User(
                username=username,
                email=email,
                full_name=f"{first_name} {last_name}".strip(),
                auth_provider=AuthProvider.OAUTH,
                role=self.default_role,
                status=UserStatus.ACTIVE,
                email_verified=True,
                last_login=datetime.now(UTC),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            # Update existing user
            user.email = email
            user.full_name = f"{first_name} {last_name}".strip()
            user.last_login = datetime.now(UTC)
            db.commit()

        return user

    async def _create_domain_group_from_oauth(
        self,
        oauth_group: str,
        db: Session,
    ) -> DomainGroup | None:
        """Create domain group from OAuth group."""
        try:
            # Check if domain group already exists
            existing_group = (
                db.query(DomainGroup)
                .filter(DomainGroup.external_id == f"oauth:{oauth_group}")
                .first()
            )

            if existing_group:
                return existing_group

            # Create new domain group
            domain_group = DomainGroup(
                name=oauth_group,
                display_name=f"OAuth Group: {oauth_group}",
                domain_type="TEAM",
                external_id=f"oauth:{oauth_group}",
                tags=["oauth", "auto-created"],
                is_system=True,
                settings={"oauth_source": True},
            )

            db.add(domain_group)
            db.commit()
            db.refresh(domain_group)

            return domain_group

        except Exception as e:
            logger.exception(f"Failed to create domain group from OAuth: {str(e)}")
            return None


class SSOManager:
    """Main SSO manager for handling multiple providers."""

    def __init__(self, config: dict[str, Any]):
        self.providers = {}
        self.config = config

        # Initialize providers
        self._init_providers()

    def _init_providers(self):
        """Initialize SSO providers from configuration."""
        providers_config = self.config.get("providers", {})

        for provider_name, provider_config in providers_config.items():
            try:
                provider_type = provider_config.get("type", "").lower()

                if provider_type == "ldap":
                    self.providers[provider_name] = LDAPProvider(provider_config)
                elif provider_type == "saml":
                    self.providers[provider_name] = SAMLProvider(provider_config)
                elif provider_type == "oauth":
                    self.providers[provider_name] = OAuthProvider(provider_config)
                else:
                    logger.warning(f"Unknown SSO provider type: {provider_type}")

            except Exception as e:
                logger.exception(
                    f"Failed to initialize SSO provider {provider_name}: {str(e)}",
                )

    async def authenticate(
        self,
        provider_name: str,
        credentials: dict[str, Any],
        db: Session,
    ) -> tuple[User, dict[str, Any]]:
        """Authenticate user with specified SSO provider."""
        provider = self.providers.get(provider_name)
        if not provider:
            raise SSOConfigurationError(f"SSO provider '{provider_name}' not found")

        if not provider.enabled:
            raise SSOConfigurationError(f"SSO provider '{provider_name}' is disabled")

        return await provider.authenticate(credentials, db)

    async def get_user_info(
        self,
        provider_name: str,
        user_id: str,
        db: Session,
    ) -> dict[str, Any]:
        """Get user information from specified SSO provider."""
        provider = self.providers.get(provider_name)
        if not provider:
            raise SSOConfigurationError(f"SSO provider '{provider_name}' not found")

        return await provider.get_user_info(user_id, db)

    async def sync_user_groups(
        self,
        provider_name: str,
        user: User,
        db: Session,
    ) -> list[str]:
        """Synchronize user groups from specified SSO provider."""
        provider = self.providers.get(provider_name)
        if not provider:
            raise SSOConfigurationError(f"SSO provider '{provider_name}' not found")

        return await provider.sync_user_groups(user, db)

    def get_available_providers(self) -> list[dict[str, Any]]:
        """Get list of available SSO providers."""
        providers = []
        for name, provider in self.providers.items():
            providers.append(
                {
                    "name": name,
                    "type": provider.__class__.__name__.replace("Provider", "").lower(),
                    "enabled": provider.enabled,
                    "priority": provider.priority,
                },
            )

        return sorted(providers, key=lambda x: x["priority"])

    def get_provider_config(self, provider_name: str) -> dict[str, Any]:
        """Get configuration for specified SSO provider."""
        provider = self.providers.get(provider_name)
        if not provider:
            return {}

        return {
            "name": provider.name,
            "type": provider.__class__.__name__.replace("Provider", "").lower(),
            "enabled": provider.enabled,
            "priority": provider.priority,
            "config": provider.config,
        }

    async def validate_token(self, provider_name: str, token: str) -> dict[str, Any]:
        """Validate token from specified SSO provider."""
        provider = self.providers.get(provider_name)
        if not provider:
            raise SSOConfigurationError(f"SSO provider '{provider_name}' not found")

        return await provider.validate_token(token)


# Global SSO manager instance
sso_manager = None


def init_sso_manager(config: dict[str, Any]):
    """Initialize global SSO manager."""
    global sso_manager
    sso_manager = SSOManager(config)


def get_sso_manager() -> SSOManager:
    """Get global SSO manager instance."""
    if sso_manager is None:
        raise SSOConfigurationError("SSO manager not initialized")
    return sso_manager
