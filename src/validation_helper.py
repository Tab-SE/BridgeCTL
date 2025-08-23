import re


class ValidK8sNodeOS:
    Ubuntu20_04 = "Ubuntu20.04"
    RELH_8 = "RELH-8"


class ValidationHelper:
    @staticmethod
    def is_valid_email(email):
        if not email:
            return False
        # RFC 5322 compliant email regex that handles most valid email formats
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    @staticmethod
    def is_valid_ipaddress(ipaddress):
        if not ipaddress:
            return False
        try:
            # Split into octets and validate each one
            octets = ipaddress.split('.')
            if len(octets) != 4:
                return False
            return all(0 <= int(octet) <= 255 for octet in octets)
        except (AttributeError, TypeError, ValueError):
            return False

    @staticmethod
    def is_valid_guid(guid):
        if not guid:
            return False
        # UUID format: 8 chars-4 chars-4 chars-4 chars-12 chars
        pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        return bool(re.match(pattern, guid))
    
    @staticmethod
    def is_property_not_null(data: dict, key: str):
        val = data.get(key)
        if not val:
            raise Exception(f"property {key} is null")
        return val
    
    valid_docker_image_pattern = r"^[a-zA-Z0-9_.-]*$"

    @classmethod
    def is_valid_docker_image_name(cls, name):
        if not name:
            return False
        return bool(re.match(cls.valid_docker_image_pattern, name))

    @classmethod
    def is_valid_host(cls, host):
        if not host:
            return False
        return re.match(r"^[a-zA-Z0-9.-]*$", host)
