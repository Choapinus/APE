"""Implementation functions for APE MCP tools.

All database access is now asynchronous using **aiosqlite** instead of the
standard blocking ``sqlite3`` module.  Each helper opens a connection with
``async with aiosqlite.connect(...)`` and awaits all cursor operations.  This
change keeps the public async signatures intact while eliminating thread
blocking inside the event-loop.
"""

import aiosqlite
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional
import re

from loguru import logger

from .session_manager import get_session_manager
from ape.settings import settings
from ape.errors import DatabaseError, ToolExecutionError
from ape.core.vector_memory import get_vector_memory
from .plugin import discover
from ape.resources import list_resources as _list_resources

# Configuration
DB_PATH = settings.SESSION_DB_PATH


async def check_table_exists(table_name: str) -> bool:
    """Return *True* when ``table_name`` exists in the SQLite schema."""

    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None
    except Exception as e:
        logger.error(f"Error checking table existence: {e}")
        return False


async def execute_database_query_impl(sql_query: str) -> str:
    """Implementation of execute_database_query without MCP decoration."""
    logger.info(f"🗃️ [IMPL] Executing database query: {sql_query[:100]}...")
    
    # ------------------------------------------------------------------
    # SECURITY HARDENING – Accept *read-only* SELECT queries only
    # ------------------------------------------------------------------
    if not sql_query or not sql_query.strip():
        error_msg = "ERROR: Empty SQL query provided"
        logger.error(f"💥 [IMPL] {error_msg}")
        return error_msg

    normalized = sql_query.strip().rstrip(";").lstrip().upper()

    # Reject anything that is not a simple SELECT … FROM …
    if not normalized.startswith("SELECT"):
        return (
            "SECURITY_ERROR: Only read-only SELECT statements are allowed. "
            "Destructive or mutating queries are blocked."
        )

    # Very coarse injection guard – block multiple statements & keywords
    forbidden_tokens = [";", "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "ATTACH", "DETACH"]
    if any(tok in normalized for tok in forbidden_tokens):
        return "SECURITY_ERROR: Potentially unsafe SQL detected – query rejected."

    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            # Use WAL journal mode for better concurrency during async access
            await conn.execute("PRAGMA journal_mode=WAL")
            cursor = await conn.cursor()
            
            # Execute the SELECT query (read-only → no transaction needed)
            await cursor.execute(sql_query)
            
            columns = [description[0] for description in cursor.description]
            rows = await cursor.fetchall()
            
            if not rows:
                logger.info("📊 [IMPL] Query executed successfully, no results found")
                return "QUERY_RESULT: No data found – the query returned zero rows."
            
            results = [dict(zip(columns, row)) for row in rows]
            logger.info(f"✅ [IMPL] SELECT query returned {len(results)} rows")
            return f"QUERY_RESULT: {json.dumps(results, indent=2, default=str)}"
            
    except aiosqlite.Error as e:
        logger.error(f"💥 [IMPL] Database error: {e}")
        raise DatabaseError(str(e)) from e
    except Exception as e:
        logger.error(f"💥 [IMPL] Error executing database query: {e}")
        raise ToolExecutionError(str(e)) from e


async def get_conversation_history_impl(session_id: str = None, limit: int = 10) -> str:
    """Implementation of get_conversation_history without MCP decoration."""
    logger.info(f"📚 [IMPL] Getting conversation history: session_id={session_id}, limit={limit}")
    
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            cursor = await conn.cursor()
            
            if session_id:
                # Get history for specific session
                sql_query = """
                    SELECT role, content, timestamp 
                    FROM history 
                    WHERE session_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """
                await cursor.execute(sql_query, (session_id, limit))
            else:
                # Get recent history across all sessions
                sql_query = """
                    SELECT role, content, timestamp 
                    FROM history 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """
                await cursor.execute(sql_query, (limit,))
            
            rows = await cursor.fetchall()
        
        if not rows:
            logger.info("📭 [IMPL] No conversation history found")
            return "No conversation history found."
        
        # Format the history
        history = []
        for role, content, timestamp in reversed(rows):  # Reverse to show chronological order
            history.append({
                "role": role,
                "content": content,
                "timestamp": timestamp
            })
        
        logger.info(f"✅ [IMPL] Conversation history retrieved successfully, {len(history)} messages")
        return json.dumps(history, indent=2)
        
    except Exception as e:
        logger.error(f"💥 [IMPL] Error getting conversation history: {e}")
        return f"Error getting conversation history: {str(e)}"


async def get_database_info_impl() -> str:
    """Implementation of get_database_info without MCP decoration."""
    logger.info("🗄️ [IMPL] Getting database information")
    
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            cursor = await conn.cursor()
            
            # First, get list of tables
            await cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = await cursor.fetchall()
            
            if not tables:
                return json.dumps({
                    "database_path": DB_PATH,
                    "status": "Database exists but contains no tables",
                    "tables": []
                }, indent=2)
            
            # Get schema and stats for each table
            database_info = {
                "database_path": DB_PATH,
                "tables": {}
            }
            
            for (table_name,) in tables:
                # Get table schema
                await cursor.execute(f"PRAGMA table_info({table_name})")
                columns = await cursor.fetchall()
                
                schema = {}
                for col in columns:
                    col_id, name, data_type, not_null, default_value, primary_key = col
                    schema[name] = {
                        "type": data_type,
                        "not_null": bool(not_null),
                        "default": default_value,
                        "primary_key": bool(primary_key)
                    }
                
                # Get row count
                await cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_rowcount = await cursor.fetchone()
                row_count = row_rowcount[0] if row_rowcount else 0
                
                database_info["tables"][table_name] = {
                    "schema": schema,
                    "row_count": row_count
                }
                
                # If it's the history table, get additional stats
                if table_name == 'history':
                    await cursor.execute("""
                        SELECT role, COUNT(*) 
                        FROM history 
                        GROUP BY role
                    """)
                    role_counts = dict(await cursor.fetchall())
                    
                    await cursor.execute("""
                        SELECT COUNT(DISTINCT session_id) 
                        FROM history
                    """)
                    session_row = await cursor.fetchone()
                    session_count = session_row[0] if session_row else 0
                    
                    await cursor.execute("""
                        SELECT DATE(timestamp) as date, COUNT(*) as count
                        FROM history 
                        WHERE timestamp >= datetime('now', '-7 days')
                        GROUP BY DATE(timestamp)
                        ORDER BY date DESC
                    """)
                    recent_activity = dict(await cursor.fetchall())
                    
                    database_info["tables"][table_name]["statistics"] = {
                        "messages_by_role": role_counts,
                        "unique_sessions": session_count,
                        "recent_activity_7_days": recent_activity
                    }
        
        logger.info(f"✅ [IMPL] Database info retrieved successfully")
        return json.dumps(database_info, indent=2)
        
    except Exception as e:
        logger.error(f"💥 [IMPL] Error getting database info: {e}")
        return f"Error getting database info: {str(e)}"


async def search_conversations_impl(query: str, limit: int = 5) -> str:
    """Implementation of search_conversations without MCP decoration."""
    logger.info(f"🔍 [IMPL] Searching conversations for: '{query}' (limit: {limit})")
    
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            cursor = await conn.cursor()
            
            # Simple text search in content
            sql_query = """
                SELECT session_id, role, content, timestamp 
                FROM history 
                WHERE content LIKE ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """
            
            search_term = f"%{query}%"
            await cursor.execute(sql_query, (search_term, limit))
            
            rows = await cursor.fetchall()
        
        if not rows:
            logger.info(f"🔍 [IMPL] No conversations found matching: '{query}'")
            return f"No conversations found matching: {query}"
        
        # Format results
        results = []
        for session_id, role, content, timestamp in rows:
            # Truncate long content
            display_content = content[:200] + "..." if len(content) > 200 else content
            
            results.append({
                "session_id": session_id,
                "role": role,
                "content": display_content,
                "timestamp": timestamp,
                "relevance": "Contains: " + query
            })
        
        logger.info(f"✅ [IMPL] Search completed successfully, {len(results)} results found")
        return json.dumps(results, indent=2)
        
    except Exception as e:
        logger.error(f"💥 [IMPL] Error searching conversations: {e}")
        return f"Error searching conversations: {str(e)}"



async def get_last_N_user_interactions_impl(n: int = 5, session_id: str = None) -> str:
    """Implementation of the get_last_N_user_interactions tool."""
    try:
        logger.info(f"👤 [IMPL] Getting last {n} user interactions for session: {session_id}")
        
        # Build the query
        query = "SELECT content, timestamp FROM history WHERE role = 'user'"
        params = []
        
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
            
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(n)
        
        # Execute query using direct sqlite connection
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(query, params) as cur:
                rows = await cur.fetchall()
        
        if not rows:
            return f"No user interactions found for session: {session_id or 'any session'}"
        
        # Format results
        result = {
            "session_filter": session_id or "all sessions",
            "user_interactions_count": len(rows),
            "interactions": []
        }
        
        for content, timestamp in reversed(rows):  # Reverse to show chronological order
            result["interactions"].append({
                "content": content,
                "timestamp": timestamp
            })
        
        response = f"Last {len(rows)} User Interactions:\n\n"
        for i, interaction in enumerate(result["interactions"], 1):
            response += f"{i}. [{interaction['timestamp']}]\n"
            response += f"   User: {interaction['content']}\n\n"
        
        logger.info("✅ [IMPL] User interactions retrieved successfully")
        return response
        
    except Exception as e:
        logger.error(f"❌ [IMPL] Error getting user interactions: {e}")
        raise ValueError(f"Failed to get user interactions: {str(e)}")


async def get_last_N_tool_interactions_impl(n: int = 5, session_id: str = None) -> str:
    """Implementation of the get_last_N_tool_interactions tool."""
    try:
        logger.info(f"🔧 [IMPL] Getting last {n} tool interactions for session: {session_id}")
        
        # Build the query
        query = "SELECT content, timestamp FROM history WHERE role = 'tool'"
        params = []
        
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
            
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(n)
        
        # Execute query using direct sqlite connection
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(query, params) as cur:
                rows = await cur.fetchall()
        
        if not rows:
            return f"No tool interactions found for session: {session_id or 'any session'}"
        
        # Format results
        result = {
            "session_filter": session_id or "all sessions",
            "tool_interactions_count": len(rows),
            "interactions": []
        }
        
        for content, timestamp in reversed(rows):  # Reverse to show chronological order
            result["interactions"].append({
                "content": content,
                "timestamp": timestamp
            })
        
        response = f"Last {len(rows)} Tool Interactions:\n\n"
        for i, interaction in enumerate(result["interactions"], 1):
            response += f"{i}. [{interaction['timestamp']}]\n"
            # Try to extract tool name from content if it's formatted
            content_preview = interaction['content'][:100] + "..." if len(interaction['content']) > 100 else interaction['content']
            response += f"   Tool Result: {content_preview}\n\n"
        
        logger.info("✅ [IMPL] Tool interactions retrieved successfully")
        return response
        
    except Exception as e:
        logger.error(f"❌ [IMPL] Error getting tool interactions: {e}")
        raise ValueError(f"Failed to get tool interactions: {str(e)}")


async def get_last_N_agent_interactions_impl(n: int = 5, session_id: str = None) -> str:
    """Implementation of the get_last_N_agent_interactions tool."""
    try:
        logger.info(f"🤖 [IMPL] Getting last {n} agent interactions for session: {session_id}")
        
        # Build the query
        query = "SELECT content, timestamp FROM history WHERE role = 'assistant'"
        params = []
        
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
            
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(n)
        
        # Execute query using direct sqlite connection
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(query, params) as cur:
                rows = await cur.fetchall()
        
        if not rows:
            return f"No agent interactions found for session: {session_id or 'any session'}"
        
        # Format results
        result = {
            "session_filter": session_id or "all sessions",
            "agent_interactions_count": len(rows),
            "interactions": []
        }
        
        for content, timestamp in reversed(rows):  # Reverse to show chronological order
            result["interactions"].append({
                "content": content,
                "timestamp": timestamp
            })
        
        response = f"Last {len(rows)} Agent Interactions:\n\n"
        for i, interaction in enumerate(result["interactions"], 1):
            response += f"{i}. [{interaction['timestamp']}]\n"
            content_preview = interaction['content'][:100] + "..." if len(interaction['content']) > 100 else interaction['content']
            response += f"   Agent: {content_preview}\n\n"
        
        logger.info("✅ [IMPL] Agent interactions retrieved successfully")
        return response
        
    except Exception as e:
        logger.error(f"❌ [IMPL] Error getting agent interactions: {e}")
        raise ValueError(f"Failed to get agent interactions: {str(e)}")


async def list_tables() -> str:
    """Get a list of all tables in the database."""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            cursor = await conn.cursor()
            
            await cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = await cursor.fetchall()
        
        return ", ".join([row[0] for row in tables]) if tables else "No tables found"
    except Exception as e:
        logger.error(f"Error listing tables: {e}")
        return "Error listing tables"


async def memory_append_impl(text: str, metadata: dict | None = None) -> str:
    """Implementation of the memory_append tool."""
    logger.info(f"🧠 [IMPL] Appending to vector memory: {text[:50]}...")
    
    try:
        vector_memory = await get_vector_memory()
        vector_memory.add(text, metadata)
        
        logger.info("✅ [IMPL] Successfully scheduled text for embedding and storage.")
        return "Successfully scheduled text for embedding and storage."
        
    except Exception as e:
        logger.error(f"💥 [IMPL] Error appending to vector memory: {e}")
        raise ToolExecutionError(str(e)) from e


# ------------------------------------------------------------------
# 📄 Text Summarisation
# ------------------------------------------------------------------
async def summarize_text_impl(text: str, max_tokens: int | None = None) -> str:
    """Return a concise summary of *text*.

    High-level algorithm:
    1. Enforce a 4 000-token hard limit on *input* for safety.
    2. Try to get a high-quality TL;DR from the configured Ollama model.
    3. If the summary is too long, retry once with a more insistent prompt.
    4. If it's still too long, apply a smarter sentence-based truncation.
    5. If the Ollama request fails, fall back to a heuristic extractive summary.

    The function remains **self-contained** (no external async helpers) so that
    unit tests can monkey-patch the Ollama client easily.
    """

    from ape.utils import count_tokens  # local import to keep globals light
    from ape.settings import settings
    import asyncio
    import re
    from loguru import logger

    # ------------------------------------------------------------------
    # 0) Pre-processing – strip private reasoning if disabled by settings
    # ------------------------------------------------------------------

    if not settings.SUMMARIZE_THOUGHTS:
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)

    # ------------------------------------------------------------------
    # 1) Guards – reject oversized inputs early
    # ------------------------------------------------------------------
    INPUT_LIMIT = 4000  # tokens
    if count_tokens(text) > INPUT_LIMIT:
        return (
            "SECURITY_ERROR: Input too large for summarize_text tool. "
            f"Maximum allowed is {INPUT_LIMIT} tokens."
        )

    # Use centrally defined cap; ignore caller-provided value unless it lowers the cap further (internal calls only)
    token_cap = settings.SUMMARY_MAX_TOKENS

    # ------------------------------------------------------------------
    # 2) Attempt intelligent TL;DR via Ollama (with retry)
    # ------------------------------------------------------------------
    try:
        import importlib

        ollama = importlib.import_module("ollama")
        client = ollama.AsyncClient(host=str(settings.OLLAMA_BASE_URL))
        model_name: str = getattr(settings, "SUMMARY_MODEL", settings.LLM_MODEL)

        # --- First attempt ---
        prompt1 = (
            f"You are an expert summariser. Provide a concise TL;DR of the following "
            f"text. It is critical that your response is AT MOST {token_cap} tokens long.\n\n"
            f"Text to summarize:\n{text.strip()}\n\nTL;DR:"
        )
        resp1 = await asyncio.wait_for(
            client.generate(model=model_name, prompt=prompt1), timeout=30
        )
        summary = (resp1.get("response", "") if isinstance(resp1, dict) else str(resp1)).strip()

        # --- Check and Retry if necessary ---
        if summary and count_tokens(summary) > token_cap:
            logger.warning(f"summarize_text_impl: First summary attempt was too long ({count_tokens(summary)} > {token_cap}). Retrying...")
            prompt2 = (
                f"Your previous summary was too long. Make it even more concise. "
                f"The summary MUST be under {token_cap} tokens.\n\n"
                f"Previous summary to shorten:\n{summary}\n\nConcise TL;DR:"
            )
            resp2 = await asyncio.wait_for(
                client.generate(model=model_name, prompt=prompt2), timeout=30
            )
            summary = (resp2.get("response", "") if isinstance(resp2, dict) else str(resp2)).strip()

        # --- Final check and smart truncation (fallback) ---
        if summary and count_tokens(summary) > token_cap:
            logger.warning(f"summarize_text_impl: Retry attempt was still too long. Applying smart truncation.")
            sentences = re.split(r'(?<=[.!?])\s+', summary)
            truncated_summary = ""
            for sent in sentences:
                if count_tokens(truncated_summary + sent) <= token_cap:
                    truncated_summary += sent + " "
                else:
                    break
            summary = truncated_summary.strip()
            if not summary: # if first sentence is too long, just chop words
                 words = summary.split()
                 while count_tokens(summary) > token_cap and len(words)>1:
                     words.pop()
                     summary = " ".join(words) + "..."

        if summary:
            return summary

    except Exception as exc:  # pragma: no cover – network errors are common in CI
        logger.debug(f"summarize_text_impl: Ollama call failed → fallback heuristic ({exc})")

    # ------------------------------------------------------------------
    # 3) Heuristic fallback – first-sentences extractive summary
    # ------------------------------------------------------------------
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    summary_sentences: list[str] = []
    summary_token_count = 0

    for sent in sentences:
        if not sent:
            continue
        sent_tokens = count_tokens(sent)
        if summary_token_count + sent_tokens > token_cap:
            break
        summary_sentences.append(sent)
        summary_token_count += sent_tokens

    if not summary_sentences and text:
        words = text.split()
        truncated = " ".join(words[: min(len(words), token_cap)])
        summary_sentences.append(truncated)

    summary = " ".join(summary_sentences).strip()

    # Final guarantee, though less likely to be needed with sentence-based logic
    while count_tokens(summary) > token_cap:
        summary = " ".join(summary.split()[:-1])

    return summary or "(no content)"

