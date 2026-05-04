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
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class ResourceService extends ServiceImpl<ResourceMapper, Resource> {

    private static final Set<String> SUPPORTED_TYPES = Set.of("MATERIAL", "PERSONNEL", "VEHICLE");
    private static final Set<String> SUPPORTED_STATUSES = Set.of("AVAILABLE", "IN_USE", "MAINTENANCE", "DEPLETED");

    private final AuditLogService auditLogService;

    @Transactional
    public ResourceVO createResource(CreateResourceRequest request) {
        Resource resource = Resource.builder()
                .type(normalizeType(request.getType()))
                .name(request.getName())
                .quantity(request.getQuantity())
                .unit(request.getUnit())
                .location(request.getLocation())
                .status(request.getQuantity() == 0 ? "DEPLETED" : "AVAILABLE")
                .attributes(request.getAttributes() == null ? Map.of() : request.getAttributes())
                .description(request.getDescription())
                .deleted(false)
                .build();

        save(resource);

        auditLogService.logAsync("RESOURCE_CREATE", "RESOURCE", resource.getId(),
                Map.of("name", resource.getName(), "type", resource.getType()));

        return convertToVO(resource);
    }

    @Transactional
    public ResourceVO updateResource(String id, UpdateResourceRequest request) {
        Resource resource = requireResource(id);

        if (StringUtils.hasText(request.getName())) {
            resource.setName(request.getName());
        }
        if (request.getQuantity() != null) {
            if (request.getQuantity() < 0) {
                throw new BusinessException(ErrorCode.PARAM_INVALID, "Resource quantity cannot be negative");
            }
            resource.setQuantity(request.getQuantity());
        }
        if (StringUtils.hasText(request.getUnit())) {
            resource.setUnit(request.getUnit());
        }
        if (StringUtils.hasText(request.getLocation())) {
            resource.setLocation(request.getLocation());
        }
        if (StringUtils.hasText(request.getStatus())) {
            resource.setStatus(normalizeStatus(request.getStatus()));
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
        return convertToVO(requireResource(id));
    }

    public Page<ResourceVO> queryResources(ResourceQueryRequest request) {
        Page<Resource> page = new Page<>(request.getPage(), request.getSize());
        LambdaQueryWrapper<Resource> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(request.getType())) {
            wrapper.eq(Resource::getType, normalizeType(request.getType()));
        }
        if (StringUtils.hasText(request.getStatus())) {
            wrapper.eq(Resource::getStatus, normalizeStatus(request.getStatus()));
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
            wrapper.eq(Resource::getType, normalizeType(type));
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
                .values().stream()
                .collect(Collectors.toList());
    }

    @Transactional
    public void adjustQuantity(String id, int delta) {
        Resource resource = requireResource(id);
        int newQuantity = resource.getQuantity() + delta;
        if (newQuantity < 0) {
            throw new BusinessException(ErrorCode.RESOURCE_INSUFFICIENT_STOCK);
        }
        resource.setQuantity(newQuantity);
        if (newQuantity == 0 && "AVAILABLE".equals(resource.getStatus())) {
            resource.setStatus("DEPLETED");
        } else if (newQuantity > 0 && "DEPLETED".equals(resource.getStatus())) {
            resource.setStatus("AVAILABLE");
        }
        updateById(resource);
    }

    @Transactional
    public void deleteResource(String id) {
        Resource resource = requireResource(id);
        removeById(id);
        auditLogService.logAsync("RESOURCE_DELETE", "RESOURCE", id,
                Map.of("name", resource.getName()));
    }

    private Resource requireResource(String id) {
        Resource resource = getById(id);
        if (resource == null) {
            throw new BusinessException(ErrorCode.RESOURCE_NOT_FOUND);
        }
        return resource;
    }

    private String normalizeType(String rawType) {
        String normalized = normalizeRequired(rawType, "Resource type is required");
        if (!SUPPORTED_TYPES.contains(normalized)) {
            throw new BusinessException(ErrorCode.PARAM_INVALID, "Invalid resource type: " + rawType);
        }
        return normalized;
    }

    private String normalizeStatus(String rawStatus) {
        String normalized = normalizeRequired(rawStatus, "Resource status is required");
        if (!SUPPORTED_STATUSES.contains(normalized)) {
            throw new BusinessException(ErrorCode.PARAM_INVALID, "Invalid resource status: " + rawStatus);
        }
        return normalized;
    }

    private String normalizeRequired(String value, String missingMessage) {
        if (!StringUtils.hasText(value)) {
            throw new BusinessException(ErrorCode.PARAM_INVALID, missingMessage);
        }
        return value.trim().toUpperCase(Locale.ROOT);
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
