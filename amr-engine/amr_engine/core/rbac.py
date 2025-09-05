from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timedelta
from enum import Enum
from pydantic import BaseModel
import jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Role(str, Enum):
    """User roles with hierarchical permissions."""
    ADMIN = "admin"
    MICROBIOLOGIST = "microbiologist"  
    LAB_TECH = "lab_tech"
    CLINICIAN = "clinician"
    INFECTION_PREVENTION = "infection_prevention"
    SURVEILLANCE = "surveillance"
    READONLY = "readonly"


class Permission(str, Enum):
    """System permissions."""
    # Core AMR operations
    CLASSIFY_AMR = "classify_amr"
    VIEW_RESULTS = "view_results"
    
    # Data management
    CREATE_OBSERVATIONS = "create_observations"
    UPDATE_OBSERVATIONS = "update_observations"
    DELETE_OBSERVATIONS = "delete_observations"
    
    # Rules management
    VIEW_RULES = "view_rules"
    RELOAD_RULES = "reload_rules"
    MODIFY_RULES = "modify_rules"
    
    # Surveillance and analytics
    VIEW_SURVEILLANCE = "view_surveillance"
    GENERATE_ANTIBIOGRAM = "generate_antibiogram"
    EXPORT_SURVEILLANCE = "export_surveillance"
    
    # System administration
    MANAGE_USERS = "manage_users"
    MANAGE_SITES = "manage_sites"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    SYSTEM_CONFIG = "system_config"
    
    # MoH reporting
    SUBMIT_MOH_REPORTS = "submit_moh_reports"
    VIEW_MOH_REPORTS = "view_moh_reports"


class Site(BaseModel):
    """Healthcare site/facility."""
    site_id: str
    name: str
    address: Optional[str] = None
    contact_info: Optional[str] = None
    active: bool = True
    site_type: str = "hospital"  # hospital, clinic, lab, etc.
    parent_site_id: Optional[str] = None
    metadata: Dict[str, Any] = {}


class User(BaseModel):
    """System user with multi-site access."""
    user_id: str
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    roles: List[Role] = []
    site_access: List[str] = []  # List of site_ids user can access
    active: bool = True
    last_login: Optional[datetime] = None
    password_hash: Optional[str] = None
    metadata: Dict[str, Any] = {}


class RolePermissions:
    """Mapping of roles to permissions."""
    
    ROLE_PERMISSIONS = {
        Role.ADMIN: {
            Permission.CLASSIFY_AMR,
            Permission.VIEW_RESULTS,
            Permission.CREATE_OBSERVATIONS,
            Permission.UPDATE_OBSERVATIONS,
            Permission.DELETE_OBSERVATIONS,
            Permission.VIEW_RULES,
            Permission.RELOAD_RULES,
            Permission.MODIFY_RULES,
            Permission.VIEW_SURVEILLANCE,
            Permission.GENERATE_ANTIBIOGRAM,
            Permission.EXPORT_SURVEILLANCE,
            Permission.MANAGE_USERS,
            Permission.MANAGE_SITES,
            Permission.VIEW_AUDIT_LOGS,
            Permission.SYSTEM_CONFIG,
            Permission.SUBMIT_MOH_REPORTS,
            Permission.VIEW_MOH_REPORTS,
        },
        Role.MICROBIOLOGIST: {
            Permission.CLASSIFY_AMR,
            Permission.VIEW_RESULTS,
            Permission.CREATE_OBSERVATIONS,
            Permission.UPDATE_OBSERVATIONS,
            Permission.VIEW_RULES,
            Permission.VIEW_SURVEILLANCE,
            Permission.GENERATE_ANTIBIOGRAM,
            Permission.EXPORT_SURVEILLANCE,
            Permission.SUBMIT_MOH_REPORTS,
            Permission.VIEW_MOH_REPORTS,
        },
        Role.LAB_TECH: {
            Permission.CLASSIFY_AMR,
            Permission.VIEW_RESULTS,
            Permission.CREATE_OBSERVATIONS,
            Permission.VIEW_RULES,
        },
        Role.CLINICIAN: {
            Permission.CLASSIFY_AMR,
            Permission.VIEW_RESULTS,
            Permission.VIEW_SURVEILLANCE,
        },
        Role.INFECTION_PREVENTION: {
            Permission.VIEW_RESULTS,
            Permission.VIEW_SURVEILLANCE,
            Permission.GENERATE_ANTIBIOGRAM,
            Permission.EXPORT_SURVEILLANCE,
            Permission.VIEW_MOH_REPORTS,
        },
        Role.SURVEILLANCE: {
            Permission.VIEW_SURVEILLANCE,
            Permission.GENERATE_ANTIBIOGRAM,
            Permission.EXPORT_SURVEILLANCE,
            Permission.SUBMIT_MOH_REPORTS,
            Permission.VIEW_MOH_REPORTS,
        },
        Role.READONLY: {
            Permission.VIEW_RESULTS,
            Permission.VIEW_SURVEILLANCE,
        }
    }
    
    @classmethod
    def get_permissions(cls, roles: List[Role]) -> Set[Permission]:
        """Get all permissions for a list of roles."""
        permissions: Set[Permission] = set()
        for role in roles:
            permissions.update(cls.ROLE_PERMISSIONS.get(role, set()))
        return permissions


