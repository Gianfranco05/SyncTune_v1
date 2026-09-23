from app.core import crypto


def test_encrypt_decrypt_roundtrip():
    token = "a-very-secret-spotify-refresh-token"
    encrypted = crypto.encrypt(token)
    assert encrypted != token
    assert crypto.decrypt(encrypted) == token


def test_encrypted_value_does_not_contain_the_plaintext():
    token = "another-secret-token-value"
    encrypted = crypto.encrypt(token)
    assert token not in encrypted
