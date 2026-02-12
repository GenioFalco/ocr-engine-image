import json
import jsonschema
from typing import Dict, Any, Optional

def validate_json(data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """
    Validate data against JSON schema.
    Returns True if valid, raises generic error or false if not.
    """
    try:
        jsonschema.validate(instance=data, schema=schema)
        return True
    except jsonschema.exceptions.ValidationError:
        return False
