package com.smartcartai.backend.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import org.springframework.beans.factory.annotation.Autowired;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/agents")
@Tag(name = "Agents", description = "Agent orchestration endpoints")
public class AgentController {

    @Autowired
    private RestTemplate restTemplate;
    
    // Agent URLs (can be configured via application.properties)
    private static final String INVENTORY_AGENT_URL = System.getenv().getOrDefault(
        "INVENTORY_AGENT_URL", "http://localhost:9005"
    );
    private static final String DECISION_ORCHESTRATOR_URL = System.getenv().getOrDefault(
        "DECISION_ORCHESTRATOR_URL", "http://localhost:9000"
    );
    private static final String CHAT_AGENT_URL = System.getenv().getOrDefault(
        "CHAT_AGENT_URL", "http://localhost:9006"
    );
    private static final String DASHBOARD_AGENT_URL = System.getenv().getOrDefault(
        "DASHBOARD_AGENT_URL", "http://localhost:9008"
    );

    @PostMapping("/inventory/signal")
    @Operation(summary = "Signal an inventory item to the Inventory Monitoring Agent")
    public ResponseEntity<Map<String, Object>> signalInventoryItem(
            @RequestBody Map<String, Object> payload) {
        try {
            String url = INVENTORY_AGENT_URL + "/inventory";
            Map<String, Object> response = restTemplate.postForObject(url, payload, Map.class);
            return ResponseEntity.ok(response != null ? response : new HashMap<>());
        } catch (Exception e) {
            Map<String, Object> error = new HashMap<>();
            error.put("error", e.getMessage());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
        }
    }

    @PostMapping("/orchestrate")
    @Operation(summary = "Request prescriptive intervention from Decision Orchestrator Agent")
    public ResponseEntity<Map<String, Object>> orchestrateIntervention(
            @RequestBody Map<String, Object> payload) {
        try {
            String url = DECISION_ORCHESTRATOR_URL + "/orchestrate";
            Map<String, Object> response = restTemplate.postForObject(url, payload, Map.class);
            return ResponseEntity.ok(response != null ? response : new HashMap<>());
        } catch (Exception e) {
            Map<String, Object> error = new HashMap<>();
            error.put("error", e.getMessage());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
        }
    }

    @GetMapping("/inventory/health")
    @Operation(summary = "Check Inventory Monitoring Agent health")
    public ResponseEntity<Map<String, Object>> checkInventoryAgentHealth() {
        try {
            String url = INVENTORY_AGENT_URL + "/health";
            Map<String, Object> response = restTemplate.getForObject(url, Map.class);
            return ResponseEntity.ok(response != null ? response : new HashMap<>());
        } catch (Exception e) {
            Map<String, Object> error = new HashMap<>();
            error.put("error", e.getMessage());
            error.put("status", "unavailable");
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(error);
        }
    }

    @GetMapping("/orchestrator/health")
    @Operation(summary = "Check Decision Orchestrator Agent health")
    public ResponseEntity<Map<String, Object>> checkOrchestratorHealth() {
        try {
            String url = DECISION_ORCHESTRATOR_URL + "/health";
            Map<String, Object> response = restTemplate.getForObject(url, Map.class);
            return ResponseEntity.ok(response != null ? response : new HashMap<>());
        } catch (Exception e) {
            Map<String, Object> error = new HashMap<>();
            error.put("error", e.getMessage());
            error.put("status", "unavailable");
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(error);
        }
    }

    @PostMapping("/inventory/monitor/start")
    @Operation(summary = "Start continuous inventory monitoring")
    public ResponseEntity<Map<String, Object>> startMonitoring() {
        try {
            String url = INVENTORY_AGENT_URL + "/monitor/start";
            Map<String, Object> response = restTemplate.postForObject(url, null, Map.class);
            return ResponseEntity.ok(response != null ? response : new HashMap<>());
        } catch (Exception e) {
            Map<String, Object> error = new HashMap<>();
            error.put("error", e.getMessage());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
        }
    }

