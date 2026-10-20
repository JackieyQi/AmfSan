#!/usr/bin/env python3
"""One-time reset and schema migration. Run with all API/scheduler/consumers stopped."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Clear old monitor/price configurations and migrate")
    parser.add_argument("--services-stopped", action="store_true", help="Confirm API and all task workers are stopped")
    args = parser.parse_args()
    if not args.apply or not args.services_stopped:
        parser.error("Requires --apply --services-stopped. Load the target deployment's environment first.")

    from playhouse.migrate import PostgresqlMigrator, MySQLMigrator, migrate
    from exts import MysqlClient, get_database_engine
    from cache import AllCache
    from cache.order import MarketPriceLimitCache
    from models.user import UserSymbolPlotTable

    db = MysqlClient.get_database()

    table = UserSymbolPlotTable._meta.table_name
    fields = ("monitor_direction", "take_profit_price", "stop_loss_price", "config_version",
              "last_signal_ts", "last_signal_reason")
    columns = {column.name for column in db.get_columns(table)}
    existing = columns.intersection(fields)
    if existing:
        parser.error(
            "Direction fields already exist: " + ", ".join(sorted(existing))
            + ". No configurations were changed. Migration may be complete or interrupted; "
              "inspect the database and Redis manually before restarting services."
        )

    migrator_cls = PostgresqlMigrator if get_database_engine() == "postgresql" else MySQLMigrator
    migrator = migrator_cls(db)
    try:
        with db.atomic():
            # Deliberately no compatibility/default direction for old rows.
            db.execute_sql('DELETE FROM symbol_plot_table')
            for name in fields:
                field = UserSymbolPlotTable._meta.fields[name].clone()
                required = not field.null
                field.null = True
                field.default = None
                migrate(migrator.add_column(table, name, field))
                if required:
                    migrate(migrator.add_not_null(table, name))
    except Exception:
        print("Database migration failed; keep services stopped and inspect the schema manually. "
              "MySQL DDL may have partially committed.", file=sys.stderr)
        raise
    print("Old monitor configurations cleared; direction fields added.")

    try:
        client = AllCache.get_client()
        client.delete("symbol:cfg", MarketPriceLimitCache.key)
        for redis_key in client.scan_iter(match="sl_tp:*"):
            client.delete(redis_key)
    except Exception:
        print("Database migration completed, but Redis cleanup failed. Keep services stopped "
              "and finish Redis cleanup manually; rerunning this script will be refused.", file=sys.stderr)
        raise
    print("Old price alert configurations cleared. Market/indicator/signal history preserved.")


if __name__ == "__main__":
    main()
