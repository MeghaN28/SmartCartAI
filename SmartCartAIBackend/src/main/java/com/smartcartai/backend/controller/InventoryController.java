package com.smartcartai.backend.controller;

import com.smartcartai.backend.dto.InventoryWithoutIdResponse;
import com.smartcartai.backend.entity.Inventory;
import com.smartcartai.backend.repository.InventoryRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/inventory")
@Tag(name = "Inventory", description = "Inventory master data")
public class InventoryController {

    private final InventoryRepository repository;

    public InventoryController(InventoryRepository repository) {
        this.repository = repository;
    }

    @GetMapping
    @Operation(summary = "Get all inventory items (without id)")
    public ResponseEntity<List<InventoryWithoutIdResponse>> getAllWithoutId() {
        List<InventoryWithoutIdResponse> list = repository.findAll().stream()
                .map(this::toResponse)
                .collect(Collectors.toList());
        return ResponseEntity.ok(list);
    }

    private InventoryWithoutIdResponse toResponse(Inventory e) {
        return new InventoryWithoutIdResponse(
                e.getItemName(),
                e.getCategory(),
                e.getForm(),
                e.getUsage(),
                e.getItemType(),
                e.getVendorId(),
                e.getMinStock(),
                e.getMaxCapacity(),
                e.getOpeningStock(),
                e.getExpiryDate(),
                e.getSellingPrice()
        );
    }
}
