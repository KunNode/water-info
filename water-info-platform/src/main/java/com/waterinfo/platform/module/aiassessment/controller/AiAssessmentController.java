package com.waterinfo.platform.module.aiassessment.controller;

import com.waterinfo.platform.common.api.ApiResponse;
import com.waterinfo.platform.module.aiassessment.dto.UpsertAiAssessmentRequest;
import com.waterinfo.platform.module.aiassessment.service.AiAssessmentService;
import com.waterinfo.platform.module.aiassessment.vo.AiAssessmentVO;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.List;

@RestController
@RequestMapping("/api/v1/ai-assessments")
@RequiredArgsConstructor
public class AiAssessmentController {

    private final AiAssessmentService aiAssessmentService;

    @GetMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR', 'VIEWER')")
    public ApiResponse<List<AiAssessmentVO>> list(
            @RequestParam(required = false) String stationId,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime since,
            @RequestParam(defaultValue = "20") Integer limit) {
        return ApiResponse.success(aiAssessmentService.listRecent(stationId, since, limit));
    }

    @PostMapping
    @PreAuthorize("hasAnyRole('ADMIN', 'OPERATOR')")
    public ApiResponse<AiAssessmentVO> upsert(@Valid @RequestBody UpsertAiAssessmentRequest request) {
        return ApiResponse.success(aiAssessmentService.upsert(request));
    }
}
