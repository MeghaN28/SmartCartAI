package com.smartcartai.backend.repository;

import com.smartcartai.backend.entity.Sales;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface SalesRepository extends JpaRepository<Sales, String> {

    List<Sales> findAll();
}
