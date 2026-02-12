package com.smartcartai.backend.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;

@Entity
@Table(name = "inventory")
@Getter
@Setter
public class Inventory {

    @Id
    @Column(name = "inventory_id", length = 32)
    private String inventoryId;

    @Column(name = "item_name", nullable = false, columnDefinition = "TEXT")
    private String itemName;

    @Column(columnDefinition = "TEXT")
    private String category;

    @Column(columnDefinition = "TEXT")
    private String form;

    @Column(name = "usage", columnDefinition = "TEXT")
    private String usage;

    @Column(name = "item_type", columnDefinition = "TEXT")
    private String itemType;

    @Column(name = "vendor_id", length = 32)
    private String vendorId;

    @Column(name = "min_stock")
    private Integer minStock;

    @Column(name = "max_capacity")
    private Integer maxCapacity;

    @Column(name = "opening_stock")
    private Integer openingStock;

    @Column(name = "expiry_date")
    private java.time.LocalDate expiryDate;

    @Column(name = "selling_price", precision = 12, scale = 2)
    private java.math.BigDecimal sellingPrice;
}
