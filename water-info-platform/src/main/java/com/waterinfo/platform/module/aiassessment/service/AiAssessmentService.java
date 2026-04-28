package com.waterinfo.platform.module.aiassessment.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.waterinfo.platform.config.AiAssessmentWebSocketHandler;
import com.waterinfo.platform.module.aiassessment.dto.UpsertAiAssessmentRequest;
import com.waterinfo.platform.module.aiassessment.entity.AiAssessment;
import com.waterinfo.platform.module.aiassessment.mapper.AiAssessmentMapper;
import com.waterinfo.platform.module.aiassessment.vo.AiAssessmentVO;
import com.waterinfo.platform.module.station.entity.Station;
import com.waterinfo.platform.module.station.mapper.StationMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class AiAssessmentService extends ServiceImpl<AiAssessmentMapper, AiAssessment> {

    private final StationMapper stationMapper;
    private final AiAssessmentWebSocketHandler webSocketHandler;

    @Transactional
    public AiAssessmentVO upsert(UpsertAiAssessmentRequest request) {
        LocalDateTime assessedAt = request.getAssessedAt() != null ? request.getAssessedAt() : LocalDateTime.now();
        LocalDateTime minute = assessedAt.truncatedTo(ChronoUnit.MINUTES);
        AiAssessment assessment = AiAssessment.builder()
                .id(UUID.randomUUID().toString())
                .stationId(request.getStationId())
                .metricType(request.getMetricType())
                .level(normalize(request.getLevel()))
                .summary(request.getSummary())
                .planExcerpt(request.getPlanExcerpt())
                .source(normalize(request.getSource()))
                .assessedAt(assessedAt)
                .assessedAtMinute(minute)
                .build();

        baseMapper.upsert(assessment);
        AiAssessment saved = getOne(new LambdaQueryWrapper<AiAssessment>()
                .eq(AiAssessment::getStationId, assessment.getStationId())
                .eq(AiAssessment::getSource, assessment.getSource())
                .eq(AiAssessment::getAssessedAtMinute, assessment.getAssessedAtMinute()));
        AiAssessmentVO vo = toVO(saved != null ? saved : assessment);
        webSocketHandler.broadcastAssessment(Map.of(
                "id", vo.getId(),
                "stationId", vo.getStationId(),
                "stationName", vo.getStationName() != null ? vo.getStationName() : "",
                "metricType", vo.getMetricType() != null ? vo.getMetricType() : "",
                "level", vo.getLevel(),
                "summary", vo.getSummary(),
                "planExcerpt", vo.getPlanExcerpt() != null ? vo.getPlanExcerpt() : "",
                "source", vo.getSource(),
                "assessedAt", vo.getAssessedAt() != null ? vo.getAssessedAt().toString() : ""
        ));
        return vo;
    }

    public List<AiAssessmentVO> listRecent(String stationId, LocalDateTime since, int limit) {
        LambdaQueryWrapper<AiAssessment> wrapper = new LambdaQueryWrapper<>();
        if (StringUtils.hasText(stationId)) {
            wrapper.eq(AiAssessment::getStationId, stationId);
        }
        if (since != null) {
            wrapper.ge(AiAssessment::getAssessedAt, since);
        }
        wrapper.orderByDesc(AiAssessment::getAssessedAt).last("LIMIT " + Math.max(1, Math.min(limit, 100)));
        return list(wrapper).stream().map(this::toVO).toList();
    }

    private AiAssessmentVO toVO(AiAssessment assessment) {
        Station station = stationMapper.selectById(assessment.getStationId());
        return AiAssessmentVO.builder()
                .id(assessment.getId())
                .stationId(assessment.getStationId())
                .stationName(station != null ? station.getName() : null)
                .metricType(assessment.getMetricType())
                .level(assessment.getLevel())
                .summary(assessment.getSummary())
                .planExcerpt(assessment.getPlanExcerpt())
                .source(assessment.getSource())
                .assessedAt(assessment.getAssessedAt())
                .createdAt(assessment.getCreatedAt())
                .build();
    }

    private String normalize(String value) {
        return value == null ? "" : value.trim().toUpperCase();
    }
}
