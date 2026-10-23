#!/usr/bin/env python3
"""Create only the custom strategy table. Existing data is not modified."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    if not parser.parse_args().apply:
        parser.error("Load the deployment environment, then supply --apply")
    from exts import MysqlClient
    from models.user import UserStrategyTable
    database = MysqlClient.get_database()
    with database:
        with database.bind_ctx([UserStrategyTable]):
            database.create_tables([UserStrategyTable], safe=True)
    print("Custom strategy table ready.")


if __name__ == "__main__":
    main()
