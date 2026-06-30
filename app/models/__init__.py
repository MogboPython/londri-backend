# Import all models here so that SQLAlchemy's mapper registry and
# Alembic's autogenerate can discover every table.

from app.infrastructure.database.models.business import Business  # noqa: F401
from app.infrastructure.database.models.catalog import PriceListItem, SubscriptionPlan  # noqa: F401
from app.infrastructure.database.models.messaging import MessageLog  # noqa: F401
from app.infrastructure.database.models.order import Order, OrderItem, OrderStatusEvent  # noqa: F401
from app.infrastructure.database.models.payment import Payout, Transaction  # noqa: F401
from app.infrastructure.database.models.subscription import CustomerSubscription  # noqa: F401
from app.infrastructure.database.models.user import OtpRecord, User  # noqa: F401
