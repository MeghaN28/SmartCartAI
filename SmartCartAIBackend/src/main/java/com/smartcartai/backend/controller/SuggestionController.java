package com.smartcartai.backend.controller;

import com.smartcartai.backend.entity.Suggestion;
import com.smartcartai.backend.entity.SuggestionFoodBank;
import com.smartcartai.backend.repository.SuggestionFoodBankRepository;
import com.smartcartai.backend.repository.SuggestionFoodBankView;
import com.smartcartai.backend.repository.SuggestionRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/suggestions")
@Tag(name = "Suggestions", description = "AI-generated inventory suggestions")
public class SuggestionController {

    private final SuggestionRepository repository;
    private final SuggestionFoodBankRepository foodBankRepository;

    public SuggestionController(SuggestionRepository repository, SuggestionFoodBankRepository foodBankRepository) {
        this.repository = repository;
        this.foodBankRepository = foodBankRepository;
    }

    /** Batch-fetches suggestion_food_bank rows (joined to food_banks) and attaches them by suggestion_id. */
    private List<Suggestion> withFoodBanks(List<Suggestion> suggestions) {
        if (suggestions.isEmpty()) {
            return suggestions;
        }
        List<Integer> ids = suggestions.stream().map(Suggestion::getSuggestionId).collect(Collectors.toList());
        Map<Integer, List<SuggestionFoodBank>> byId = foodBankRepository.findWithFoodBankBySuggestionIdIn(ids).stream()
                .map(v -> {
                    SuggestionFoodBank sfb = new SuggestionFoodBank();
                    sfb.setId(v.getId());
                    sfb.setSuggestionId(v.getSuggestionId());
                    sfb.setFoodBankId(v.getFoodBankId());
                    sfb.setRank(v.getRank());
                    sfb.setDistanceMi(v.getDistanceMi());
                    sfb.setName(v.getName());
                    sfb.setAddress(v.getAddress());
                    return sfb;
                })
                .collect(Collectors.groupingBy(SuggestionFoodBank::getSuggestionId));
        suggestions.forEach(s -> s.setFoodBanks(byId.getOrDefault(s.getSuggestionId(), List.of())));
        return suggestions;
    }

    @GetMapping
    @Operation(summary = "Get all suggestions")
    public ResponseEntity<List<Suggestion>> getAll() {
        return ResponseEntity.ok(withFoodBanks(repository.findAllByOrderByCreatedAtDesc()));
    }

    @GetMapping("/status/{status}")
    @Operation(summary = "Get suggestions by status")
    public ResponseEntity<List<Suggestion>> getByStatus(@PathVariable String status) {
        return ResponseEntity.ok(withFoodBanks(repository.findByStatusOrderByCreatedAtDesc(status)));
    }

    @GetMapping("/inventory/{inventoryId}")
    @Operation(summary = "Get suggestions for a specific inventory item")
    public ResponseEntity<List<Suggestion>> getByInventoryId(@PathVariable String inventoryId) {
        return ResponseEntity.ok(withFoodBanks(repository.findByInventoryIdOrderByCreatedAtDesc(inventoryId)));
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

    @DeleteMapping("/{id}")
    @Operation(summary = "Delete a suggestion by ID")
    public ResponseEntity<Map<String, Object>> deleteById(@PathVariable Integer id) {
        if (!repository.existsById(id)) {
            return ResponseEntity.notFound().build();
        }
        repository.deleteById(id);
        return ResponseEntity.ok(Map.of("deleted", true, "id", id));
    }
}
