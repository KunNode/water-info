# Resource Management Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a resource management module (materials, personnel, vehicles) with CRUD, dispatch tracking, and AI integration so the ResourceDispatcher agent queries real inventory instead of generating hypothetical allocations.

**Architecture:** New `resource` module in Spring Boot following existing entity/dto/vo/mapper/service/controller pattern. New `resource_tools.py` in AI service with `SimpleTool` wrappers calling the platform API. Frontend adds a top-level "资源管理" menu with 4 sub-pages.

**Tech Stack:** Java 17 / Spring Boot 3.2.2 / MyBatis-Plus (backend), Vue 3 / TypeScript / Element Plus (frontend), Python 3.11 / FastAPI / SimpleTool (AI service), PostgreSQL 15 / Flyway (database).

**Spec:** `docs/superpowers/specs/2026-05-04-resource-management-design.md`

---

## File Map

### Backend (water-info-platform)
- Create: `src/main/resources/db/migration/V11__resource_management.sql`
- Create: `module/resource/entity/Resource.java`
- Create: `module/resource/entity/ResourceDispatch.java`
- Create: `module/resource/dto/CreateResourceRequest.java`
- Create: `module/resource/dto/UpdateResourceRequest.java`
- Create: `module/resource/dto/ResourceQueryRequest.java`
- Create: `module/resource/dto/CreateDispatchRequest.java`
- Create: `module/resource/dto/UpdateDispatchStatusRequest.java`
- Create: `module/resource/dto/DispatchQueryRequest.java`
- Create: `module/resource/vo/ResourceVO.java`
- Create: `module/resource/vo/ResourceStatsVO.java`
- Create: `module/resource/vo/ResourceDispatchVO.java`
- Create: `module/resource/mapper/ResourceMapper.java`
- Create: `module/resource/mapper/ResourceDispatchMapper.java`
- Create: `module/resource/service/ResourceService.java`
- Create: `module/resource/service/ResourceDispatchService.java`
- Create: `module/resource/controller/ResourceController.java`
- Create: `module/resource/controller/ResourceDispatchController.java`
- Modify: `common/exception/ErrorCode.java` (add 2000 range)

### Frontend (water-info-admin)
- Create: `src/api/resource.ts`
- Create: `src/views/resource/material/index.vue`
- Create: `src/views/resource/personnel/index.vue`
- Create: `src/views/resource/vehicle/index.vue`
- Create: `src/views/resource/dispatch/index.vue`
- Create: `src/views/resource/components/ResourceForm.vue`
- Create: `src/views/resource/components/DispatchForm.vue`
- Modify: `src/types/models.ts` (add Resource types)
- Modify: `src/utils/format.ts` (add resource maps)
- Modify: `src/router/index.ts` (add /resource routes)

### AI Service (water-info-ai)
- Create: `app/tools/resource_tools.py`
- Modify: `app/services/platform_client.py` (add resource API methods)
- Modify: `app/state.py` (extend ResourceAllocation)
- Modify: `app/agents/resource_dispatcher.py` (use tools)

---

### Task 1: Database Migration V11

**Files:**
- Create: `water-info-platform/src/main/resources/db/migration/V11__resource_management.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
-- V11__resource_management.sql
-- Resource management tables for emergency resource tracking and dispatch

CREATE TABLE resource (
    id           VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    type         VARCHAR(20)  NOT NULL,
    name         VARCHAR(100) NOT NULL,
    quantity     INTEGER      NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    unit         VARCHAR(20)  NOT NULL,
    location     VARCHAR(200) NOT NULL,
    status       VARCHAR(20)  NOT NULL DEFAULT 'AVAILABLE',
    attributes   JSONB        NOT NULL DEFAULT '{}',
    description  TEXT,
    created_at   TIMESTAMP    NOT NULL DEFAULT now(),
    updated_at   TIMESTAMP    NOT NULL DEFAULT now(),
    deleted      BOOLEAN      NOT NULL DEFAULT false
);

CREATE INDEX idx_resource_type ON resource (type);
CREATE INDEX idx_resource_status ON resource (status);
CREATE INDEX idx_resource_name ON resource (name);
CREATE INDEX idx_resource_attributes ON resource USING gin (attributes);

COMMENT ON TABLE resource IS '应急资源台账';
COMMENT ON COLUMN resource.type IS '资源类型: MATERIAL/PERSONNEL/VEHICLE';
COMMENT ON COLUMN resource.status IS '状态: AVAILABLE/IN_USE/MAINTENANCE/DEPLETED';
COMMENT ON COLUMN resource.attributes IS '类型特有属性(JSONB)';

CREATE TABLE resource_dispatch (
    id             VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    resource_id    VARCHAR(36)  NOT NULL REFERENCES resource(id),
    plan_id        VARCHAR(50),
    quantity       INTEGER      NOT NULL CHECK (quantity > 0),
    from_location  VARCHAR(200) NOT NULL,
    to_location    VARCHAR(200) NOT NULL,
    status         VARCHAR(20)  NOT NULL DEFAULT 'PENDING',
    dispatched_at  TIMESTAMP,
    arrived_at     TIMESTAMP,
    returned_at    TIMESTAMP,
    operator       VARCHAR(50),
    source         VARCHAR(20)  NOT NULL DEFAULT 'MANUAL',
    notes          TEXT,
    created_at     TIMESTAMP    NOT NULL DEFAULT now(),
    updated_at     TIMESTAMP    NOT NULL DEFAULT now()
);

CREATE INDEX idx_dispatch_resource_id ON resource_dispatch (resource_id);
CREATE INDEX idx_dispatch_status ON resource_dispatch (status);
CREATE INDEX idx_dispatch_plan_id ON resource_dispatch (plan_id);
CREATE INDEX idx_dispatch_dispatched_at ON resource_dispatch (dispatched_at);

COMMENT ON TABLE resource_dispatch IS '资源调度记录';
COMMENT ON COLUMN resource_dispatch.status IS '状态: PENDING/DISPATCHED/ARRIVED/RETURNED/CANCELLED';
COMMENT ON COLUMN resource_dispatch.source IS '来源: AI/MANUAL';
```

- [ ] **Step 2: Verify migration file exists and is valid SQL**

Run: `cat water-info-platform/src/main/resources/db/migration/V11__resource_management.sql | head -5`
Expected: Shows the CREATE TABLE statement.

- [ ] **Step 3: Commit**

```bash
git add water-info-platform/src/main/resources/db/migration/V11__resource_management.sql
git commit -m "feat(db): add resource and resource_dispatch tables (V11)"
```

---

### Task 2: ErrorCode Additions

**Files:**
- Modify: `water-info-platform/src/main/java/com/waterinfo/platform/common/exception/ErrorCode.java:60-61`

- [ ] **Step 1: Add resource error codes**

After the line `DEPT_NOT_FOUND(1902, "Department not found");`, replace the semicolon with a comma and add:

```java
    DEPT_NOT_FOUND(1902, "Department not found"),

    // Resource errors (2000-2099)
    RESOURCE_NOT_FOUND(2000, "Resource not found"),
    RESOURCE_INSUFFICIENT_STOCK(2001, "Insufficient resource stock"),
    DISPATCH_NOT_FOUND(2002, "Dispatch record not found"),
    DISPATCH_INVALID_STATUS_TRANSITION(2003, "Invalid dispatch status transition");
```

- [ ] **Step 2: Verify compilation**

Run: `cd water-info-platform && ./mvnw compile -q`
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit**

```bash
git add water-info-platform/src/main/java/com/waterinfo/platform/common/exception/ErrorCode.java
git commit -m "feat: add resource error codes (2000-2099 range)"
```

---

### Task 3: Resource Entity, DTOs, VO, Mapper

**Files:**
- Create: `water-info-platform/src/main/java/com/waterinfo/platform/module/resource/entity/Resource.java`
- Create: `water-info-platform/src/main/java/com/waterinfo/platform/module/resource/dto/CreateResourceRequest.java`
- Create: `water-info-platform/src/main/java/com/waterinfo/platform/module/resource/dto/UpdateResourceRequest.java`
- Create: `water-info-platform/src/main/java/com/waterinfo/platform/module/resource/dto/ResourceQueryRequest.java`
- Create: `water-info-platform/src/main/java/com/waterinfo/platform/module/resource/vo/ResourceVO.java`
- Create: `water-info-platform/src/main/java/com/waterinfo/platform/module/resource/vo/ResourceStatsVO.java`
- Create: `water-info-platform/src/main/java/com/waterinfo/platform/module/resource/mapper/ResourceMapper.java`

- [ ] **Step 1: Create Resource entity**

```java
package com.waterinfo.platform.module.resource.entity;

import com.baomidou.mybatisplus.annotation.*;
import com.waterinfo.platform.common.mybatis.typehandler.JsonbMapTypeHandler;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName(value = "resource", autoResultMap = true)
public class Resource {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String type;
    private String name;
    private Integer quantity;
    private String unit;
    private String location;
    private String status;

    @TableField(typeHandler = JsonbMapTypeHandler.class)
    private Map<String, Object> attributes;

    private String description;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    @TableLogic
    private Boolean deleted;
}
```

- [ ] **Step 2: Create CreateResourceRequest DTO**

```java
package com.waterinfo.platform.module.resource.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.Map;

@Data
public class CreateResourceRequest {

    @NotBlank(message = "资源类型不能为空")
    private String type;

    @NotBlank(message = "资源名称不能为空")
    @Size(max = 100, message = "资源名称不超过100个字符")
    private String name;

    @NotNull(message = "数量不能为空")
    @Min(value = 0, message = "数量不能为负数")
    private Integer quantity;

    @NotBlank(message = "单位不能为空")
    @Size(max = 20, message = "单位不超过20个字符")
    private String unit;

    @NotBlank(message = "存放地点不能为空")
    @Size(max = 200, message = "存放地点不超过200个字符")
    private String location;

    private Map<String, Object> attributes;

    private String description;
}
```

- [ ] **Step 3: Create UpdateResourceRequest DTO**

```java
package com.waterinfo.platform.module.resource.dto;

import lombok.Data;

import java.util.Map;

@Data
public class UpdateResourceRequest {

    private String name;
    private Integer quantity;
    private String unit;
    private String location;
    private String status;
    private Map<String, Object> attributes;
    private String description;
}
```

- [ ] **Step 4: Create ResourceQueryRequest DTO**

```java
package com.waterinfo.platform.module.resource.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;
import com.waterinfo.platform.common.api.PageRequest;

@Data
@EqualsAndHashCode(callSuper = true)
public class ResourceQueryRequest extends PageRequest {

    private String type;
    private String status;
    private String keyword;
}
```

- [ ] **Step 5: Create ResourceVO**

```java
package com.waterinfo.platform.module.resource.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.Map;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ResourceVO {

    private String id;
    private String type;
    private String name;
    private Integer quantity;
    private String unit;
    private String location;
    private String status;
    private Map<String, Object> attributes;
    private String description;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
```

- [ ] **Step 6: Create ResourceStatsVO**

