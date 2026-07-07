import json
import logging
import os

from cryptography.fernet import Fernet
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from mcp import StdioServerParameters

logger = logging.getLogger("lifequest.tools")

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# DATA SECURITY LAYER / SECURITY FEATURES REQUIREMENT:
# We implement at-rest encryption for the local save file `save.json`.
# This protects sensitive personal data (e.g. financial transaction amounts,
# job descriptions, interview prep tips, and visa deadlines) stored locally on disk.
encryption_key = os.environ.get("SAVE_ENCRYPTION_KEY")
if not encryption_key:
    raise ValueError(
        "Missing SAVE_ENCRYPTION_KEY environment variable. Save file encryption cannot proceed."
    )

encryption_key = encryption_key.strip()

try:
    cipher = Fernet(encryption_key.encode())
except Exception as e:
    raise ValueError(f"Invalid SAVE_ENCRYPTION_KEY provided: {e}") from e

# Define McpToolset pointing to the project directory, limited to read/write_file
mcp_filesystem_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", PROJECT_DIR],
        ),
    ),
    tool_filter=["read_file", "write_file"],
)

DEFAULT_STATE = {
    "hp": 100,
    "gold": 500,
    "xp": 0,
    "quest_log": [],
    "real_balance": 1000.0,  # Stored only locally in save.json
    "real_transactions": [],  # Stored only locally in save.json
    "budget": 1500,
    "deadlines": [],
}


async def load_game_state(callback_context: CallbackContext) -> None:
    """Loads game state from save.json using the MCP filesystem server."""
    state_data = DEFAULT_STATE.copy()
    try:
        session = await mcp_filesystem_toolset._mcp_session_manager.create_session()
        read_result = await session.call_tool(
            "read_file", arguments={"path": "save.json"}
        )

        is_error = (
            getattr(read_result, "isError", False)
            or "no such file" in getattr(read_result.content[0], "text", "").lower()
        )

        if read_result and read_result.content and not is_error:
            encrypted_content = read_result.content[0].text
            decrypted_content = cipher.decrypt(encrypted_content.encode()).decode()
            loaded = json.loads(decrypted_content)
            state_data.update(loaded)
            logger.info("Loaded encrypted game state successfully from save.json")
        else:
            logger.info(
                "No save.json found, creating save.json with encrypted default state"
            )
            content_str = json.dumps(DEFAULT_STATE, indent=2)
            encrypted_content = cipher.encrypt(content_str.encode()).decode()
            await session.call_tool(
                "write_file",
                arguments={"path": "save.json", "content": encrypted_content},
            )
    except Exception as e:
        logger.warning(
            f"Failed to read/write/decrypt save.json via MCP toolset ({e}). Using default state in memory."
        )

    # Populate callback_context.state with the loaded state
    for k, v in state_data.items():
        callback_context.state[k] = v


async def save_game_state(callback_context: CallbackContext) -> None:
    """Saves game state to save.json using the MCP filesystem server."""
    # Build current state dictionary
    state_keys = [
        "hp",
        "gold",
        "xp",
        "quest_log",
        "real_balance",
        "real_transactions",
        "budget",
        "deadlines",
    ]
    state_to_save = {}
    for k in state_keys:
        if k in callback_context.state:
            state_to_save[k] = callback_context.state[k]
        else:
            state_to_save[k] = DEFAULT_STATE[k]

    try:
        session = await mcp_filesystem_toolset._mcp_session_manager.create_session()
        content_str = json.dumps(state_to_save, indent=2)
        encrypted_content = cipher.encrypt(content_str.encode()).decode()
        await session.call_tool(
            "write_file",
            arguments={"path": "save.json", "content": encrypted_content},
        )
        logger.info("Saved encrypted game state successfully to save.json")
    except Exception as e:
        logger.error(
            f"Failed to encrypt and save game state to save.json via MCP toolset: {e}"
        )
