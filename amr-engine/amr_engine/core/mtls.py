"""
Mutual TLS (mTLS) support for client certificate authentication.
"""
from __future__ import annotations

import logging
import ssl
from pathlib import Path
from typing import Optional
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from fastapi import Request, HTTPException, status

from ..config import get_settings

logger = logging.getLogger(__name__)


class MTLSValidator:
    """Validates client certificates for mTLS authentication."""
    
    def __init__(self):
        self.settings = get_settings()
        self._ca_cert: Optional[x509.Certificate] = None
        self._load_ca_certificate()
    
    def _load_ca_certificate(self) -> None:
        """Load CA certificate for client certificate validation."""
        if not self.settings.MTLS_CA_CERT_PATH:
            logger.warning("mTLS enabled but no CA certificate path configured")
            return
        
        ca_cert_path = Path(self.settings.MTLS_CA_CERT_PATH)
        if not ca_cert_path.exists():
            logger.error(f"CA certificate file not found: {ca_cert_path}")
            return
        
        try:
            with open(ca_cert_path, 'rb') as f:
                cert_data = f.read()
            
            # Try PEM format first
            try:
                self._ca_cert = x509.load_pem_x509_certificate(cert_data)
                logger.info("Loaded CA certificate in PEM format")
            except ValueError:
                # Try DER format
                self._ca_cert = x509.load_der_x509_certificate(cert_data)
                logger.info("Loaded CA certificate in DER format")
                
        except Exception as e:
            logger.error(f"Failed to load CA certificate: {e}")
            raise
    
    def validate_client_certificate(self, request: Request) -> Optional[dict]:
        """Validate client certificate from request."""
        if not self.settings.MTLS_ENABLED:
            return None
        
        # Get client certificate from request
        # Note: In a real deployment, this would be extracted from the TLS connection
        # For now, we'll check for certificate headers that might be set by a proxy
        cert_header = request.headers.get('X-Client-Cert')
        if not cert_header:
            if self.settings.MTLS_ENABLED:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Client certificate required for mTLS"
                )
            return None
        
        try:
            # Decode the certificate (assuming it's base64 encoded)
            import base64
            cert_data = base64.b64decode(cert_header)
            client_cert = x509.load_pem_x509_certificate(cert_data)
            
            return self._validate_certificate(client_cert)
            
        except Exception as e:
            logger.warning(f"Invalid client certificate: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid client certificate"
            )
    
    def _validate_certificate(self, client_cert: x509.Certificate) -> dict:
        """Validate client certificate against CA and extract client info."""
        if not self._ca_cert:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="mTLS validation not properly configured"
            )
        
        # Validate certificate chain (simplified - in production use full chain validation)
        try:
            # Check if certificate is signed by our CA
            ca_public_key = self._ca_cert.public_key()
            ca_public_key.verify(
                client_cert.signature,
                client_cert.tbs_certificate_bytes,
                # Note: This is a simplified validation, proper implementation
                # would use cryptography's validation methods
            )
        except Exception as e:
            logger.warning(f"Certificate validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Certificate not trusted"
            )
        
        # Check certificate validity period
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc)
        if now < client_cert.not_valid_before or now > client_cert.not_valid_after:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Certificate expired or not yet valid"
            )
        
        # Extract client information from certificate
        subject = client_cert.subject
        client_info = {
            "auth_method": "mtls",
            "certificate_subject": str(subject),
            "certificate_serial": str(client_cert.serial_number),
        }
        
        # Extract common name
        try:
            cn = subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            client_info["common_name"] = cn
            client_info["sub"] = cn
        except (IndexError, AttributeError):
            client_info["sub"] = f"cert:{client_cert.serial_number}"
        
        # Extract organization
        try:
            org = subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value
            client_info["organization"] = org
        except (IndexError, AttributeError):
            pass
        
        # Check for admin role in certificate extensions or subject
        client_info["scope"] = self._determine_scope(client_cert)
        
        return client_info
    
    def _determine_scope(self, client_cert: x509.Certificate) -> str:
        """Determine client scope/role from certificate."""
        # Check certificate extensions for role information
        try:
            # Look for custom extension or subject alternative name
            for extension in client_cert.extensions:
                if extension.oid._name == "subjectAltName":
                    san = extension.value
                    for name in san:
                        if hasattr(name, 'value') and 'admin' in name.value.lower():
                            return "admin"
        except Exception:
            pass
        
        # Check common name for admin indicators
        try:
            subject = client_cert.subject
            cn = subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
            if 'admin' in cn.lower() or 'administrator' in cn.lower():
                return "admin"
        except (IndexError, AttributeError):
            pass
        
        # Default scope
        return "user"


# Global mTLS validator instance
mtls_validator = MTLSValidator()


def validate_mtls(request: Request) -> Optional[dict]:
    """Validate mTLS client certificate from request."""
    return mtls_validator.validate_client_certificate(request)