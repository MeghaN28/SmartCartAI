package com.smartcartai.backend.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.smartcartai.backend.mcp.McpStreamableHttpClient;

/**
 * Lightweight holder for shared MCP clients (to reuse sessions).
 */
final class McpClients {
    private static volatile McpStreamableHttpClient chat;
    private static volatile String chatUrl;
    private static volatile McpStreamableHttpClient orchestrator;
    private static volatile String orchestratorUrl;

    private McpClients() {}

    static McpStreamableHttpClient chat(String url, ObjectMapper mapper) {
        McpStreamableHttpClient existing = chat;
        if (existing != null && url != null && url.equals(chatUrl)) return existing;
        synchronized (McpClients.class) {
            if (chat == null || chatUrl == null || !chatUrl.equals(url)) {
                chat = new McpStreamableHttpClient(url, mapper);
                chatUrl = url;
            }
            return chat;
        }
    }

    static McpStreamableHttpClient orchestrator(String url, ObjectMapper mapper) {
        McpStreamableHttpClient existing = orchestrator;
        if (existing != null && url != null && url.equals(orchestratorUrl)) return existing;
        synchronized (McpClients.class) {
            if (orchestrator == null || orchestratorUrl == null || !orchestratorUrl.equals(url)) {
                orchestrator = new McpStreamableHttpClient(url, mapper);
                orchestratorUrl = url;
            }
            return orchestrator;
        }
    }
}