async def call_slm_impl(
    prompt: str,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    think: bool = False,
) -> str:
    """Invoke a Small Language Model for simple, fast tasks."""
    logger.info(f"🧠 [IMPL] Calling SLM with prompt: {prompt[:80]}...")

    try:
        import importlib
        import asyncio

        ollama = importlib.import_module("ollama")
        client = ollama.AsyncClient(host=str(settings.OLLAMA_BASE_URL))
        model_name: str = settings.SLM_MODEL

        options = {}
        if temperature is not None:
            options["temperature"] = temperature
        if top_p is not None:
            options["top_p"] = top_p
        if top_k is not None:
            options["top_k"] = top_k

        final_prompt = prompt
        if think:
            final_prompt = (
                "You are a helpful assistant. Please think step by step before answering the user's query. "
                "Use <think>...</think> tags to write down your thoughts.\n\n"
                f"User query: {prompt}"
            )

        response = await asyncio.wait_for(
            client.generate(model=model_name, prompt=final_prompt, options=options),
            timeout=45  # Generous timeout for the SLM
        )

        if isinstance(response, dict):
            result = response.get("response", "").strip()
        else:
            try:
                result = response.response.strip()
            except AttributeError:
                result = str(response).strip()

        logger.info("✅ [IMPL] SLM call successful.")
        return result

    except asyncio.TimeoutError:
        logger.error(f"💥 [IMPL] SLM call timed out.")
        raise ToolExecutionError("The request to the Small Language Model timed out.")
    except Exception as e:
        logger.error(f"💥 [IMPL] Error calling SLM: {e}")
        raise ToolExecutionError(f"An error occurred while calling the SLM: {e}")

async def list_available_resources_impl() -> str:
    """Implementation of the list_available_resources tool."""
    logger.info("📚 [IMPL] Getting list of available resources")
    try:
        resources = [meta.to_dict() for meta in _list_resources()]
        return json.dumps(resources, indent=2)
    except Exception as e:
        logger.error(f"❌ [IMPL] Error getting resource list: {e}")
        raise ValueError(f"Failed to get resource list: {str(e)}")