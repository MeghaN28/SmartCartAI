package com.smartcartai.backend.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI smartCartOpenAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("SmartCart AI Backend API")
                        .description("REST API to fetch inventory, sales, consumption and demand data from PostgreSQL")
                        .version("1.0.0"));
    }
}