```java
package com.waterinfo.platform.module.resource.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ResourceStatsVO {

    private String type;
    private String status;
    private Long count;
    private Integer totalQuantity;
}
```

- [ ] **Step 7: Create ResourceMapper**

```java
package com.waterinfo.platform.module.resource.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.waterinfo.platform.module.resource.entity.Resource;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface ResourceMapper extends BaseMapper<Resource> {
}
```

- [ ] **Step 8: Verify compilation**

Run: `cd water-info-platform && ./mvnw compile -q`
Expected: BUILD SUCCESS

- [ ] **Step 9: Commit**

```bash
git add water-info-platform/src/main/java/com/waterinfo/platform/module/resource/
git commit -m "feat(resource): add Resource entity, DTOs, VO, mapper"
```

---

### Task 4: ResourceDispatch Entity, DTOs, VO, Mapper

**Files:**
- Create: `water-info-platform/src/main/java/com/waterinfo/platform/module/resource/entity/ResourceDispatch.java`
- Create: `water-info-platform/src/main/java/com/waterinfo/platform/module/resource/dto/CreateDispatchRequest.java`
- Create: `water-info-platform/src/main/java/com/waterinfo/platform/module/resource/dto/UpdateDispatchStatusRequest.java`
- Create: `water-info-platform/src/main/java/com/waterinfo/platform/module/resource/dto/DispatchQueryRequest.java`
- Create: `water-info-platform/src/main/java/com/waterinfo/platform/module/resource/vo/ResourceDispatchVO.java`
- Create: `water-info-platform/src/main/java/com/waterinfo/platform/module/resource/mapper/ResourceDispatchMapper.java`

- [ ] **Step 1: Create ResourceDispatch entity**

```java
package com.waterinfo.platform.module.resource.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@TableName("resource_dispatch")
public class ResourceDispatch {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String resourceId;
    private String planId;
    private Integer quantity;
    private String fromLocation;
    private String toLocation;
    private String status;
    private LocalDateTime dispatchedAt;
    private LocalDateTime arrivedAt;
    private LocalDateTime returnedAt;
    private String operator;
    private String source;
    private String notes;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
```

- [ ] **Step 2: Create CreateDispatchRequest DTO**

```java
package com.waterinfo.platform.module.resource.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Min;
import lombok.Data;

@Data
public class CreateDispatchRequest {

    @NotBlank(message = "资源ID不能为空")
    private String resourceId;

    private String planId;

    @NotNull(message = "调度数量不能为空")
    @Min(value = 1, message = "调度数量必须大于0")
    private Integer quantity;

    @NotBlank(message = "调出地点不能为空")
    private String fromLocation;

    @NotBlank(message = "调入地点不能为空")
    private String toLocation;

    private String notes;
}
```

- [ ] **Step 3: Create UpdateDispatchStatusRequest DTO**

```java
package com.waterinfo.platform.module.resource.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

@Data
public class UpdateDispatchStatusRequest {

    @NotBlank(message = "状态不能为空")
    private String status;

    private String notes;
}
```

- [ ] **Step 4: Create DispatchQueryRequest DTO**

```java
package com.waterinfo.platform.module.resource.dto;

import lombok.Data;
import lombok.EqualsAndHashCode;
import com.waterinfo.platform.common.api.PageRequest;

@Data
@EqualsAndHashCode(callSuper = true)
public class DispatchQueryRequest extends PageRequest {

    private String resourceId;
    private String planId;
    private String status;
    private String source;
}
```

- [ ] **Step 5: Create ResourceDispatchVO**

```java
package com.waterinfo.platform.module.resource.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ResourceDispatchVO {

    private String id;
    private String resourceId;
    private String resourceName;
    private String resourceType;
    private String planId;
    private Integer quantity;
    private String fromLocation;
    private String toLocation;
    private String status;
    private LocalDateTime dispatchedAt;
    private LocalDateTime arrivedAt;
    private LocalDateTime returnedAt;
    private String operator;
    private String source;
    private String notes;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
```

- [ ] **Step 6: Create ResourceDispatchMapper**

```java
package com.waterinfo.platform.module.resource.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.waterinfo.platform.module.resource.entity.ResourceDispatch;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface ResourceDispatchMapper extends BaseMapper<ResourceDispatch> {
}
```

- [ ] **Step 7: Verify compilation**

Run: `cd water-info-platform && ./mvnw compile -q`
Expected: BUILD SUCCESS

- [ ] **Step 8: Commit**

```bash
git add water-info-platform/src/main/java/com/waterinfo/platform/module/resource/
git commit -m "feat(resource): add ResourceDispatch entity, DTOs, VO, mapper"
```

---

### Task 5: ResourceService

**Files:**
- Create: `water-info-platform/src/main/java/com/waterinfo/platform/module/resource/service/ResourceService.java`

- [ ] **Step 1: Create ResourceService**

```java
package com.waterinfo.platform.module.resource.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.waterinfo.platform.common.exception.BusinessException;
import com.waterinfo.platform.common.exception.ErrorCode;
import com.waterinfo.platform.module.audit.service.AuditLogService;
import com.waterinfo.platform.module.resource.dto.CreateResourceRequest;
import com.waterinfo.platform.module.resource.dto.ResourceQueryRequest;
import com.waterinfo.platform.module.resource.dto.UpdateResourceRequest;
import com.waterinfo.platform.module.resource.entity.Resource;
import com.waterinfo.platform.module.resource.mapper.ResourceMapper;
import com.waterinfo.platform.module.resource.vo.ResourceStatsVO;
import com.waterinfo.platform.module.resource.vo.ResourceVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class ResourceService extends ServiceImpl<ResourceMapper, Resource> {

    private final AuditLogService auditLogService;

    @Transactional
    public ResourceVO createResource(CreateResourceRequest request) {
        Resource resource = Resource.builder()
                .type(request.getType())
                .name(request.getName())
                .quantity(request.getQuantity())
                .unit(request.getUnit())
                .location(request.getLocation())
                .status("AVAILABLE")
                .attributes(request.getAttributes())
                .description(request.getDescription())
                .build();

        save(resource);

        auditLogService.logAsync("RESOURCE_CREATE", "RESOURCE", resource.getId(),
                Map.of("name", resource.getName(), "type", resource.getType()));

        return convertToVO(resource);
    }

    @Transactional
    public ResourceVO updateResource(String id, UpdateResourceRequest request) {
        Resource resource = getById(id);
        if (resource == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND);
        }

        if (StringUtils.hasText(request.getName())) {
            resource.setName(request.getName());
        }
        if (request.getQuantity() != null) {
            resource.setQuantity(request.getQuantity());
        }
        if (StringUtils.hasText(request.getUnit())) {
            resource.setUnit(request.getUnit());
        }
        if (StringUtils.hasText(request.getLocation())) {
            resource.setLocation(request.getLocation());
        }
        if (StringUtils.hasText(request.getStatus())) {
            resource.setStatus(request.getStatus());
        }
        if (request.getAttributes() != null) {
            resource.setAttributes(request.getAttributes());
        }
        if (request.getDescription() != null) {
            resource.setDescription(request.getDescription());
        }

        updateById(resource);

        auditLogService.logAsync("RESOURCE_UPDATE", "RESOURCE", resource.getId(),
                Map.of("name", resource.getName()));

        return convertToVO(resource);
    }

    public ResourceVO getResourceById(String id) {
        Resource resource = getById(id);
        if (resource == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND);
        }
        return convertToVO(resource);
    }

    public Page<ResourceVO> queryResources(ResourceQueryRequest request) {
        Page<Resource> page = new Page<>(request.getPage(), request.getSize());
        LambdaQueryWrapper<Resource> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(request.getType())) {
            wrapper.eq(Resource::getType, request.getType());
        }
        if (StringUtils.hasText(request.getStatus())) {
            wrapper.eq(Resource::getStatus, request.getStatus());
        }
        if (StringUtils.hasText(request.getKeyword())) {
            wrapper.and(w -> w
                    .like(Resource::getName, request.getKeyword())
                    .or()
                    .like(Resource::getLocation, request.getKeyword()));
        }

        wrapper.orderByDesc(Resource::getCreatedAt);
        Page<Resource> result = page(page, wrapper);

        Page<ResourceVO> voPage = new Page<>(result.getCurrent(), result.getSize(), result.getTotal());
        voPage.setRecords(result.getRecords().stream()
                .map(this::convertToVO)
                .collect(Collectors.toList()));
        return voPage;
    }

    public List<ResourceVO> getAvailableResources(String type, String location) {
        LambdaQueryWrapper<Resource> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Resource::getStatus, "AVAILABLE");
        wrapper.gt(Resource::getQuantity, 0);
        if (StringUtils.hasText(type)) {
            wrapper.eq(Resource::getType, type);
        }
        if (StringUtils.hasText(location)) {
            wrapper.like(Resource::getLocation, location);
        }
        wrapper.orderByDesc(Resource::getUpdatedAt);

        return list(wrapper).stream()
                .map(this::convertToVO)
                .collect(Collectors.toList());
    }

    public List<ResourceStatsVO> getStats() {
        // Implemented via MyBatis-Plus lambda aggregation is not directly supported,
        // so we use a simple approach: list all and group in Java.
        // For production with large datasets, consider a custom SQL query.
        List<Resource> all = list(new LambdaQueryWrapper<Resource>()
                .select(Resource::getType, Resource::getStatus, Resource::getQuantity));

        return all.stream()
                .collect(Collectors.groupingBy(
                        r -> r.getType() + ":" + r.getStatus(),
                        Collectors.collectingAndThen(Collectors.toList(), group -> {
                            Resource first = group.get(0);
                            return ResourceStatsVO.builder()
                                    .type(first.getType())
                                    .status(first.getStatus())
                                    .count((long) group.size())
                                    .totalQuantity(group.stream().mapToInt(Resource::getQuantity).sum())
                                    .build();
                        })))
                .values().stream().collect(Collectors.toList());
    }

    @Transactional
    public void adjustQuantity(String id, int delta) {
        Resource resource = getById(id);
        if (resource == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND);
        }
        int newQty = resource.getQuantity() + delta;
        if (newQty < 0) {
            throw new BusinessException(ErrorCode.RESOURCE_INSUFFICIENT_STOCK);
        }
        resource.setQuantity(newQty);
        if (newQty == 0 && "AVAILABLE".equals(resource.getStatus())) {
            resource.setStatus("DEPLETED");
        } else if (newQty > 0 && "DEPLETED".equals(resource.getStatus())) {
            resource.setStatus("AVAILABLE");
        }
        updateById(resource);
    }

    @Transactional
    public void deleteResource(String id) {
        Resource resource = getById(id);
        if (resource == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND);
        }
        removeById(id);
        auditLogService.logAsync("RESOURCE_DELETE", "RESOURCE", id,
                Map.of("name", resource.getName()));
    }

    private ResourceVO convertToVO(Resource resource) {
        return ResourceVO.builder()
                .id(resource.getId())
                .type(resource.getType())
                .name(resource.getName())
                .quantity(resource.getQuantity())
                .unit(resource.getUnit())
                .location(resource.getLocation())
                .status(resource.getStatus())
                .attributes(resource.getAttributes())
                .description(resource.getDescription())
                .createdAt(resource.getCreatedAt())
                .updatedAt(resource.getUpdatedAt())
                .build();
    }
}
```

