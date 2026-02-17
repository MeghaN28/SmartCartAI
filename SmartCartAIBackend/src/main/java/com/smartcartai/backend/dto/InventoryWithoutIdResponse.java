package com.smartcartai.backend.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.LocalDate;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class InventoryWithoutIdResponse {

    private String itemName;
    private String category;
    private String form;
    private String usage;
    private String itemType;
    private String vendorId;
    private Integer minStock;
    private Integer maxCapacity;
    private Integer openingStock;
    private LocalDate expiryDate;
    private BigDecimal sellingPrice;
}
