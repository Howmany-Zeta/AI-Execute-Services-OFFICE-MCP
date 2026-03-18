# python-middleware/app/tools/__init__.py

import importlib
import inspect
import logging
import os
import pkgutil
from typing import Dict, Any

from aiecs.tools.base_tool import BaseTool

logger = logging.getLogger(__name__)

# Global tool registry
TOOL_REGISTRY: Dict[str, Any] = {}
TOOL_CLASSES: Dict[str, Any] = {}
# TOOL_CONFIGS: Legacy configuration dictionary.
# Values here are passed as explicit config to tools (highest precedence).
# Prefer using YAML config files (config/tools/{tool_name}.yaml) or .env files instead.
TOOL_CONFIGS: Dict[str, Any] = {}


def register_tool(name):
    """
    Decorator for registering tool classes

    Args:
        name: Tool name

    Returns:
        Decorated class
    """

    def wrapper(cls):
        # Store tool class but don't instantiate immediately
        TOOL_CLASSES[name] = cls
        # Backward compatibility: if class inherits from BaseTool, don't
        # instantiate immediately
        if not issubclass(cls, BaseTool):
            TOOL_REGISTRY[name] = cls()
        return cls

    return wrapper


def get_tool(name):
    """
    Get tool instance

    Args:
        name: Tool name

    Returns:
        Tool instance

    Raises:
        ValueError: If tool is not registered
    """
    # Check if placeholder needs to be replaced or lazy instantiation is needed
    if name in TOOL_CLASSES:
        # If TOOL_REGISTRY contains placeholder or doesn't exist, instantiate
        # real tool class
        current_tool = TOOL_REGISTRY.get(name)
        is_placeholder = getattr(current_tool, "is_placeholder", False)

        if current_tool is None or is_placeholder:
            # Lazy instantiation of BaseTool subclasses, replace placeholder
            # Configuration is loaded automatically by BaseTool using ToolConfigLoader:
            # 1. TOOL_CONFIGS values (explicit config, highest precedence)
            # 2. YAML config files (config/tools/{tool_name}.yaml or config/tools.yaml)
            # 3. Environment variables (via dotenv from .env files)
            # 4. Tool defaults (lowest priority)
            tool_class = TOOL_CLASSES[name]
            config = TOOL_CONFIGS.get(name, {})
            # Pass tool name to BaseTool for config file discovery (used for YAML file lookup)
            # Check if tool class accepts tool_name parameter (for backward compatibility)
            sig = inspect.signature(tool_class.__init__)
            if "tool_name" in sig.parameters or any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
            ):
                TOOL_REGISTRY[name] = tool_class(config=config, tool_name=name)
            else:
                # Tool class doesn't accept tool_name, only pass config
                TOOL_REGISTRY[name] = tool_class(config=config)
            logger.debug(f"Instantiated tool '{name}' from class {tool_class.__name__}")

    if name not in TOOL_REGISTRY:
        raise ValueError(f"Tool '{name}' is not registered")

    return TOOL_REGISTRY[name]


def list_tools():
    """
    List all registered tools

    Returns:
        List of tool information dictionaries
    """
    tools = []
    all_tool_names = list(set(list(TOOL_REGISTRY.keys()) + list(TOOL_CLASSES.keys())))

    for tool_name in all_tool_names:
        try:
            # Prefer using information from existing instances
            if tool_name in TOOL_REGISTRY:
                tool_instance = TOOL_REGISTRY[tool_name]
                tool_info = {
                    "name": tool_name,
                    "description": getattr(tool_instance, "description", f"{tool_name} tool"),
                    "category": getattr(tool_instance, "category", "general"),
                    "class_name": tool_instance.__class__.__name__,
                    "module": tool_instance.__class__.__module__,
                    "status": "loaded",
                }
            elif tool_name in TOOL_CLASSES:
                # Get information from class definition but don't instantiate
                tool_class = TOOL_CLASSES[tool_name]
                tool_info = {
                    "name": tool_name,
                    "description": getattr(tool_class, "description", f"{tool_name} tool"),
                    "category": getattr(tool_class, "category", "general"),
                    "class_name": tool_class.__name__,
                    "module": tool_class.__module__,
                    "status": "available",
                }
            else:
                continue

            tools.append(tool_info)

        except Exception as e:
            logger.warning(f"Failed to get info for tool {tool_name}: {e}")
            # Provide basic information
            tools.append(
                {
                    "name": tool_name,
                    "description": f"{tool_name} (info unavailable)",
                    "category": "unknown",
                    "class_name": "Unknown",
                    "module": "unknown",
                    "status": "error",
                }
            )

    return tools


