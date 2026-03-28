"""快速测试数据库连接"""
import asyncio
from app.services.database import get_db_service


async def main():
    db = get_db_service()
    try:
        print("=== 测试 PostgreSQL 连接 ===")
        stations = await db.get_all_stations()
        print(f"监测站数量: {len(stations)}")
        for s in stations:
            print(f"  - {s['name']} ({s['code']}) [{s['status']}]")

        print("\n=== 防洪态势概览 ===")
        overview = await db.get_flood_situation_overview()
        print(f"站点数: {overview['station_count']}")
        print(f"活跃告警数: {overview['alarm_count']}")
        print(f"告警统计: {overview['alarm_statistics']}")

        for s in overview["stations"]:
            wl = s.get("water_level")
            warn = s.get("warning_level")
            danger = s.get("danger_level")
            print(f"  - {s['name']}: 水位={wl}, 警戒={warn}, 危险={danger}")

        print("\n=== 测试完成 ===")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
