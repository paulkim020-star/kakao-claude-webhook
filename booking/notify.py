"""
리마인드 알림 스케줄러.

1분마다 발송 시각이 지난 pending 알림을 찾아 발송 처리합니다.
MVP에서는 실제 발송 채널(카카오 알림톡/SMS)이 연결되어 있지 않으므로
로그로 남기고 sent 처리만 합니다. 실제 발송은 send_notification() 한 곳만
바꾸면 됩니다 (알림톡은 사업자 심사 필요 → 기획안 2차 범위).
"""

import asyncio
import logging
import sqlite3

from booking.db import get_conn
from booking.engine import now_kst, TIME_FMT

logger = logging.getLogger("booking.notify")

_KIND_LABEL = {
    "confirm": "예약 확정 안내",
    "day_before": "전날 리마인드",
    "same_day": "당일 리마인드",
}


def send_notification(reservation: sqlite3.Row, kind: str) -> None:
    """알림 1건 발송. 알림톡/SMS 연동 시 이 함수만 교체."""
    logger.info(
        "[알림 발송] %s | %s님(%s) %s %s 예약(%s)",
        _KIND_LABEL.get(kind, kind),
        reservation["customer_name"],
        reservation["phone"],
        reservation["start_at"],
        reservation["service_name"],
        reservation["code"],
    )


def process_due_notifications(now=None) -> int:
    """발송 시각이 지난 알림을 발송하고 sent 처리. 발송 건수 반환."""
    now = now or now_kst()
    conn = get_conn()
    try:
        due = conn.execute(
            "SELECT n.id AS notification_id, n.kind, r.*, s.name AS service_name"
            " FROM notification n"
            " JOIN reservation r ON r.id = n.reservation_id"
            " JOIN service s ON s.id = r.service_id"
            " WHERE n.status = 'pending' AND n.due_at <= ?"
            "   AND r.status = 'confirmed'",
            (now.strftime(TIME_FMT),),
        ).fetchall()
        for row in due:
            send_notification(row, row["kind"])
            conn.execute(
                "UPDATE notification SET status = 'sent', sent_at = ? WHERE id = ?",
                (now.strftime(TIME_FMT), row["notification_id"]),
            )
        return len(due)
    finally:
        conn.close()


async def notification_loop() -> None:
    """앱 시작 시 백그라운드 태스크로 실행 (main.py lifespan 참고)."""
    while True:
        try:
            process_due_notifications()
        except Exception:  # noqa: BLE001
            logger.exception("알림 처리 중 오류")
        await asyncio.sleep(60)
