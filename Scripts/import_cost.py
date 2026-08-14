import argparse
import os
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv


REQUIRED_ENV_VARS = (
    "EFA_EXCEL_FILE",
    "EFA_DB_HOST",
    "EFA_DB_PORT",
    "EFA_DB_NAME",
    "EFA_DB_USER",
    "EFA_DB_PASSWORD",
)
REQUIRED_COLUMNS = ("номер", "закупочная цена")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTICLE_TO_OFFER_ID = {
    "001Б": "УФ 001Б",
    "002Б": "УФ 002Б",
    "003Б": "УФ 003Б",
    "004Б": "УФ 004Б",
    "005Б": "УФ 005Б",
}
KNOWN_OFFER_IDS = frozenset(ARTICLE_TO_OFFER_ID.values())


class ConfigurationError(RuntimeError):
    """Raised when the local import configuration is invalid."""


class InputDataError(RuntimeError):
    """Raised when the source Excel file does not meet the import format."""


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import EFA product cost prices from Excel.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the import and check product matches without changing the database.",
    )
    return parser.parse_args()


def load_local_environment() -> None:
    """Load an optional project-local .env without overriding system variables."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigurationError(
            f"Required environment variable {name} is not set. "
            "Set it in .env or in the system environment."
        )
    return value


def get_database_port() -> int:
    raw_port = get_required_env("EFA_DB_PORT")
    try:
        return int(raw_port)
    except ValueError as error:
        raise ConfigurationError(
            f"EFA_DB_PORT must be an integer; received {raw_port!r}."
        ) from error


def get_configuration() -> dict[str, str | int]:
    load_local_environment()
    values = {name: get_required_env(name) for name in REQUIRED_ENV_VARS}
    values["EFA_DB_PORT"] = get_database_port()
    return values


def load_source_data(excel_file: str) -> pd.DataFrame:
    source_path = Path(excel_file)
    if not source_path.is_file():
        raise InputDataError(
            f"Excel file was not found: {source_path}. "
            "Check EFA_EXCEL_FILE in .env or the system environment."
        )

    dataframe = pd.read_excel(source_path)
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in dataframe.columns]
    if missing_columns:
        columns = ", ".join(missing_columns)
        raise InputDataError(f"Excel file is missing required column(s): {columns}.")
    return dataframe


def normalize_offer_id(source_number: str) -> str | None:
    """Map only explicitly approved Excel article numbers to OZON offer IDs."""
    if source_number in KNOWN_OFFER_IDS:
        return source_number
    return ARTICLE_TO_OFFER_ID.get(source_number)


def prepare_updates(
    dataframe: pd.DataFrame,
) -> tuple[list[tuple[str, str, float]], list[tuple[int, str, str]]]:
    updates = []
    errors = []

    for excel_row, (_, row) in enumerate(dataframe.iterrows(), start=2):
        raw_source_number = row["номер"]
        source_number = "" if pd.isna(raw_source_number) else str(raw_source_number).strip()
        if not source_number:
            errors.append((excel_row, "", "номер товара пустой"))
            continue

        offer_id = normalize_offer_id(source_number)
        if offer_id is None:
            errors.append((excel_row, source_number, "Не удалось определить формат артикула"))
            continue

        raw_cost_price = row["закупочная цена"]
        if pd.isna(raw_cost_price):
            errors.append((excel_row, offer_id, "закупочная цена пустая"))
            continue
        try:
            cost_price = float(raw_cost_price)
        except (TypeError, ValueError):
            errors.append(
                (
                    excel_row,
                    offer_id,
                    f"закупочная цена {raw_cost_price!r} не преобразуется в число",
                )
            )
            continue
        if pd.isna(cost_price):
            errors.append((excel_row, offer_id, "закупочная цена не является числом"))
            continue
        updates.append((source_number, offer_id, cost_price))

    return updates, errors


def connect_to_database(configuration: dict[str, str | int]):
    return psycopg2.connect(
        host=configuration["EFA_DB_HOST"],
        port=configuration["EFA_DB_PORT"],
        dbname=configuration["EFA_DB_NAME"],
        user=configuration["EFA_DB_USER"],
        password=configuration["EFA_DB_PASSWORD"],
    )


def find_missing_offer_ids(connection, updates: list[tuple[str, str, float]]) -> list[str]:
    not_found = []
    with connection.cursor() as cursor:
        for _, offer_id, _ in updates:
            cursor.execute(
                "SELECT 1 FROM products WHERE offer_id = %s",
                (offer_id,),
            )
            if cursor.fetchone() is None:
                not_found.append(offer_id)
    return not_found


def import_costs(connection, updates: list[tuple[str, str, float]]) -> tuple[int, list[str]]:
    updated = 0
    not_found = []

    with connection.cursor() as cursor:
        for _, offer_id, cost_price in updates:
            cursor.execute(
                """
                UPDATE products
                SET cost_price = %s
                WHERE offer_id = %s
                """,
                (cost_price, offer_id),
            )
            if cursor.rowcount:
                updated += cursor.rowcount
            else:
                not_found.append(offer_id)

    return updated, not_found


def print_dry_run_result(
    total_rows: int,
    updates: list[tuple[str, str, float]],
    not_found: list[str],
    errors: list[tuple[int, str, str]],
) -> None:
    print("[RESULT]")
    print("Импорт себестоимости (dry-run)")
    print()
    print(f"Всего строк в Excel: {total_rows}")
    print(f"Корректных записей: {len(updates)}")
    print(f"Будет обновлено товаров: {len(updates) - len(not_found)}")
    print(f"Не найдено в products: {len(not_found)}")

    if updates:
        print("Нормализация идентификаторов:")
        for source_number, offer_id, _ in updates:
            print(f"Исходный номер: {source_number}")
            print(f"Нормализованный offer_id: {offer_id}")

    if not_found:
        print("Список ненайденных offer_id:")
        for offer_id in not_found:
            print(f"- {offer_id}")

    if errors:
        print("Ошибки данных:")
        for excel_row, offer_id, reason in errors:
            offer_id_label = offer_id or "не указан"
            print(f"- строка Excel {excel_row}; offer_id: {offer_id_label}; причина: {reason}")


def run_dry_run(
    configuration: dict[str, str | int],
    dataframe: pd.DataFrame,
    updates: list[tuple[str, str, float]],
    errors: list[tuple[int, str, str]],
) -> None:
    print("[DATABASE]")
    print("Подключение к PostgreSQL")
    connection = None
    try:
        connection = connect_to_database(configuration)
        not_found = find_missing_offer_ids(connection, updates)
        print_dry_run_result(len(dataframe), updates, not_found, errors)
    except psycopg2.Error as error:
        raise RuntimeError(
            "Не удалось выполнить dry-run: PostgreSQL недоступен или таблица products "
            f"недоступна. Причина: {error}"
        ) from error
    finally:
        if connection is not None:
            connection.close()


def run_import(
    configuration: dict[str, str | int],
    updates: list[tuple[str, str, float]],
    errors: list[tuple[int, str, str]],
) -> None:
    if errors:
        details = "; ".join(
            f"строка {excel_row}, offer_id {offer_id or 'не указан'}: {reason}"
            for excel_row, offer_id, reason in errors
        )
        raise InputDataError(f"Импорт отменён из-за ошибок данных: {details}")

    print("[DATABASE]")
    print("Подключение к PostgreSQL")
    connection = None
    try:
        connection = connect_to_database(configuration)
        print("[IMPORT]")
        print("Обновление данных")
        updated, not_found = import_costs(connection, updates)
        connection.commit()
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        if connection is not None:
            connection.close()

    print("[RESULT]")
    print(f"Обновлено товаров: {updated}")
    if not_found:
        print("Не найдены по offer_id:")
        for offer_id in not_found:
            print(f"- {offer_id}")


def main() -> None:
    arguments = parse_arguments()
    print("[CONFIG]")
    print("Проверка конфигурации")
    configuration = get_configuration()

    print("[EXCEL]")
    print("Проверка файла и данных")
    dataframe = load_source_data(str(configuration["EFA_EXCEL_FILE"]))
    updates, errors = prepare_updates(dataframe)

    if arguments.dry_run:
        run_dry_run(configuration, dataframe, updates, errors)
    else:
        run_import(configuration, updates, errors)


if __name__ == "__main__":
    try:
        main()
    except (ConfigurationError, InputDataError, RuntimeError) as error:
        print(f"[RESULT]\nИмпорт не выполнен: {error}")
        raise SystemExit(1)
    except psycopg2.Error as error:
        print(f"[RESULT]\nОшибка PostgreSQL: {error}")
        raise SystemExit(1)