def discover_tools(package_path: str = "aiecs.tools"):
    """
    Discover and register all tools in the package

    Args:
        package_path: Package path to search
    """
    package = importlib.import_module(package_path)
    if package.__file__ is None:
        return
    package_dir = os.path.dirname(package.__file__)

    for _, module_name, is_pkg in pkgutil.iter_modules([package_dir]):
        if is_pkg:
            # Recursively search for tools in subpackages
            discover_tools(f"{package_path}.{module_name}")
        else:
            # Import module
            try:
                importlib.import_module(f"{package_path}.{module_name}")
            except Exception as e:
                logger.error(f"Error importing module {module_name}: {e}")


# Lazy loading strategy: don't import all tools at package init
# Tools will be loaded on-demand when requested


def _ensure_task_tools_available():
    """Ensure task_tools module is available for lazy loading"""
    try:
        return True
    except ImportError as e:
        logger.error(f"Failed to import task_tools: {e}")
        return False


def _auto_discover_tools():
    """Automatically discover all tools by scanning tool directories"""
    import re

    # Define tool directories and their categories
    tool_dirs = [
        ("task_tools", "task"),
        ("docs", "docs"),
        ("statistics", "statistics"),
        ("search_tool", "task"),  # Enhanced search tool
        ("api_sources", "task"),  # API data sources (legacy)
        ("knowledge_graph", "knowledge_graph"),  # Knowledge Graph tools
    ]

    discovered_tools = []

    for dir_name, category in tool_dirs:
        dir_path = os.path.join(os.path.dirname(__file__), dir_name)
        if not os.path.exists(dir_path):
            continue

        # Check if this is a package (has __init__.py) or a directory of
        # modules
        init_file = os.path.join(dir_path, "__init__.py")
        files_to_scan = []

        if os.path.isfile(init_file):
            # Scan __init__.py for package-level registrations
            files_to_scan.append(("__init__.py", init_file))

        # Scan all other Python files in the directory
        for filename in os.listdir(dir_path):
            if filename.endswith(".py") and not filename.startswith("__"):
                file_path = os.path.join(dir_path, filename)
                files_to_scan.append((filename, file_path))

        # Process all files
        for filename, file_path in files_to_scan:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                    # Find @register_tool decorators (two patterns)
                    # Pattern 1: @register_tool("name") decorator syntax
                    decorator_pattern = r'@register_tool\([\'"]([^\'"]+)[\'"]\)'
                    decorator_matches = re.findall(decorator_pattern, content)

                    # Pattern 2: register_tool("name")(ClassName) function call
                    # syntax
                    function_pattern = r'register_tool\([\'"]([^\'"]+)[\'"]\)\([A-Za-z_][A-Za-z0-9_]*\)'
                    function_matches = re.findall(function_pattern, content)

                    # Combine all matches
                    all_matches = list(set(decorator_matches + function_matches))

                    for tool_name in all_matches:
                        # Try to extract description from class docstring or
                        # module docstring
                        description = f"{tool_name} tool"

                        # Method 1: Look for class definition after the
                        # decorator
                        class_pattern = rf'@register_tool\([\'"]({tool_name})[\'"]\)\s*class\s+\w+.*?"""(.*?)"""'
                        class_match = re.search(class_pattern, content, re.DOTALL)
                        if class_match:
                            doc = class_match.group(2).strip()
                            # Get first line of docstring
                            first_line = doc.split("\n")[0].strip()
                            if first_line and len(first_line) < 200:
                                description = first_line

                        # Method 2: For __init__.py files, try to extract from
                        # module docstring
                        if not class_match and filename == "__init__.py":
                            module_doc_pattern = r'^"""(.*?)"""'
                            module_doc_match = re.search(
                                module_doc_pattern,
                                content,
                                re.DOTALL | re.MULTILINE,
                            )
                            if module_doc_match:
                                doc = module_doc_match.group(1).strip()
                                # Get first non-empty line
                                for line in doc.split("\n"):
                                    line = line.strip()
                                    if line and not line.startswith("#") and len(line) < 200:
                                        description = line
                                        break

                        discovered_tools.append((tool_name, description, category))
            except Exception as e:
                logger.debug(f"Error scanning {filename}: {e}")

    return discovered_tools


def _register_known_tools():
    """Register known tools without importing heavy dependencies"""
    # Automatically discover all tools
    discovered_tools = _auto_discover_tools()

    logger.info(f"Auto-discovered {len(discovered_tools)} tools")

    # Register as placeholder until actually loaded
    for tool_info in discovered_tools:
        tool_name, description, category = tool_info
        if tool_name not in TOOL_REGISTRY and tool_name not in TOOL_CLASSES:
            # Create a placeholder class for discovery
            class ToolPlaceholder:
                def __init__(self, name, desc, cat):
                    self.name = name
                    self.description = desc
                    self.category = cat
                    self.is_placeholder = True

            TOOL_REGISTRY[tool_name] = ToolPlaceholder(tool_name, description, category)


# Register known tools for discovery
_register_known_tools()

try:
    pass
except ImportError:
    pass

try:
    pass
except ImportError:
    pass

# Don't auto-discover tools at import time for performance
# Tools will be discovered when explicitly requested via discover_tools() call
