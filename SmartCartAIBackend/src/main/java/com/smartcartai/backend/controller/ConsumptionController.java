package com.smartcartai.backend.controller;

import com.smartcartai.backend.entity.Consumption;
import com.smartcartai.backend.repository.ConsumptionRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/consumption")
@Tag(name = "Consumption", description = "Consumption / usage logs")
public class ConsumptionController {

    private final ConsumptionRepository repository;

    public ConsumptionController(ConsumptionRepository repository) {
        this.repository = repository;
    }

    @GetMapping
    @Operation(summary = "Get all consumption records")
    public ResponseEntity<List<Consumption>> getAll() {
        return ResponseEntity.ok(repository.findAll());
    }
}
