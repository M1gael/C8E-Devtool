import os
import hashlib
import hmac
from tina4_python.orm import ORM, IntegerField, StringField

class Staff(ORM):
    table_name = "staff"

    id = IntegerField(primary_key=True, auto_increment=True)
    name = StringField(required=True, max_length=255)
    email = StringField(required=True, max_length=255)
    password_hash = StringField(required=True, max_length=255)

    def set_password(self, password):
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
        self.password_hash = salt.hex() + ":" + key.hex()

    def verify_password(self, password):
        if not self.password_hash:
            return False
        try:
            salt_hex, key_hex = self.password_hash.split(":")
            salt = bytes.fromhex(salt_hex)
            key = bytes.fromhex(key_hex)
            new_key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
            return hmac.compare_digest(key, new_key)
        except Exception:
            return False

    def safe_dict(self):
        data = self.to_dict()
        data.pop("password_hash", None)
        return data
