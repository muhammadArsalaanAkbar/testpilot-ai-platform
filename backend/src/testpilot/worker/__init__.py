"""Import every domain's models module here so SQLModel.metadata is fully
populated before any worker job runs.

Unlike the API process (which transitively imports every domain via
api/main.py's routers) or alembic/env.py (which does this explicitly for
autogenerate), a worker process only imports the one job module it needs —
without this, SQLAlchemy can raise `NoReferencedTableError` resolving a
cross-domain foreign key (e.g. generation_runs.requested_by_user_id ->
users.id) that was never loaded. Every feature phase that adds a models.py
MUST add its import below, mirroring alembic/env.py's own list.
"""

from testpilot.ai_generation import models as _ai_generation_models  # noqa: F401
from testpilot.audit import models as _audit_models  # noqa: F401
from testpilot.auth import models as _auth_models  # noqa: F401
from testpilot.billing import models as _billing_models  # noqa: F401
from testpilot.core import models as _core_models  # noqa: F401
from testpilot.orgs import models as _orgs_models  # noqa: F401
from testpilot.projects import models as _projects_models  # noqa: F401
from testpilot.testcases import models as _testcases_models  # noqa: F401
