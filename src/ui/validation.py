"""
Validation utilities for copick entity names using copick.util.escape rules
"""
import re
from typing import Tuple


def validate_copick_name(input_str: str) -> Tuple[bool, str, str]:
    """
    Validate a string for use as copick object name, user_id or session_id.
    
    Args:
        input_str: The input string to validate
        
    Returns:
        Tuple of (is_valid, sanitized_name, error_message)
        - is_valid: True if the original string is valid
        - sanitized_name: The sanitized version of the input
        - error_message: Error message if invalid, empty string if valid
    """
    if not input_str:
        return False, "", "Name cannot be empty"
    
    # Define invalid characters pattern from copick.util.escape
    # Invalid: <>:"/\|?* (Windows), control chars, spaces, and underscores
    invalid_chars = r'[<>:"/\\|?*\x00-\x1F\x7F\s_]'
    
    # Check if string contains invalid characters
    has_invalid = bool(re.search(invalid_chars, input_str))
    
    # Create sanitized version
    sanitized = re.sub(invalid_chars, "-", input_str)
    sanitized = sanitized.strip("-")
    
    if sanitized == "":
        return False, "", "Name cannot consist only of invalid characters"
    
    if has_invalid:
        # Get list of invalid characters found
        invalid_found = set(re.findall(invalid_chars, input_str))
        invalid_list = ', '.join(f"'{char}'" if char != ' ' else "'space'" 
                                for char in sorted(invalid_found))
        error_msg = f"Invalid characters: {invalid_list}"
        return False, sanitized, error_msg
    
    return True, input_str, ""


def get_invalid_characters(input_str: str) -> list:
    """
    Get list of invalid characters in the input string.
    
    Args:
        input_str: The input string to check
        
    Returns:
        List of invalid characters found
    """
    invalid_chars = r'[<>:"/\\|?*\x00-\x1F\x7F\s_]'
    return list(set(re.findall(invalid_chars, input_str)))


def generate_smart_copy_name(base_name: str, existing_names: list) -> str:
    """
    Generate a smart copy name with auto-increment.
    Always uses -copy1, -copy2, etc. format.
    
    Args:
        base_name: The original name to copy
        existing_names: List of existing names to check against
        
    Returns:
        New unique name with -copy suffix and number
    """
    counter = 1
    while True:
        candidate = f"{base_name}-copy{counter}"
        if candidate not in existing_names:
            return candidate
        counter += 1