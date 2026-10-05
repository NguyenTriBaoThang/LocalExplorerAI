"""Print RS256 key material for the .env file.

    python -m scripts.generate_auth_keys [--kid 2026-10] [--bits 3072]

The private key never leaves your machine; paste the output into your untracked .env (development) or your
secret manager (production). To rotate: generate a new pair, make it the active key, and keep the old
public key in AUTH_JWT_PUBLIC_KEYS_B64 until every token signed with it has expired.
"""

import argparse
import json
from datetime import datetime, timezone

from app.auth import generate_rsa_keypair


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--kid", default=datetime.now(timezone.utc).strftime("%Y-%m"), help="key id (default: current year-month)")
    parser.add_argument("--bits", type=int, default=3072, choices=(2048, 3072, 4096))
    args = parser.parse_args()
    private_b64, public_b64 = generate_rsa_keypair(args.bits)
    print(f"AUTH_JWT_KEY_ID={args.kid}")
    print(f"AUTH_JWT_PRIVATE_KEY_B64={private_b64}")
    print(f"# Public key for this id, to keep when this key is later retired:")
    print(f"# AUTH_JWT_PUBLIC_KEYS_B64={json.dumps({args.kid: public_b64})}")


if __name__ == "__main__":
    main()
