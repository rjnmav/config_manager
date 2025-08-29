# ConfigManager

A **thread-safe, singleton-based** Python configuration manager for `.json` and `.cfg/.ini` files.  
Designed for **multi-threaded applications** where configuration data must be consistent, globally accessible, and safely updated at runtime.


## Overview

`ConfigManager` is a utility for managing application settings in a clean, centralized, and safe manner. It solves common configuration issues by:

- Using a **singleton pattern** to share state across your entire application.
- Guaranteeing **thread safety** for both read and write operations.
- Supporting multiple file formats: `.json`, `.cfg`, `.ini`.
- Allowing **dot-notation access** for nested JSON data.
- Providing **auto-save** or manual persistence options.

Ideal for microservices, long-running daemons, desktop apps, and CLI tools that require reliable configuration handling.

## Features

| Feature | Description |
|---------|-------------|
| **Singleton** | All instances share the same configuration state. |
| **Thread-Safe** | Multiple readers, one writer — no race conditions. |
| **Multi-Format** | Works with `.json`, `.cfg`, `.ini`. |
| **Auto-Save** | Instantly persists changes to disk if enabled. |
| **Dot-Notation** | Access nested JSON keys like `"database.host"`. |
| **Section Support** | Native handling for CFG/INI sections. |
| **Create or Load** | Automatically loads existing configs or creates new ones. |


## Installation

Install from PyPI:

```bash
pip install configmanager-threadsafe
```


## Usage

1. Create or Load a Config File

    ```python
    from config_manager import ConfigManager

    # Load existing or create a new JSON config
    config = ConfigManager("settings.json", initial_data={"app": {"debug": True}})
    ```

2. Get and Set Values

    ```python
    # Retrieve values (dot notation for JSON)
    debug_mode = config.get("app.debug", default=False)

    # Update values
    config.set("app.debug", False)
    ```

3. Work with CFG/INI Files

    ```python
    # Create a CFG config
    config = ConfigManager("settings.cfg", initial_data={"Database": {"host": "localhost"}})

    # Get a value from a section
    db_host = config.get("host", section="Database")

    # Set a value in a section
    config.set("host", "127.0.0.1", section="Database")
    ```

4. Thread-Safe Auto-Saving

    ```python
    config.set("app.mode", "production")  # Automatically saves if auto_save=True
    ```

5. Manual Save & Reload

    ```python
    config.save_config()  # Save manually
    config.reload()       # Reload from file
    ```

## API Reference

`ConfigManager(config_file=None, auto_save=True, initial_data=None)`
Creates or returns the global ConfigManager instance.

### Parameters:

- `config_file` (str | Path) – Path to `.json`, `.cfg`, or `.ini` file.
- `auto_save` (bool) – Whether to automatically save after changes.
- `initial_data` (dict) – Used when creating a new configuration.


## Core Methods
| Method                                                                | Description                                  |
| --------------------------------------------------------------------- | -------------------------------------------- |
| `load_config(path, auto_save=True)`                                   | Load config from an existing file.           |
| `create_config(path, initial_data=None, auto_save=True, force=False)` | Create a new config file.                    |
| `create_or_load_config(path, initial_data=None, auto_save=True)`      | Load if exists, else create new.             |
| `get(key, default=None, section=None)`                                | Retrieve a value (dot notation for JSON).    |
| `set(key, value, section=None)`                                       | Set a value (section required for CFG).      |
| `has(key, section=None)`                                              | Check if a key exists.                       |
| `delete(key, section=None)`                                           | Remove a key from config.                    |
| `get_section(section)`                                                | Get all keys in a section.                   |
| `get_all()`                                                           | Return the entire configuration.             |
| `save_config()`                                                       | Save the current state to disk.              |
| `reload()`                                                            | Reload from file, replacing in-memory state. |
| `reset()`                                                             | Clear all configuration data and settings.   |


## Thread Safety

`ConfigManager` is designed for safe concurrent usage:

- Singleton initialization is protected by a lock.
- Reads are allowed concurrently.
- Writes are serialized to prevent data corruption.
- File I/O operations are atomic.