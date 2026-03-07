package com.waterinfo.platform.common.api;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.io.Serializable;
import java.util.List;

/**
 * Pagination response wrapper
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class PageResponse<T> implements Serializable {

    private static final long serialVersionUID = 1L;

    private List<T> records;
    private Long total;
    private Integer page;
    private Integer size;
    private Integer pages;

    public static <T> PageResponse<T> of(List<T> records, Long total, Integer page, Integer size) {
        int pages = (int) Math.ceil((double) total / size);
        return PageResponse.<T>builder()
                .records(records)
                .total(total)
                .page(page)
                .size(size)
                .pages(pages)
                .build();
    }

    public static <T> PageResponse<T> of(com.baomidou.mybatisplus.extension.plugins.pagination.Page<T> page) {
        return PageResponse.<T>builder()
                .records(page.getRecords())
                .total(page.getTotal())
                .page((int) page.getCurrent())
                .size((int) page.getSize())
                .pages((int) page.getPages())
                .build();
    }
}
