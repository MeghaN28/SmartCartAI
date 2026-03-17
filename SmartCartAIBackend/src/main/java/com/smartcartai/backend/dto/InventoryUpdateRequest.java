package com.smartcartai.backend.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class InventoryUpdateRequest {
    private String itemName;
    private String category;
    private Integer openingStock;
    private Integer minStock;
}
