import json
import os
from pathlib import Path
from typing import Any, Sequence

import duckdb
import jwt
import re
import uvicorn

from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import Context, FastMCP
from mcp.types import (
    AnyFunction,
    Content,
    GetPromptResult,
    TextContent,
    SamplingMessage,
)
from mcp.types import Tool as MCPTool


os.environ["SECRET_KEY"] = Path("secret_key.txt").read_text()

USER_INFO = json.load(Path("user_info.json").open("r"))
DATA_CATALOG = Path("data/CATALOG.md").read_text()

DATABASE_PATH = Path("wealth.db")
DATABASE = duckdb.connect(str(DATABASE_PATH))


# get information about a specific customer
DATABASE.execute(
    "PREPARE query_customer_info AS SELECT * FROM clients WHERE client_id = ?"
)

# get a list of accounts for a specific customer
DATABASE.execute(
    "PREPARE query_customer_accounts AS SELECT * FROM accounts WHERE client_id = ?"
)

# get a list of holdings for a specific account
DATABASE.execute(
    """PREPARE query_account_holdings AS 
    SELECT h.*, a.account_name, a.account_type, a.currency, a.status FROM holdings h inner join accounts a on h.account_id = a.account_id
    WHERE a.client_id = ? and a.account_id = ?"""
)

# get a list of transactions for a specific account
DATABASE.execute(
    """PREPARE query_account_transactions AS 
    SELECT t.*, a.account_name, a.account_type, a.currency, a.status FROM transactions t inner join accounts a on t.account_id = a.account_id
    WHERE a.client_id = ? and a.account_id = ?"""
)


class SimpleAuthServerProvider:
    """
    A simple authentication provider that uses access tokens.
    This is meant for demonstration purposes only.
    """

    async def load_access_token(self, token: str) -> AccessToken | None:
        decoded_token = jwt.decode(
            token,
            os.environ["SECRET_KEY"],
            algorithms=["HS256"],
        )

        if "client_id" not in decoded_token:
            return None
        client_id = decoded_token["client_id"]
        print(f"Decoded token for client_id: {client_id}")

        query = "SELECT * FROM clients WHERE client_id = ?"
        result = DATABASE.execute(query, (client_id,)).fetchone()

        if not result:
            return None

        return AccessToken(
            client_id=decoded_token["client_id"],
            token=token,
            scopes=decoded_token["scopes"],
        )


class RestrictedFastMCP(FastMCP):
    """
    A custom FastMCP class that restricts the tools available to the user.
    This is useful for scenarios where you want to limit the functionality
    of the MCP server to a specific set of tools.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def list_tools(self) -> list[MCPTool]:
        """List all available tools."""

        ctx = self.get_context()
        request_ctx = ctx.request_context

        if request_ctx is None:
            raise ValueError(
                "Request context is not available. Ensure this is called within a request context."
            )

        user = request_ctx.request.user
        client_id = user.display_name
        scopes = user.scopes

        all_tools = self._tool_manager.list_tools()
        scoped_tools = [
            tool
            for tool in all_tools
            if set(tool.annotations.required_scope).intersection(scopes)
        ]

        return [
            MCPTool(
                name=info.name,
                # title=info.title,
                description=info.description,
                inputSchema=info.parameters,
                annotations=info.annotations,
            )
            for info in scoped_tools
        ]

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> Sequence[Content]:
        """Call a tool by name with arguments."""

        context = self.get_context()
        user = context.request_context.request.user
        user_scopes = user.scopes
        tool = self._tool_manager.get_tool(name)

        if not tool or not set(tool.annotations.required_scope).intersection(
            user_scopes
        ):
            raise ValueError(
                f"Unknown tool: {name} or insufficient access. Contact your administrator."
            )

        return await super().call_tool(name, arguments)  # type: ignore


auth_settings = AuthSettings(
    issuer_url="https://www.example.com",
    required_scopes=["authenticated"],
    resource_server_url="https://www.example_mcp.com",
)  # type: ignore

# Create server
mcp = RestrictedFastMCP(
    "Echo Server",
    stateless_http=True,
    auth_server_provider=SimpleAuthServerProvider(),
    auth=auth_settings,
)


@mcp.tool(annotations={"required_scope": ["client"]})
def get_customer_info(context: Context) -> dict:
    """Get information about a specific customer."""
    request = context.request_context.request
    user = request.user
    client_id = user.display_name

    return (
        DATABASE.execute(f"EXECUTE query_customer_info('{client_id}')")
        .fetchdf()
        .to_dict(orient="records")[0]
    )


@mcp.tool(annotations={"required_scope": ["client"]})
def get_customer_accounts(context: Context) -> str:
    """Get a list of accounts for a specific customer."""
    request = context.request_context.request
    user = request.user
    client_id = user.display_name

    return (
        DATABASE.execute(f"EXECUTE query_customer_accounts('{client_id}')")
        .fetchdf()
        .to_markdown(index=False)
    )


@mcp.tool(annotations={"required_scope": ["client"]})
def get_account_holdings(account_id: str, context: Context) -> str:
    """Get a list of holdings for a specific account."""
    request = context.request_context.request
    user = request.user
    client_id = user.display_name

    return (
        DATABASE.execute(
            f"EXECUTE query_account_holdings('{client_id}', '{account_id}')"
        )
        .fetchdf()
        .to_markdown(index=False)
    )


@mcp.tool(annotations={"required_scope": ["client"]})
def get_account_transactions(account_id: str, context: Context) -> str:
    """Get a list of transactions for a specific account."""
    request = context.request_context.request
    user = request.user
    client_id = user.display_name

    return (
        DATABASE.execute(
            f"EXECUTE query_account_transactions('{client_id}', '{account_id}')"
        )
        .fetchdf()
        .to_markdown(index=False)
    )


@mcp.tool(annotations={"required_scope": ["portfolio_analyst"]})  # type: ignore
def get_data_catalog(context: Context) -> str:
    """Provides information about the data catalog.
    Used to help construct SQL queries."""
    return DATA_CATALOG


def is_read_only_query(query: str) -> bool:
    """
    Returns True if the query is a read-only SELECT (including CTEs), False otherwise.
    Ignores leading whitespace and SQL comments.
    """
    # Remove leading SQL comments and whitespace
    cleaned = re.sub(r"^\s*(--[^\n]*\n|\s)*", "", query, flags=re.MULTILINE)
    # Check if it starts with SELECT or WITH (case-insensitive)
    return cleaned.strip().lower().startswith(("select", "with"))


@mcp.tool(annotations={"required_scope": ["portfolio_analyst"]})  # type: ignore
def run_custom_query(query: str, context: Context) -> str:
    """Run a custom SQL query on the wealth database.
    Parameters:
    - query: The SQL query to execute. Only SELECT queries are allowed.
    """

    if not is_read_only_query(query):
        raise ValueError("Only SELECT queries are allowed.")
    try:
        result = DATABASE.execute(query).fetchdf()
        return result.to_markdown(index=False)
    except Exception as e:
        return f"Error executing query: {e}"


if __name__ == "__main__":
    app = mcp.streamable_http_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
