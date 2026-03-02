package com.smartcartai.backend.mcp;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Minimal MCP client for Streamable HTTP transport.
 *
 * Notes:
 * - FastMCP commonly returns responses as text/event-stream (SSE). This client parses the first "data:" JSON payload.
 * - Notifications (no id) are accepted with 202 and no body.
 */
public final class McpStreamableHttpClient {
    private static final String ACCEPT_HEADER = "application/json, text/event-stream";
    private static final String DEFAULT_PROTOCOL_VERSION = "2025-03-26";

    private final HttpClient http;
    private final ObjectMapper mapper;
    private final URI mcpEndpoint;
    private final AtomicLong ids = new AtomicLong(1);

    private volatile String sessionId;
    private volatile String protocolVersion = DEFAULT_PROTOCOL_VERSION;
    private volatile boolean initialized;

    public McpStreamableHttpClient(String mcpEndpointUrl, ObjectMapper mapper) {
        this.http = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(5))
                .build();
        this.mapper = mapper;
        this.mcpEndpoint = URI.create(mcpEndpointUrl);
    }

    public synchronized void ensureInitialized() throws IOException, InterruptedException {
        if (initialized) return;

        long id = ids.getAndIncrement();
        Map<String, Object> params = new HashMap<>();
        params.put("protocolVersion", protocolVersion);
        params.put("capabilities", Map.of(
                "roots", Map.of("listChanged", true),
                "sampling", Map.of()
        ));
        params.put("clientInfo", Map.of(
                "name", "SmartCartAIBackend",
                "version", "1.0.0"
        ));

        Map<String, Object> initReq = new HashMap<>();
        initReq.put("jsonrpc", "2.0");
        initReq.put("id", id);
        initReq.put("method", "initialize");
        initReq.put("params", params);

        HttpResponse<String> initResp = postJson(initReq, /*expectResponse=*/true);
        JsonNode initJson = parseMcpResponseBody(initResp);
        if (initJson.has("error")) {
            throw new IOException("MCP initialize error: " + initJson.get("error").toString());
        }
        JsonNode result = initJson.path("result");
        String negotiated = result.path("protocolVersion").asText(DEFAULT_PROTOCOL_VERSION);
        this.protocolVersion = negotiated;

        // Session id may be assigned at initialization time.
        this.sessionId = headerIgnoreCase(initResp, "mcp-session-id").orElse(this.sessionId);

        // Send initialized notification
        Map<String, Object> initializedNote = Map.of(
                "jsonrpc", "2.0",
                "method", "notifications/initialized"
        );
        postJson(initializedNote, /*expectResponse=*/false);

        this.initialized = true;
    }

    public Map<String, Object> callTool(String toolName, Map<String, Object> arguments)
            throws IOException, InterruptedException {
        try {
            return callToolOnce(toolName, arguments);
        } catch (IOException e) {
            // If the server restarted or the session expired/invalid, reset and retry once.
            // FastMCP may return 400 with messages like "No valid session ID provided".
            String msg = e.getMessage() == null ? "" : e.getMessage().toLowerCase();
            boolean sessionProblem =
                    msg.contains("session expired")
                            || msg.contains("no valid session id")
                            || msg.contains("invalid session")
                            || (msg.contains("http 400") && msg.contains("session"));
            if (sessionProblem) {
                synchronized (this) {
                    this.initialized = false;
                    this.sessionId = null;
                }
                return callToolOnce(toolName, arguments);
            }
            throw e;
        }
    }

    private Map<String, Object> callToolOnce(String toolName, Map<String, Object> arguments)
            throws IOException, InterruptedException {
        ensureInitialized();
        long id = ids.getAndIncrement();
        Map<String, Object> req = new HashMap<>();
        req.put("jsonrpc", "2.0");
        req.put("id", id);
        req.put("method", "tools/call");
        req.put("params", Map.of(
                "name", toolName,
                "arguments", arguments != null ? arguments : Map.of()
        ));

        HttpResponse<String> resp = postJson(req, /*expectResponse=*/true);
        JsonNode json = parseMcpResponseBody(resp);
        if (json.has("error")) {
            throw new IOException("MCP tools/call error: " + json.get("error").toString());
        }

        JsonNode result = json.path("result");
        // FastMCP includes structuredContent for dict results
        JsonNode structured = result.get("structuredContent");
        if (structured != null && !structured.isNull()) {
            return mapper.convertValue(structured, new TypeReference<Map<String, Object>>() {});
        }

        // Fallback: if only text content is present, try to parse JSON text
        JsonNode content = result.path("content");
        if (content.isArray() && content.size() > 0) {
            JsonNode first = content.get(0);
            String text = first.path("text").asText(null);
            if (text != null && text.trim().startsWith("{")) {
                try {
                    return mapper.readValue(text, new TypeReference<Map<String, Object>>() {});
                } catch (Exception ignored) {
                }
            }
        }
        // Last resort: return raw result
        return mapper.convertValue(result, new TypeReference<Map<String, Object>>() {});
    }

    private HttpResponse<String> postJson(Map<String, Object> message, boolean expectResponse)
            throws IOException, InterruptedException {
        String body = mapper.writeValueAsString(message);
        HttpRequest.Builder b = HttpRequest.newBuilder()
                .uri(mcpEndpoint)
                .timeout(Duration.ofSeconds(30))
                .header("Content-Type", "application/json")
                .header("Accept", ACCEPT_HEADER);

        if (sessionId != null && !sessionId.isBlank()) {
            b.header("Mcp-Session-Id", sessionId);
        }
        if (initialized) {
            b.header("MCP-Protocol-Version", protocolVersion);
        }

        HttpRequest req = b.POST(HttpRequest.BodyPublishers.ofString(body)).build();
        HttpResponse<String> resp = http.send(req, HttpResponse.BodyHandlers.ofString());

        // Cache session id if present
        this.sessionId = headerIgnoreCase(resp, "mcp-session-id").orElse(this.sessionId);

        int code = resp.statusCode();
        if (!expectResponse) {
            if (code != 202 && code != 200) {
                throw new IOException("MCP notification failed: HTTP " + code);
            }
            return resp;
        }

        if (code == 404 && sessionId != null) {
            // Session expired; reset and caller can retry by re-initializing.
            this.initialized = false;
            this.sessionId = null;
            throw new IOException("MCP session expired (404). Please retry.");
        }

        if (code < 200 || code >= 300) {
            throw new IOException("MCP request failed: HTTP " + code + " body=" + truncate(resp.body(), 300));
        }
        return resp;
    }

    private JsonNode parseMcpResponseBody(HttpResponse<String> resp) throws IOException {
        String ct = headerIgnoreCase(resp, "content-type").orElse("");
        String body = resp.body() == null ? "" : resp.body();

        if (ct.toLowerCase().contains("text/event-stream")) {
            // Parse SSE: find first "data: {json...}" line for event: message
            String[] lines = body.split("\n");
            for (String raw : lines) {
                String line = raw.stripTrailing();
                if (line.startsWith("data:")) {
                    String json = line.substring("data:".length()).trim();
                    if (json.startsWith("{") && json.contains("\"jsonrpc\"")) {
                        return mapper.readTree(json);
                    }
                }
            }
            throw new IOException("Could not parse SSE MCP response (no data: jsonrpc found)");
        }

        // application/json case
        return mapper.readTree(body);
    }

    private static Optional<String> headerIgnoreCase(HttpResponse<?> resp, String name) {
        return resp.headers().map().entrySet().stream()
                .filter(e -> e.getKey() != null && e.getKey().equalsIgnoreCase(name))
                .findFirst()
                .flatMap(e -> e.getValue().stream().findFirst());
    }

    private static String truncate(String s, int max) {
        if (s == null) return "";
        if (s.length() <= max) return s;
        return s.substring(0, max) + "...";
    }
}

