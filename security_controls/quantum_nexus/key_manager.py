# Quantum Nexus - Post-Quantum Key Manager
# Path: /security_controls/quantum_nexus/key_manager.py
# Description: Manages quantum-safe cryptographic keys with HSM integration

import os
import json
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from pyoqs import KeyEncapsulation, Signature

class QuantumKeyManager:
    def __init__(self, config_path='key_config.json'):
        self.kem_alg = "Kyber768"
        self.sig_alg = "Dilithium3"
        self.keys = {}
        self.load_config(config_path)
        
    def load_config(self, config_path):
        """Load key management configuration"""
        if os.path.exists(config_path):
            with open(config_path) as f:
                self.config = json.load(f)
        else:
            self.config = {
                "key_rotation_interval": 86400,
                "max_key_age": 604800,
                "hsm_integration": False
            }
    
    def generate_key_pair(self):
        """Generate new quantum-safe key pair"""
        kem = KeyEncapsulation(self.kem_alg)
        public_kem_key = kem.generate_keypair()
        secret_kem_key = kem.export_secret_key()
        
        sig = Signature(self.sig_alg)
        public_sig_key = sig.generate_keypair()
        secret_sig_key = sig.export_secret_key()
        
        key_id = os.urandom(16).hex()
        self.keys[key_id] = {
            'kem_public': public_kem_key,
            'kem_private': secret_kem_key,
            'sig_public': public_sig_key,
            'sig_private': secret_sig_key,
            'generated_at': int(time.time())
        }
        
        return key_id
    
    def hybrid_encrypt(self, key_id, plaintext):
        """Encrypt data using hybrid (PQ + ECC) scheme"""
        if key_id not in self.keys:
            raise ValueError("Invalid key ID")
            
        # Generate ephemeral ECC key
        ecc_priv = X25519PrivateKey.generate()
        ecc_pub = ecc_priv.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        # Perform KEM
        kem = KeyEncapsulation(self.kem_alg)
        kem_public = self.keys[key_id]['kem_public']
        ciphertext, shared_secret_kem = kem.encap_secret(kem_public)
        
        # Perform ECDH
        shared_secret_ecc = ecc_priv.exchange(
            X25519PrivateKey.from_private_bytes(
                self.keys[key_id]['kem_private'][:32]  # First 32 bytes as ECC key
            ).public_key()
        )
        
        # Derive final key
        hkdf = HKDF(
            algorithm=hashes.SHA384(),
            length=64,
            salt=None,
            info=b'quantum_hybrid',
            backend=default_backend()
        )
        final_key = hkdf.derive(shared_secret_kem + shared_secret_ecc)
        
        # Sign the ciphertext
        sig = Signature(self.sig_alg)
        sig_private = self.keys[key_id]['sig_private']
        signature = sig.sign(ciphertext + ecc_pub)
        
        return {
            'ciphertext': ciphertext,
            'ecc_pub': ecc_pub,
            'signature': signature,
            'key_id': key_id
        }
    
    def rotate_keys(self):
        """Rotate keys based on configured policy"""
        now = time.time()
        for key_id in list(self.keys.keys()):
            key_age = now - self.keys[key_id]['generated_at']
            if key_age > self.config['max_key_age']:
                self.revoke_key(key_id)
    
    def revoke_key(self, key_id):
        """Revoke a specific key"""
        if key_id in self.keys:
            # Securely wipe key material
            for k in ['kem_private', 'sig_private']:
                self.keys[key_id][k] = os.urandom(len(self.keys[key_id][k]))
            del self.keys[key_id]
