package com.waterinfo.platform.module.alarm.dto;

import com.waterinfo.platform.module.alarm.entity.Alarm;
import lombok.Builder;
import lombok.Data;

@Data
@Builder
public class AlarmCreateResult {

    private Alarm alarm;

    private boolean created;

    private boolean updated;

    public boolean isNewOrEscalated() {
        return created;
    }
}
