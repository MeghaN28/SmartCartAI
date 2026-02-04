package com.smartcartai.backend.controller;

import com.smartcartai.backend.entity.Sales;
import com.smartcartai.backend.repository.SalesRepository;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/sales")
@Tag(name = "Sales", description = "Sales transactions")
public class SalesController {

    private final SalesRepository repository;

    public SalesController(SalesRepository repository) {
        this.repository = repository;
    }

    @GetMapping
    @Operation(summary = "Get all sales")
    public ResponseEntity<List<Sales>> getAll() {
        return ResponseEntity.ok(repository.findAll());
    }
}
