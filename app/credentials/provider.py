from __future__ import annotations

import base64
import os
from abc import ABC, abstractmethod

from cryptography.fernet import Fernet


def _fernet_key_from_secret(secret: str) -> bytes:
    normalized = secret.encode("utf-8")
    if len(normalized) < 32:
        normalized = (normalized * ((32 // len(normalized)) + 1))[:32]
    return base64.urlsafe_b64encode(normalized[:32])


class CredentialProvider(ABC):
    @abstractmethod
    def store(self, credential_reference: str, secret_value: str) -> None: ...

    @abstractmethod
    def retrieve(self, credential_reference: str) -> str: ...

    @abstractmethod
    def delete(self, credential_reference: str) -> None: ...


class EnvironmentCredentialProvider(CredentialProvider):
    def __init__(self, encryption_key: str):
        self.cipher = Fernet(_fernet_key_from_secret(encryption_key))

    def store(self, credential_reference: str, secret_value: str) -> None:
        encrypted = self.cipher.encrypt(secret_value.encode("utf-8")).decode("utf-8")
        os.environ[credential_reference] = encrypted

    def retrieve(self, credential_reference: str) -> str:
        encrypted = os.getenv(credential_reference)
        if not encrypted:
            raise KeyError("Credential not found")
        return self.cipher.decrypt(encrypted.encode("utf-8")).decode("utf-8")

    def delete(self, credential_reference: str) -> None:
        os.environ.pop(credential_reference, None)
