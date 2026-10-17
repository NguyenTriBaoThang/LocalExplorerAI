"""Tạo User mẫu sao cho shard nào cũng có người (spec scale §9.3). Chạy lại không tạo trùng.

Trong cụm: docker compose -f docker-compose.cluster.yml exec api uv run --no-dev python -m scripts.seed_users
"""
import bcrypt

from app.db import connect, shard_of, shard_urls

PASSWORD = "travility-demo"
MAX_USERS = 10


def seed(conn) -> list[tuple[str, int, int]]:
    """Tạo demo1, demo2, … tới khi có ít nhất 2 User và đủ mặt mọi shard; trả [(email, user_id, shard)]."""
    need, out = max(len(shard_urls()), 1), []
    pw = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
    for i in range(1, MAX_USERS + 1):
        email = f"demo{i}@travility.vn"
        conn.execute("INSERT INTO users(email, password_hash) VALUES (%s, %s) ON CONFLICT (email) DO NOTHING",
                     (email, pw))
        uid = conn.execute("SELECT id FROM users WHERE email = %s", (email,)).fetchone()["id"]
        out.append((email, uid, shard_of(uid)))
        if i >= 2 and len({s for *_, s in out}) == need:
            return out
    raise SystemExit(f"Đã tạo {MAX_USERS} User mà chưa phủ đủ {need} shard")


if __name__ == "__main__":
    with connect() as conn:
        for email, uid, shard in seed(conn):
            print(f"{email}  mật khẩu {PASSWORD}  user_id {uid}  shard {shard}")