class RBACManager:
    """Role-Based Access Control manager."""
    
    def __init__(self, jwt_secret: str = "change-me-in-production"):
        self.jwt_secret = jwt_secret
        self.users: Dict[str, User] = {}
        self.sites: Dict[str, Site] = {}
        self._load_default_data()
    
    def _load_default_data(self):
        """Load default users and sites."""
        # Default admin user
        admin_user = User(
            user_id="admin",
            username="admin",
            email="admin@example.com",
            full_name="System Administrator",
            roles=[Role.ADMIN],
            site_access=["*"],  # Access to all sites
            password_hash=self.hash_password("admin123")
        )
        self.users[admin_user.user_id] = admin_user
        
        # Default site
        default_site = Site(
            site_id="site-001",
            name="Main Hospital",
            address="123 Medical Center Dr",
            site_type="hospital"
        )
        self.sites[default_site.site_id] = default_site
    
    def hash_password(self, password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def create_user(
        self, 
        username: str,
        password: str,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        roles: List[Role] = None,
        site_access: List[str] = None
    ) -> User:
        """Create a new user."""
        user_id = f"user-{len(self.users) + 1:04d}"
        user = User(
            user_id=user_id,
            username=username,
            email=email,
            full_name=full_name,
            roles=roles or [Role.READONLY],
            site_access=site_access or [],
            password_hash=self.hash_password(password)
        )
        self.users[user_id] = user
        return user
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user credentials."""
        user = self.get_user_by_username(username)
        if user and user.password_hash and self.verify_password(password, user.password_hash):
            user.last_login = datetime.utcnow()
            return user
        return None
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        for user in self.users.values():
            if user.username == username:
                return user
        return None
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self.users.get(user_id)
    
    def create_jwt_token(self, user: User, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT token for user."""
        to_encode = {
            "sub": user.user_id,
            "username": user.username,
            "roles": [role.value for role in user.roles],
            "site_access": user.site_access
        }
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=24)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.jwt_secret, algorithm="HS256")
        return encoded_jwt
    
    def verify_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            return payload
        except jwt.PyJWTError:
            return None
    
    def has_permission(self, user: User, permission: Permission) -> bool:
        """Check if user has specific permission."""
        user_permissions = RolePermissions.get_permissions(user.roles)
        return permission in user_permissions
    
    def can_access_site(self, user: User, site_id: str) -> bool:
        """Check if user can access specific site."""
        if "*" in user.site_access:  # Global access
            return True
        return site_id in user.site_access
    
    def filter_data_by_site_access(
        self, 
        user: User, 
        data: List[Dict[str, Any]], 
        site_field: str = "site_id"
    ) -> List[Dict[str, Any]]:
        """Filter data based on user's site access."""
        if "*" in user.site_access:
            return data
        
        return [
            item for item in data 
            if item.get(site_field) in user.site_access
        ]
    
    def create_site(
        self,
        name: str,
        address: Optional[str] = None,
        site_type: str = "hospital",
        parent_site_id: Optional[str] = None
    ) -> Site:
        """Create a new site."""
        site_id = f"site-{len(self.sites) + 1:03d}"
        site = Site(
            site_id=site_id,
            name=name,
            address=address,
            site_type=site_type,
            parent_site_id=parent_site_id
        )
        self.sites[site_id] = site
        return site
    
    def get_site(self, site_id: str) -> Optional[Site]:
        """Get site by ID."""
        return self.sites.get(site_id)
    
    def get_user_sites(self, user: User) -> List[Site]:
        """Get all sites accessible by user."""
        if "*" in user.site_access:
            return list(self.sites.values())
        
        return [
            site for site_id, site in self.sites.items()
            if site_id in user.site_access
        ]
    
    def add_user_to_site(self, user_id: str, site_id: str) -> bool:
        """Add user access to a site."""
        user = self.users.get(user_id)
        if user and site_id in self.sites:
            if site_id not in user.site_access:
                user.site_access.append(site_id)
            return True
        return False
    
    def remove_user_from_site(self, user_id: str, site_id: str) -> bool:
        """Remove user access from a site."""
        user = self.users.get(user_id)
        if user and site_id in user.site_access:
            user.site_access.remove(site_id)
            return True
        return False
    
    def update_user_roles(self, user_id: str, roles: List[Role]) -> bool:
        """Update user roles."""
        user = self.users.get(user_id)
        if user:
            user.roles = roles
            return True
        return False


class SecurityContext:
    """Security context for request processing."""
    
    def __init__(
        self,
        user: User,
        site_id: Optional[str] = None,
        permissions: Optional[Set[Permission]] = None
    ):
        self.user = user
        self.site_id = site_id
        self.permissions = permissions or RolePermissions.get_permissions(user.roles)
    
    def has_permission(self, permission: Permission) -> bool:
        """Check permission in current context."""
        return permission in self.permissions
    
    def can_access_site(self, site_id: str) -> bool:
        """Check site access in current context."""
        if "*" in self.user.site_access:
            return True
        return site_id in self.user.site_access
    
    def require_permission(self, permission: Permission):
        """Raise exception if permission not granted."""
        if not self.has_permission(permission):
            raise PermissionError(f"Permission '{permission.value}' required")
    
    def require_site_access(self, site_id: str):
        """Raise exception if site access not granted."""
        if not self.can_access_site(site_id):
            raise PermissionError(f"Access to site '{site_id}' not permitted")


# Global RBAC manager
rbac_manager = RBACManager()