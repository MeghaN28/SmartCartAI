package com.smartcartai.backend.security;

import io.jsonwebtoken.Claims;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;
import java.util.Set;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 20)
public class ApiJwtFilter extends OncePerRequestFilter {

    private final JwtService jwtService;
    private static final Set<String> OPEN_PATH_PREFIXES = Set.of(
            "/api/auth/token",
            "/api/agents/chat/health",
            "/api/agents/orchestrator/health",
            "/api/agents/inventory/health",
            "/api/agents/dashboard/health"
    );
    private static final List<String> DEV_ALLOWED_ORIGINS = List.of(
            "http://localhost:8081",
            "http://127.0.0.1:8081",
            "http://localhost:3000",
            "http://127.0.0.1:3000"
    );

    public ApiJwtFilter(JwtService jwtService) {
        this.jwtService = jwtService;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        String path = request.getRequestURI();
        if (!path.startsWith("/api/")) return true;
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) return true;
        return OPEN_PATH_PREFIXES.stream().anyMatch(path::startsWith);
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        boolean enforce = Boolean.parseBoolean(System.getenv().getOrDefault("JWT_ENFORCE", "true"));
        if (!enforce) {
            filterChain.doFilter(request, response);
            return;
        }

        String auth = request.getHeader("Authorization");
        if (auth == null || !auth.startsWith("Bearer ")) {
            reject(request, response, "Missing Bearer token");
            return;
        }

        String token = auth.substring("Bearer ".length()).trim();
        try {
            Claims claims = jwtService.parse(token);
            request.setAttribute("auth.subject", claims.getSubject());
            filterChain.doFilter(request, response);
        } catch (Exception e) {
            reject(request, response, "Invalid or expired token");
        }
    }

    private void reject(HttpServletRequest request, HttpServletResponse response, String message) throws IOException {
        applyCorsHeadersIfAllowed(request, response);
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType("application/json");
        response.getWriter().write("{\"error\":\"" + message + "\"}");
    }

    private void applyCorsHeadersIfAllowed(HttpServletRequest request, HttpServletResponse response) {
        String origin = request.getHeader("Origin");
        if (origin != null && DEV_ALLOWED_ORIGINS.contains(origin)) {
            response.setHeader("Access-Control-Allow-Origin", origin);
            response.setHeader("Vary", "Origin");
            response.setHeader("Access-Control-Allow-Credentials", "true");
            response.setHeader("Access-Control-Allow-Headers", "Authorization, Content-Type, Accept, X-Requested-With");
            response.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS");
        }
    }
}
