package com.smartcartai.backend.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.LocalDate;

@Entity
@Table(name = "sales")
@Getter
@Setter
public class Sales {

    @Id
    @Column(name = "invoice_id", length = 64)
    private String invoiceId;

    @Column(name = "vendor_id", length = 32)
    private String vendorId;

    @Column(name = "inventory_id", nullable = false, length = 32)
    private String inventoryId;

    @Column(name = "purchase_date")
    private LocalDate purchaseDate;

    private Integer quantity;

    @Column(name = "unit_cost", precision = 12, scale = 2)
    private BigDecimal unitCost;

    @Column(name = "total_cost", precision = 12, scale = 2)
    private BigDecimal totalCost;

    @Column(name = "payment_status", columnDefinition = "TEXT")
    private String paymentStatus;

    @Column(name = "account_code", columnDefinition = "TEXT")
    private String accountCode;

    @Column(name = "delivery_date")
    private LocalDate deliveryDate;
}
