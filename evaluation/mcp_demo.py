import asyncio

from fastmcp import Client


async def main():
    # Chat Agent MCP (HTTP transport) runs at http://localhost:9106/mcp when started via ./start_agents_mcp.sh
    async with Client("http://localhost:9106/mcp") as chat:
        tools = await chat.list_tools()
        print("Chat tools:", [t.name for t in tools])
        res = await chat.call_tool("chat", {"query": "What items can be discounted?"})
        print("Chat response:", res.data)


if __name__ == "__main__":
    asyncio.run(main())

