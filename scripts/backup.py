"""Create and verify a PostgreSQL custom archive without overwriting existing files.

Usage: python -m scripts.backup backups/banking.dump [--bin-dir PATH]
The encryption key must be backed up separately in your secret store.
"""
import argparse
import os
from pathlib import Path
import subprocess
from sqlalchemy.engine import make_url
from app.core.config import settings


def backup(destination: Path, bin_dir: Path | None = None):
    url = make_url(settings.DATABASE_URL)
    if not url.drivername.startswith("postgresql"):
        raise ValueError("Backups require PostgreSQL")
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    suffix = ".exe" if os.name == "nt" else ""
    def executable(name):
        return str(bin_dir / (name + suffix)) if bin_dir else name
    env = {**os.environ, "PGHOST": url.host or "localhost", "PGPORT": str(url.port or 5432),
           "PGUSER": url.username or "", "PGPASSWORD": url.password or "", "PGDATABASE": url.database or ""}
    for name in ("sslmode", "sslrootcert", "sslcert", "sslkey"):
        if name in url.query:
            env["PG" + name.upper()] = str(url.query[name])
    hidden = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    # Exclusive creation prevents accidental overwrite, including concurrent runs.
    with destination.open("xb") as output:
        subprocess.run([executable("pg_dump"), "--format=custom", "--no-password"],
                       stdout=output, env=env, creationflags=hidden, check=True)
    subprocess.run([executable("pg_restore"), "--list", str(destination)],
                   stdout=subprocess.DEVNULL, env=env, creationflags=hidden, check=True)
    print(f"Verified archive: {destination}")
    print("Store ENCRYPTION_KEY separately; this archive cannot decrypt KYC files without it.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--bin-dir", type=Path)
    args = parser.parse_args()
    backup(args.destination, args.bin_dir)
