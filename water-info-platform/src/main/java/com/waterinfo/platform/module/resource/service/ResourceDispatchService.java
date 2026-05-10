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
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class ResourceDispatchService extends ServiceImpl<ResourceDispatchMapper, ResourceDispatch> {

    private static final Set<String> VALID_TRANSITIONS = Set.of(
            "PENDING->DISPATCHED",
            "DISPATCHED->ARRIVED",
            "ARRIVED->RETURNED",
            "PENDING->CANCELLED",
            "DISPATCHED->CANCELLED"
    );
    private static final Set<String> RESTORE_STOCK_FROM_STATUSES = Set.of("PENDING", "DISPATCHED");

    @Lazy
    private final ResourceService resourceService;
    private final AuditLogService auditLogService;

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

        resourceService.adjustQuantity(resource.getId(), -request.getQuantity());

        ResourceDispatch dispatch = ResourceDispatch.builder()
                .resourceId(request.getResourceId())
                .planId(request.getPlanId())
                .quantity(request.getQuantity())
                .fromLocation(request.getFromLocation())
                .toLocation(request.getToLocation())
                .status("PENDING")
                .source(normalizeSource(source))
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

        String previousStatus = dispatch.getStatus();
        String nextStatus = normalizeStatus(request.getStatus());
        String transition = previousStatus + "->" + nextStatus;
        if (!VALID_TRANSITIONS.contains(transition)) {
            throw new BusinessException(ErrorCode.DISPATCH_INVALID_STATUS_TRANSITION,
                    "不允许从 " + previousStatus + " 变更为 " + nextStatus);
        }

        LocalDateTime now = LocalDateTime.now();
        dispatch.setStatus(nextStatus);

        switch (nextStatus) {
            case "DISPATCHED" -> dispatch.setDispatchedAt(now);
            case "ARRIVED" -> dispatch.setArrivedAt(now);
            case "RETURNED" -> {
                dispatch.setReturnedAt(now);
                resourceService.adjustQuantity(dispatch.getResourceId(), dispatch.getQuantity());
            }
            case "CANCELLED" -> {
                if (RESTORE_STOCK_FROM_STATUSES.contains(previousStatus)) {
                    resourceService.adjustQuantity(dispatch.getResourceId(), dispatch.getQuantity());
                }
            }
            default -> {
            }
        }

        if (StringUtils.hasText(request.getNotes())) {
            dispatch.setNotes(request.getNotes());
        }

        updateById(dispatch);

        auditLogService.logAsync("DISPATCH_STATUS_UPDATE", "RESOURCE_DISPATCH", dispatch.getId(),
                Map.of("status", nextStatus));

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
            wrapper.eq(ResourceDispatch::getStatus, normalizeStatus(request.getStatus()));
        }
        if (StringUtils.hasText(request.getSource())) {
            wrapper.eq(ResourceDispatch::getSource, normalizeSource(request.getSource()));
        }

        wrapper.orderByDesc(ResourceDispatch::getCreatedAt);
        Page<ResourceDispatch> result = page(page, wrapper);

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

    private String normalizeStatus(String rawStatus) {
        if (!StringUtils.hasText(rawStatus)) {
            throw new BusinessException(ErrorCode.PARAM_INVALID, "Dispatch status is required");
        }
        return rawStatus.trim().toUpperCase(Locale.ROOT);
    }

    private String normalizeSource(String rawSource) {
        if (!StringUtils.hasText(rawSource)) {
            return "MANUAL";
        }
        String source = rawSource.trim().toUpperCase(Locale.ROOT);
        if (!Set.of("AI", "MANUAL").contains(source)) {
            throw new BusinessException(ErrorCode.PARAM_INVALID, "Invalid dispatch source: " + rawSource);
        }
        return source;
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
