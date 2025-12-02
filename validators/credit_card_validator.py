"""Credit card number validation using Luhn algorithm."""

import re
from typing import Optional, Tuple


class CreditCardValidator:
    """Validates credit card numbers using Luhn algorithm and format checks."""
    
    # Credit card patterns by type
    CARD_PATTERNS = {
        'visa': re.compile(r'^4[0-9]{12}(?:[0-9]{3})?$'),
        'mastercard': re.compile(r'^5[1-5][0-9]{14}$'),
        'amex': re.compile(r'^3[47][0-9]{13}$'),
        'discover': re.compile(r'^6(?:011|5[0-9]{2})[0-9]{12}$'),
        'diners': re.compile(r'^3[0-9]{13}$'),
        'jcb': re.compile(r'^(?:2131|1800|35\d{3})\d{11}$'),
    }
    
    @staticmethod
    def luhn_check(card_number: str) -> bool:
        """Validate credit card number using Luhn algorithm.
        
        Args:
            card_number: Credit card number as string (digits only)
            
        Returns:
            True if Luhn check passes
        """
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', card_number)
        
        if not digits or len(digits) < 13:
            return False
        
        # Luhn algorithm
        total = 0
        reverse_digits = digits[::-1]
        
        for i, digit in enumerate(reverse_digits):
            n = int(digit)
            if i % 2 == 1:  # Every second digit from right
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        
        return total % 10 == 0
    
    @staticmethod
    def get_card_type(card_number: str) -> Optional[str]:
        """Determine credit card type from number.
        
        Args:
            card_number: Credit card number as string
            
        Returns:
            Card type ('visa', 'mastercard', 'amex', etc.) or None
        """
        digits = re.sub(r'\D', '', card_number)
        
        for card_type, pattern in CreditCardValidator.CARD_PATTERNS.items():
            if pattern.match(digits):
                return card_type
        
        return None
    
    @staticmethod
    def validate(card_number: str) -> Tuple[bool, Optional[str]]:
        """Validate credit card number.
        
        Args:
            card_number: Credit card number as string (may contain spaces/dashes)
            
        Returns:
            Tuple of (is_valid, card_type)
        """
        # Remove spaces and dashes
        digits = re.sub(r'[\s\-]', '', card_number)
        
        # Check length (credit cards are 13-19 digits)
        if len(digits) < 13 or len(digits) > 19:
            return False, None
        
        # Check if all digits
        if not digits.isdigit():
            return False, None
        
        # Luhn check
        if not CreditCardValidator.luhn_check(digits):
            return False, None
        
        # Determine card type
        card_type = CreditCardValidator.get_card_type(digits)
        
        return True, card_type
    
    @staticmethod
    def normalize(card_number: str) -> str:
        """Normalize credit card number (remove spaces/dashes).
        
        Args:
            card_number: Credit card number as string
            
        Returns:
            Normalized card number (digits only)
        """
        return re.sub(r'[\s\-]', '', card_number)
