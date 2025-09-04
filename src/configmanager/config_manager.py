# =============================================================================
# config_manager.py
#
# Description:
#   A configuration manager module for loading and managing configuration files
#   in various formats (e.g., JSON, CFG). Provides an interface to access and
#   update configuration values in Python projects.
#
# Usage:
#   from configmanager.config_manager import ConfigManager
#   config = ConfigManager('path/to/config.json')
#   value = config.get('section', 'key')
#
# Author: Rajan Panchal
# =============================================================================


import json
import threading
import configparser
from pathlib import Path
from typing import Any, Dict, Union, Optional, Type


class ConfigManager:
    """
    A fully thread-safe global configuration manager that supports both JSON and CFG files.
    Implements singleton pattern to ensure global access across the application.
    Once a config file is loaded, all instances will use the same configuration.
    
    Thread Safety Features:
    - Singleton creation is thread-safe
    - All read/write operations are thread-safe
    - File I/O operations are thread-safe
    - Supports multiple readers, single writer pattern
    """
    
    _instance = None
    _creation_lock = threading.Lock()  # For singleton creation
    
    def __new__(cls, config_file: Union[str, Path] = None, auto_save: bool = True, initial_data: Dict = None):
        if cls._instance is None:
            with cls._creation_lock:
                if cls._instance is None:
                    cls._instance = super(ConfigManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_file: Union[str, Path] = None, auto_save: bool = True, initial_data: Dict = None):
        if self._initialized:
            # If already initialized and no new config file specified, return existing instance
            if config_file is None:
                return
            # If a different config file is specified, issue a warning but keep existing config
            if config_file and self._config_file_path and Path(config_file) != self._config_file_path:
                print(f"Warning: ConfigManager already initialized with {self._config_file_path}. "
                      f"Ignoring new config file: {config_file}")
            return
            
        self._config_data = {}
        self._config_file_path = None
        self._file_type = None
        self._auto_save = auto_save
        
        # Thread safety locks
        self._data_lock = threading.RLock()  # For data operations (allows recursive calls)
        self._file_lock = threading.Lock()   # For file I/O operations
        
        self._initialized = True
        
        # Auto-load config file if provided
        if config_file:
            self.create_or_load_config(config_file, initial_data, auto_save)
    
    def load_config(self, file_path: Union[str, Path], auto_save: bool = True) -> None:
        """
        Load configuration from a file. Thread-safe.
        
        Args:
            file_path: Path to the configuration file (.json or .cfg/.ini)
            auto_save: Whether to automatically save changes to file
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        with self._file_lock:  # Ensure only one thread does file I/O at a time
            with self._data_lock:  # Ensure data consistency
                self._config_file_path = file_path
                self._auto_save = auto_save
                
                # Determine file type by extension
                extension = file_path.suffix.lower()
                if extension == '.json':
                    self._file_type = 'json'
                    self._load_json()
                elif extension in ['.cfg', '.ini']:
                    self._file_type = 'cfg'
                    self._load_cfg()
                else:
                    raise ValueError(f"Unsupported file type: {extension}. Supported types: .json, .cfg, .ini")
    
    def create_config(self, file_path: Union[str, Path], initial_data: Dict = None, auto_save: bool = True, force: bool = False) -> None:
        """
        Create a new configuration file with optional initial data. Thread-safe.
        
        Args:
            file_path: Path where to create the configuration file
            initial_data: Initial configuration data
            auto_save: Whether to automatically save changes to file
            force: If True, overwrites existing files; if False, raises error if file exists
        """
        file_path = Path(file_path)
        initial_data = initial_data or {}
        
        # Check if file exists and force is False
        if file_path.exists() and not force:
            raise FileExistsError(f"Configuration file already exists: {file_path}. Use force=True to overwrite.")
        
        with self._file_lock:  # Ensure only one thread does file I/O at a time
            with self._data_lock:  # Ensure data consistency
                # If this is switching to a new file, warn user
                if self._config_file_path and self._config_file_path != file_path:
                    print(f"Warning: Switching from {self._config_file_path} to {file_path}")
                
                self._config_file_path = file_path
                self._auto_save = auto_save
                self._config_data = initial_data.copy()
                
                # Determine file type by extension
                extension = file_path.suffix.lower()
                if extension == '.json':
                    self._file_type = 'json'
                elif extension in ['.cfg', '.ini']:
                    self._file_type = 'cfg'
                else:
                    raise ValueError(f"Unsupported file type: {extension}. Supported types: .json, .cfg, .ini")
                
                # Create directory if it doesn't exist
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Save initial config
                self._save_config_internal()

    def _merge_defaults_with_existing(self, existing_data: Dict, defaults: Dict, force_add: bool = False) -> Dict:
        """
        Merge default values with existing configuration, preserving existing values.
        Only adds keys that don't exist in the existing configuration.
        Uses case-insensitive key matching.
        
        Args:
            existing_data: Current configuration data
            defaults: Default values to merge
            force_add: If True, add directly to existing_data; if False, add to 'general' section
            
        Returns:
            Merged configuration data
        """
        merged = existing_data.copy()

        def key_exists_case_insensitive(target_dict, key):
            """Check if a key exists in dictionary (case-insensitive)"""
            key_lower = key.lower()
            return any(existing_key.lower() == key_lower for existing_key in target_dict.keys())

        for key, value in defaults.items():
            if force_add:
                # Direct addition to current level
                if not key_exists_case_insensitive(merged, key):
                    merged[key.lower()] = value
            elif not isinstance(value, dict):
                # Non-dict values go to 'general' section
                if 'general' not in merged:
                    merged['general'] = {}
                if not key_exists_case_insensitive(merged['general'], key):
                    merged['general'][key.lower()] = value
            else:
                # Dict values become sections
                section_key_lower = key.lower()
                if not key_exists_case_insensitive(merged, key):
                    merged[section_key_lower] = {}
                # Find the actual key (might be different case)
                actual_section_key = section_key_lower
                for existing_key in merged.keys():
                    if existing_key.lower() == section_key_lower:
                        actual_section_key = existing_key
                        break
                merged[actual_section_key] = self._merge_defaults_with_existing(merged[actual_section_key], value, force_add=True)
        return merged
    
    def create_or_load_config(self, file_path: Union[str, Path], initial_data: Dict = None, auto_save: bool = True) -> None:
        """
        Load config if file exists, otherwise create it with initial data. 
        If file exists, merge defaults with existing data (only add missing keys). Thread-safe.
        This is the method used internally by __init__.
        
        Args:
            file_path: Path to the configuration file
            initial_data: Initial configuration data (used as defaults)  
            auto_save: Whether to automatically save changes to file
        """
        file_path = Path(file_path)
        initial_data = initial_data or {}

        with self._file_lock:  # Ensure only one thread does file I/O at a time
            with self._data_lock:  # Ensure data consistency
                # If this is switching to a new file, warn user
                if self._config_file_path and self._config_file_path != file_path:
                    print(f"Warning: Switching from {self._config_file_path} to {file_path}")
                
                self._config_file_path = file_path
                self._auto_save = auto_save
                
                # Determine file type by extension
                extension = file_path.suffix.lower()
                if extension == '.json':
                    self._file_type = 'json'
                elif extension in ['.cfg', '.ini']:
                    self._file_type = 'cfg'
                else:
                    raise ValueError(f"Unsupported file type: {extension}. Supported types: .json, .cfg, .ini")
                
                # Create directory if it doesn't exist
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                if file_path.exists():
                    # File exists, load existing data
                    if self._file_type == 'json':
                        self._load_json()
                    elif self._file_type == 'cfg':
                        self._load_cfg()
                    
                    # Merge defaults with existing data (only add missing keys)
                    if initial_data:
                        self._config_data = self._merge_defaults_with_existing(self._config_data, initial_data)
                        if self._auto_save:
                            self._save_config_internal()
                else:
                    # File doesn't exist, create with initial data
                    self._config_data = initial_data.copy()
                    self._save_config_internal()
    
    def _load_json(self) -> None:
        """Load configuration from JSON file."""
        with open(self._config_file_path, 'r', encoding='utf-8') as f:
            self._config_data = json.load(f)
    
    def _load_cfg(self) -> None:
        """Load configuration from CFG/INI file."""
        parser = configparser.ConfigParser()
        # Preserve case of option names (keys)
        parser.optionxform = str
        parser.read(self._config_file_path, encoding='utf-8')
        
        # Convert ConfigParser to dictionary
        self._config_data = {}
        for section_name in parser.sections():
            self._config_data[section_name] = dict(parser[section_name])
    
    def save_config(self) -> None:
        """Save current configuration to file. Thread-safe."""
        with self._file_lock:
            self._save_config_internal()
    
    def _save_config_internal(self) -> None:
        """Internal save method - assumes file lock is already held."""
        if not self._config_file_path:
            raise ValueError("No configuration file path set. Use load_config() or create_config() first.")
        
        if self._file_type == 'json':
            self._save_json()
        elif self._file_type == 'cfg':
            self._save_cfg()
    
    def _save_json(self) -> None:
        """Save configuration to JSON file."""
        with open(self._config_file_path, 'w', encoding='utf-8') as f:
            json.dump(self._config_data, f, indent=4, ensure_ascii=False)
    
    def _save_cfg(self) -> None:
        """Save configuration to CFG/INI file."""
        parser = configparser.ConfigParser()
        # Preserve case of option names (keys)
        parser.optionxform = str
        
        # Add sections and keys
        for section_name, section_data in self._config_data.items():
            if not isinstance(section_data, dict):
                # If there's no 'general' section, create it
                if not parser.has_section('general'):
                    parser.add_section('general')
                parser.set('general', section_name, str(section_data))
            else:
                if not parser.has_section(section_name):
                    parser.add_section(section_name)
                for key, value in section_data.items():
                    parser.set(section_name, key, str(value))
        
        with open(self._config_file_path, 'w', encoding='utf-8') as f:
            parser.write(f)

    def get(self, key: str, default: Any = None, section: str = None, type_change: Type = None) -> Any:
        """
        Get a configuration value. Thread-safe.
        Uses case-insensitive key matching.

        Args:
            key: Configuration key
            default: Default value if key not found
            section: Section name (for CFG files, optional for JSON)
            type: Optional callable for type conversion (e.g., int, float)

        Returns:
            Configuration value (possibly type-converted), or default if not found.
        """
        with self._data_lock:
            data = self._config_data

            # Validate that _config_data is usable
            if not isinstance(data, dict):
                return default
            
            def str_to_bool(s: str) -> bool:
                s = s.strip().lower()
                if s in ("true", "1", "yes", "y", "t"):
                    return True
                elif s in ("false", "0", "no", "n", "f"):
                    return False
                else:
                    raise ValueError(f"Can't convert {s!r} to bool")

            # Helper for safe type conversion
            def convert(value):
                if type_change is None or value is None:
                    return value
                if not callable(type_change):
                    raise TypeError(f"Provided type '{type_change}' is not callable")
                try:
                    if type_change == bool and isinstance(value, str):
                        return str_to_bool(value)
                    return type_change(value)
                except (ValueError, TypeError):
                    raise ValueError(
                        f"Cannot convert value '{value}' for key '{key}' to type {getattr(type_change, '__name__', str(type_change))}"
                    )

            # Helper for case-insensitive key lookup
            def get_key_case_insensitive(target_dict, search_key):
                """Get value from dict using case-insensitive key matching"""
                if not isinstance(target_dict, dict):
                    return None
                search_key_lower = search_key.lower()
                for dict_key, dict_value in target_dict.items():
                    if dict_key.lower() == search_key_lower:
                        return dict_value
                return None

            # ---------- CFG with section ----------
            if self._file_type == 'cfg' and section:
                if not isinstance(section, str):
                    return default
                section_data = get_key_case_insensitive(data, section)
                if section_data is None:
                    return default
                value = get_key_case_insensitive(section_data, key)
                if value is None:
                    return default
                return convert(value)

            # ---------- CFG without section ----------
            if self._file_type == 'cfg' and not section:
                # Check top-level key (case-insensitive)
                value = get_key_case_insensitive(data, key)
                if value is not None:
                    return convert(value)
                # Search inside section dictionaries
                for sec, sec_data in data.items():
                    if isinstance(sec_data, dict):
                        value = get_key_case_insensitive(sec_data, key)
                        if value is not None:
                            return convert(value)
                return default

            # ---------- JSON or other formats ----------
            try:
                if section:
                    if section == 'general':
                        section_data = data
                    else:
                        section_data = get_key_case_insensitive(data, section)
                    if section_data is None:
                        return default
                    value = get_key_case_insensitive(section_data, key)
                    if value is None:
                        return default
                    return convert(value)
                else:
                    # First check top-level key (case-insensitive)
                    value = get_key_case_insensitive(data, key)
                    if value is not None:
                        return convert(value)
                    # Search inside section dictionaries
                    for sec_data in data.values():
                        if isinstance(sec_data, dict):
                            value = get_key_case_insensitive(sec_data, key)
                            if value is not None:
                                return convert(value)
                    return default
            except (KeyError, TypeError, AttributeError):
                return default
    
    def set(self, key: str, value: Any, section: str = None) -> None:
        """
        Set a configuration value. Thread-safe.
        
        Args:
            key: Configuration key
            value: Value to set
            section: Section name (required for CFG files, optional for JSON)
        """
        with self._data_lock:
            if self._file_type == 'cfg':
                if not section:
                    raise ValueError("Section is required for CFG files")
                
                if section not in self._config_data:
                    self._config_data[section] = {}
                
                self._config_data[section][key] = str(value)
            else:
                # For JSON, support nested keys with dot notation
                keys = key.split('.')
                data = self._config_data
                
                # Navigate to the parent of the target key
                for k in keys[:-1]:
                    if k not in data:
                        data[k] = {}
                    data = data[k]
                
                # Set the final key
                data[keys[-1]] = value
            
            if self._auto_save:
                with self._file_lock:
                    self._save_config_internal()
    
    def has(self, key: str, section: str = None) -> bool:
        """
        Check if a configuration key exists. Thread-safe.
        Uses case-insensitive key matching.
        
        Args:
            key: Configuration key
            section: Section name (for CFG files)
            
        Returns:
            True if key exists, False otherwise
        """
        # Helper for case-insensitive key lookup
        def key_exists_case_insensitive(target_dict, search_key):
            """Check if a key exists in dictionary (case-insensitive)"""
            if not isinstance(target_dict, dict):
                return False
            search_key_lower = search_key.lower()
            return any(existing_key.lower() == search_key_lower for existing_key in target_dict.keys())

        with self._data_lock:
            if self._file_type == 'cfg' and section:
                section_exists = key_exists_case_insensitive(self._config_data, section)
                if not section_exists:
                    return False
                # Find the actual section key
                actual_section_key = None
                for existing_key in self._config_data.keys():
                    if existing_key.lower() == section.lower():
                        actual_section_key = existing_key
                        break
                return key_exists_case_insensitive(self._config_data[actual_section_key], key)
            elif self._file_type == 'cfg' and not section:
                # Search in all sections
                for section_data in self._config_data.values():
                    if key_exists_case_insensitive(section_data, key):
                        return True
                return False
            else:
                # For JSON, support nested keys with dot notation
                keys = key.split('.')
                value = self._config_data
                try:
                    for k in keys[:-1]:
                        # Case-insensitive navigation
                        found_key = None
                        for existing_key in value.keys():
                            if existing_key.lower() == k.lower():
                                found_key = existing_key
                                break
                        if found_key is None:
                            return False
                        value = value[found_key]
                    # Check final key case-insensitively
                    return key_exists_case_insensitive(value, keys[-1])
                except (KeyError, TypeError):
                    return False
    
    def delete(self, key: str, section: str = None) -> bool:
        """
        Delete a configuration key. Thread-safe.
        
        Args:
            key: Configuration key to delete
            section: Section name (for CFG files)
            
        Returns:
            True if key was deleted, False if key didn't exist
        """
        with self._data_lock:
            if self._file_type == 'cfg':
                if not section:
                    raise ValueError("Section is required for CFG files")
                
                if section in self._config_data and key in self._config_data[section]:
                    del self._config_data[section][key]
                    if self._auto_save:
                        with self._file_lock:
                            self._save_config_internal()
                    return True
                return False
            else:
                # For JSON, support nested keys with dot notation
                keys = key.split('.')
                data = self._config_data
                
                try:
                    # Navigate to the parent of the target key
                    for k in keys[:-1]:
                        data = data[k]
                    
                    # Delete the final key
                    if keys[-1] in data:
                        del data[keys[-1]]
                        if self._auto_save:
                            with self._file_lock:
                                self._save_config_internal()
                        return True
                    return False
                except (KeyError, TypeError):
                    return False
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get all values from a specific section (CFG) or nested object (JSON). Thread-safe.
        
        Args:
            section: Section/object name
            
        Returns:
            Dictionary of key-value pairs
        """
        with self._data_lock:
            if self._file_type == 'cfg':
                return self._config_data.get(section, {}).copy()
            else:
                return self._config_data.get(section, {}).copy()
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get all configuration data. Thread-safe.
        
        Returns:
            Complete configuration dictionary
        """
        with self._data_lock:
            return self._config_data.copy()
    
    def reload(self) -> None:
        """Reload configuration from file. Thread-safe."""
        if not self._config_file_path or not self._config_file_path.exists():
            raise ValueError("No valid configuration file to reload")
        
        with self._file_lock:
            with self._data_lock:
                if self._file_type == 'json':
                    self._load_json()
                elif self._file_type == 'cfg':
                    self._load_cfg()
    
    def reset(self) -> None:
        """Reset the configuration manager (clear all data). Thread-safe."""
        with self._data_lock:
            self._config_data = {}
            self._config_file_path = None
            self._file_type = None
    
    @property
    def file_path(self) -> Optional[Path]:
        """Get the current configuration file path."""
        return self._config_file_path
    
    @property
    def file_type(self) -> Optional[str]:
        """Get the current configuration file type."""
        return self._file_type