    @GetMapping("/inventory/monitor/status")
    @Operation(summary = "Check monitoring status")
    public ResponseEntity<Map<String, Object>> getMonitoringStatus() {
        try {
            String url = INVENTORY_AGENT_URL + "/monitor/status";
            Map<String, Object> response = restTemplate.getForObject(url, Map.class);
            return ResponseEntity.ok(response != null ? response : new HashMap<>());
        } catch (Exception e) {
            Map<String, Object> error = new HashMap<>();
            error.put("error", e.getMessage());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
        }
    }

    @PostMapping("/chat")
    @Operation(summary = "Chat with the AI assistant about inventory")
    public ResponseEntity<Map<String, Object>> chat(@RequestBody Map<String, Object> payload) {
        try {
            String url = CHAT_AGENT_URL + "/chat";
            Map<String, Object> response = restTemplate.postForObject(url, payload, Map.class);
            return ResponseEntity.ok(response != null ? response : new HashMap<>());
        } catch (Exception e) {
            Map<String, Object> error = new HashMap<>();
            error.put("error", e.getMessage());
            error.put("answer", "I'm sorry, I'm having trouble connecting to the chat service. Please try again later.");
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
        }
    }

    @PostMapping("/proactive")
    @Operation(summary = "Get proactive inventory alerts (waste, out of stock, low stock, overstock) with recommendations")
    public ResponseEntity<Map<String, Object>> proactive(@RequestBody(required = false) Map<String, Object> payload) {
        try {
            String url = CHAT_AGENT_URL + "/proactive";
            Map<String, Object> body = payload != null ? payload : new HashMap<>();
            Map<String, Object> response = restTemplate.postForObject(url, body, Map.class);
            return ResponseEntity.ok(response != null ? response : new HashMap<>());
        } catch (Exception e) {
            Map<String, Object> error = new HashMap<>();
            error.put("error", e.getMessage());
            error.put("answer", "Proactive alerts are unavailable. Try asking 'Check inventory and suggest actions'.");
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
        }
    }

    @GetMapping("/chat/health")
    @Operation(summary = "Check Chat Agent health")
    public ResponseEntity<Map<String, Object>> checkChatAgentHealth() {
        try {
            String url = CHAT_AGENT_URL + "/health";
            Map<String, Object> response = restTemplate.getForObject(url, Map.class);
            return ResponseEntity.ok(response != null ? response : new HashMap<>());
        } catch (Exception e) {
            Map<String, Object> error = new HashMap<>();
            error.put("error", e.getMessage());
            error.put("status", "unavailable");
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(error);
        }
    }

    @PostMapping("/dashboard/item-insights")
    @Operation(summary = "Get item insights for dashboard search popup")
    public ResponseEntity<Map<String, Object>> dashboardItemInsights(@RequestBody Map<String, Object> payload) {
        try {
            String url = DASHBOARD_AGENT_URL + "/item-insights";
            Map<String, Object> response = restTemplate.postForObject(url, payload, Map.class);
            return ResponseEntity.ok(response != null ? response : new HashMap<>());
        } catch (Exception e) {
            Map<String, Object> error = new HashMap<>();
            error.put("error", e.getMessage());
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
        }
    }

    @GetMapping("/dashboard/health")
    @Operation(summary = "Check Dashboard Agent health")
    public ResponseEntity<Map<String, Object>> checkDashboardAgentHealth() {
        try {
            String url = DASHBOARD_AGENT_URL + "/health";
            Map<String, Object> response = restTemplate.getForObject(url, Map.class);
            return ResponseEntity.ok(response != null ? response : new HashMap<>());
        } catch (Exception e) {
            Map<String, Object> error = new HashMap<>();
            error.put("error", e.getMessage());
            error.put("status", "unavailable");
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(error);
        }
    }
}
