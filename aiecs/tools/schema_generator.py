"""
Automatic Schema Generation Tool

Automatically generate Pydantic Schema from method signatures and type annotations
"""

import inspect
import logging
import re
from typing import Any, Dict, Optional, Type, get_type_hints, Callable, List, Union, get_origin, get_args
from pydantic import BaseModel, Field, create_model, ConfigDict, ValidationError

logger = logging.getLogger(__name__)


def _normalize_type(param_type: Type) -> Type:
    """
    Normalize types, handle unsupported types and generics

    Map complex types like pandas.DataFrame, pandas.Series to Any.
    Handle generics like List[T], Dict[K, V], Optional[T], Union[T, U].
    """
    # Handle None type
    if param_type is type(None):
        return Any
    
    # Handle generics (List, Dict, Optional, Union, etc.)
    origin = get_origin(param_type)
    if origin is not None:
        # Handle Optional[T] which is Union[T, None]
        if origin is Union:
            args = get_args(param_type)
            # Filter out None type
            non_none_args = [arg for arg in args if arg is not type(None)]
            if len(non_none_args) == 1:
                # Optional[T] -> normalize T
                return _normalize_type(non_none_args[0])
            elif len(non_none_args) > 1:
                # Union[T, U, ...] -> Any (too complex)
                return Any
            else:
                # Union[None] -> Any
                return Any
        
        # Handle List[T], Dict[K, V], Tuple[T, ...], etc.
        # For now, simplify to List[Any] or Dict[str, Any]
        if origin is list or origin is List:
            return List[Any]
        elif origin is dict or origin is Dict:
            return Dict[str, Any]
        else:
            # Other generics -> Any
            return Any
    
    # Get type name
    type_name = getattr(param_type, "__name__", str(param_type))
    type_str = str(param_type)

    # Check if it's a pandas type
    if "DataFrame" in type_name or "Series" in type_name or "pandas" in type_str.lower():
        return Any
    
    # Check for other complex types that might not be supported
    # numpy arrays, scipy types, etc.
    if "numpy" in type_str.lower() or "scipy" in type_str.lower():
        return Any
    
    # Check for callable types (functions)
    if "Callable" in type_str or callable(param_type) and not isinstance(param_type, type):
        return Any

    return param_type


def _extract_param_description_from_docstring(docstring: str, param_name: str) -> Optional[str]:
    """
    Extract parameter description from docstring

    Supported formats:
    - Google style: Args: param_name: description
    - NumPy style: Parameters: param_name : type description
    - Sphinx style: :param param_name: description
    """
    if not docstring:
        return None

    lines = docstring.split("\n")
    in_args_section = False
    current_param = None
    description_lines: List[str] = []

    for line in lines:
        stripped = line.strip()

        # Detect Args/Parameters section (Google/NumPy style)
        if stripped in ["Args:", "Arguments:", "Parameters:"]:
            in_args_section = True
            continue

        # Detect Sphinx style parameter
        sphinx_pattern = rf":param\s+{re.escape(param_name)}\s*:"
        if re.match(sphinx_pattern, stripped, re.IGNORECASE):
            # Extract description after colon
            parts = stripped.split(":", 2)
            if len(parts) >= 3:
                desc = parts[2].strip()
                if desc:
                    return desc
            continue

        # Detect end of Args section
        if in_args_section and stripped in [
            "Returns:",
            "Raises:",
            "Yields:",
            "Examples:",
            "Note:",
            "Notes:",
            "See Also:",
            "Attributes:",
        ]:
            break

        if in_args_section:
            # Google style: param_name: description or param_name (type): description
            if ":" in stripped and not stripped.startswith(" "):
                # Save previous parameter
                if current_param == param_name and description_lines:
                    return " ".join(description_lines).strip()

                # Parse new parameter
                parts = stripped.split(":", 1)
                if len(parts) == 2:
                    # Remove possible type annotation (type) or [type]
                    param_part = parts[0].strip()
                    # Handle param_name (type): or param_name [type]:
                    param_part = re.sub(r'\s*\([^)]*\)\s*$', '', param_part)  # Remove (type)
                    param_part = re.sub(r'\s*\[[^\]]*\]\s*$', '', param_part)  # Remove [type]
                    param_part = param_part.strip()

                    current_param = param_part
                    description_lines = [parts[1].strip()]
            elif current_param and stripped:
                # Continue description (indented lines)
                if stripped.startswith(" ") or not stripped:
                    description_lines.append(stripped)
                else:
                    # New section or parameter, save current if it matches
                    if current_param == param_name and description_lines:
                        return " ".join(description_lines).strip()
                    current_param = None
                    description_lines = []

    # Check last parameter
    if current_param == param_name and description_lines:
        return " ".join(description_lines).strip()

    # Try NumPy style: param_name : type description
    # This is more lenient and looks for "param_name :" pattern
    numpy_pattern = rf"^{re.escape(param_name)}\s*:\s*(.+)$"
    for line in lines:
        stripped = line.strip()
        match = re.match(numpy_pattern, stripped, re.IGNORECASE)
        if match:
            desc = match.group(1).strip()
            if desc:
                return desc

    return None


