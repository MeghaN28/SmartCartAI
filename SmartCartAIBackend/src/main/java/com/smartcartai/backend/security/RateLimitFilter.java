package com.smartcartai.backend.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public class RateLimitFilter extends OncePerRequestFilter {

    private static class WindowCounter {
        long windowStartEpochSec;
        int count;
    }

    private final Map<String, WindowCounter> counters = new ConcurrentHashMap<>();

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !request.getRequestURI().startsWith("/api/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {
        int maxReq = Integer.parseInt(System.getenv().getOrDefault("RATE_LIMIT_MAX_REQUESTS", "120"));
        long windowSec = Long.parseLong(System.getenv().getOrDefault("RATE_LIMIT_WINDOW_SECONDS", "60"));
        String client = request.getHeader("X-Forwarded-For");
        if (client == null || client.isBlank()) client = request.getRemoteAddr();
        if (client == null || client.isBlank()) client = "unknown";

        long now = Instant.now().getEpochSecond();
        WindowCounter wc = counters.computeIfAbsent(client, k -> new WindowCounter());
        synchronized (wc) {
            if (wc.windowStartEpochSec == 0 || (now - wc.windowStartEpochSec) >= windowSec) {
                wc.windowStartEpochSec = now;
                wc.count = 0;
            }
            wc.count += 1;
            if (wc.count > maxReq) {
                response.setStatus(429);
                response.setContentType("application/json");
                response.setHeader("Retry-After", String.valueOf(windowSec));
                response.getWriter().write("{\"error\":\"Rate limit exceeded\"}");
                return;
            }
        }

        filterChain.doFilter(request, response);
    }
}
