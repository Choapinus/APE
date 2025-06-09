import sqlite3
import json
from loguru import logger
from pydantic import BaseModel, Field
from typing import Type, List, Dict, Any

class BaseTool(BaseModel):
    """The base class for all tools."""
    
    class Args(BaseModel):
        """The arguments for the tool. This should be overridden by subclasses."""
        pass

    @classmethod
    def get_name(cls) -> str:
        """Returns the name of the tool, derived from the class name."""
        return cls.__name__

    @classmethod
    def get_description(cls) -> str:
        """Returns the description of the tool from its docstring."""
        return cls.__doc__ or ""

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        """Generates a JSON schema for the tool's arguments."""
        # Pydantic's schema generation is powerful but can be verbose.
        # We simplify it for the LLM.
        args_schema = cls.Args.model_json_schema()
        
        return {
            "type": "function",
            "function": {
                "name": cls.get_name(),
                "description": cls.get_description(),
                "parameters": {
                    "type": "object",
                    "properties": args_schema.get("properties", {}),
                    "required": args_schema.get("required", []),
                },
            },
        }

    def execute(self, **kwargs):
        """Executes the tool with the given arguments."""
        raise NotImplementedError

class GetLastNInteractionsTool(BaseTool):
    """Retrieves the last N user/assistant interactions from the conversation history database."""

    class Args(BaseModel):
        n: int = Field(default=5, description="The number of interactions to retrieve.")

    def execute(self, n: int = 5) -> str:
        logger.info(f"Executing tool: {self.get_name()} with n={n}")
        db_path = "ape/sessions.db"  # This should ideally be passed in or configured
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            query = "SELECT role, content, images FROM history ORDER BY timestamp DESC LIMIT ?"
            rows = cursor.execute(query, (n * 2,)).fetchall()
            conn.close()

            interactions = []
            for role, content, images in reversed(rows):
                # Skip specific tool-related internal messages but keep user/assistant content
                if (role == "tool" or 
                    (role == "assistant" and content.startswith("Thought:") and "Action:" in content and "Observation:" in content)):
                    continue
                
                interaction = {"role": role, "content": content}
                if images:
                    interaction["has_image"] = True
                interactions.append(interaction)
            
            # Only take the last n interactions after filtering
            interactions = interactions[:n]
            
            return json.dumps(interactions, indent=2)
        except Exception as e:
            logger.error(f"Error executing tool {self.get_name()}: {e}")
            return json.dumps({"error": f"Could not retrieve interactions. Reason: {str(e)}"})


class DatabaseInfoTool(BaseTool):
    """Retrieves information about the database schema, tables, and structure."""

    class Args(BaseModel):
        pass  # No arguments needed

    def execute(self, **kwargs) -> str:
        logger.info(f"Executing tool: {self.get_name()}")
        db_path = "ape/sessions.db"
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get database schema
            schema_query = "SELECT sql FROM sqlite_master WHERE type='table';"
            schema_rows = cursor.execute(schema_query).fetchall()
            
            # Get table names and row counts
            tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
            table_names = cursor.execute(tables_query).fetchall()
            
            db_info = {
                "database_path": db_path,
                "tables": {},
                "schema": {}
            }
            
            for (table_name,) in table_names:
                if table_name == 'sqlite_sequence':
                    continue
                    
                # Get row count
                count_query = f"SELECT COUNT(*) FROM {table_name};"
                count = cursor.execute(count_query).fetchone()[0]
                
                # Get column info
                pragma_query = f"PRAGMA table_info({table_name});"
                columns = cursor.execute(pragma_query).fetchall()
                
                db_info["tables"][table_name] = {
                    "row_count": count,
                    "columns": [
                        {
                            "name": col[1],
                            "type": col[2],
                            "not_null": bool(col[3]),
                            "default_value": col[4],
                            "primary_key": bool(col[5])
                        }
                        for col in columns
                    ]
                }
            
            # Add schema SQL
            for (sql,) in schema_rows:
                if sql:
                    table_name = sql.split()[2]  # Extract table name from CREATE TABLE statement
                    if table_name in db_info["tables"]:
                        db_info["schema"][table_name] = sql
            
            conn.close()
            return json.dumps(db_info, indent=2)
            
        except Exception as e:
            logger.error(f"Error executing tool {self.get_name()}: {e}")
            return json.dumps({"error": f"Could not retrieve database info. Reason: {str(e)}"})