- [ ] **Step 2: Verify compilation**

Run: `cd water-info-platform && ./mvnw compile -q`
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit**

```bash
git add water-info-platform/src/main/java/com/waterinfo/platform/module/resource/service/ResourceService.java
git commit -m "feat(resource): add ResourceService with CRUD and inventory management"
```

---

### Task 6: ResourceDispatchService

**Files:**
- Create: `water-info-platform/src/main/java/com/waterinfo/platform/module/resource/service/ResourceDispatchService.java`

- [ ] **Step 1: Create ResourceDispatchService**

```java
package com.waterinfo.platform.module.resource.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.waterinfo.platform.common.exception.BusinessException;
import com.waterinfo.platform.common.exception.ErrorCode;
import com.waterinfo.platform.module.audit.service.AuditLogService;
import com.waterinfo.platform.module.resource.dto.CreateDispatchRequest;
import com.waterinfo.platform.module.resource.dto.DispatchQueryRequest;
import com.waterinfo.platform.module.resource.dto.UpdateDispatchStatusRequest;
import com.waterinfo.platform.module.resource.entity.Resource;
import com.waterinfo.platform.module.resource.entity.ResourceDispatch;
import com.waterinfo.platform.module.resource.mapper.ResourceDispatchMapper;
import com.waterinfo.platform.module.resource.vo.ResourceDispatchVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Lazy;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class ResourceDispatchService extends ServiceImpl<ResourceDispatchMapper, ResourceDispatch> {

    @Lazy
    private final ResourceService resourceService;
    private final AuditLogService auditLogService;

    private static final Set<String> VALID_TRANSITIONS = Set.of(
            "PENDING->DISPATCHED",
            "DISPATCHED->ARRIVED",
            "ARRIVED->RETURNED",
            "PENDING->CANCELLED",
            "DISPATCHED->CANCELLED"
    );

    @Transactional
    public ResourceDispatchVO createDispatch(CreateDispatchRequest request, String source) {
        Resource resource = resourceService.getById(request.getResourceId());
        if (resource == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND);
        }
        if (resource.getQuantity() < request.getQuantity()) {
            throw new BusinessException(ErrorCode.RESOURCE_INSUFFICIENT_STOCK,
                    "可用库存 " + resource.getQuantity() + "，请求 " + request.getQuantity());
        }

        // Decrement resource quantity
        resourceService.adjustQuantity(resource.getId(), -request.getQuantity());

        ResourceDispatch dispatch = ResourceDispatch.builder()
                .resourceId(request.getResourceId())
                .planId(request.getPlanId())
                .quantity(request.getQuantity())
                .fromLocation(request.getFromLocation())
                .toLocation(request.getToLocation())
                .status("PENDING")
                .source(source)
                .operator(request.getNotes())
                .notes(request.getNotes())
                .build();

        save(dispatch);

        auditLogService.logAsync("DISPATCH_CREATE", "RESOURCE_DISPATCH", dispatch.getId(),
                Map.of("resourceId", resource.getId(), "quantity", request.getQuantity()));

        return convertToVO(dispatch, resource);
    }

    @Transactional
    public ResourceDispatchVO updateStatus(String id, UpdateDispatchStatusRequest request) {
        ResourceDispatch dispatch = getById(id);
        if (dispatch == null) {
            throw new BusinessException(ErrorCode.DISPATCH_NOT_FOUND);
        }

        String transition = dispatch.getStatus() + "->" + request.getStatus();
        if (!VALID_TRANSITIONS.contains(transition)) {
            throw new BusinessException(ErrorCode.DISPATCH_INVALID_STATUS_TRANSITION,
                    "不允许从 " + dispatch.getStatus() + " 变更为 " + request.getStatus());
        }

        LocalDateTime now = LocalDateTime.now();
        dispatch.setStatus(request.getStatus());

        switch (request.getStatus()) {
            case "DISPATCHED" -> dispatch.setDispatchedAt(now);
            case "ARRIVED" -> dispatch.setArrivedAt(now);
            case "RETURNED" -> {
                dispatch.setReturnedAt(now);
                // Restore resource quantity on return
                resourceService.adjustQuantity(dispatch.getResourceId(), dispatch.getQuantity());
            }
            case "CANCELLED" -> {
                // Restore resource quantity on cancel
                if ("PENDING".equals(dispatch.getStatus()) || "DISPATCHED".equals(dispatch.getStatus())) {
                    resourceService.adjustQuantity(dispatch.getResourceId(), dispatch.getQuantity());
                }
            }
        }

        if (StringUtils.hasText(request.getNotes())) {
            dispatch.setNotes(request.getNotes());
        }

        updateById(dispatch);

        auditLogService.logAsync("DISPATCH_STATUS_UPDATE", "RESOURCE_DISPATCH", dispatch.getId(),
                Map.of("status", request.getStatus()));

        Resource resource = resourceService.getById(dispatch.getResourceId());
        return convertToVO(dispatch, resource);
    }

    public ResourceDispatchVO getDispatchById(String id) {
        ResourceDispatch dispatch = getById(id);
        if (dispatch == null) {
            throw new BusinessException(ErrorCode.DISPATCH_NOT_FOUND);
        }
        Resource resource = resourceService.getById(dispatch.getResourceId());
        return convertToVO(dispatch, resource);
    }

    public Page<ResourceDispatchVO> queryDispatches(DispatchQueryRequest request) {
        Page<ResourceDispatch> page = new Page<>(request.getPage(), request.getSize());
        LambdaQueryWrapper<ResourceDispatch> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(request.getResourceId())) {
            wrapper.eq(ResourceDispatch::getResourceId, request.getResourceId());
        }
        if (StringUtils.hasText(request.getPlanId())) {
            wrapper.eq(ResourceDispatch::getPlanId, request.getPlanId());
        }
        if (StringUtils.hasText(request.getStatus())) {
            wrapper.eq(ResourceDispatch::getStatus, request.getStatus());
        }
        if (StringUtils.hasText(request.getSource())) {
            wrapper.eq(ResourceDispatch::getSource, request.getSource());
        }

        wrapper.orderByDesc(ResourceDispatch::getCreatedAt);
        Page<ResourceDispatch> result = page(page, wrapper);

        // Batch fetch resources for enrichment
        List<String> resourceIds = result.getRecords().stream()
                .map(ResourceDispatch::getResourceId)
                .distinct()
                .collect(Collectors.toList());

        Map<String, Resource> resourceMap = resourceIds.isEmpty()
                ? Map.of()
                : resourceService.listByIds(resourceIds).stream()
                .collect(Collectors.toMap(Resource::getId, r -> r));

        Page<ResourceDispatchVO> voPage = new Page<>(result.getCurrent(), result.getSize(), result.getTotal());
        voPage.setRecords(result.getRecords().stream()
                .map(d -> convertToVO(d, resourceMap.get(d.getResourceId())))
                .collect(Collectors.toList()));
        return voPage;
    }

    public List<ResourceDispatchVO> getDispatchesByPlanId(String planId) {
        List<ResourceDispatch> dispatches = list(new LambdaQueryWrapper<ResourceDispatch>()
                .eq(ResourceDispatch::getPlanId, planId)
                .orderByDesc(ResourceDispatch::getCreatedAt));

        List<String> resourceIds = dispatches.stream()
                .map(ResourceDispatch::getResourceId)
                .distinct()
                .collect(Collectors.toList());

        Map<String, Resource> resourceMap = resourceIds.isEmpty()
                ? Map.of()
                : resourceService.listByIds(resourceIds).stream()
                .collect(Collectors.toMap(Resource::getId, r -> r));

        return dispatches.stream()
                .map(d -> convertToVO(d, resourceMap.get(d.getResourceId())))
                .collect(Collectors.toList());
    }

    private ResourceDispatchVO convertToVO(ResourceDispatch dispatch, Resource resource) {
        return ResourceDispatchVO.builder()
                .id(dispatch.getId())
                .resourceId(dispatch.getResourceId())
                .resourceName(resource != null ? resource.getName() : null)
                .resourceType(resource != null ? resource.getType() : null)
                .planId(dispatch.getPlanId())
                .quantity(dispatch.getQuantity())
                .fromLocation(dispatch.getFromLocation())
                .toLocation(dispatch.getToLocation())
                .status(dispatch.getStatus())
                .dispatchedAt(dispatch.getDispatchedAt())
                .arrivedAt(dispatch.getArrivedAt())
                .returnedAt(dispatch.getReturnedAt())
                .operator(dispatch.getOperator())
                .source(dispatch.getSource())
                .notes(dispatch.getNotes())
                .createdAt(dispatch.getCreatedAt())
                .updatedAt(dispatch.getUpdatedAt())
                .build();
    }
}
```

- [ ] **Step 2: Verify compilation**

Run: `cd water-info-platform && ./mvnw compile -q`
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit**

```bash
git add water-info-platform/src/main/java/com/waterinfo/platform/module/resource/service/ResourceDispatchService.java
git commit -m "feat(resource): add ResourceDispatchService with status machine and inventory linkage"
```

---

### Task 7: Resource and Dispatch Controllers

**Files:**
- Create: `water-info-platform/src/main/java/com/waterinfo/platform/module/resource/controller/ResourceController.java`
- Create: `water-info-platform/src/main/java/com/waterinfo/platform/module/resource/controller/ResourceDispatchController.java`

- [ ] **Step 1: Create ResourceController**

```java
package com.waterinfo.platform.module.resource.controller;

import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.common.api.PageResponse;
import com.waterinfo.platform.module.resource.dto.CreateResourceRequest;
import com.waterinfo.platform.module.resource.dto.ResourceQueryRequest;
import com.waterinfo.platform.module.resource.dto.UpdateResourceRequest;
import com.waterinfo.platform.module.resource.service.ResourceService;
import com.waterinfo.platform.module.resource.vo.ResourceStatsVO;
import com.waterinfo.platform.module.resource.vo.ResourceVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@Tag(name = "资源管理", description = "应急资源管理接口")
@RestController
@RequestMapping("/api/v1/resources")
@RequiredArgsConstructor
public class ResourceController {

    private final ResourceService resourceService;

    @Operation(summary = "创建资源")
    @PostMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<ResourceVO> createResource(@Valid @RequestBody CreateResourceRequest request) {
        return ApiResponse.success(resourceService.createResource(request));
    }

    @Operation(summary = "资源详情")
    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<ResourceVO> getResource(@PathVariable String id) {
        return ApiResponse.success(resourceService.getResourceById(id));
    }

    @Operation(summary = "查询资源列表")
    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<PageResponse<ResourceVO>> queryResources(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) String type,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String keyword) {

        ResourceQueryRequest request = new ResourceQueryRequest();
        request.setPage(page);
        request.setSize(size);
        request.setType(type);
        request.setStatus(status);
        request.setKeyword(keyword);

        return ApiResponse.success(PageResponse.of(resourceService.queryResources(request)));
    }

    @Operation(summary = "更新资源")
    @PutMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<ResourceVO> updateResource(@PathVariable String id, @Valid @RequestBody UpdateResourceRequest request) {
        return ApiResponse.success(resourceService.updateResource(id, request));
    }

    @Operation(summary = "删除资源")
    @DeleteMapping("/{id}")
    @PreAuthorize("hasRole('ADMIN')")
    public ApiResponse<Void> deleteResource(@PathVariable String id) {
        resourceService.deleteResource(id);
        return ApiResponse.success();
    }

    @Operation(summary = "资源统计")
    @GetMapping("/stats")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<List<ResourceStatsVO>> getStats() {
        return ApiResponse.success(resourceService.getStats());
    }

    @Operation(summary = "可用资源查询（AI专用）")
    @GetMapping("/available")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<List<ResourceVO>> getAvailableResources(
            @RequestParam(required = false) String type,
            @RequestParam(required = false) String location) {
        return ApiResponse.success(resourceService.getAvailableResources(type, location));
    }
}
```

