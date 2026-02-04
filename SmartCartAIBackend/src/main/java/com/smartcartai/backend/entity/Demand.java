package com.smartcartai.backend.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDate;

@Entity
@Table(name = "demand")
@Getter
@Setter
public class Demand {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "demand_id")
    private Integer demandId;

    @Column(name = "inventory_id", nullable = false, length = 32)
    private String inventoryId;

    @Column(name = "predicted_demand")
    private Integer predictedDemand;

    @Column(name = "model_version", columnDefinition = "TEXT")
    private String modelVersion;

    @Column(name = "prediction_date")
    private LocalDate predictionDate;
}