class GenerateDatabaseQueryTool(BaseTool):
    """Generates and executes SQL queries on the database based on natural language requests."""

    class Args(BaseModel):
        query_description: str = Field(description="Natural language description of what data you want to query")
        limit: int = Field(default=10, description="Maximum number of rows to return")

    def execute(self, query_description: str, limit: int = 10) -> str:
        logger.info(f"Executing tool: {self.get_name()} with query_description='{query_description}', limit={limit}")
        db_path = "ape/sessions.db"
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # First get database schema to understand available tables/columns
            tables_info = {}
            tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
            table_names = cursor.execute(tables_query).fetchall()
            
            for (table_name,) in table_names:
                if table_name == 'sqlite_sequence':
                    continue
                pragma_query = f"PRAGMA table_info({table_name});"
                columns = cursor.execute(pragma_query).fetchall()
                tables_info[table_name] = [col[1] for col in columns]  # Column names
            
            # Generate SQL query based on description and available schema
            sql_query = self._generate_sql_query(query_description, tables_info, limit)
            
            if not sql_query:
                return json.dumps({"error": "Could not generate appropriate SQL query for the request"})
            
            logger.info(f"Generated SQL query: {sql_query}")
            
            # Execute the query
            rows = cursor.execute(sql_query).fetchall()
            
            # Get column names for the result
            column_names = [description[0] for description in cursor.description]
            
            conn.close()
            
            # Format results
            results = {
                "generated_query": sql_query,
                "column_names": column_names,
                "rows": rows[:limit],  # Ensure we don't exceed limit
                "total_rows_returned": len(rows)
            }
            
            return json.dumps(results, indent=2, default=str)  # default=str handles datetime objects
            
        except Exception as e:
            logger.error(f"Error executing tool {self.get_name()}: {e}")
            return json.dumps({"error": f"Could not execute database query. Reason: {str(e)}"})
    
    def _generate_sql_query(self, description: str, tables_info: dict, limit: int) -> str:
        """Generate SQL query based on natural language description and available schema."""
        description_lower = description.lower()
        
        # For the history table, create common query patterns
        if "history" in tables_info:
            if any(word in description_lower for word in ["interaction", "message", "conversation", "chat"]):
                if any(word in description_lower for word in ["recent", "last", "latest"]):
                    return f"SELECT role, content, timestamp FROM history ORDER BY timestamp DESC LIMIT {limit};"
                elif any(word in description_lower for word in ["user", "users"]):
                    return f"SELECT role, content, timestamp FROM history WHERE role = 'user' ORDER BY timestamp DESC LIMIT {limit};"
                elif any(word in description_lower for word in ["assistant", "bot", "ai"]):
                    return f"SELECT role, content, timestamp FROM history WHERE role = 'assistant' ORDER BY timestamp DESC LIMIT {limit};"
                elif any(word in description_lower for word in ["session"]):
                    if "count" in description_lower:
                        return f"SELECT session_id, COUNT(*) as message_count FROM history GROUP BY session_id ORDER BY message_count DESC LIMIT {limit};"
                    else:
                        return f"SELECT DISTINCT session_id, MIN(timestamp) as first_message, MAX(timestamp) as last_message FROM history GROUP BY session_id ORDER BY last_message DESC LIMIT {limit};"
                else:
                    return f"SELECT * FROM history ORDER BY timestamp DESC LIMIT {limit};"
        
        # If no specific pattern matches, try to build a basic query
        if len(tables_info) == 1:
            table_name = list(tables_info.keys())[0]
            return f"SELECT * FROM {table_name} LIMIT {limit};"
        
        return None  # Could not generate query

# Tool Registration
# We instantiate the tools and store them in a registry.
# This makes it easy to add new tools - just create a new class.
_tools_classes: List[Type[BaseTool]] = [
    GetLastNInteractionsTool,
    DatabaseInfoTool,
    GenerateDatabaseQueryTool,
]

AVAILABLE_TOOLS: Dict[str, BaseTool] = {tool_class.get_name(): tool_class() for tool_class in _tools_classes}
TOOL_DEFINITIONS: List[Dict[str, Any]] = [tool_class.get_schema() for tool_class in _tools_classes] 