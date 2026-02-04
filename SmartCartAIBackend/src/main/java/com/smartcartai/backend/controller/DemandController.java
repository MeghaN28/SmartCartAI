package com.smartcartai.backend.controller;

import com.smartcartai.backend.entity.Demand;
import com.smartcartai.backend.repository.DemandRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/demand")
@Tag(name = "Demand", description = "Demand predictions")
public class DemandController {

    private final DemandRepository repository;

    public DemandController(DemandRepository repository) {
        this.repository = repository;
    }

    @GetMapping
    @Operation(summary = "Get all demand predictions")
    public ResponseEntity<List<Demand>> getAll() {
        return ResponseEntity.ok(repository.findAll());
    }
}
