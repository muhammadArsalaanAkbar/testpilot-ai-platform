import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

from testpilot.ai_analysis import models as _ai_analysis_models  # noqa: F401,E402
from testpilot.ai_generation import models as _ai_generation_models  # noqa: F401,E402
from testpilot.assistant import models as _assistant_models  # noqa: F401,E402
from testpilot.audit import models as _audit_models  # noqa: F401,E402
from testpilot.auth import models as _auth_models  # noqa: F401,E402
from testpilot.billing import models as _billing_models  # noqa: F401,E402

# Import every domain's models module here so SQLModel.metadata is fully
# populated before autogenerate compares it against the database. Each
# feature phase that adds a models.py MUST add its import below.
from testpilot.core import models as _core_models  # noqa: F401,E402
from testpilot.core.config import get_settings
from testpilot.execution import artifact_models as _execution_artifact_models  # noqa: F401,E402
from testpilot.execution import models as _execution_models  # noqa: F401,E402
from testpilot.issues import models as _issues_models  # noqa: F401,E402
from testpilot.notifications import models as _notifications_models  # noqa: F401,E402
from testpilot.orgs import models as _orgs_models  # noqa: F401,E402
from testpilot.projects import models as _projects_models  # noqa: F401,E402
from testpilot.testcases import models as _testcases_models  # noqa: F401,E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

_settings = get_settings()
# Migrations need DDL/role-management privileges the least-privilege runtime
# role (database_url) deliberately does not have — see config.py.
config.set_main_option("sqlalchemy.url", _settings.migrations_database_url or _settings.database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
