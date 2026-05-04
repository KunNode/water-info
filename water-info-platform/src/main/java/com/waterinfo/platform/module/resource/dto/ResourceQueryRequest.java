package com.waterinfo.platform.module.resource.dto;

import com.waterinfo.platform.common.api.PageRequest;
import lombok.Data;
import lombok.EqualsAndHashCode;

@Data
@EqualsAndHashCode(callSuper = true)
public class ResourceQueryRequest extends PageRequest {

    private String type;
    private String status;
    private String keyword;
}