- [ ] **Step 2: Create ResourceDispatchController**

```java
package com.waterinfo.platform.module.resource.controller;

import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.common.api.PageResponse;
import com.waterinfo.platform.module.resource.dto.CreateDispatchRequest;
import com.waterinfo.platform.module.resource.dto.DispatchQueryRequest;
import com.waterinfo.platform.module.resource.dto.UpdateDispatchStatusRequest;
import com.waterinfo.platform.module.resource.service.ResourceDispatchService;
import com.waterinfo.platform.module.resource.vo.ResourceDispatchVO;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

@Tag(name = "资源调度", description = "资源调度记录接口")
@RestController
@RequestMapping("/api/v1/resource-dispatches")
@RequiredArgsConstructor
public class ResourceDispatchController {

    private final ResourceDispatchService dispatchService;

    @Operation(summary = "创建调度单")
    @PostMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<ResourceDispatchVO> createDispatch(@Valid @RequestBody CreateDispatchRequest request) {
        return ApiResponse.success(dispatchService.createDispatch(request, "MANUAL"));
    }

    @Operation(summary = "调度详情")
    @GetMapping("/{id}")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<ResourceDispatchVO> getDispatch(@PathVariable String id) {
        return ApiResponse.success(dispatchService.getDispatchById(id));
    }

    @Operation(summary = "查询调度记录")
    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<PageResponse<ResourceDispatchVO>> queryDispatches(
            @RequestParam(defaultValue = "1") Integer page,
            @RequestParam(defaultValue = "20") Integer size,
            @RequestParam(required = false) String resourceId,
            @RequestParam(required = false) String planId,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String source) {

        DispatchQueryRequest request = new DispatchQueryRequest();
        request.setPage(page);
        request.setSize(size);
        request.setResourceId(resourceId);
        request.setPlanId(planId);
        request.setStatus(status);
        request.setSource(source);

        return ApiResponse.success(PageResponse.of(dispatchService.queryDispatches(request)));
    }

    @Operation(summary = "更新调度状态")
    @PatchMapping("/{id}/status")
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<ResourceDispatchVO> updateDispatchStatus(
            @PathVariable String id,
            @Valid @RequestBody UpdateDispatchStatusRequest request) {
        return ApiResponse.success(dispatchService.updateStatus(id, request));
    }
}
```

- [ ] **Step 3: Verify compilation**

Run: `cd water-info-platform && ./mvnw compile -q`
Expected: BUILD SUCCESS

- [ ] **Step 4: Commit**

```bash
git add water-info-platform/src/main/java/com/waterinfo/platform/module/resource/controller/
git commit -m "feat(resource): add ResourceController and ResourceDispatchController"
```

---

### Task 8: Frontend TypeScript Types and Format Maps

**Files:**
- Modify: `water-info-admin/src/types/models.ts` (append resource types)
- Modify: `water-info-admin/src/utils/format.ts` (append resource maps)

- [ ] **Step 1: Add Resource types to models.ts**

Append to the end of `water-info-admin/src/types/models.ts`:

```ts
// ─── Resource ───
export type ResourceType = 'MATERIAL' | 'PERSONNEL' | 'VEHICLE'
export type ResourceStatus = 'AVAILABLE' | 'IN_USE' | 'MAINTENANCE' | 'DEPLETED'
export type DispatchStatus = 'PENDING' | 'DISPATCHED' | 'ARRIVED' | 'RETURNED' | 'CANCELLED'
export type DispatchSource = 'AI' | 'MANUAL'

export interface Resource {
  id: string
  type: ResourceType
  name: string
  quantity: number
  unit: string
  location: string
  status: ResourceStatus
  attributes: Record<string, any>
  description: string
  createdAt: string
  updatedAt: string
}

export interface CreateResourceRequest {
  type: ResourceType
  name: string
  quantity: number
  unit: string
  location: string
  attributes?: Record<string, any>
  description?: string
}

export interface UpdateResourceRequest {
  name?: string
  quantity?: number
  unit?: string
  location?: string
  status?: ResourceStatus
  attributes?: Record<string, any>
  description?: string
}

export interface ResourceQuery {
  page?: number
  size?: number
  type?: ResourceType
  status?: ResourceStatus
  keyword?: string
}

export interface ResourceStats {
  type: string
  status: string
  count: number
  totalQuantity: number
}

export interface ResourceDispatch {
  id: string
  resourceId: string
  resourceName: string
  resourceType: string
  planId: string
  quantity: number
  fromLocation: string
  toLocation: string
  status: DispatchStatus
  dispatchedAt: string | null
  arrivedAt: string | null
  returnedAt: string | null
  operator: string
  source: DispatchSource
  notes: string
  createdAt: string
  updatedAt: string
}

export interface CreateDispatchRequest {
  resourceId: string
  planId?: string
  quantity: number
  fromLocation: string
  toLocation: string
  notes?: string
}

export interface UpdateDispatchStatusRequest {
  status: DispatchStatus
  notes?: string
}

export interface DispatchQuery {
  page?: number
  size?: number
  resourceId?: string
  planId?: string
  status?: DispatchStatus
  source?: DispatchSource
}
```

- [ ] **Step 2: Add resource format maps to format.ts**

Append to the end of `water-info-admin/src/utils/format.ts`:

```ts
export const resourceTypeMap: Record<string, string> = {
  MATERIAL: '物资', PERSONNEL: '人员', VEHICLE: '车辆设备',
}
export const resourceStatusMap: Record<string, { label: string; type: string }> = {
  AVAILABLE: { label: '可用', type: 'success' },
  IN_USE: { label: '使用中', type: '' },
  MAINTENANCE: { label: '维护中', type: 'warning' },
  DEPLETED: { label: '已耗尽', type: 'danger' },
}
export const dispatchStatusMap: Record<string, { label: string; type: string }> = {
  PENDING: { label: '待调度', type: 'info' },
  DISPATCHED: { label: '已调度', type: '' },
  ARRIVED: { label: '已到达', type: 'success' },
  RETURNED: { label: '已归还', type: 'warning' },
  CANCELLED: { label: '已取消', type: 'danger' },
}
export const dispatchSourceMap: Record<string, string> = {
  AI: 'AI调度', MANUAL: '手动调度',
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd water-info-admin && npx vue-tsc --noEmit 2>&1 | tail -5`
Expected: No errors related to the new types (existing errors are OK).

- [ ] **Step 4: Commit**

```bash
git add water-info-admin/src/types/models.ts water-info-admin/src/utils/format.ts
git commit -m "feat(resource): add Resource TypeScript types and format maps"
```

---

### Task 9: Frontend API Layer and Router

**Files:**
- Create: `water-info-admin/src/api/resource.ts`
- Modify: `water-info-admin/src/router/index.ts`

- [ ] **Step 1: Create resource API file**

```ts
import { get, post, put, patch, del } from './request'
import type {
  Resource,
  CreateResourceRequest,
  UpdateResourceRequest,
  ResourceQuery,
  ResourceStats,
  ResourceDispatch,
  CreateDispatchRequest,
  UpdateDispatchStatusRequest,
  DispatchQuery,
  PageResponse,
} from '@/types'

// ─── Resource CRUD ───

export function getResources(params: ResourceQuery) {
  return get<PageResponse<Resource>>('/resources', params)
}

export function getResource(id: string) {
  return get<Resource>(`/resources/${id}`)
}

export function createResource(data: CreateResourceRequest) {
  return post<Resource>('/resources', data)
}

export function updateResource(id: string, data: UpdateResourceRequest) {
  return put<Resource>(`/resources/${id}`, data)
}

export function deleteResource(id: string) {
  return del<void>(`/resources/${id}`)
}

export function getResourceStats() {
  return get<ResourceStats[]>('/resources/stats')
}

export function getAvailableResources(params?: { type?: string; location?: string }) {
  return get<Resource[]>('/resources/available', params)
}

// ─── Dispatch CRUD ───

export function getDispatches(params: DispatchQuery) {
  return get<PageResponse<ResourceDispatch>>('/resource-dispatches', params)
}

export function getDispatch(id: string) {
  return get<ResourceDispatch>(`/resource-dispatches/${id}`)
}

export function createDispatch(data: CreateDispatchRequest) {
  return post<ResourceDispatch>('/resource-dispatches', data)
}

export function updateDispatchStatus(id: string, data: UpdateDispatchStatusRequest) {
  return patch<ResourceDispatch>(`/resource-dispatches/${id}/status`, data)
}
```

- [ ] **Step 2: Add resource routes to router**

In `water-info-admin/src/router/index.ts`, add a new route entry before the `/map` route. Insert after the `/ai` block:

```ts
  {
    path: '/resource',
    component: Layout,
    redirect: '/resource/material',
    meta: { title: '资源管理', icon: 'Box' },
    children: [
      {
        path: 'material',
        name: 'ResourceMaterial',
        component: () => import('@/views/resource/material/index.vue'),
        meta: { title: '物资管理', icon: 'Goods' },
      },
      {
        path: 'personnel',
        name: 'ResourcePersonnel',
        component: () => import('@/views/resource/personnel/index.vue'),
        meta: { title: '人员管理', icon: 'User' },
      },
      {
        path: 'vehicle',
        name: 'ResourceVehicle',
        component: () => import('@/views/resource/vehicle/index.vue'),
        meta: { title: '车辆设备', icon: 'Van' },
      },
      {
        path: 'dispatch',
        name: 'ResourceDispatch',
        component: () => import('@/views/resource/dispatch/index.vue'),
        meta: { title: '调度记录', icon: 'Promotion' },
      },
    ],
  },
```

- [ ] **Step 3: Verify no syntax errors**

