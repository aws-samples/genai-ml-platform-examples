"""
Unit tests for encryption functionality in ConfigurationManager
"""

import pytest
import os
import tempfile
import yaml
from pathlib import Path
from mlp_sdk.config import ConfigurationManager
from mlp_sdk.exceptions import ConfigurationError


class TestEncryptionBasics:
    """Test basic encryption/decryption functionality"""
    
    def test_generate_key(self):
        """Test key generation produces valid base64 key"""
        key = ConfigurationManager.generate_key()
        assert isinstance(key, str)
        assert len(key) > 0
        
        # Should be able to use generated key
        import base64
        decoded = base64.b64decode(key)
        assert len(decoded) == 32  # AES-256 requires 32 bytes
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption are inverses"""
        key = ConfigurationManager.generate_key()
        config_mgr = ConfigurationManager(encryption_key=key)
        
        plaintext = "my-secret-value"
        encrypted = config_mgr.encrypt_value(plaintext)
        decrypted = config_mgr.decrypt_value(encrypted)
        
        assert decrypted == plaintext
        assert encrypted != plaintext  # Should be different
    
    def test_encrypt_with_different_keys_fails(self):
        """Test that decryption with wrong key fails"""
        key1 = ConfigurationManager.generate_key()
        key2 = ConfigurationManager.generate_key()
        
        config_mgr1 = ConfigurationManager(encryption_key=key1)
        config_mgr2 = ConfigurationManager(encryption_key=key2)
        
        plaintext = "my-secret-value"
        encrypted = config_mgr1.encrypt_value(plaintext)
        
        with pytest.raises(ConfigurationError):
            config_mgr2.decrypt_value(encrypted)
    
    def test_encrypt_without_key_fails(self):
        """Test that encryption without key raises error"""
        config_mgr = ConfigurationManager()
        
        with pytest.raises(ConfigurationError, match="No encryption key available"):
            config_mgr.encrypt_value("test")
    
    def test_decrypt_without_key_fails(self):
        """Test that decryption without key raises error"""
        config_mgr = ConfigurationManager()
        
        with pytest.raises(ConfigurationError, match="No encryption key available"):
            config_mgr.decrypt_value("test")


class TestKeyLoading:
    """Test loading keys from various sources"""
    
    def test_load_key_from_env(self):
        """Test loading key from environment variable"""
        key = ConfigurationManager.generate_key()
        os.environ['TEST_ENCRYPTION_KEY'] = key
        
        try:
            loaded_key = ConfigurationManager.load_key_from_env('TEST_ENCRYPTION_KEY')
            assert loaded_key is not None
            assert len(loaded_key) == 32
        finally:
            del os.environ['TEST_ENCRYPTION_KEY']
    
    def test_load_key_from_env_not_found(self):
        """Test loading key from non-existent env var returns None"""
        loaded_key = ConfigurationManager.load_key_from_env('NONEXISTENT_KEY')
        assert loaded_key is None
    
    def test_load_key_from_file(self):
        """Test loading key from file"""
        key = ConfigurationManager.generate_key()
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.key') as f:
            f.write(key)
            key_file = f.name
        
        try:
            loaded_key = ConfigurationManager.load_key_from_file(key_file)
            assert loaded_key is not None
            assert len(loaded_key) == 32
        finally:
            os.unlink(key_file)
    
    def test_load_key_from_file_not_found(self):
        """Test loading key from non-existent file raises error"""
        with pytest.raises(ConfigurationError, match="Encryption key file not found"):
            ConfigurationManager.load_key_from_file('/nonexistent/path/key.txt')


class TestConfigFileEncryption:
    """Test encrypting/decrypting configuration files"""
    
    def test_encrypt_decrypt_config_file(self):
        """Test encrypting and decrypting specific fields in config file"""
        key = ConfigurationManager.generate_key()
        config_mgr = ConfigurationManager(encryption_key=key)
        
        # Create test config
        test_config = {
            'defaults': {
                'iam': {
                    'execution_role': 'arn:aws:iam::123456789012:role/TestRole'
                },
                's3': {
                    'default_bucket': 'my-bucket'
                }
            }
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            input_file = os.path.join(tmpdir, 'input.yaml')
            encrypted_file = os.path.join(tmpdir, 'encrypted.yaml')
            decrypted_file = os.path.join(tmpdir, 'decrypted.yaml')
            
            # Write input config
            with open(input_file, 'w') as f:
                yaml.safe_dump(test_config, f)
            
            # Encrypt specific field
            config_mgr.encrypt_config_file(
                input_file,
                encrypted_file,
                ['defaults.iam.execution_role']
            )
            
            # Load encrypted config and verify field is encrypted
            with open(encrypted_file, 'r') as f:
                encrypted_config = yaml.safe_load(f)
            
            encrypted_role = encrypted_config['defaults']['iam']['execution_role']
            assert encrypted_role != test_config['defaults']['iam']['execution_role']
            
            # Decrypt the config
            config_mgr.decrypt_config_file(
                encrypted_file,
                decrypted_file,
                ['defaults.iam.execution_role']
            )
            
            # Load decrypted config and verify it matches original
            with open(decrypted_file, 'r') as f:
                decrypted_config = yaml.safe_load(f)
            
            assert decrypted_config == test_config
