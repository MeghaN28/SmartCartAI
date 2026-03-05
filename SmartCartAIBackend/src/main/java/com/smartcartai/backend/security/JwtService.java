package com.smartcartai.backend.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.stereotype.Service;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;
import java.util.HashMap;
import java.util.Map;

@Service
public class JwtService {

    private static final String DEFAULT_SECRET = "smartcart-change-this-jwt-secret-before-production";
    private static final long DEFAULT_EXP_MINUTES = 120L;

    private SecretKey signingKey() {
        String secret = System.getenv().getOrDefault("JWT_SECRET", DEFAULT_SECRET);
        try {
            byte[] raw = secret.getBytes(StandardCharsets.UTF_8);
            if (raw.length >= 32) {
                return Keys.hmacShaKeyFor(raw);
            }
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hashed = md.digest(raw);
            return Keys.hmacShaKeyFor(hashed);
        } catch (Exception e) {
            throw new IllegalStateException("Could not initialize JWT signing key", e);
        }
    }

    public String issueToken(String subject) {
        long expMinutes = Long.parseLong(System.getenv().getOrDefault("JWT_EXP_MINUTES", String.valueOf(DEFAULT_EXP_MINUTES)));
        Instant now = Instant.now();
        Instant exp = now.plus(expMinutes, ChronoUnit.MINUTES);
        return Jwts.builder()
                .subject(subject)
                .issuedAt(Date.from(now))
                .expiration(Date.from(exp))
                .signWith(signingKey())
                .compact();
    }

    public Claims parse(String token) {
        return Jwts.parser()
                .verifyWith(signingKey())
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    public Map<String, Object> tokenResponse(String subject) {
        String token = issueToken(subject);
        long expMinutes = Long.parseLong(System.getenv().getOrDefault("JWT_EXP_MINUTES", String.valueOf(DEFAULT_EXP_MINUTES)));
        Map<String, Object> out = new HashMap<>();
        out.put("access_token", token);
        out.put("token_type", "Bearer");
        out.put("expires_in_seconds", expMinutes * 60);
        out.put("subject", subject);
        return out;
    }
}
