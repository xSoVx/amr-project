"""
Mutual TLS (mTLS) Certificate Validation Module

This module provides secure certificate validation for healthcare applications,
implementing HIPAA-compliant mTLS authentication for AMR classification services.
"""

import ssl
import certifi
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.x509.verification import PolicyBuilder
from cryptography.x509.oid import NameOID, ExtensionOID


logger = logging.getLogger(__name__)


class MTLSValidationError(Exception):
    """Raised when mTLS certificate validation fails"""
    pass


class MTLSValidator:
    """
    Healthcare-grade mTLS certificate validator
    
    Provides comprehensive certificate validation against CA and allowed subjects
    for secure healthcare data exchange compliance.
    """
    
    def __init__(
        self, 
        ca_cert_path: str, 
        allowed_subjects: List[str],
        crl_urls: Optional[List[str]] = None,
        ocsp_enabled: bool = False
    ):
        """
        Initialize mTLS validator
        
        Args:
            ca_cert_path: Path to Certificate Authority certificate
            allowed_subjects: List of allowed certificate subject distinguished names
            crl_urls: Optional Certificate Revocation List URLs
            ocsp_enabled: Enable OCSP (Online Certificate Status Protocol) checking
        """
        self.ca_cert_path = Path(ca_cert_path)
        self.allowed_subjects = set(allowed_subjects)
        self.crl_urls = crl_urls or []
        self.ocsp_enabled = ocsp_enabled
        self._ca_cert = None
        self._load_ca_certificate()
        
    def _load_ca_certificate(self) -> None:
        """Load and validate CA certificate"""
        try:
            if not self.ca_cert_path.exists():
                raise MTLSValidationError(f"CA certificate not found: {self.ca_cert_path}")
                
            with open(self.ca_cert_path, 'rb') as f:
                cert_data = f.read()
                
            # Try PEM format first, then DER
            try:
                self._ca_cert = x509.load_pem_x509_certificate(cert_data, default_backend())
            except ValueError:
                self._ca_cert = x509.load_der_x509_certificate(cert_data, default_backend())
                
            logger.info(f"Loaded CA certificate: {self._ca_cert.subject}")
            
        except Exception as e:
            raise MTLSValidationError(f"Failed to load CA certificate: {e}")
    
    def validate_client_cert(self, cert_der: bytes) -> bool:
        """
        Validate client certificate against CA and allowed subjects
        
        Args:
            cert_der: Client certificate in DER format
            
        Returns:
            bool: True if certificate is valid, False otherwise
            
        Raises:
            MTLSValidationError: If validation fails critically
        """
        try:
            # Parse certificate
            cert = x509.load_der_x509_certificate(cert_der, default_backend())
            
            # Validate certificate chain
            if not self._validate_cert_chain(cert):
                logger.warning("Certificate chain validation failed")
                return False
                
            # Check subject against allowed list
            if not self._check_subject(cert):
                logger.warning(f"Certificate subject not allowed: {cert.subject}")
                return False
                
            # Check certificate validity period
            if not self._check_validity_period(cert):
                logger.warning("Certificate is expired or not yet valid")
                return False
                
            # Check key usage extensions
            if not self._check_key_usage(cert):
                logger.warning("Certificate key usage validation failed")
                return False
                
            # Check revocation status if configured
            if self.crl_urls or self.ocsp_enabled:
                if not self._check_revocation_status(cert):
                    logger.warning("Certificate revocation check failed")
                    return False
                    
            logger.info(f"Certificate validation successful: {cert.subject}")
            return True
            
        except Exception as e:
            logger.error(f"Certificate validation failed: {e}")
            raise MTLSValidationError(f"Certificate validation error: {e}")
    
    def _validate_cert_chain(self, cert: x509.Certificate) -> bool:
        """Validate certificate against CA chain"""
        try:
            # Build certificate store with CA certificate
            from cryptography.x509.verification import Store
            store = Store([self._ca_cert])
            
            # Build validation policy
            builder = PolicyBuilder().store(store)
            verifier = builder.build()
            
            # Verify certificate
            chain = verifier.verify(cert, [])
            return len(chain) > 0
            
        except Exception as e:
            logger.error(f"Certificate chain validation failed: {e}")
            return False
    
    def _check_subject(self, cert: x509.Certificate) -> bool:
        """Check if certificate subject is in allowed list"""
        try:
            subject_dn = cert.subject.rfc4514_string()
            
            # Check exact match first
            if subject_dn in self.allowed_subjects:
                return True
                
            # Check common name if exact match fails
            try:
                cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
                if cn in self.allowed_subjects:
                    return True
            except (IndexError, AttributeError):
                pass
                
            return False
            
        except Exception as e:
            logger.error(f"Subject validation failed: {e}")
            return False
    
    def _check_validity_period(self, cert: x509.Certificate) -> bool:
        """Check certificate validity period"""
        try:
            import datetime
            now = datetime.datetime.now(datetime.timezone.utc)
            
            if cert.not_valid_before_utc > now:
                logger.warning("Certificate not yet valid")
                return False
                
            if cert.not_valid_after_utc < now:
                logger.warning("Certificate has expired")
                return False
                
            # Warn if certificate expires soon (30 days)
            expires_soon = now + datetime.timedelta(days=30)
            if cert.not_valid_after_utc < expires_soon:
                logger.warning(f"Certificate expires soon: {cert.not_valid_after_utc}")
                
            return True
            
        except Exception as e:
            logger.error(f"Validity period check failed: {e}")
            return False
    
    def _check_key_usage(self, cert: x509.Certificate) -> bool:
        """Validate certificate key usage extensions"""
        try:
            # Check if key usage extension exists
            try:
                key_usage = cert.extensions.get_extension_for_oid(
                    ExtensionOID.KEY_USAGE
                ).value
                
                # For client certificates, we expect:
                # - digital_signature for authentication
                # - key_encipherment for key exchange
                if not (key_usage.digital_signature and key_usage.key_encipherment):
                    logger.warning("Invalid key usage for client certificate")
                    return False
                    
            except x509.ExtensionNotFound:
                # Key usage extension not found - acceptable for some deployments
                logger.info("Key usage extension not found in certificate")
                
            # Check enhanced key usage if present
            try:
                eku = cert.extensions.get_extension_for_oid(
                    ExtensionOID.EXTENDED_KEY_USAGE
                ).value
                
                # Check for client authentication
                from cryptography.x509.oid import ExtendedKeyUsageOID
                if ExtendedKeyUsageOID.CLIENT_AUTH not in eku:
                    logger.warning("Certificate missing client authentication EKU")
                    return False
                    
            except x509.ExtensionNotFound:
                # EKU extension not found - acceptable
                pass
                
            return True
            
        except Exception as e:
            logger.error(f"Key usage validation failed: {e}")
            return False
    
    def _check_revocation_status(self, cert: x509.Certificate) -> bool:
        """Check certificate revocation status via CRL or OCSP"""
        # Note: Full CRL/OCSP implementation would require additional dependencies
        # This is a placeholder for production implementation
        
        if self.crl_urls:
            logger.info("CRL checking not implemented - would check against URLs: %s", self.crl_urls)
            
        if self.ocsp_enabled:
            logger.info("OCSP checking not implemented - would validate certificate status")
            
        # For now, assume certificate is not revoked
        # In production, implement actual CRL/OCSP checking
        return True
    
    def get_cert_info(self, cert_der: bytes) -> Dict[str, Any]:
        """
        Extract certificate information for logging/debugging
        
        Args:
            cert_der: Certificate in DER format
            
        Returns:
            Dict containing certificate information
        """
        try:
            cert = x509.load_der_x509_certificate(cert_der, default_backend())
            
            return {
                "subject": cert.subject.rfc4514_string(),
                "issuer": cert.issuer.rfc4514_string(),
                "serial_number": str(cert.serial_number),
                "not_valid_before": cert.not_valid_before_utc.isoformat(),
                "not_valid_after": cert.not_valid_after_utc.isoformat(),
                "signature_algorithm": cert.signature_algorithm_oid._name,
                "public_key_algorithm": cert.public_key().algorithm.name
            }
            
        except Exception as e:
            logger.error(f"Failed to extract certificate info: {e}")
            return {"error": str(e)}


def create_ssl_context(
    ca_cert_path: str,
    client_cert_path: Optional[str] = None,
    client_key_path: Optional[str] = None,
    require_client_cert: bool = True
) -> ssl.SSLContext:
    """
    Create SSL context for mTLS connections
    
    Args:
        ca_cert_path: Path to CA certificate
        client_cert_path: Path to client certificate (for client-side)
        client_key_path: Path to client private key (for client-side)
        require_client_cert: Whether to require client certificates (server-side)
        
    Returns:
        Configured SSL context
    """
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    
    # Load CA certificate for verification
    context.load_verify_locations(ca_cert_path)
    
    # Configure certificate verification
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED if require_client_cert else ssl.CERT_OPTIONAL
    
    # Load client certificate and key if provided
    if client_cert_path and client_key_path:
        context.load_cert_chain(client_cert_path, client_key_path)
        
    # Security settings
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    
    # Cipher suite restrictions for healthcare compliance
    context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
    
    return context