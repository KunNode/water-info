package com.waterinfo.platform.module.resource.dto;

import com.waterinfo.platform.common.api.PageRequest;
import lombok.Data;
import lombok.EqualsAndHashCode;

@Data
@EqualsAndHashCode(callSuper = true)
public class DispatchQueryRequest extends PageRequest {

    private String resourceId;
    private String planId;
    private String status;
    private String source;
}
