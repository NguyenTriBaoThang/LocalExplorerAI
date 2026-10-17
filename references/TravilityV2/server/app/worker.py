"""planner: nhận việc từ Redis Streams (spec scale §5, §7).

Chạy: python -m app.worker                      (điều phối: stream jobs, chạy các generator của app.trips)
      python -m app.worker --stream agent_jobs  (agent chuyên gia của lập lịch đa agent)
"""
import argparse
import json
import logging
import socket
import threading
import time

import psycopg
from redis.exceptions import RedisError, ResponseError

from app import jobs, kv, multi, nodes, trips
from app.db import SHARD_DOWN, connect, init_schemas, shard_conn, shard_urls

logger = logging.getLogger(__name__)
CLAIM_IDLE_MS = 20_000  # việc im lặng quá bấy nhiêu = worker giữ nó đã chết → worker khác nhận lại
BEAT_S = 5  # worker đang chạy việc báo "còn sống" mỗi bấy nhiêu giây
MAX_DELIVERIES = 2  # chạy lại tối đa 1 lần (spec §5.2)


def _beat(c, msg_id: str, me: str, stop: threading.Event) -> None:
    """Nhịp tim: XCLAIM JUSTID đặt lại thời gian im lặng của việc mà không tăng số lần giao."""
    while not stop.wait(BEAT_S):
        try:
            c.xclaim(jobs.STREAM, jobs.GROUP, me, 0, [msg_id], justid=True)
        except RedisError:
            pass


def ensure_group(c, stream: str = jobs.STREAM, group: str = jobs.GROUP) -> None:
    try:
        c.xgroup_create(stream, group, id="0", mkstream=True)
    except ResponseError as e:
        if "BUSYGROUP" not in str(e):
            raise


def run_job(conn, c, me: str, msg_id: str, f: dict, retry: bool = False) -> None:
    """Chạy một việc trong một transaction: worker chết giữa chừng → Postgres rollback, lần chạy lại bắt đầu sạch.

    `conn` là kết nối sẵn của worker ở chế độ một database. Có SHARD_URLS thì mỗi việc tự mở kết nối tới shard
    của User (conn có thể là None); shard chết → event error, không thử lại (spec scale S29).
    Event cuối chỉ phát sau khi commit, để client không bao giờ thấy Itinerary chưa được lưu.
    """
    job_id = f["job_id"]

    def fail(message: str) -> None:
        jobs.publish(job_id, trips.sse({"type": "error", "message": message}))
        jobs.finish(job_id)
        c.xack(jobs.STREAM, jobs.GROUP, msg_id)

    if c.exists(f"job:{job_id}:done"):  # đã xong ở lần giao trước, event cuối và end đã ghi cùng lúc với cờ done
        c.xack(jobs.STREAM, jobs.GROUP, msg_id)
        return
    if retry:
        delivered = c.xpending_range(jobs.STREAM, jobs.GROUP, msg_id, msg_id, 1)[0]["times_delivered"]
        if delivered > MAX_DELIVERIES:
            return fail("Có lỗi khi lập lịch trình, bạn thử lại nhé.")
        jobs.publish(job_id, trips.sse({"type": "thinking", "text": "Đang thử lại…"}))
    elif time.time() * 1000 - int(msg_id.split("-")[0]) > jobs.QUIET_S * 1000:
        # Xếp hàng lâu hơn thời gian api chờ: client đã nhận lỗi và có thể đã gửi lại → không chạy việc cũ.
        return fail("Hệ thống lập lịch đang bận hoặc chưa chạy, bạn thử lại sau nhé.")
    own = None
    if shard_urls():
        try:
            own = shard_conn(int(f["user_id"]))
        except psycopg.OperationalError:
            return fail(SHARD_DOWN)
    job_conn = own or conn
    stop = threading.Event()
    threading.Thread(target=_beat, args=(c, msg_id, me, stop), daemon=True).start()
    try:
        held = None
        with job_conn.transaction():
            for ev in trips.guarded(trips.JOBS[f["kind"]](job_conn, int(f["user_id"]), **json.loads(f["params"]))):
                if held is not None:
                    jobs.publish(job_id, held)
                held = ev
        jobs.complete(job_id, held)
        c.xack(jobs.STREAM, jobs.GROUP, msg_id)
        logger.info("xong việc %s (%s)", job_id, f["kind"])
    finally:
        stop.set()
        if own is not None:
            own.close()


def step(conn, c, me: str) -> bool:
    """Nhận và chạy tối đa một việc; True nếu có việc. Việc bị worker chết bỏ dở được ưu tiên trước.

    ponytail: một việc một lúc mỗi tiến trình; cần chạy song song nhiều hơn thì tăng số bản planner.
    """
    claimed = c.xautoclaim(jobs.STREAM, jobs.GROUP, me, CLAIM_IDLE_MS, count=1)[1]
    if claimed:
        run_job(conn, c, me, *claimed[0], retry=True)
        return True
    got = c.xreadgroup(jobs.GROUP, me, {jobs.STREAM: ">"}, count=1, block=500)
    if not got:
        return False
    run_job(conn, c, me, *got[0][1][0])
    return True


def agent_step(c, me: str) -> bool:
    """Vai agent: nhận và chạy tối đa một việc từ agent_jobs; True nếu có việc.

    Giao nhiều nhất một lần: XACK dù lỗi, không nhận lại. Thiếu kết quả thì điều phối tự quay về agent đơn (spec §7).
    """
    got = c.xreadgroup(multi.AGENT_GROUP, me, {multi.AGENT_STREAM: ">"}, count=1, block=500)
    if not got:
        return False
    msg_id, f = got[0][1][0]
    try:
        # Xếp hàng lâu hơn thời gian điều phối chờ: nó đã chuyển sang agent đơn → không tốn quota LLM nữa.
        if time.time() * 1000 - int(msg_id.split("-")[0]) <= multi.AGENT_WAIT_S * 1000:
            multi.serve(c, f)
            logger.info("agent %s xong việc %s", f["role"], f["key"])
    finally:
        c.xack(multi.AGENT_STREAM, multi.AGENT_GROUP, msg_id)
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("--stream", choices=[jobs.STREAM, multi.AGENT_STREAM], default=jobs.STREAM)
    agent = ap.parse_args().stream == multi.AGENT_STREAM
    c, me = kv.client(), socket.gethostname()
    if c is None:
        raise SystemExit("planner cần REDIS_URL")
    init_schemas()
    nodes.start("planner-agent" if agent else "planner")
    logger.info("planner %s sẵn sàng (%s)", me, "agent" if agent else "điều phối")
    conn = None
    while True:
        try:
            if agent:  # mỗi việc tự mở kết nối đọc bảng places (multi.agent_conn)
                ensure_group(c, multi.AGENT_STREAM, multi.AGENT_GROUP)
                agent_step(c, me)
                continue
            ensure_group(c)  # mỗi vòng: `redis-cli flushdb` trong runbook xoá luôn consumer group
            if conn is None and not shard_urls():  # có shard thì mỗi việc tự mở kết nối (run_job)
                conn = connect()
            step(conn, c, me)
        except Exception:
            logger.exception("planner lỗi, thử lại sau 1 giây")
            if conn is not None:
                conn.close()
            conn = None
            time.sleep(1)


if __name__ == "__main__":
    main()
