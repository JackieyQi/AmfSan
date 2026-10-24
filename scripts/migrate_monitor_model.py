#!/usr/bin/env python3
"""Add monitor model selection without deleting or converting existing records."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--services-stopped', action='store_true')
    args = parser.parse_args()
    if not args.apply or not args.services_stopped:
        parser.error('Requires --apply --services-stopped; load the target environment first.')

    from playhouse.migrate import MySQLMigrator, PostgresqlMigrator, migrate
    from exts import MysqlClient, get_database_engine
    from models.user import UserSymbolPlotTable

    db = MysqlClient.get_database()
    table = UserSymbolPlotTable._meta.table_name
    name = 'strategy_model_key'
    if name in {column.name for column in db.get_columns(table)}:
        print('Model column already exists; no changes made.')
        return
    migrator_cls = PostgresqlMigrator if get_database_engine() == 'postgresql' else MySQLMigrator
    migrate(migrator_cls(db).add_column(table, name, UserSymbolPlotTable._meta.fields[name].clone()))
    print('Model column added. Existing rows remain unbound and do not send alerts; delete them in the UI.')


if __name__ == '__main__':
    main()
