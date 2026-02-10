package com.smartcartai.backend.controller;

import com.smartcartai.backend.entity.Suggestion;
import com.smartcartai.backend.repository.SuggestionRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/suggestions")
@Tag(name = "Suggestions", description = "AI-generated inventory suggestions")
public class SuggestionController {

    private final SuggestionRepository repository;

    public SuggestionController(SuggestionRepository repository) {
        this.repository = repository;
    }

    @GetMapping
    @Operation(summary = "Get all suggestions")
    public ResponseEntity<List<Suggestion>> getAll() {
        return ResponseEntity.ok(repository.findAllByOrderByCreatedAtDesc());
    }

    @GetMapping("/status/{status}")
    @Operation(summary = "Get suggestions by status")
    public ResponseEntity<List<Suggestion>> getByStatus(@PathVariable String status) {
        return ResponseEntity.ok(repository.findByStatusOrderByCreatedAtDesc(status));
    }

    @GetMapping("/inventory/{inventoryId}")
    @Operation(summary = "Get suggestions for a specific inventory item")
    public ResponseEntity<List<Suggestion>> getByInventoryId(@PathVariable String inventoryId) {
        return ResponseEntity.ok(repository.findByInventoryIdOrderByCreatedAtDesc(inventoryId));
    }

    @PutMapping("/{id}/status")
    @Operation(summary = "Update suggestion status")
    public ResponseEntity<Suggestion> updateStatus(
            @PathVariable Integer id,
            @RequestBody Map<String, String> request) {
        String status = request.get("status");
        return repository.findById(id)
                .map(suggestion -> {
                    suggestion.setStatus(status);
                    return ResponseEntity.ok(repository.save(suggestion));
                })
                .orElse(ResponseEntity.notFound().build());
    }
}