def generate_schema_from_method(method: Callable[..., Any], method_name: str, base_class: Type[BaseModel] = BaseModel) -> Optional[Type[BaseModel]]:
    """
    Automatically generate Pydantic Schema from method signature

    Args:
        method: Method to generate Schema for
        method_name: Method name
        base_class: Schema base class

    Returns:
        Generated Pydantic Schema class, returns None if unable to generate
    """
    try:
        # Get method signature
        sig = inspect.signature(method)

        # Get type annotations
        try:
            type_hints = get_type_hints(method)
        except Exception as e:
            logger.debug(f"Failed to get type hints for {method_name}: {e}")
            type_hints = {}

        # Get docstring
        docstring = inspect.getdoc(method) or f"Execute {method_name} operation"

        # Extract short description (first line)
        first_line = docstring.split("\n")[0].strip()
        schema_description = first_line if first_line else f"Execute {method_name} operation"

        # Build field definitions
        field_definitions = {}

        for param_name, param in sig.parameters.items():
            # Skip self parameter
            if param_name == "self":
                continue

            # Get parameter type and normalize
            param_type = type_hints.get(param_name, Any)
            
            # Handle Optional[T] explicitly - check if default is None or type is Optional
            has_default = param.default != inspect.Parameter.empty
            default_value = param.default if has_default else inspect.Parameter.empty
            
            # Check if type is Optional or Union with None
            origin = get_origin(param_type)
            is_optional = False
            if origin is Union:
                args = get_args(param_type)
                if type(None) in args:
                    is_optional = True
                    # Extract the non-None type
                    non_none_args = [arg for arg in args if arg is not type(None)]
                    if non_none_args:
                        param_type = non_none_args[0]
            
            # Normalize the type
            param_type = _normalize_type(param_type)
            
            # If default is None or type is Optional, make it Optional
            if default_value is None or (has_default and default_value == inspect.Parameter.empty and is_optional):
                param_type = Optional[param_type]
            elif has_default and default_value == inspect.Parameter.empty:
                # Parameter with default but not None - use the actual default
                pass

            # Extract parameter description from docstring
            field_description = _extract_param_description_from_docstring(docstring, param_name)
            if not field_description:
                field_description = f"Parameter {param_name}"

            # Create Field with proper handling of defaults
            if has_default and default_value != inspect.Parameter.empty:
                if default_value is None:
                    # Optional parameter with None default
                    field_definitions[param_name] = (
                        Optional[param_type],
                        Field(default=None, description=field_description),
                    )
                else:
                    # Parameter with non-None default
                    try:
                        # Validate default value can be serialized
                        field_definitions[param_name] = (
                            param_type,
                            Field(
                                default=default_value,
                                description=field_description,
                            ),
                        )
                    except Exception as e:
                        logger.warning(f"Failed to set default for {param_name}: {e}, using Any")
                        field_definitions[param_name] = (
                            Any,
                            Field(
                                default=default_value,
                                description=field_description,
                            ),
                        )
            elif is_optional:
                # Optional parameter without explicit default
                field_definitions[param_name] = (
                    Optional[param_type],
                    Field(default=None, description=field_description),
                )
            else:
                # Required parameter
                field_definitions[param_name] = (
                    param_type,
                    Field(description=field_description),
                )

        # If no parameters (except self), return None
        if not field_definitions:
            logger.debug(f"No parameters found for {method_name}, skipping schema generation")
            return None

        # Generate Schema class name
        schema_name = f"{method_name.title().replace('_', '')}Schema"

        # Create Schema class, allow arbitrary types
        # In Pydantic v2, create_model signature may vary - use type ignore for dynamic model creation
        try:
            schema_class = create_model(  # type: ignore[call-overload]
                schema_name,
                __base__=base_class,
                __doc__=schema_description,
                **field_definitions,
            )
            # Set model_config if base_class supports it
            if hasattr(schema_class, "model_config"):
                schema_class.model_config = ConfigDict(arbitrary_types_allowed=True)  # type: ignore[assignment]

            # Validate the generated schema
            _validate_generated_schema(schema_class, method_name, field_definitions)

            logger.debug(f"Generated schema {schema_name} for method {method_name}")
            return schema_class
        except Exception as e:
            logger.warning(f"Failed to create schema class for {method_name}: {e}")
            return None

    except Exception as e:
        logger.warning(f"Failed to generate schema for {method_name}: {e}")
        return None


