"""
Payload CMS API client for MCP server.
"""

import json
import logging
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin

import httpx

from .config import PayloadConfig
from .exceptions import (
    APIError,
    AuthenticationError,
    ConnectionError,
    NotFoundError,
    RateLimitError,
    ValidationError
)

logger = logging.getLogger(__name__)


class PayloadClient:
    """Client for interacting with Payload CMS API."""
    
    def __init__(self, config: PayloadConfig):
        self.config = config
        self.base_url = config.base_url.rstrip('/')
        self.auth_token = config.auth_token
        self.timeout = config.timeout
        self.verify_ssl = config.verify_ssl
        self.bypass_proxy = config.bypass_proxy
        
        # Prepare headers
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Add JWT authentication header
        if self.auth_token:
            self.headers["Authorization"] = f"JWT {self.auth_token}"
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Payload CMS API."""
        # For Payload CMS, we need to append the endpoint to the base URL
        # without using urljoin since it can replace the path component
        if endpoint:
            # Remove leading slash to avoid double slashes
            endpoint = endpoint.lstrip('/')
            url = f"{self.base_url}/{endpoint}"
        else:
            url = self.base_url
        
        # Ensure proper URL encoding for query parameters
        encoded_params = None
        if params:
            # Use quote_plus for proper URL encoding of complex query parameters
            # This handles bracket notation correctly for Payload API
            encoded_params = {}
            for key, value in params.items():
                encoded_params[key] = value
        
        try:
            client_config = {
                "timeout": self.timeout,
                "verify": self.verify_ssl
            }
            
            # For httpx, we need to use a different approach for proxy bypass
            # We'll set the NO_PROXY environment variable to bypass proxies for localhost
            import os
            original_no_proxy = os.environ.get("NO_PROXY")
            
            if self.bypass_proxy:
                # Set NO_PROXY to bypass proxies for localhost
                os.environ["NO_PROXY"] = "localhost,127.0.0.1"
            
            try:
                async with httpx.AsyncClient(**client_config) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        headers=self.headers,
                        params=encoded_params,
                        json=data
                    )
                    
                    # Handle different response statuses
                    if response.status_code == 400:
                        # Bad Request - typically validation errors
                        error_data = {}
                        try:
                            error_data = response.json()
                            message = error_data.get("message", "Bad request")
                        except json.JSONDecodeError:
                            message = "Bad request"
                        raise ValidationError(f"Validation error: {message}", response_data=error_data)
                    elif response.status_code == 401:
                        # Unauthorized - authentication failed
                        raise AuthenticationError("JWT authentication failed - please check your token")
                    elif response.status_code == 403:
                        # Forbidden - insufficient permissions
                        error_data = {}
                        try:
                            error_data = response.json()
                            message = error_data.get("message", "Access forbidden")
                        except json.JSONDecodeError:
                            message = "Access forbidden"
                        raise APIError(f"Access forbidden: {message}", response.status_code, error_data)
                    elif response.status_code == 404:
                        # Not Found
                        raise NotFoundError("Resource not found", response.status_code)
                    elif response.status_code == 422:
                        # Unprocessable Entity - typically validation errors
                        error_data = {}
                        try:
                            error_data = response.json()
                            message = error_data.get("message", "Unprocessable entity")
                        except json.JSONDecodeError:
                            message = "Unprocessable entity"
                        raise ValidationError(f"Validation error: {message}", response_data=error_data)
                    elif response.status_code == 429:
                        # Too Many Requests - rate limiting
                        raise RateLimitError("Rate limit exceeded", response.status_code)
                    elif response.status_code >= 500:
                        # Server errors
                        error_data = {}
                        try:
                            error_data = response.json()
                            message = error_data.get("message", "Server error")
                        except json.JSONDecodeError:
                            message = "Server error"
                        raise APIError(f"Server error: {message}", response.status_code, error_data)
                    elif response.status_code >= 400:
                        # All other client errors
                        error_data = {}
                        try:
                            error_data = response.json()
                            message = error_data.get("message", "Client error")
                        except json.JSONDecodeError:
                            message = "Client error"
                        raise APIError(
                            f"API request failed: {response.status_code} - {message}",
                            response.status_code,
                            error_data
                        )
                
                    # Return JSON response
                    try:
                        return response.json()
                    except json.JSONDecodeError:
                        return {"data": response.text}
            finally:
                # Restore original NO_PROXY value
                if self.bypass_proxy:
                    if original_no_proxy is not None:
                        os.environ["NO_PROXY"] = original_no_proxy
                    else:
                        os.environ.pop("NO_PROXY", None)
                    
        except httpx.ConnectError as e:
            raise ConnectionError(f"Failed to connect to Payload CMS: {str(e)}")
        except httpx.TimeoutException as e:
            raise ConnectionError(f"Request timeout: {str(e)}")
        except httpx.HTTPError as e:
            raise ConnectionError(f"HTTP error: {str(e)}")
    
    
    async def create_object(
        self,
        collection_name: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new object in the specified collection.
        
        Args:
            collection_name: Name of the collection
            data: Object data to create
            
        Returns:
            Created object data
            
        Raises:
            ValidationError: If the data is invalid
            AuthenticationError: If authentication fails
            APIError: If the API request fails
            ConnectionError: If connection to Payload CMS fails
        """
        if not collection_name:
            raise ValidationError("Collection name is required")
        
        if not data:
            raise ValidationError("Data is required for creating an object")
            
        try:
            response = await self._make_request(
                "POST",
                collection_name,
                data=data
            )
            
            logger.debug(f"Successfully created object in collection {collection_name}")
            return response
            
        except ValidationError:
            # Re-raise validation errors as-is
            raise
        except AuthenticationError:
            # Re-raise authentication errors as-is
            raise
        except APIError as e:
            logger.error(f"API error creating object in collection {collection_name}: {str(e)}")
            # Check if it's a validation error from the API
            if e.status_code == 400:
                raise ValidationError(f"Validation error: {e.message}", response_data=e.response_data)
            raise
        except ConnectionError:
            # Re-raise connection errors as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating object in collection {collection_name}: {str(e)}")
            raise APIError(f"Unexpected error: {str(e)}")
    
    async def search_objects(
        self,
        collection_name: str,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        page: Optional[int] = None,
        sort: Optional[str] = None,
        depth: Optional[int] = None,
        locale: Optional[str] = None,
        fallback_locale: Optional[str] = None,
        select: Optional[Dict[str, Any]] = None,
        populate: Optional[Dict[str, Any]] = None,
        joins: Optional[Dict[str, Any]] = None,
        trash: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Search objects in a collection using Payload REST API.
        
        Args:
            collection_name: Name of the collection
            where: MongoDB-like query filters
            limit: Maximum number of results per page
            page: Page number for pagination
            sort: Field(s) to sort by (prefix with '-' for descending)
            depth: Controls the depth of population for relationships
            locale: Specifies the locale for retrieving documents
            fallback_locale: Specifies a fallback locale
            select: Fields to include in the result
            populate: Fields to populate from related documents
            joins: Custom requests for join fields
            trash: Whether to include soft-deleted documents
            
        Returns:
            Search results with pagination info
            
        Raises:
            ValidationError: If the query parameters are invalid
            AuthenticationError: If authentication fails
            NotFoundError: If the collection is not found
            APIError: If the API request fails
            ConnectionError: If connection to Payload CMS fails
        """
        if not collection_name:
            raise ValidationError("Collection name is required")
            
        # Validate pagination parameters
        if limit is not None and limit <= 0:
            raise ValidationError("Limit must be a positive integer")
        if page is not None and page <= 0:
            raise ValidationError("Page must be a positive integer")
        if depth is not None and depth < 0:
            raise ValidationError("Depth must be a non-negative integer")
            
        try:
            # Build query parameters with proper URL encoding
            params = {}
            
            # Handle where clause with proper formatting
            if where:
                # Convert the where clause to properly formatted query params
                # Using the format: where[field][operator]=value
                self._build_where_params(where, params)
            
            # Add other query parameters
            if limit is not None:
                params["limit"] = limit
            if page is not None:
                params["page"] = page
            if sort is not None:
                params["sort"] = sort
            if depth is not None:
                params["depth"] = depth
            if locale is not None:
                params["locale"] = locale
            if fallback_locale is not None:
                params["fallback-locale"] = fallback_locale
            if trash is not None:
                params["trash"] = "true" if trash else "false"
            
            # Handle select parameter with proper formatting
            if select:
                self._build_nested_params(select, "select", params)
            
            # Handle populate parameter with proper formatting
            if populate:
                self._build_nested_params(populate, "populate", params)
            
            # Handle joins parameter with proper formatting
            if joins:
                self._build_nested_params(joins, "joins", params)
            
            response = await self._make_request(
                "GET",
                collection_name,
                params=params
            )
            
            logger.debug(f"Successfully searched objects in collection {collection_name}")
            return response
            
        except ValidationError:
            # Re-raise validation errors as-is
            raise
        except AuthenticationError:
            # Re-raise authentication errors as-is
            raise
        except NotFoundError:
            # Re-raise not found errors as-is
            raise
        except APIError as e:
            logger.error(f"API error searching objects in collection {collection_name}: {str(e)}")
            # Check if it's a validation error from the API
            if e.status_code == 400:
                raise ValidationError(f"Invalid query parameters: {e.message}", response_data=e.response_data)
            raise
        except ConnectionError:
            # Re-raise connection errors as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error searching objects in collection {collection_name}: {str(e)}")
            raise APIError(f"Unexpected error: {str(e)}")
    
    def _build_where_params(self, where: Dict[str, Any], params: Dict[str, Any], prefix: str = "where") -> None:
        """
        Build properly formatted where query parameters for Payload API.
        
        Args:
            where: The where clause dictionary
            params: The params dictionary to update
            prefix: The prefix for the parameter names (default: "where")
        """
        for field, value in where.items():
            if isinstance(value, dict):
                # Handle operators like equals, contains, etc.
                for operator, operator_value in value.items():
                    param_key = f"{prefix}[{field}][{operator}]"
                    if isinstance(operator_value, (list, dict)):
                        # For complex values, JSON encode them
                        params[param_key] = json.dumps(operator_value)
                    else:
                        params[param_key] = operator_value
            else:
                # Simple equality check
                param_key = f"{prefix}[{field}][equals]"
                params[param_key] = value
    
    def _build_nested_params(self, nested_dict: Dict[str, Any], param_type: str, params: Dict[str, Any]) -> None:
        """
        Build properly formatted nested parameters like select, populate, joins.
        
        Args:
            nested_dict: The nested dictionary
            param_type: The type of parameter (select, populate, joins)
            params: The params dictionary to update
        """
        for key, value in nested_dict.items():
            if isinstance(value, dict):
                # Handle nested objects like select[field][nested]=true
                for nested_key, nested_value in value.items():
                    param_key = f"{param_type}[{key}][{nested_key}]"
                    params[param_key] = str(nested_value).lower() if isinstance(nested_value, bool) else nested_value
            else:
                # Handle simple values like select[field]=true
                param_key = f"{param_type}[{key}]"
                params[param_key] = str(value).lower() if isinstance(value, bool) else value
    
    async def update_object(
        self,
        collection_name: str,
        object_id: Union[str, int],
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an object by ID.
        
        Args:
            collection_name: Name of the collection
            object_id: ID of the object to update
            data: Updated object data
            
        Returns:
            Updated object data
            
        Raises:
            ValidationError: If the data or ID is invalid
            AuthenticationError: If authentication fails
            NotFoundError: If the object is not found
            APIError: If the API request fails
            ConnectionError: If connection to Payload CMS fails
        """
        if not collection_name:
            raise ValidationError("Collection name is required")
            
        if not object_id:
            raise ValidationError("Object ID is required")
            
        if not data:
            raise ValidationError("Data is required for updating an object")
            
        try:
            response = await self._make_request(
                "PATCH",
                f"{collection_name}/{object_id}",
                data=data
            )
            
            logger.debug(f"Successfully updated object {object_id} in collection {collection_name}")
            return response
            
        except ValidationError:
            # Re-raise validation errors as-is
            raise
        except AuthenticationError:
            # Re-raise authentication errors as-is
            raise
        except NotFoundError:
            # Re-raise not found errors as-is
            raise
        except APIError as e:
            logger.error(f"API error updating object {object_id} in collection {collection_name}: {str(e)}")
            # Check if it's a validation error from the API
            if e.status_code == 400:
                raise ValidationError(f"Validation error: {e.message}", response_data=e.response_data)
            raise
        except ConnectionError:
            # Re-raise connection errors as-is
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating object {object_id} in collection {collection_name}: {str(e)}")
            raise APIError(f"Unexpected error: {str(e)}")
    