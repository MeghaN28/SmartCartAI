package com.smartcartai.backend.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

@Entity
@Table(name = "consumption")
@Getter
@Setter
public class Consumption {

    @Id
    @Column(name = "transaction_id", length = 64)
    private String transactionId;

    @Column(name = "transaction_date")
    private java.time.LocalDate transactionDate;

    @Column(name = "inventory_id", nullable = false, length = 32)
    private String inventoryId;

    @Column(name = "quantity_consumed")
    private Integer quantityConsumed;

    @Column(columnDefinition = "TEXT")
    private String department;

    @Column(name = "staff_id", length = 32)
    private String staffId;

    @Column(columnDefinition = "TEXT")
    private String shift;

    @Column(name = "consumption_reason", columnDefinition = "TEXT")
    private String consumptionReason;

    @Column(name = "remaining_stock")
    private Integer remainingStock;

    @Column(name = "batch_lot", columnDefinition = "TEXT")
    private String batchLot;
}
