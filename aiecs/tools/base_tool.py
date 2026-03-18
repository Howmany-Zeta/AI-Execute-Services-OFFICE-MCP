import inspect
import logging
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, ValidationError
import re

from aiecs.tools.tool_executor import (
    InputValidationError,
    SecurityError,
    get_executor,
    ExecutorConfig,
)
from aiecs.config import get_tool_config_loader
from aiecs.tools.schema_generator import generate_schema_from_method

logger = logging.getLogger(__name__)


class BaseTool:
    """
    Base class for all tools, providing common functionality:
    - Input validation with Pydantic schemas
    - Caching with TTL and content-based keys
    - Concurrency with async/sync execution
    - Error handling with retries and context
    - Performance optimization with metrics
    - Logging with structured output

    Tools inheriting from this class focus on business logic, leveraging
    the executor's cross-cutting concerns.

    Example:
        class MyTool(BaseTool):
            class ReadSchema(BaseModel):
                path: str

            @validate_input(ReadSchema)
            @cache_result(ttl=300)
            @run_in_executor
            @measure_execution_time
            @sanitize_input
            def read(self, path: str):
                # Implementation
                pass
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, tool_name: Optional[str] = None):
        """
        Initialize the tool with optional configuration.

        Configuration is automatically loaded from:
        1. Explicit config dict (highest priority)
        2. YAML config files (config/tools/{tool_name}.yaml or config/tools.yaml)
        3. Environment variables (via dotenv from .env files)
        4. Tool defaults (lowest priority)

        Args:
            config (Dict[str, Any], optional): Tool-specific configuration that overrides
                all other sources. If None, configuration is loaded automatically.
            tool_name (str, optional): Registered tool name. If None, uses class name.

        Raises:
            ValueError: If config is invalid.
            ValidationError: If config validation fails (when Config class exists).
        """
        # Detect Config class if it exists
        config_class = self._detect_config_class()
        
        # Determine tool name (for config file discovery)
        if tool_name is None:
            tool_name = self.__class__.__name__
        
        # Load configuration using ToolConfigLoader
        if config_class:
            # Tool has Config class - use loader to load and validate config
            loader = get_tool_config_loader()
            try:
                loaded_config = loader.load_tool_config(
                    tool_name=tool_name,
                    config_schema=config_class,
                    explicit_config=config,
                )
                # Instantiate Config class with loaded config
                self._config_obj = config_class(**loaded_config)
                self._config = loaded_config
            except ValidationError as e:
                logger.error(f"Configuration validation failed for {tool_name}: {e}")
                raise
            except Exception as e:
                logger.warning(f"Failed to load configuration for {tool_name}: {e}. Using defaults.")
                # Fallback to explicit config or empty dict
                self._config = config or {}
                try:
                    self._config_obj = config_class(**self._config)
                except Exception:
                    # If even defaults fail, create empty config object
                    self._config_obj = None
        else:
            # No Config class - backward compatibility mode
            # Still try to load from YAML/env if config provided, otherwise use as-is
            if config:
                # Use explicit config as-is
                self._config = config
            else:
                # Try to load from YAML/env even without Config class
                loader = get_tool_config_loader()
                try:
                    self._config = loader.load_tool_config(
                        tool_name=tool_name,
                        config_schema=None,
                        explicit_config=None,
                    )
                except Exception as e:
                    logger.debug(f"Could not load config for {tool_name}: {e}. Using empty config.")
                    self._config = {}
            self._config_obj = None
        
        # Extract only executor-related config fields to avoid passing tool-specific
        # fields (e.g., user_agent, temp_dir) to ExecutorConfig
        executor_config = self._extract_executor_config(self._config)
        self._executor = get_executor(executor_config)
        self._schemas: Dict[str, Type[BaseModel]] = {}
        self._async_methods: List[str] = []
        # Schema coverage tracking
        self._schema_coverage: Dict[str, Any] = {
            "total_methods": 0,
            "manual_schemas": 0,
            "auto_generated_schemas": 0,
            "missing_schemas": 0,
            "schema_quality": {},
        }
        self._register_schemas()
        self._register_async_methods()
        # Log schema coverage after registration
        self._log_schema_coverage()

    def _extract_executor_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract only executor-related configuration fields from the full config.
        
        This prevents tool-specific fields (e.g., user_agent, temp_dir) from being
        passed to ExecutorConfig, which would cause validation issues or be silently
        ignored.
        
        Args:
            config (Dict[str, Any]): Full configuration dictionary.
            
        Returns:
            Dict[str, Any]: Filtered configuration containing only ExecutorConfig fields.
        """
        if not config:
            return {}
        
        # Get all valid field names from ExecutorConfig
        executor_fields = set(ExecutorConfig.model_fields.keys())
        
        # Filter config to only include executor-related fields
        executor_config = {
            key: value
            for key, value in config.items()
            if key in executor_fields
        }
        
        return executor_config

    def _detect_config_class(self) -> Optional[Type[BaseModel]]:
        """
        Detect Config class in tool class hierarchy via introspection.

        Looks for a class named 'Config' that inherits from BaseModel or BaseSettings.

        Returns:
            Config class if found, None otherwise
        """
        # Check current class and all base classes
        for cls in [self.__class__] + list(self.__class__.__mro__):
            if hasattr(cls, "Config"):
                config_attr = getattr(cls, "Config")
                # Check if Config is a class and inherits from BaseModel
                if isinstance(config_attr, type):
                    # Import BaseSettings here to avoid circular imports
                    try:
                        from pydantic_settings import BaseSettings
                        if issubclass(config_attr, (BaseModel, BaseSettings)):
                            return config_attr
                    except ImportError:
                        # Fallback if pydantic_settings not available
                        if issubclass(config_attr, BaseModel):
                            return config_attr
        return None

    def _register_schemas(self) -> None:
        """
        Register Pydantic schemas for operations by inspecting inner Schema classes.
        Falls back to auto-generation when manual schemas are missing.

        Example:
            class MyTool(BaseTool):
                class ReadSchema(BaseModel):
                    path: str
                def read(self, path: str):
                    pass
            # Registers 'read' -> ReadSchema (manual)
            # Auto-generates schema for 'write' if WriteSchema doesn't exist
        """
        # First pass: Register manual schemas
        manual_schemas = {}
        for attr_name in dir(self.__class__):
            attr = getattr(self.__class__, attr_name)
            if isinstance(attr, type) and issubclass(attr, BaseModel) and attr.__name__.endswith("Schema"):
                # Normalize schema name to operation name
                # Handle Method_nameSchema -> method_name convention
                schema_base_name = attr.__name__.replace("Schema", "")
                # Convert CamelCase to snake_case, then to lowercase
                # e.g., Read_csvSchema -> read_csv
                op_name = self._normalize_schema_name_to_method(schema_base_name)
                manual_schemas[op_name] = attr
                self._schemas[op_name] = attr
                self._schema_coverage["manual_schemas"] += 1
                logger.debug(f"Registered manual schema {attr.__name__} -> {op_name}")

        # Second pass: Auto-generate schemas for methods without manual schemas
        public_methods = self._get_public_methods()
        self._schema_coverage["total_methods"] = len(public_methods)
        
        for method_name in public_methods:
            # Skip if already has manual schema
            if method_name in self._schemas:
                continue
            
            # Skip async wrappers (they share schemas with sync methods)
            if method_name.endswith("_async"):
                sync_method_name = method_name[:-6]  # Remove "_async"
                if sync_method_name in self._schemas:
                    self._schemas[method_name] = self._schemas[sync_method_name]
                    logger.debug(f"Reusing schema for async method {method_name} from {sync_method_name}")
                    continue
            
            # Try to auto-generate schema
            method = getattr(self.__class__, method_name)
            if callable(method) and not isinstance(method, type):
                try:
                    auto_schema = generate_schema_from_method(method, method_name)
                    if auto_schema:
                        self._schemas[method_name] = auto_schema
                        self._schema_coverage["auto_generated_schemas"] += 1
                        logger.info(f"Auto-generated schema for method {method_name} -> {auto_schema.__name__}")
                    else:
                        self._schema_coverage["missing_schemas"] += 1
                        logger.debug(f"No schema generated for method {method_name} (no parameters)")
                except Exception as e:
                    self._schema_coverage["missing_schemas"] += 1
                    logger.warning(f"Failed to auto-generate schema for {method_name}: {e}")

    def _normalize_schema_name_to_method(self, schema_base_name: str) -> str:
        """
        Convert schema name to method name.
        
        Handles conventions like:
        - Read_csvSchema -> read_csv
        - ReadCsvSchema -> readcsv (fallback, but should use Read_csvSchema)
        - ReadSchema -> read
        
        Args:
            schema_base_name: Schema name without "Schema" suffix
            
        Returns:
            Normalized method name
        """
        # If name contains underscores, preserve them (e.g., Read_csv -> read_csv)
        if "_" in schema_base_name:
            # Convert first letter to lowercase, keep rest as-is
            if schema_base_name:
                return schema_base_name[0].lower() + schema_base_name[1:]
            return schema_base_name.lower()
        
        # Convert CamelCase to snake_case
        # Insert underscore before uppercase letters (except first)
        result = []
        for i, char in enumerate(schema_base_name):
            if char.isupper() and i > 0:
                result.append("_")
            result.append(char.lower())
        return "".join(result)

    def _get_public_methods(self) -> List[str]:
        """
        Get list of public methods that should have schemas.
        
        Returns:
            List of method names
        """
        methods = []
        for attr_name in dir(self.__class__):
            # Skip private methods
            if attr_name.startswith("_"):
                continue
            
            # Skip base class methods
            if attr_name in ["run", "run_async", "run_batch"]:
                continue
            
            attr = getattr(self.__class__, attr_name)
            
            # Skip non-method attributes
            if not callable(attr):
                continue
            
            # Skip classes (like Config, Schema, etc.)
            if isinstance(attr, type):
                continue
            
            methods.append(attr_name)
        
        return methods

    def _log_schema_coverage(self) -> None:
        """
        Log schema coverage metrics after registration.
        """
        coverage = self._schema_coverage
        total = coverage["total_methods"]
        if total == 0:
            return
        
        manual = coverage["manual_schemas"]
        auto = coverage["auto_generated_schemas"]
        missing = coverage["missing_schemas"]
        
        coverage_pct = ((manual + auto) / total * 100) if total > 0 else 0
        
        logger.info(
            f"Schema coverage for {self.__class__.__name__}: "
            f"{coverage_pct:.1f}% ({manual + auto}/{total}) - "
            f"Manual: {manual}, Auto: {auto}, Missing: {missing}"
        )
        
        if missing > 0:
            logger.debug(f"{missing} methods without schemas in {self.__class__.__name__}")

    def get_schema_coverage(self) -> Dict[str, Any]:
        """
        Get schema coverage metrics for this tool.
        
        Returns:
            Dictionary with coverage metrics:
            - total_methods: Total number of public methods
            - manual_schemas: Number of manually defined schemas
            - auto_generated_schemas: Number of auto-generated schemas
            - missing_schemas: Number of methods without schemas
            - coverage_percentage: Percentage of methods with schemas
            - quality_metrics: Quality metrics for schemas
        """
        total = self._schema_coverage["total_methods"]
        manual = self._schema_coverage["manual_schemas"]
        auto = self._schema_coverage["auto_generated_schemas"]
        missing = self._schema_coverage["missing_schemas"]
        
        coverage_pct = ((manual + auto) / total * 100) if total > 0 else 0
        
        # Calculate quality metrics
        quality_metrics = self._calculate_schema_quality()
        
        return {
            "total_methods": total,
            "manual_schemas": manual,
            "auto_generated_schemas": auto,
            "missing_schemas": missing,
            "coverage_percentage": coverage_pct,
            "quality_metrics": quality_metrics,
        }

    def _calculate_schema_quality(self) -> Dict[str, float]:
        """
        Calculate schema quality metrics.
        
        Returns:
            Dictionary with quality scores:
            - description_quality: Percentage of fields with meaningful descriptions
            - type_coverage: Percentage of fields with type annotations
            - overall_score: Overall quality score
        """
        total_fields = 0
        fields_with_descriptions = 0
        fields_with_types = 0
        
        for schema in self._schemas.values():
            if not hasattr(schema, "model_fields"):
                continue
            
            for field_name, field_info in schema.model_fields.items():
                total_fields += 1
                
                # Check for meaningful description (not just "Parameter {name}")
                desc = field_info.description
                if desc and desc != f"Parameter {field_name}":
                    fields_with_descriptions += 1
                
                # Check for type annotation
                if field_info.annotation is not None and field_info.annotation != Any:
                    fields_with_types += 1
        
        description_quality = (fields_with_descriptions / total_fields * 100) if total_fields > 0 else 0
        type_coverage = (fields_with_types / total_fields * 100) if total_fields > 0 else 0
        overall_score = (description_quality + type_coverage) / 2 if total_fields > 0 else 0
        
        return {
            "description_quality": description_quality,
            "type_coverage": type_coverage,
            "overall_score": overall_score,
        }

    def _register_async_methods(self) -> None:
        """
        Register async methods for proper execution handling.
        """
        for attr_name in dir(self.__class__):
            attr = getattr(self.__class__, attr_name)
            if inspect.iscoroutinefunction(attr) and not attr_name.startswith("_"):
                self._async_methods.append(attr_name)

    def _sanitize_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize keyword arguments to prevent injection attacks.

        Args:
            kwargs (Dict[str, Any]): Input keyword arguments.

        Returns:
            Dict[str, Any]: Sanitized keyword arguments.

        Raises:
            SecurityError: If kwargs contain malicious content.
        """
        sanitized = {}
        for k, v in kwargs.items():
            if isinstance(v, str) and re.search(r"(\bSELECT\b|\bINSERT\b|--|;|/\*)", v, re.IGNORECASE):
                raise SecurityError(f"Input parameter '{k}' contains potentially malicious content")
            sanitized[k] = v
        return sanitized

    def run(self, op: str, **kwargs) -> Any:
        """
        Execute a synchronous operation with parameters.

        Args:
            op (str): The name of the operation to execute.
            **kwargs: The parameters to pass to the operation.

        Returns:
            Any: The result of the operation.

        Raises:
            ToolExecutionError: If the operation fails.
            InputValidationError: If input parameters are invalid.
            SecurityError: If inputs contain malicious content.
        """
        schema_class = self._schemas.get(op)
        if schema_class:
            try:
                schema = schema_class(**kwargs)
                kwargs = schema.model_dump(exclude_unset=True)
            except ValidationError as e:
                raise InputValidationError(f"Invalid input parameters: {e}")
        kwargs = self._sanitize_kwargs(kwargs)
        return self._executor.execute(self, op, **kwargs)

    async def run_async(self, op: str, **kwargs) -> Any:
        """
        Execute an asynchronous operation with parameters.

        Args:
            op (str): The name of the operation to execute.
            **kwargs: The parameters to pass to the operation.

        Returns:
            Any: The result of the operation.

        Raises:
            ToolExecutionError: If the operation fails.
            InputValidationError: If input parameters are invalid.
            SecurityError: If inputs contain malicious content.
        """
        schema_class = self._schemas.get(op)
        if schema_class:
            try:
                schema = schema_class(**kwargs)
                kwargs = schema.model_dump(exclude_unset=True)
            except ValidationError as e:
                raise InputValidationError(f"Invalid input parameters: {e}")
        kwargs = self._sanitize_kwargs(kwargs)
        return await self._executor.execute_async(self, op, **kwargs)

    async def run_batch(self, operations: List[Dict[str, Any]]) -> List[Any]:
        """
        Execute multiple operations in parallel.

        Args:
            operations (List[Dict[str, Any]]): List of operation dictionaries with 'op' and 'kwargs'.

        Returns:
            List[Any]: List of operation results.

        Raises:
            ToolExecutionError: If any operation fails.
            InputValidationError: If input parameters are invalid.
        """
        return await self._executor.execute_batch(self, operations)

    def _get_method_schema(self, method_name: str) -> Optional[Type[BaseModel]]:
        """
        Get the schema for a method if it exists.
        Checks registered schemas first, then tries to find manual schema,
        and finally falls back to auto-generation.

        Args:
            method_name (str): The name of the method.

        Returns:
            Optional[Type[BaseModel]]: The schema class or None.
        """
        # First check registered schemas (includes both manual and auto-generated)
        if method_name in self._schemas:
            schema = self._schemas[method_name]
            # Log whether it's manual or auto-generated
            schema_type = "manual" if self._is_manual_schema(method_name, schema) else "auto-generated"
            logger.debug(f"Retrieved {schema_type} schema for method {method_name}")
            return schema
        
        # Try to find manual schema by convention
        # Convert method_name to schema name (e.g., read_csv -> Read_csvSchema)
        schema_name = self._method_name_to_schema_name(method_name)
        for attr_name in dir(self.__class__):
            if attr_name == schema_name:
                attr = getattr(self.__class__, attr_name)
                if isinstance(attr, type) and issubclass(attr, BaseModel):
                    # Register it for future use
                    self._schemas[method_name] = attr
                    self._schema_coverage["manual_schemas"] += 1
                    logger.debug(f"Found and registered manual schema {schema_name} for method {method_name}")
                    return attr
        
        # Fallback to auto-generation if method exists
        if hasattr(self.__class__, method_name):
            method = getattr(self.__class__, method_name)
            if callable(method) and not isinstance(method, type):
                try:
                    auto_schema = generate_schema_from_method(method, method_name)
                    if auto_schema:
                        self._schemas[method_name] = auto_schema
                        self._schema_coverage["auto_generated_schemas"] += 1
                        logger.info(f"Auto-generated schema on-demand for method {method_name}")
                        return auto_schema
                except Exception as e:
                    logger.debug(f"Could not auto-generate schema for {method_name}: {e}")
        
        return None

    def _method_name_to_schema_name(self, method_name: str) -> str:
        """
        Convert method name to schema name following convention.
        
        Examples:
        - read_csv -> Read_csvSchema
        - read -> ReadSchema
        
        Args:
            method_name: Method name in snake_case
            
        Returns:
            Schema class name
        """
        # Preserve underscores: read_csv -> Read_csv
        parts = method_name.split("_")
        capitalized_parts = [part.capitalize() for part in parts]
        return "".join(capitalized_parts) + "Schema"

    def _is_manual_schema(self, method_name: str, schema: Type[BaseModel]) -> bool:
        """
        Check if a schema was manually defined (not auto-generated).
        
        Args:
            method_name: Method name
            schema: Schema class
            
        Returns:
            True if schema is manually defined, False if auto-generated
        """
        # Check if schema exists as a class attribute
        schema_name = schema.__name__
        if hasattr(self.__class__, schema_name):
            attr = getattr(self.__class__, schema_name)
            if isinstance(attr, type) and attr == schema:
                return True
        return False
