import json
import os
from typing import Dict

class LanguageManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LanguageManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.current_lang = "en"
            self.translations: Dict[str, str] = {}
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.locales_dir = os.path.join(self.base_dir, "locales")
            self.initialized = True
            
            # Ensure locales dir exists
            if not os.path.exists(self.locales_dir):
                os.makedirs(self.locales_dir)

    def load_language(self, lang_code: str):
        """Loads the translation file for the given language code."""
        self.current_lang = lang_code
        file_path = os.path.join(self.locales_dir, f"{lang_code}.json")
        
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.translations = json.load(f)
            except Exception as e:
                print(f"Error loading language {lang_code}: {e}")
                self.translations = {}
        else:
            print(f"Warning: Locale file not found for {lang_code}")
            self.translations = {}

    def get(self, key: str) -> str:
        """Returns the translated string or the key if not found."""
        return self.translations.get(key, key)

    def is_rtl(self) -> bool:
        return self.current_lang == "ar"

# Global Instance helper
_manager = LanguageManager()

def tr(key: str, **kwargs) -> str:
    translated = _manager.get(key)
    # If translation is missing (manager returns key), don't uppercase it if it's a technical key
    is_missing = (translated == key)
    
    if kwargs:
        try:
            # Format raw translation
            res = translated.format(**kwargs)
            return res.upper()
        except (KeyError, ValueError):
            try:
                # Robust replacement
                res = translated
                for k, v in kwargs.items():
                    import re
                    res = re.sub(re.escape('{' + k + '}'), str(v), res, flags=re.IGNORECASE)
                return res.upper()
            except:
                pass
            
    return translated.upper() if not is_missing else translated
    
def get_lang_manager():
    return _manager