Run: `cd water-info-admin && npx vue-tsc --noEmit 2>&1 | grep -i "resource" | head -5`
Expected: No errors mentioning "resource" (view files don't exist yet, but the types and API should be clean).

- [ ] **Step 4: Commit**

```bash
git add water-info-admin/src/api/resource.ts water-info-admin/src/router/index.ts
git commit -m "feat(resource): add resource API layer and router entries"
```

---

### Task 10: ResourceForm Component

**Files:**
- Create: `water-info-admin/src/views/resource/components/ResourceForm.vue`

- [ ] **Step 1: Create ResourceForm component**

```vue
<template>
  <el-dialog :model-value="visible" :title="isEdit ? '编辑资源' : '新增资源'" width="600px" @close="handleClose" destroy-on-close>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <el-form-item label="资源类型" prop="type">
        <el-select v-model="form.type" placeholder="请选择类型" style="width: 100%" :disabled="isEdit">
          <el-option v-for="(label, key) in resourceTypeMap" :key="key" :label="label" :value="key" />
        </el-select>
      </el-form-item>
      <el-form-item label="资源名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入资源名称" />
      </el-form-item>
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="数量" prop="quantity">
            <el-input-number v-model="form.quantity" :min="0" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="单位" prop="unit">
            <el-input v-model="form.unit" placeholder="个/人/辆/台" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="存放地点" prop="location">
        <el-input v-model="form.location" placeholder="请输入存放/驻扎地点" />
      </el-form-item>

      <!-- Type-specific attributes -->
      <template v-if="form.type === 'MATERIAL'">
        <el-divider content-position="left">物资信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="品牌">
              <el-input v-model="materialAttrs.brand" placeholder="品牌" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="规格">
              <el-input v-model="materialAttrs.spec" placeholder="规格型号" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="有效期">
              <el-date-picker v-model="materialAttrs.expiry_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最低库存">
              <el-input-number v-model="materialAttrs.min_stock_alert" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
      </template>

      <template v-if="form.type === 'PERSONNEL'">
        <el-divider content-position="left">人员信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="队伍人数">
              <el-input-number v-model="personnelAttrs.team_size" :min="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="负责人">
              <el-input v-model="personnelAttrs.leader" placeholder="负责人姓名" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="联系电话">
          <el-input v-model="personnelAttrs.contact" placeholder="联系电话" />
        </el-form-item>
        <el-form-item label="技能标签">
          <el-select v-model="personnelAttrs.skills" multiple filterable allow-create placeholder="输入技能标签" style="width: 100%">
            <el-option label="水上救援" value="水上救援" />
            <el-option label="急救" value="急救" />
            <el-option label="排水作业" value="排水作业" />
            <el-option label="堤防加固" value="堤防加固" />
            <el-option label="通信保障" value="通信保障" />
          </el-select>
        </el-form-item>
      </template>

      <template v-if="form.type === 'VEHICLE'">
        <el-divider content-position="left">车辆信息</el-divider>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="车牌号">
              <el-input v-model="vehicleAttrs.plate_number" placeholder="车牌号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="载重/容量">
              <el-input v-model="vehicleAttrs.capacity" placeholder="如：5吨" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="燃料类型">
          <el-select v-model="vehicleAttrs.fuel_type" placeholder="选择燃料类型" style="width: 100%" clearable>
            <el-option label="柴油" value="柴油" />
            <el-option label="汽油" value="汽油" />
            <el-option label="电动" value="电动" />
            <el-option label="混合动力" value="混合动力" />
          </el-select>
        </el-form-item>
      </template>

      <el-form-item label="备注">
        <el-input v-model="form.description" type="textarea" :rows="2" placeholder="备注说明" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { createResource, updateResource } from '@/api/resource'
import { resourceTypeMap } from '@/utils/format'
import type { Resource, ResourceType } from '@/types'

const props = defineProps<{
  visible: boolean
  data: Resource | null
}>()

const emit = defineEmits<{
  'update:visible': [val: boolean]
  success: []
}>()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const isEdit = computed(() => !!props.data?.id)

const form = reactive({
  type: '' as '' | ResourceType,
  name: '',
  quantity: 0,
  unit: '',
  location: '',
  description: '',
})

const materialAttrs = reactive({
  brand: '',
  spec: '',
  expiry_date: '',
  min_stock_alert: 0,
})

const personnelAttrs = reactive({
  team_size: 1,
  leader: '',
  contact: '',
  skills: [] as string[],
})

const vehicleAttrs = reactive({
  plate_number: '',
  capacity: '',
  fuel_type: '',
})

const rules: FormRules = {
  type: [{ required: true, message: '请选择资源类型', trigger: 'change' }],
  name: [{ required: true, message: '请输入资源名称', trigger: 'blur' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }],
  unit: [{ required: true, message: '请输入单位', trigger: 'blur' }],
  location: [{ required: true, message: '请输入存放地点', trigger: 'blur' }],
}

function getAttributes(): Record<string, any> {
  if (form.type === 'MATERIAL') {
    return { ...materialAttrs }
  }
  if (form.type === 'PERSONNEL') {
    return { ...personnelAttrs }
  }
  if (form.type === 'VEHICLE') {
    return { ...vehicleAttrs }
  }
  return {}
}

function setAttributes(attrs: Record<string, any>) {
  if (form.type === 'MATERIAL') {
    Object.assign(materialAttrs, {
      brand: attrs.brand || '',
      spec: attrs.spec || '',
      expiry_date: attrs.expiry_date || '',
      min_stock_alert: attrs.min_stock_alert || 0,
    })
  }
  if (form.type === 'PERSONNEL') {
    Object.assign(personnelAttrs, {
      team_size: attrs.team_size || 1,
      leader: attrs.leader || '',
      contact: attrs.contact || '',
      skills: attrs.skills || [],
    })
  }
  if (form.type === 'VEHICLE') {
    Object.assign(vehicleAttrs, {
      plate_number: attrs.plate_number || '',
      capacity: attrs.capacity || '',
      fuel_type: attrs.fuel_type || '',
    })
  }
}

watch(
  () => props.visible,
  (val) => {
    if (val && props.data) {
      Object.assign(form, {
        type: props.data.type,
        name: props.data.name,
        quantity: props.data.quantity,
        unit: props.data.unit,
        location: props.data.location,
        description: props.data.description || '',
      })
      setAttributes(props.data.attributes || {})
    } else if (val) {
      Object.assign(form, { type: '', name: '', quantity: 0, unit: '', location: '', description: '' })
      Object.assign(materialAttrs, { brand: '', spec: '', expiry_date: '', min_stock_alert: 0 })
      Object.assign(personnelAttrs, { team_size: 1, leader: '', contact: '', skills: [] })
      Object.assign(vehicleAttrs, { plate_number: '', capacity: '', fuel_type: '' })
    }
  },
)

function handleClose() {
  formRef.value?.resetFields()
  emit('update:visible', false)
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload = { ...form, attributes: getAttributes() }
    if (isEdit.value) {
      await updateResource(props.data!.id, payload as any)
    } else {
      await createResource(payload as any)
    }
    ElMessage.success(isEdit.value ? '编辑成功' : '新增成功')
    emit('success')
    handleClose()
  } finally {
    submitting.value = false
  }
}
</script>
```

- [ ] **Step 2: Commit**

```bash
mkdir -p water-info-admin/src/views/resource/components
git add water-info-admin/src/views/resource/components/ResourceForm.vue
git commit -m "feat(resource): add ResourceForm component with type-aware attributes"
```

---

### Task 11: DispatchForm Component

**Files:**
- Create: `water-info-admin/src/views/resource/components/DispatchForm.vue`

- [ ] **Step 1: Create DispatchForm component**

```vue
<template>
  <el-dialog :model-value="visible" title="创建调度单" width="520px" @close="handleClose" destroy-on-close>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
      <el-form-item label="选择资源" prop="resourceId">
        <el-select
          v-model="form.resourceId"
          filterable
          remote
          :remote-method="searchResources"
          :loading="searching"
          placeholder="输入资源名称搜索"
          style="width: 100%"
        >
          <el-option
            v-for="r in resourceOptions"
            :key="r.id"
            :label="`${r.name} (${r.quantity} ${r.unit} · ${r.location})`"
            :value="r.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="调度数量" prop="quantity">
        <el-input-number v-model="form.quantity" :min="1" :max="selectedResourceQty" style="width: 100%" />
      </el-form-item>
      <el-form-item label="调出地点" prop="fromLocation">
        <el-input v-model="form.fromLocation" placeholder="调出地点" />
      </el-form-item>
      <el-form-item label="调入地点" prop="toLocation">
        <el-input v-model="form.toLocation" placeholder="调入地点" />
      </el-form-item>
      <el-form-item label="关联预案">
        <el-input v-model="form.planId" placeholder="预案ID（可选）" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.notes" type="textarea" :rows="2" placeholder="备注说明" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { createDispatch, getAvailableResources } from '@/api/resource'
import type { Resource } from '@/types'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [val: boolean]
  success: []
}>()

const formRef = ref<FormInstance>()
const submitting = ref(false)
const searching = ref(false)
const resourceOptions = ref<Resource[]>([])

const form = reactive({
  resourceId: '',
  quantity: 1,
  fromLocation: '',
  toLocation: '',
  planId: '',
  notes: '',
})

const selectedResourceQty = computed(() => {
  const r = resourceOptions.value.find((r) => r.id === form.resourceId)
  return r?.quantity || 9999
})

const rules: FormRules = {
  resourceId: [{ required: true, message: '请选择资源', trigger: 'change' }],
  quantity: [{ required: true, message: '请输入调度数量', trigger: 'blur' }],
  fromLocation: [{ required: true, message: '请输入调出地点', trigger: 'blur' }],
  toLocation: [{ required: true, message: '请输入调入地点', trigger: 'blur' }],
}

async function searchResources(query: string) {
  if (!query) return
  searching.value = true
  try {
    const res = await getAvailableResources({ type: '' })
    resourceOptions.value = (res.data || []).filter((r) =>
      r.name.toLowerCase().includes(query.toLowerCase())
    )
  } finally {
    searching.value = false
  }
}

watch(
  () => props.visible,
  (val) => {
    if (val) {
      Object.assign(form, { resourceId: '', quantity: 1, fromLocation: '', toLocation: '', planId: '', notes: '' })
      resourceOptions.value = []
    }
  },
)

function handleClose() {
  formRef.value?.resetFields()
  emit('update:visible', false)
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await createDispatch(form as any)
    ElMessage.success('调度单创建成功')
    emit('success')
    handleClose()
  } finally {
    submitting.value = false
  }
}
</script>
```

- [ ] **Step 2: Commit**

```bash
git add water-info-admin/src/views/resource/components/DispatchForm.vue
git commit -m "feat(resource): add DispatchForm component"
```

---

### Task 12: Resource List Page (Material)

**Files:**
- Create: `water-info-admin/src/views/resource/material/index.vue`

- [ ] **Step 1: Create the material list page**

This page uses the `RESOURCE_TYPE` constant to filter for `MATERIAL` type. The personnel and vehicle pages follow the same pattern with different type filters.

```vue
<template>
  <div class="fm-admin-page">
    <div class="fm-page-head">
      <h1>物资管理</h1>
      <span class="sub">// emergency materials inventory</span>
      <span class="sp" />
      <span class="fm-tag fm-tag--brand">{{ total }} total</span>
      <el-button v-permission="['ADMIN', 'OPERATOR']" type="primary" :icon="Plus" @click="handleAdd">
        新增物资
      </el-button>
    </div>

    <div class="fm-summary-strip">
      <div class="fm-card fm-mini-stat">
        <div class="label">TOTAL</div>
        <div class="value">{{ total }}</div>
        <div class="hint">物资种类</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">AVAILABLE</div>
        <div class="value">{{ availableCount }}</div>
        <div class="hint">可用物资</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">QUANTITY</div>
        <div class="value">{{ totalQuantity }}</div>
        <div class="hint">总库存量</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">LOW STOCK</div>
        <div class="value">{{ lowStockCount }}</div>
        <div class="hint">库存预警</div>
      </div>
    </div>

    <div class="fm-admin-search">
      <el-form :model="queryParams" inline>
        <el-form-item label="关键词">
          <el-input v-model="queryParams.keyword" placeholder="物资名称/存放地点" clearable @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" placeholder="全部" clearable>
            <el-option v-for="(val, key) in resourceStatusMap" :key="key" :label="val.label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="fm-admin-table">
      <div class="fm-admin-table__head">
        <span class="title">物资列表</span>
        <span class="mono">{{ queryParams.page }} / {{ Math.max(1, Math.ceil(total / queryParams.size)) }} page</span>
        <span class="sp" />
        <span class="fm-tag">显示 {{ tableData.length }} 条</span>
      </div>
      <div class="fm-admin-table__body">
      <el-table v-loading="loading" :data="tableData" stripe>
        <el-table-column prop="name" label="物资名称" min-width="150" />
        <el-table-column prop="quantity" label="库存数量" width="110">
          <template #default="{ row }">
            <span :class="{ 'text-danger': isLowStock(row) }">{{ row.quantity }} {{ row.unit }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="location" label="存放地点" min-width="150" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="resourceStatusMap[row.status]?.type || 'info'" size="small">
              {{ resourceStatusMap[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="规格" width="120">
          <template #default="{ row }">{{ row.attributes?.spec || '-' }}</template>
        </el-table-column>
        <el-table-column label="品牌" width="100">
          <template #default="{ row }">{{ row.attributes?.brand || '-' }}</template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="170">
          <template #default="{ row }">{{ formatDate(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-permission="['ADMIN', 'OPERATOR']" link type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button v-permission="['ADMIN']" link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        style="margin-top: 16px; justify-content: flex-end"
        @size-change="fetchData"
        @current-change="fetchData"
      />
      </div>
    </div>

    <ResourceForm v-model:visible="formVisible" :data="currentRow" @success="fetchData" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'
import { getResources, deleteResource } from '@/api/resource'
import { formatDate, resourceStatusMap } from '@/utils/format'
import ResourceForm from '../components/ResourceForm.vue'
import type { Resource, ResourceStatus } from '@/types'

const loading = ref(false)
const tableData = ref<Resource[]>([])
const total = ref(0)
const formVisible = ref(false)
const currentRow = ref<Resource | null>(null)

const queryParams = reactive({
  page: 1,
  size: 20,
  keyword: '',
  type: 'MATERIAL' as const,
  status: '' as '' | ResourceStatus,
})

const availableCount = computed(() => tableData.value.filter((r) => r.status === 'AVAILABLE').length)
const totalQuantity = computed(() => tableData.value.reduce((sum, r) => sum + r.quantity, 0))
const lowStockCount = computed(() => tableData.value.filter(isLowStock).length)

function isLowStock(row: Resource): boolean {
  const alert = row.attributes?.min_stock_alert
  return typeof alert === 'number' && alert > 0 && row.quantity < alert
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getResources(queryParams as any)
    tableData.value = res.data?.records || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  queryParams.page = 1
  fetchData()
}

function handleReset() {
  queryParams.keyword = ''
  queryParams.status = ''
  handleSearch()
}

function handleAdd() {
  currentRow.value = null
  formVisible.value = true
}

function handleEdit(row: Resource) {
  currentRow.value = { ...row }
  formVisible.value = true
}

async function handleDelete(row: Resource) {
  await ElMessageBox.confirm(`确认删除物资「${row.name}」？`, '提示', { type: 'warning' })
  await deleteResource(row.id)
  ElMessage.success('删除成功')
  fetchData()
}

onMounted(fetchData)
</script>

<style scoped>
.text-danger {
  color: var(--el-color-danger);
  font-weight: 600;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
mkdir -p water-info-admin/src/views/resource/material
git add water-info-admin/src/views/resource/material/index.vue
git commit -m "feat(resource): add material management list page"
```

---

### Task 13: Personnel and Vehicle List Pages

**Files:**
- Create: `water-info-admin/src/views/resource/personnel/index.vue`
- Create: `water-info-admin/src/views/resource/vehicle/index.vue`

- [ ] **Step 1: Create personnel list page**

The personnel page is structurally identical to the material page, with `type: 'PERSONNEL'` and columns showing `team_size`, `leader`, `contact`, `skills` from attributes.

Create `water-info-admin/src/views/resource/personnel/index.vue`:

```vue
<template>
  <div class="fm-admin-page">
    <div class="fm-page-head">
      <h1>人员管理</h1>
      <span class="sub">// rescue teams & personnel</span>
      <span class="sp" />
      <span class="fm-tag fm-tag--brand">{{ total }} total</span>
      <el-button v-permission="['ADMIN', 'OPERATOR']" type="primary" :icon="Plus" @click="handleAdd">
        新增人员
      </el-button>
    </div>

    <div class="fm-summary-strip">
      <div class="fm-card fm-mini-stat">
        <div class="label">TEAMS</div>
        <div class="value">{{ total }}</div>
        <div class="hint">队伍/人员组</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">AVAILABLE</div>
        <div class="value">{{ availableCount }}</div>
        <div class="hint">可用队伍</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">PERSONNEL</div>
        <div class="value">{{ totalPersonnel }}</div>
        <div class="hint">总人数</div>
      </div>
    </div>

    <div class="fm-admin-search">
      <el-form :model="queryParams" inline>
        <el-form-item label="关键词">
          <el-input v-model="queryParams.keyword" placeholder="队伍名称/存放地点" clearable @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" placeholder="全部" clearable>
            <el-option v-for="(val, key) in resourceStatusMap" :key="key" :label="val.label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="fm-admin-table">
      <div class="fm-admin-table__head">
        <span class="title">人员列表</span>
        <span class="mono">{{ queryParams.page }} / {{ Math.max(1, Math.ceil(total / queryParams.size)) }} page</span>
        <span class="sp" />
        <span class="fm-tag">显示 {{ tableData.length }} 条</span>
      </div>
      <div class="fm-admin-table__body">
      <el-table v-loading="loading" :data="tableData" stripe>
        <el-table-column prop="name" label="队伍名称" min-width="150" />
        <el-table-column label="人数" width="80">
          <template #default="{ row }">{{ row.attributes?.team_size || row.quantity }}</template>
        </el-table-column>
        <el-table-column label="负责人" width="100">
          <template #default="{ row }">{{ row.attributes?.leader || '-' }}</template>
        </el-table-column>
        <el-table-column label="联系电话" width="130">
          <template #default="{ row }">{{ row.attributes?.contact || '-' }}</template>
        </el-table-column>
        <el-table-column label="技能" min-width="200">
          <template #default="{ row }">
            <el-tag v-for="skill in (row.attributes?.skills || [])" :key="skill" size="small" style="margin-right: 4px">{{ skill }}</el-tag>
            <span v-if="!row.attributes?.skills?.length">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="location" label="驻扎地点" min-width="150" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="resourceStatusMap[row.status]?.type || 'info'" size="small">
              {{ resourceStatusMap[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-permission="['ADMIN', 'OPERATOR']" link type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button v-permission="['ADMIN']" link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        style="margin-top: 16px; justify-content: flex-end"
        @size-change="fetchData"
        @current-change="fetchData"
      />
      </div>
    </div>

    <ResourceForm v-model:visible="formVisible" :data="currentRow" @success="fetchData" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'
import { getResources, deleteResource } from '@/api/resource'
import { formatDate, resourceStatusMap } from '@/utils/format'
import ResourceForm from '../components/ResourceForm.vue'
import type { Resource, ResourceStatus } from '@/types'

const loading = ref(false)
const tableData = ref<Resource[]>([])
const total = ref(0)
const formVisible = ref(false)
const currentRow = ref<Resource | null>(null)

const queryParams = reactive({
  page: 1,
  size: 20,
  keyword: '',
  type: 'PERSONNEL' as const,
  status: '' as '' | ResourceStatus,
})

const availableCount = computed(() => tableData.value.filter((r) => r.status === 'AVAILABLE').length)
const totalPersonnel = computed(() => tableData.value.reduce((sum, r) => sum + (r.attributes?.team_size || r.quantity), 0))

async function fetchData() {
  loading.value = true
  try {
    const res = await getResources(queryParams as any)
    tableData.value = res.data?.records || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

function handleSearch() { queryParams.page = 1; fetchData() }
function handleReset() { queryParams.keyword = ''; queryParams.status = ''; handleSearch() }
function handleAdd() { currentRow.value = null; formVisible.value = true }
function handleEdit(row: Resource) { currentRow.value = { ...row }; formVisible.value = true }

async function handleDelete(row: Resource) {
  await ElMessageBox.confirm(`确认删除「${row.name}」？`, '提示', { type: 'warning' })
  await deleteResource(row.id)
  ElMessage.success('删除成功')
  fetchData()
}

onMounted(fetchData)
</script>
```

- [ ] **Step 2: Create vehicle list page**

Create `water-info-admin/src/views/resource/vehicle/index.vue`:

```vue
<template>
  <div class="fm-admin-page">
    <div class="fm-page-head">
      <h1>车辆设备</h1>
      <span class="sub">// vehicles & heavy equipment</span>
      <span class="sp" />
      <span class="fm-tag fm-tag--brand">{{ total }} total</span>
      <el-button v-permission="['ADMIN', 'OPERATOR']" type="primary" :icon="Plus" @click="handleAdd">
        新增车辆
      </el-button>
    </div>

    <div class="fm-summary-strip">
      <div class="fm-card fm-mini-stat">
        <div class="label">TOTAL</div>
        <div class="value">{{ total }}</div>
        <div class="hint">车辆设备</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">AVAILABLE</div>
        <div class="value">{{ availableCount }}</div>
        <div class="hint">可用车辆</div>
      </div>
    </div>

    <div class="fm-admin-search">
      <el-form :model="queryParams" inline>
        <el-form-item label="关键词">
          <el-input v-model="queryParams.keyword" placeholder="车辆名称/车牌号/地点" clearable @keyup.enter="handleSearch" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" placeholder="全部" clearable>
            <el-option v-for="(val, key) in resourceStatusMap" :key="key" :label="val.label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="fm-admin-table">
      <div class="fm-admin-table__head">
        <span class="title">车辆列表</span>
        <span class="mono">{{ queryParams.page }} / {{ Math.max(1, Math.ceil(total / queryParams.size)) }} page</span>
        <span class="sp" />
        <span class="fm-tag">显示 {{ tableData.length }} 条</span>
      </div>
      <div class="fm-admin-table__body">
      <el-table v-loading="loading" :data="tableData" stripe>
        <el-table-column prop="name" label="车辆名称" min-width="150" />
        <el-table-column label="车牌号" width="120">
          <template #default="{ row }">{{ row.attributes?.plate_number || '-' }}</template>
        </el-table-column>
        <el-table-column label="载重/容量" width="120">
          <template #default="{ row }">{{ row.attributes?.capacity || '-' }}</template>
        </el-table-column>
        <el-table-column label="燃料类型" width="100">
          <template #default="{ row }">{{ row.attributes?.fuel_type || '-' }}</template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" width="80" />
        <el-table-column prop="location" label="停放地点" min-width="150" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="resourceStatusMap[row.status]?.type || 'info'" size="small">
              {{ resourceStatusMap[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-permission="['ADMIN', 'OPERATOR']" link type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button v-permission="['ADMIN']" link type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        style="margin-top: 16px; justify-content: flex-end"
        @size-change="fetchData"
        @current-change="fetchData"
      />
      </div>
    </div>

    <ResourceForm v-model:visible="formVisible" :data="currentRow" @success="fetchData" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'
import { getResources, deleteResource } from '@/api/resource'
import { resourceStatusMap } from '@/utils/format'
import ResourceForm from '../components/ResourceForm.vue'
import type { Resource, ResourceStatus } from '@/types'

const loading = ref(false)
const tableData = ref<Resource[]>([])
const total = ref(0)
const formVisible = ref(false)
const currentRow = ref<Resource | null>(null)

const queryParams = reactive({
  page: 1,
  size: 20,
  keyword: '',
  type: 'VEHICLE' as const,
  status: '' as '' | ResourceStatus,
})

const availableCount = computed(() => tableData.value.filter((r) => r.status === 'AVAILABLE').length)

async function fetchData() {
  loading.value = true
  try {
    const res = await getResources(queryParams as any)
    tableData.value = res.data?.records || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

function handleSearch() { queryParams.page = 1; fetchData() }
function handleReset() { queryParams.keyword = ''; queryParams.status = ''; handleSearch() }
function handleAdd() { currentRow.value = null; formVisible.value = true }
function handleEdit(row: Resource) { currentRow.value = { ...row }; formVisible.value = true }

async function handleDelete(row: Resource) {
  await ElMessageBox.confirm(`确认删除「${row.name}」？`, '提示', { type: 'warning' })
  await deleteResource(row.id)
  ElMessage.success('删除成功')
  fetchData()
}

onMounted(fetchData)
</script>
```

- [ ] **Step 3: Commit**

```bash
mkdir -p water-info-admin/src/views/resource/personnel water-info-admin/src/views/resource/vehicle
git add water-info-admin/src/views/resource/personnel/ water-info-admin/src/views/resource/vehicle/
git commit -m "feat(resource): add personnel and vehicle list pages"
```

---

### Task 14: Dispatch List Page

**Files:**
- Create: `water-info-admin/src/views/resource/dispatch/index.vue`

- [ ] **Step 1: Create dispatch list page**

```vue
<template>
  <div class="fm-admin-page">
    <div class="fm-page-head">
      <h1>调度记录</h1>
      <span class="sub">// resource dispatch tracking</span>
      <span class="sp" />
      <span class="fm-tag fm-tag--brand">{{ total }} total</span>
      <el-button v-permission="['ADMIN', 'OPERATOR']" type="primary" :icon="Plus" @click="handleAdd">
        创建调度单
      </el-button>
    </div>

    <div class="fm-summary-strip">
      <div class="fm-card fm-mini-stat">
        <div class="label">TOTAL</div>
        <div class="value">{{ total }}</div>
        <div class="hint">调度记录</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">PENDING</div>
        <div class="value">{{ pendingCount }}</div>
        <div class="hint">待调度</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">IN TRANSIT</div>
        <div class="value">{{ dispatchedCount }}</div>
        <div class="hint">运输中</div>
      </div>
      <div class="fm-card fm-mini-stat">
        <div class="label">AI SOURCE</div>
        <div class="value">{{ aiCount }}</div>
        <div class="hint">AI自动调度</div>
      </div>
    </div>

    <div class="fm-admin-search">
      <el-form :model="queryParams" inline>
        <el-form-item label="状态">
          <el-select v-model="queryParams.status" placeholder="全部" clearable>
            <el-option v-for="(val, key) in dispatchStatusMap" :key="key" :label="val.label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-select v-model="queryParams.source" placeholder="全部" clearable>
            <el-option v-for="(label, key) in dispatchSourceMap" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="预案ID">
          <el-input v-model="queryParams.planId" placeholder="预案ID" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="fm-admin-table">
      <div class="fm-admin-table__head">
        <span class="title">调度记录</span>
        <span class="mono">{{ queryParams.page }} / {{ Math.max(1, Math.ceil(total / queryParams.size)) }} page</span>
        <span class="sp" />
        <span class="fm-tag">显示 {{ tableData.length }} 条</span>
      </div>
      <div class="fm-admin-table__body">
      <el-table v-loading="loading" :data="tableData" stripe>
        <el-table-column prop="resourceName" label="资源名称" min-width="150" />
        <el-table-column prop="resourceType" label="类型" width="90">
          <template #default="{ row }">
            <el-tag size="small">{{ resourceTypeMap[row.resourceType] || row.resourceType }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="quantity" label="数量" width="80" />
        <el-table-column prop="fromLocation" label="调出地点" min-width="130" />
        <el-table-column prop="toLocation" label="调入地点" min-width="130" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="dispatchStatusMap[row.status]?.type || 'info'" size="small">
              {{ dispatchStatusMap[row.status]?.label || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="100">
          <template #default="{ row }">
            <el-tag :type="row.source === 'AI' ? 'warning' : ''" size="small">
              {{ dispatchSourceMap[row.source] || row.source }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="planId" label="关联预案" width="130">
          <template #default="{ row }">{{ row.planId || '-' }}</template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="170">
          <template #default="{ row }">{{ formatDate(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'PENDING'"
              v-permission="['ADMIN', 'OPERATOR']"
              link type="primary"
              @click="handleStatusUpdate(row, 'DISPATCHED')"
            >调度</el-button>
            <el-button
              v-if="row.status === 'DISPATCHED'"
              v-permission="['ADMIN', 'OPERATOR']"
              link type="success"
              @click="handleStatusUpdate(row, 'ARRIVED')"
            >到达</el-button>
            <el-button
              v-if="row.status === 'ARRIVED'"
              v-permission="['ADMIN', 'OPERATOR']"
              link type="warning"
              @click="handleStatusUpdate(row, 'RETURNED')"
            >归还</el-button>
            <el-button
              v-if="row.status === 'PENDING' || row.status === 'DISPATCHED'"
              v-permission="['ADMIN']"
              link type="danger"
              @click="handleStatusUpdate(row, 'CANCELLED')"
            >取消</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="queryParams.page"
        v-model:page-size="queryParams.size"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        style="margin-top: 16px; justify-content: flex-end"
        @size-change="fetchData"
        @current-change="fetchData"
      />
      </div>
    </div>

    <DispatchForm v-model:visible="formVisible" @success="fetchData" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'
import { getDispatches, updateDispatchStatus } from '@/api/resource'
import { formatDate, resourceTypeMap, dispatchStatusMap, dispatchSourceMap } from '@/utils/format'
import DispatchForm from '../components/DispatchForm.vue'
import type { ResourceDispatch, DispatchStatus, DispatchSource } from '@/types'

const loading = ref(false)
const tableData = ref<ResourceDispatch[]>([])
const total = ref(0)
const formVisible = ref(false)

const queryParams = reactive({
  page: 1,
  size: 20,
  status: '' as '' | DispatchStatus,
  source: '' as '' | DispatchSource,
  planId: '',
  resourceId: '',
})

const pendingCount = computed(() => tableData.value.filter((d) => d.status === 'PENDING').length)
const dispatchedCount = computed(() => tableData.value.filter((d) => d.status === 'DISPATCHED').length)
const aiCount = computed(() => tableData.value.filter((d) => d.source === 'AI').length)

async function fetchData() {
  loading.value = true
  try {
    const res = await getDispatches(queryParams as any)
    tableData.value = res.data?.records || []
    total.value = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

function handleSearch() { queryParams.page = 1; fetchData() }
function handleReset() { queryParams.status = ''; queryParams.source = ''; queryParams.planId = ''; handleSearch() }
function handleAdd() { formVisible.value = true }

async function handleStatusUpdate(row: ResourceDispatch, newStatus: DispatchStatus) {
  const labels: Record<string, string> = {
    DISPATCHED: '调度', ARRIVED: '确认到达', RETURNED: '归还', CANCELLED: '取消',
  }
  await ElMessageBox.confirm(`确认将调度单状态变更为「${labels[newStatus]}」？`, '提示', { type: 'warning' })
  await updateDispatchStatus(row.id, { status: newStatus })
  ElMessage.success('状态更新成功')
  fetchData()
}

onMounted(fetchData)
</script>
```

- [ ] **Step 2: Commit**

```bash
mkdir -p water-info-admin/src/views/resource/dispatch
git add water-info-admin/src/views/resource/dispatch/index.vue
git commit -m "feat(resource): add dispatch list page with status workflow"
```

---

### Task 15: AI Platform Client — Add Resource API Methods

**Files:**
- Modify: `water-info-ai/app/services/platform_client.py`

- [ ] **Step 1: Add resource methods to WaterPlatformClient**

Add these methods to the `WaterPlatformClient` class, after the existing `upsert_ai_assessment` method:

```python
    async def get_available_resources(self, resource_type: str = "", location: str = "") -> dict:
        params = {}
        if resource_type:
            params["type"] = resource_type
        if location:
            params["location"] = location
        response = await self._client.get(
            self._build_url("/resources/available"),
            headers=await self._headers(),
            params=params,
        )
        response.raise_for_status()
        return response.json()

    async def create_dispatch_order(self, payload: dict) -> dict:
        response = await self._client.post(
            self._build_url("/resource-dispatches"),
            headers=await self._headers(),
            json=payload,
        )
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 2: Verify syntax**

Run: `cd water-info-ai && python -c "from app.services.platform_client import WaterPlatformClient; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add water-info-ai/app/services/platform_client.py
git commit -m "feat(ai): add resource API methods to PlatformClient"
```

---

### Task 16: AI Resource Tools

**Files:**
- Create: `water-info-ai/app/tools/resource_tools.py`

- [ ] **Step 1: Create resource_tools.py**

```python
"""Resource management tools for the resource dispatcher agent."""

from __future__ import annotations

import json

from app.services.platform_client import get_platform_client
from app.tools.simple_tool import SimpleTool
from app.tools.trace import TracedCall


async def _query_available_resources(payload: dict) -> str:
    resource_type = str(payload.get("resource_type", ""))
    location = str(payload.get("location", ""))
    client = get_platform_client()
    result = await client.get_available_resources(
        resource_type=resource_type,
        location=location,
    )
    resources = result.get("data", [])
    return json.dumps(resources, ensure_ascii=False)


async def _create_dispatch_orders(payload: dict) -> str:
    dispatches = payload.get("dispatches", [])
    if not dispatches:
        return json.dumps({"error": "dispatches list is empty"}, ensure_ascii=False)

    client = get_platform_client()
    results = []
    for d in dispatches:
        try:
            result = await client.create_dispatch_order({
                "resourceId": d.get("resource_id", ""),
                "quantity": int(d.get("quantity", 0)),
                "fromLocation": d.get("from_location", ""),
                "toLocation": d.get("to_location", ""),
                "planId": d.get("plan_id"),
                "notes": d.get("notes"),
            })
            data = result.get("data", {})
            results.append({
                "dispatch_id": data.get("id", ""),
                "resource_id": data.get("resourceId", ""),
                "status": data.get("status", ""),
                "success": True,
            })
        except Exception as exc:
            results.append({
                "resource_id": d.get("resource_id", ""),
                "success": False,
                "error": str(exc)[:200],
            })

    return json.dumps(results, ensure_ascii=False)


query_available_resources = SimpleTool("query_available_resources", _query_available_resources)
create_dispatch_orders = SimpleTool("create_dispatch_orders", _create_dispatch_orders)

resource_tools = [
    query_available_resources,
    create_dispatch_orders,
]
```

- [ ] **Step 2: Verify syntax**

Run: `cd water-info-ai && python -c "from app.tools.resource_tools import resource_tools; print(f'{len(resource_tools)} tools loaded')"`
Expected: `2 tools loaded`

- [ ] **Step 3: Commit**

```bash
git add water-info-ai/app/tools/resource_tools.py
git commit -m "feat(ai): add resource_tools with query and dispatch tools"
```

---

### Task 17: Extend AI State — ResourceAllocation Fields

**Files:**
- Modify: `water-info-ai/app/state.py:51-58`

- [ ] **Step 1: Add resource_id and dispatch_id to ResourceAllocation**

In `water-info-ai/app/state.py`, find the `ResourceAllocation` dataclass and add two new fields:

```python
@dataclass
class ResourceAllocation:
    resource_type: str
    resource_name: str
    quantity: int
    source_location: str = ""
    target_location: str = ""
    eta_minutes: int | None = None
    status: str = "pending"
    resource_id: str | None = None
    dispatch_id: str | None = None
```

- [ ] **Step 2: Verify syntax**

Run: `cd water-info-ai && python -c "from app.state import ResourceAllocation; r = ResourceAllocation('t','n',1); print(r.resource_id, r.dispatch_id)"`
Expected: `None None`

- [ ] **Step 3: Commit**

```bash
git add water-info-ai/app/state.py
git commit -m "feat(ai): add resource_id and dispatch_id to ResourceAllocation"
```

---

### Task 18: Refactor ResourceDispatcher to Use Tools

**Files:**
- Modify: `water-info-ai/app/agents/resource_dispatcher.py`

- [ ] **Step 1: Rewrite resource_dispatcher_node to use tools**

Replace the entire content of `water-info-ai/app/agents/resource_dispatcher.py`:

```python
"""Resource dispatcher node — queries real inventory and creates dispatch orders."""

from __future__ import annotations

import json

from app.services.llm import get_llm
from app.state import ResourceAllocation, to_plain_data
from app.tools.resource_tools import query_available_resources, create_dispatch_orders
from app.tools.trace import TracedCall, make_trace
from app.utils.json_parser import extract_json


async def resource_dispatcher_node(state: dict) -> dict:
    traces: list[dict] = [
        make_trace(phase="resource_dispatch", status="started", title="开始资源调度"),
    ]

    plan = state.get("emergency_plan")
    plan_resources = list(getattr(plan, "resources", [])) if plan else []

    # Step 1: Query real available resources from the platform
    available = []
    with TracedCall(
        phase="tool_call",
        tool_name="query_available_resources",
        title="查询可用资源库存",
    ) as tc:
        result_str = await query_available_resources.ainvoke({})
        try:
            available = json.loads(result_str) if isinstance(result_str, str) else result_str
            if isinstance(available, dict):
                available = available.get("data", [])
        except (json.JSONDecodeError, TypeError):
            available = []
        tc.complete(output_summary=f"{len(available)} 项可用资源")
    traces.append(tc.trace)

    # Step 2: Build dispatch plan — deterministic baseline from plan resources matched to inventory
    resources: list[ResourceAllocation] = []
    if available:
        available_map = {r.get("id", ""): r for r in available}
        for pr in plan_resources:
            # Try to match plan resource name to available inventory
            matched = None
            for avail in available:
                if (avail.get("name", "").lower() in pr.resource_name.lower()
                        or pr.resource_name.lower() in avail.get("name", "").lower()):
                    matched = avail
                    break

            if matched and matched.get("quantity", 0) >= pr.quantity:
                resources.append(ResourceAllocation(
                    resource_type=pr.resource_type,
                    resource_name=matched.get("name", pr.resource_name),
                    quantity=min(pr.quantity, matched.get("quantity", pr.quantity)),
                    source_location=matched.get("location", pr.source_location),
                    target_location=pr.target_location,
                    eta_minutes=pr.eta_minutes,
                    resource_id=matched.get("id"),
                ))

    # Fallback: if no plan resources or no matches, use plan resources as-is
    if not resources:
        resources = plan_resources if plan_resources else [
            ResourceAllocation(
                resource_type="人员",
                resource_name="抢险队",
                quantity=12,
                source_location="市级应急仓库",
                target_location="城区河段",
                eta_minutes=30,
            )
        ]

    # Step 3: Optional LLM refinement
    llm = get_llm()
    message = f"已制定 {len(resources)} 项资源调度安排"
    if llm.is_enabled and available:
        try:
            response = await llm.ainvoke(
                json.dumps({
                    "user_query": state.get("user_query", ""),
                    "risk_assessment": to_plain_data(state.get("risk_assessment")),
                    "plan": to_plain_data(plan),
                    "available_resources": available,
                    "matched_resources": to_plain_data(resources),
                }, ensure_ascii=False, indent=2),
                system_prompt=(
                    "你是防汛资源调度智能体。根据可用资源库存和预案需求，优化调度方案。"
                    "请输出严格 JSON 数组，每项包含 resource_type, resource_name, quantity, "
                    "source_location, target_location, eta_minutes, resource_id（从可用资源中选取的ID）。"
                    "调度数量不得超过可用库存。"
                ),
                temperature=0.2,
            )
            content = getattr(response, "content", "")
            parsed = extract_json(content, expect_array=True)
            if isinstance(parsed, list) and parsed:
                refined = []
                for item in parsed:
                    if not item.get("resource_type") or not item.get("resource_name"):
                        continue
                    rid = item.get("resource_id")
                    # Validate resource_id exists in available inventory
                    if rid and rid not in {r.get("id") for r in available}:
                        rid = None
                    refined.append(ResourceAllocation(
                        resource_type=str(item.get("resource_type", "")),
                        resource_name=str(item.get("resource_name", "")),
                        quantity=int(item.get("quantity", 0)),
                        source_location=str(item.get("source_location", "")),
                        target_location=str(item.get("target_location", "")),
                        eta_minutes=int(item["eta_minutes"]) if item.get("eta_minutes") is not None else None,
                        resource_id=rid,
                    ))
                if refined:
                    resources = refined
                    message = f"已制定 {len(resources)} 项资源调度安排（LLM优化）"
        except Exception:
            pass  # Keep deterministic baseline

    # Step 4: Create dispatch orders for resources that have a resource_id
    dispatches_to_create = [
        {
            "resource_id": r.resource_id,
            "quantity": r.quantity,
            "from_location": r.source_location,
            "to_location": r.target_location,
            "plan_id": getattr(plan, "plan_id", None),
        }
        for r in resources
        if r.resource_id
    ]

    if dispatches_to_create:
        with TracedCall(
            phase="tool_call",
            tool_name="create_dispatch_orders",
            title="创建资源调度单",
        ) as tc:
            dispatch_result_str = await create_dispatch_orders.ainvoke({"dispatches": dispatches_to_create})
            try:
                dispatch_results = json.loads(dispatch_result_str) if isinstance(dispatch_result_str, str) else dispatch_result_str
                # Map dispatch IDs back to resources
                dispatch_map = {
                    d.get("resource_id"): d.get("dispatch_id")
                    for d in dispatch_results
                    if d.get("success") and d.get("dispatch_id")
                }
                for r in resources:
                    if r.resource_id and r.resource_id in dispatch_map:
                        r.dispatch_id = dispatch_map[r.resource_id]
                success_count = sum(1 for d in dispatch_results if d.get("success"))
                tc.complete(output_summary=f"{success_count}/{len(dispatches_to_create)} 调度单创建成功")
            except (json.JSONDecodeError, TypeError):
                tc.complete(output_summary="调度单结果解析失败")
        traces.append(tc.trace)

    traces.append(make_trace(
        phase="resource_dispatch", status="completed",
        title=f"资源调度完成: {len(resources)} 项",
    ))

    return {
        "resource_plan": resources,
        "current_agent": "resource_dispatcher",
        "messages": [{"role": "resource_dispatcher", "content": message}],
        "execution_traces": traces,
    }
```

- [ ] **Step 2: Verify syntax**

Run: `cd water-info-ai && python -c "from app.agents.resource_dispatcher import resource_dispatcher_node; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add water-info-ai/app/agents/resource_dispatcher.py
git commit -m "feat(ai): refactor ResourceDispatcher to query real inventory and create dispatch orders"
```

---

### Task 19: End-to-End Verification

- [ ] **Step 1: Compile backend**

Run: `cd water-info-platform && ./mvnw compile -q`
Expected: BUILD SUCCESS

- [ ] **Step 2: Lint AI service**

Run: `cd water-info-ai && uv run ruff check app/tools/resource_tools.py app/agents/resource_dispatcher.py app/state.py app/services/platform_client.py`
Expected: No errors

- [ ] **Step 3: Verify frontend types**

Run: `cd water-info-admin && npx vue-tsc --noEmit 2>&1 | grep -c "error" || echo "0 errors"`
Expected: No new errors from resource-related files

- [ ] **Step 4: Verify all files exist**

Run: `ls -la water-info-platform/src/main/java/com/waterinfo/platform/module/resource/{entity,dto,vo,mapper,service,controller}/*.java | wc -l`
Expected: 18 files (2 entity + 5 dto + 3 vo + 2 mapper + 2 service + 2 controller)

Run: `ls -la water-info-admin/src/views/resource/{material,personnel,vehicle,dispatch}/index.vue water-info-admin/src/views/resource/components/{ResourceForm,DispatchForm}.vue water-info-admin/src/api/resource.ts | wc -l`
Expected: 7 files

Run: `ls -la water-info-ai/app/tools/resource_tools.py`
Expected: File exists

- [ ] **Step 5: Final commit if any fixes were needed**

```bash
git status
# If there are uncommitted changes from fixes:
git add -A && git commit -m "fix: address verification issues in resource management module"
```
