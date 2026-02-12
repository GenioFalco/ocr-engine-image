from typing import List, Dict, Any, Optional

def is_duplicate(new_data: Dict[str, Any], existing_data_list: List[Dict[str, Any]], keys: List[str] = ["inn", "document_date", "number"]) -> bool:
    """
    Check if new_data is a duplicate of any item in existing_data_list based on keys.
    """
    if not existing_data_list:
        return False
        
    for item in existing_data_list:
        match = True
        for key in keys:
            val1 = new_data.get(key)
            val2 = item.get(key)
            # If key is missing in either, we can't be sure it's duplicate unless we are strict.
            # Let's say if all present keys match.
            if val1 and val2 and str(val1).strip().lower() != str(val2).strip().lower():
                match = False
                break
            if (val1 is None) != (val2 is None):
                match = False
                break
        
        if match:
            return True
            
    return False
