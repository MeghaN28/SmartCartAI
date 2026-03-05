package com.smartcartai.backend.controller;

import com.smartcartai.backend.security.JwtService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/auth")
@Tag(name = "Auth", description = "Authentication endpoints")
public class AuthController {

    private final JwtService jwtService;

    public AuthController(JwtService jwtService) {
        this.jwtService = jwtService;
    }

    @PostMapping("/token")
    @Operation(summary = "Issue JWT token")
    public ResponseEntity<Map<String, Object>> issueToken(@RequestBody Map<String, Object> payload) {
        String configuredUser = System.getenv().getOrDefault("APP_AUTH_USERNAME", "admin");
        String configuredPass = System.getenv().getOrDefault("APP_AUTH_PASSWORD", "change-me");
        String username = String.valueOf(payload.getOrDefault("username", "")).trim();
        String password = String.valueOf(payload.getOrDefault("password", ""));

        if (!configuredUser.equals(username) || !configuredPass.equals(password)) {
            Map<String, Object> out = new HashMap<>();
            out.put("error", "Invalid credentials");
            return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(out);
        }
        return ResponseEntity.ok(jwtService.tokenResponse(username));
    }
}
