package com.waterinfo.platform.common.api;

import lombok.Data;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.util.ArrayList;
import java.util.List;

/**
 * Pagination request parameters
 */
@Data
public class PageRequest {

    @Min(value = 1, message = "Page number must be at least 1")
    private Integer page = 1;

    @Min(value = 1, message = "Page size must be at least 1")
    @Max(value = 1000, message = "Page size must not exceed 1000")
    private Integer size = 20;

    private List<String> sort = new ArrayList<>();

    public long getOffset() {
        return (long) (page - 1) * size;
    }
}
