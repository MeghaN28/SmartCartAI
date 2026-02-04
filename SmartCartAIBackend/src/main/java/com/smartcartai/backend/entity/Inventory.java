package com.smartcartai.backend.entity;

import jakarta.persistence.*;
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
}