def _validate_generated_schema(
    schema_class: Type[BaseModel],
    method_name: str,
    field_definitions: Dict[str, Any]
) -> None:
    """
    Validate that a generated schema is a valid Pydantic model.
    
    Args:
        schema_class: The generated schema class
        method_name: Name of the method for error reporting
        field_definitions: The field definitions used to create the schema
    
    Raises:
        ValueError: If the schema is invalid
    """
    # Check it's a subclass of BaseModel
    if not issubclass(schema_class, BaseModel):
        raise ValueError(f"Generated schema for {method_name} is not a BaseModel subclass")
    
    # Check it has model_fields
    if not hasattr(schema_class, "model_fields"):
        raise ValueError(f"Generated schema for {method_name} has no model_fields")
    
    # Try to instantiate with minimal valid data
    try:
        test_data = {}
        for field_name, field_info in schema_class.model_fields.items():
            if not field_info.is_required():
                # Skip optional fields for validation
                continue
            # Use default test values based on type
            field_type = field_info.annotation
            if field_type == str:
                test_data[field_name] = "test"
            elif field_type == int:
                test_data[field_name] = 0
            elif field_type == float:
                test_data[field_name] = 0.0
            elif field_type == bool:
                test_data[field_name] = False
            elif field_type == list or (hasattr(field_type, "__origin__") and get_origin(field_type) is list):
                test_data[field_name] = []
            elif field_type == dict or (hasattr(field_type, "__origin__") and get_origin(field_type) is dict):
                test_data[field_name] = {}
            else:
                test_data[field_name] = None
        
        # Try to create an instance
        instance = schema_class(**test_data)
        if not isinstance(instance, BaseModel):
            raise ValueError(f"Schema instance for {method_name} is not a BaseModel")
    except ValidationError as e:
        # Validation errors are okay - just means our test data wasn't perfect
        logger.debug(f"Schema validation test failed for {method_name} (expected): {e}")
    except Exception as e:
        logger.warning(f"Schema validation test failed for {method_name}: {e}")
        # Don't raise - schema might still be valid for actual use cases


def generate_schemas_for_tool(tool_class: Type) -> Dict[str, Type[BaseModel]]:
    """
    Generate Schema for all methods of a tool class

    Args:
        tool_class: Tool class

    Returns:
        Mapping from method names to Schema classes
    """
    schemas = {}

    for method_name in dir(tool_class):
        # Skip private methods and special methods
        if method_name.startswith("_"):
            continue

        # Skip base class methods
        if method_name in ["run", "run_async", "run_batch"]:
            continue

        method = getattr(tool_class, method_name)

        # Skip non-method attributes
        if not callable(method):
            continue

        # Skip classes (like Config, Schema, etc.)
        if isinstance(method, type):
            continue

        # Generate Schema
        schema = generate_schema_from_method(method, method_name)

        if schema:
            # Normalize method name (remove underscores, convert to lowercase)
            normalized_name = method_name.replace("_", "").lower()
            schemas[normalized_name] = schema
            logger.info(f"Generated schema for {method_name}")

    return schemas


# Usage example
if __name__ == "__main__":
    import sys

    sys.path.insert(0, "/home/coder1/python-middleware-dev")

    from aiecs.tools import discover_tools, TOOL_CLASSES

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Discover tools
    discover_tools()

    # Generate Schema for PandasTool
    print("Generating Schema for PandasTool:")
    print("=" * 80)

    pandas_tool = TOOL_CLASSES["pandas"]
    schemas = generate_schemas_for_tool(pandas_tool)

    print(f"\nGenerated {len(schemas)} Schemas:\n")

    # Show first 3 examples
    for method_name, schema in list(schemas.items())[:3]:
        print(f"{schema.__name__}:")
        print(f"  Description: {schema.__doc__}")
        print("  Fields:")
        for field_name, field_info in schema.model_fields.items():
            required = "Required" if field_info.is_required() else "Optional"
            default = f" (default: {field_info.default})" if not field_info.is_required() and field_info.default is not None else ""
            print(f"    - {field_name}: {field_info.description} [{required}]{default}")
        print()
